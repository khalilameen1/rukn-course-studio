"""HTTP adapters for course source upload / notes / reprocess / delete."""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlmodel import Session

from app.config import settings
from app.crud import course_sources, source_analyses
from app.db import get_session
from app.models.enums import Priority, SourceCategory
from app.routers.deps import get_course_or_404
from app.schemas.course_source import (
    CourseSourceNotesCreate,
    CourseSourcePatch,
    CourseSourceRead,
    SourceAnalysisPreview,
)
from app.schemas.validators import (
    PriorityLoose,
    SourceCategoryLoose,
    SourceOriginLoose,
)
from app.services.source_ingestion import (
    cleanup_stored_paths as _cleanup_stored_paths,
    create_source_analysis as _create_source_analysis,
    process_stored_source as _process_stored_source,
)
from app.services.source_status import PROCESSING_FAILED, UPLOADED
from app.services.upload_safety import (
    assert_allowed_extension,
    assert_content_matches_extension,
    assert_declared_mime_ok,
    assert_notes_length,
    assert_path_under_root,
    read_upload_capped,
    sanitize_filename,
)

router = APIRouter(prefix="/courses/{course_id}/sources", tags=["sources"])
logger = logging.getLogger(__name__)


@router.post("/upload", response_model=CourseSourceRead, status_code=201)
async def upload_source(
    course_id: int,
    request: Request,
    file: UploadFile = File(...),
    source_category: SourceCategoryLoose = Form(SourceCategory.SCIENTIFIC_REFERENCE),
    priority: PriorityLoose = Form(Priority.MEDIUM),
    source_title: str | None = Form(None),
    include_in_generation: bool = Form(True),
    password: str | None = Form(None),
    force: bool = Form(False),
    source_origin: SourceOriginLoose = Form(None),
    session: Session = Depends(get_session),
):
    """Save the uploaded file, then extract its text.

    Course-specific only — never written to the canonical standard.
    Upload success (file + DB row) is separate from extraction/analysis success.
    """
    get_course_or_404(session, course_id)

    if file is None or not (file.filename or "").strip():
        raise HTTPException(status_code=400, detail="No file was provided.")

    suffix = assert_allowed_extension(file.filename)
    assert_declared_mime_ok(file.content_type)
    safe_name = sanitize_filename(file.filename)
    data = await read_upload_capped(
        file, max_bytes=int(getattr(settings, "max_upload_bytes", 25 * 1024 * 1024))
    )
    assert_content_matches_extension(data, suffix)

    # Soft duplicate guard: same filename or identical text content (.txt/.md).
    existing = course_sources.list(session, course_id=course_id)
    if not force:
        name_key = safe_name.casefold()
        text_hash = None
        if suffix in {".txt", ".md"}:
            from app.generation.source_memory_store import compute_source_hash

            text_hash = compute_source_hash(
                data.decode("utf-8", errors="replace")
            )
        for sibling in existing:
            sibling_name = (sibling.original_filename or "").casefold()
            if sibling_name and sibling_name == name_key:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "duplicate_filename",
                        "message": (
                            f"A source named '{safe_name}' already exists on this course. "
                            "Upload with force=true to add another copy, or delete the old one."
                        ),
                        "existing_source_id": sibling.id,
                    },
                )
            if (
                text_hash
                and sibling.source_hash
                and sibling.source_hash == text_hash
            ):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "duplicate_content",
                        "message": (
                            "A source with the same text content already exists on this course. "
                            "Upload with force=true to add another copy."
                        ),
                        "existing_source_id": sibling.id,
                    },
                )

    uploads_root = Path(settings.storage_uploads_dir)
    try:
        uploads_root.mkdir(parents=True, exist_ok=True)
        course_dir = uploads_root / str(course_id)
        course_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.exception("Cannot create upload storage directory")
        raise HTTPException(
            status_code=500,
            detail="Storage is not writable. Check STORAGE_DIR permissions and free disk space.",
        ) from exc

    stem = uuid4().hex
    dest_path = course_dir / f"{stem}{suffix}"
    try:
        dest_path.write_bytes(data)
    except OSError as exc:
        logger.exception("Failed writing upload to %s", dest_path)
        raise HTTPException(
            status_code=500,
            detail="Could not store the uploaded file. Check free disk space and STORAGE_DIR.",
        ) from exc

    if not dest_path.is_file() or dest_path.stat().st_size == 0:
        _cleanup_stored_paths(dest_path)
        raise HTTPException(status_code=500, detail="Stored upload file is missing or empty.")

    display_title = (source_title or "").strip() or safe_name

    try:
        source = course_sources.create(
            session,
            course_id=course_id,
            source_category=source_category,
            title=display_title,
            original_filename=safe_name,
            file_path=str(dest_path),
            mime_type=file.content_type,
            extracted_text=None,
            priority=priority,
            status=UPLOADED,
            include_in_generation=include_in_generation,
            source_hash=None,
        )
    except Exception as exc:
        _cleanup_stored_paths(dest_path)
        logger.exception("Database insert failed after storing upload")
        raise HTTPException(
            status_code=500,
            detail="Could not save the source record after storing the file.",
        ) from exc

    result = _process_stored_source(
        session,
        source=source,
        dest_path=dest_path,
        suffix=suffix,
        password=password,
        source_category=source_category,
        priority=priority,
        include_in_generation=include_in_generation,
        display_title=display_title,
        safe_name=safe_name,
        mime_type=file.content_type,
        source_origin=source_origin,
    )
    from app.services.audit import record_audit

    record_audit(
        session,
        action="source_upload_force" if force else "source_upload",
        actor=getattr(request.state, "username", None),
        affected_table="course_sources",
        affected_count=1,
        dry_run=False,
        confirmed=True,
        success=True,
        details={
            "course_id": course_id,
            "source_id": getattr(result, "id", None),
            "filename": safe_name,
            "force": bool(force),
            "password_supplied": bool(password),
        },
    )
    return result


@router.post("/notes", response_model=CourseSourceRead, status_code=201)
def add_source_notes(
    course_id: int,
    payload: CourseSourceNotesCreate,
    request: Request,
    session: Session = Depends(get_session),
):
    """Paste transcript/notes for this course — never the canonical standard."""
    get_course_or_404(session, course_id)
    assert_notes_length(
        payload.text, max_chars=int(getattr(settings, "max_notes_chars", 200_000))
    )
    from app.generation.source_memory_store import compute_source_hash

    display_title = (payload.title or "").strip() or (
        "Transcript" if payload.source_category == SourceCategory.TRANSCRIPT else "Notes"
    )
    text_hash = compute_source_hash(payload.text)
    include = payload.include_in_generation
    for sibling in course_sources.list(session, course_id=course_id):
        if sibling.source_hash == text_hash and sibling.include_in_generation:
            include = False
            break

    source = course_sources.create(
        session,
        course_id=course_id,
        source_category=payload.source_category,
        title=display_title,
        extracted_text=payload.text,
        priority=payload.priority,
        status="ready",
        include_in_generation=include,
        source_hash=text_hash,
    )

    try:
        _create_source_analysis(
            session,
            source.id,
            payload.text,
            payload.source_category,
            title=display_title,
            priority=payload.priority.value,
            include_in_generation=include,
            source_origin=payload.source_origin.value if payload.source_origin else None,
        )
    except Exception:
        logger.exception("Source analysis failed for notes source %s", source.id)
        source = course_sources.update(session, source.id, status=PROCESSING_FAILED) or source

    from app.services.audit import record_audit

    record_audit(
        session,
        action="source_notes",
        actor=getattr(request.state, "username", None),
        affected_table="course_sources",
        affected_count=1,
        dry_run=False,
        confirmed=True,
        success=True,
        details={"course_id": course_id, "source_id": source.id},
    )
    return source


@router.post("/{source_id}/reprocess", response_model=CourseSourceRead)
def reprocess_source(
    course_id: int,
    source_id: int,
    request: Request,
    password: str | None = Form(None),
    session: Session = Depends(get_session),
):
    """Re-run extraction/analysis on an already-stored file (no re-upload)."""
    from app.security.request_throttle import allow_reprocess_attempt
    from app.services.audit import record_audit

    get_course_or_404(session, course_id)
    if not allow_reprocess_attempt(source_id):
        raise HTTPException(
            status_code=429,
            detail="Too many reprocess attempts for this source. Wait a moment.",
        )
    source = course_sources.get(session, source_id)
    if source is None or source.course_id != course_id:
        raise HTTPException(status_code=404, detail="Source not found")
    if not source.file_path:
        raise HTTPException(
            status_code=400,
            detail="This source has no stored file to reprocess (notes-only).",
        )

    dest_path = assert_path_under_root(Path(source.file_path), Path(settings.storage_uploads_dir))
    if not dest_path.is_file():
        raise HTTPException(
            status_code=400,
            detail="Stored file is missing. Please upload the source again.",
        )

    suffix = dest_path.suffix.lower()
    if suffix not in {".docx", ".pdf", ".txt", ".md"}:
        raise HTTPException(status_code=415, detail=f"Unsupported stored file type '{suffix}'.")

    display_title = (source.title or source.original_filename or f"source-{source.id}")
    safe_name = source.original_filename or display_title
    source = course_sources.update(session, source.id, status=UPLOADED) or source

    result = _process_stored_source(
        session,
        source=source,
        dest_path=dest_path,
        suffix=suffix,
        password=password,
        source_category=source.source_category,
        priority=source.priority,
        include_in_generation=bool(source.include_in_generation),
        display_title=display_title,
        safe_name=safe_name,
        mime_type=source.mime_type,
        source_origin=None,
    )
    record_audit(
        session,
        action="source_reprocess",
        actor=getattr(request.state, "username", None),
        affected_table="course_sources",
        affected_count=1,
        dry_run=False,
        confirmed=True,
        success=True,
        details={
            "course_id": course_id,
            "source_id": source_id,
            "password_supplied": bool(password),
            "status": getattr(result, "status", None),
        },
    )
    return result


@router.get("/{source_id}/analysis", response_model=SourceAnalysisPreview)
def get_source_analysis_preview(
    course_id: int,
    source_id: int,
    session: Session = Depends(get_session),
):
    """Understanding preview only — summary + key points (never full extract)."""
    get_course_or_404(session, course_id)
    source = course_sources.get(session, source_id)
    if source is None or source.course_id != course_id:
        raise HTTPException(status_code=404, detail="Source not found")
    analyses = source_analyses.list(session, source_id=source_id)
    if not analyses:
        raise HTTPException(
            status_code=404,
            detail="No understanding preview yet for this source.",
        )
    analysis = analyses[0]
    points = analysis.key_points_json or []
    if not isinstance(points, list):
        points = []
    return SourceAnalysisPreview(
        source_id=source_id,
        source_summary=(analysis.source_summary or "").strip() or None,
        key_points=[str(p) for p in points[:8] if str(p).strip()],
    )


@router.get("", response_model=list[CourseSourceRead])
def list_sources(course_id: int, session: Session = Depends(get_session)):
    get_course_or_404(session, course_id)
    return course_sources.list(session, course_id=course_id)


@router.delete("/{source_id}", status_code=200, response_model=dict)
def delete_source(
    course_id: int,
    source_id: int,
    request: Request,
    session: Session = Depends(get_session),
    confirm: bool = Query(
        False,
        description="Required true with dry_run=false to delete the source.",
    ),
    dry_run: bool = Query(
        True,
        description="Default true: report without deleting.",
    ),
    confirm_name: str | None = Query(
        None,
        description="Must match original_filename or title when applying delete.",
    ),
):
    from app.services.audit import record_audit
    from app.services.source_ingestion import extracted_copy_path

    source = course_sources.get(session, source_id)
    if source is None or source.course_id != course_id:
        raise HTTPException(status_code=404, detail="Source not found")

    expected_name = (
        (source.original_filename or source.title or f"source-{source.id}").strip()
    )
    actor = getattr(request.state, "username", None)
    if dry_run or not confirm:
        record_audit(
            session,
            action="course_source_delete",
            actor=actor,
            affected_table="course_sources",
            affected_count=1,
            dry_run=True,
            confirmed=False,
            success=True,
            details={
                "course_id": course_id,
                "source_id": source_id,
                "expected_confirm_name": expected_name,
            },
        )
        return {
            "applied": False,
            "dry_run": True,
            "course_id": course_id,
            "source_id": source_id,
            "expected_confirm_name": expected_name,
            "message": (
                f"Dry-run: would delete source {source_id} for course {course_id}. "
                "Pass confirm=true&dry_run=false&confirm_name=<filename> to apply."
            ),
        }

    if not confirm_name or confirm_name.strip() != expected_name:
        raise HTTPException(
            status_code=400,
            detail=(
                f"confirm_name must exactly match {expected_name!r} to delete this source."
            ),
        )

    if source.file_path:
        original = Path(source.file_path)
        safe = assert_path_under_root(original, Path(settings.storage_uploads_dir))
        safe.unlink(missing_ok=True)
        extracted_copy_path(course_id, safe.stem).unlink(missing_ok=True)

    for analysis in source_analyses.list(session, source_id=source_id):
        source_analyses.delete(session, analysis.id)

    course_sources.delete(session, source_id)
    record_audit(
        session,
        action="course_source_delete",
        actor=actor,
        affected_table="course_sources",
        affected_count=1,
        dry_run=False,
        confirmed=True,
        success=True,
        details={"course_id": course_id, "source_id": source_id},
    )
    return {
        "applied": True,
        "dry_run": False,
        "course_id": course_id,
        "source_id": source_id,
        "message": f"Deleted source {source_id}.",
    }


@router.patch("/{source_id}", response_model=CourseSourceRead)
def update_source_category(
    course_id: int,
    source_id: int,
    payload: CourseSourcePatch,
    session: Session = Depends(get_session),
):
    """Patch category / include_in_generation / priority.

    Category change only re-derives avoid_points; hash-stable memory is kept.
    """
    from app.services.source_analysis import CATEGORY_AVOID_POINTS

    source = course_sources.get(session, source_id)
    if source is None or source.course_id != course_id:
        raise HTTPException(status_code=404, detail="Source not found")

    updates: dict = {}
    if payload.source_category is not None:
        updates["source_category"] = payload.source_category
    if payload.include_in_generation is not None:
        updates["include_in_generation"] = payload.include_in_generation
    if payload.priority is not None:
        updates["priority"] = payload.priority
    if payload.title is not None:
        updates["title"] = payload.title
    if updates:
        source = course_sources.update(session, source_id, **updates)

    if payload.source_category is not None:
        avoid_points = list(CATEGORY_AVOID_POINTS.get(payload.source_category.value, []))
        analyses = source_analyses.list(session, source_id=source_id)
        if analyses:
            source_analyses.update(session, analyses[0].id, avoid_points_json=avoid_points)

    return source
