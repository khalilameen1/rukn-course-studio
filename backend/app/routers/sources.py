from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlmodel import Session

from app.config import settings
from app.crud import course_sources, source_analyses
from app.db import get_session
from app.models.enums import Priority, SourceCategory, SourceOrigin
from app.routers.deps import get_course_or_404
from app.schemas.course_source import (
    CourseSourceNotesCreate,
    CourseSourcePatch,
    CourseSourceRead,
)
from app.services.extraction import extract_text
from app.services.source_analysis import CATEGORY_AVOID_POINTS, analyze_source_text
from app.services.source_status import POOR_EXTRACTION, READY
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

# Extraction quality levels whose text is trusted enough to store as
# `extracted_text`. password_required / extraction_blocked / scanned_no_text
# / failed always keep `extracted_text` empty (see app/services/extraction.py).
USABLE_EXTRACTION_STATUSES = {READY, POOR_EXTRACTION}


def _extracted_copy_path(course_id: int, stem: str) -> Path:
    return settings.storage_extracted_dir / str(course_id) / f"{stem}.txt"


def _create_source_analysis(
    session: Session,
    source_id: int,
    extracted_text: str,
    source_category: SourceCategory,
    title: str = "",
    priority: str = "medium",
    include_in_generation: bool = True,
    *,
    original_filename: str | None = None,
    mime_type: str | None = None,
    source_origin: str | None = None,
) -> None:
    """Simple, no-embeddings analysis + persistent Source Memory (once)."""
    from app.generation.source_memory_store import build_source_memory_payload

    analysis = analyze_source_text(extracted_text, source_category.value)
    chunks = [asdict(chunk) for chunk in analysis.chunks]
    memory = build_source_memory_payload(
        title=title or f"source-{source_id}",
        category=source_category.value,
        extracted_text=extracted_text,
        summary=analysis.source_summary,
        chunks=chunks,
        key_points=analysis.key_points,
        avoid_points=analysis.avoid_points,
        priority=priority,
        include_in_generation=include_in_generation,
        original_filename=original_filename,
        mime_type=mime_type,
        source_origin=source_origin,
    )
    source_analyses.create(
        session,
        source_id=source_id,
        chunks_json=chunks,
        source_summary=analysis.source_summary,
        key_points_json=analysis.key_points,
        avoid_points_json=analysis.avoid_points,
        source_memory_json=memory,
        source_hash=memory.get("source_hash"),
        extraction_version=memory.get("extraction_version"),
        extracted_at=None,  # set via memory ISO; column optional
        tokens_used=int(memory.get("tokens_used") or 0),
    )


@router.post("/upload", response_model=CourseSourceRead, status_code=201)
async def upload_source(
    course_id: int,
    file: UploadFile = File(...),
    source_category: SourceCategory = Form(SourceCategory.SCIENTIFIC_REFERENCE),
    priority: Priority = Form(Priority.MEDIUM),
    source_title: str | None = Form(None),
    include_in_generation: bool = Form(True),
    password: str | None = Form(None),
    source_origin: SourceOrigin | None = Form(None),
    session: Session = Depends(get_session),
):
    """Save the uploaded file, then extract its text (see app/services/extraction.py).

    Course-specific only — never written to Admin Knowledge.
    `password` is only used for encrypted PDFs and only ever tried as-is.
    """
    get_course_or_404(session, course_id)

    suffix = assert_allowed_extension(file.filename)
    assert_declared_mime_ok(file.content_type)
    safe_name = sanitize_filename(file.filename)
    data = await read_upload_capped(
        file, max_bytes=int(getattr(settings, "max_upload_bytes", 25 * 1024 * 1024))
    )
    assert_content_matches_extension(data, suffix)

    course_dir = settings.storage_uploads_dir / str(course_id)
    course_dir.mkdir(parents=True, exist_ok=True)
    stem = uuid4().hex
    dest_path = course_dir / f"{stem}{suffix}"
    dest_path.write_bytes(data)

    result = extract_text(dest_path, suffix, password=password)

    extracted_text = None
    source_hash = None
    if result.status in USABLE_EXTRACTION_STATUSES and result.text:
        extracted_text = result.text
        from app.generation.source_memory_store import compute_source_hash

        source_hash = compute_source_hash(extracted_text)
        extracted_path = _extracted_copy_path(course_id, stem)
        extracted_path.parent.mkdir(parents=True, exist_ok=True)
        extracted_path.write_text(result.text, encoding="utf-8")

    display_title = (source_title or "").strip() or safe_name

    source = course_sources.create(
        session,
        course_id=course_id,
        source_category=source_category,
        title=display_title,
        original_filename=safe_name,
        file_path=str(dest_path),
        mime_type=file.content_type,
        extracted_text=extracted_text,
        priority=priority,
        status=result.status,
        include_in_generation=include_in_generation,
        source_hash=source_hash,
    )

    if extracted_text:
        _create_source_analysis(
            session,
            source.id,
            extracted_text,
            source_category,
            title=display_title or f"source-{source.id}",
            priority=priority.value,
            include_in_generation=include_in_generation,
            original_filename=safe_name,
            mime_type=file.content_type,
            source_origin=source_origin.value if source_origin else None,
        )

    return source


@router.post("/notes", response_model=CourseSourceRead, status_code=201)
def add_source_notes(
    course_id: int,
    payload: CourseSourceNotesCreate,
    session: Session = Depends(get_session),
):
    """Paste transcript/notes for this course — never Admin Knowledge."""
    get_course_or_404(session, course_id)
    assert_notes_length(
        payload.text, max_chars=int(getattr(settings, "max_notes_chars", 200_000))
    )
    from app.generation.source_memory_store import compute_source_hash

    display_title = (payload.title or "").strip() or (
        "Transcript" if payload.source_category == SourceCategory.TRANSCRIPT else "Notes"
    )
    source = course_sources.create(
        session,
        course_id=course_id,
        source_category=payload.source_category,
        title=display_title,
        extracted_text=payload.text,
        priority=payload.priority,
        status="ready",
        include_in_generation=payload.include_in_generation,
        source_hash=compute_source_hash(payload.text),
    )

    _create_source_analysis(
        session,
        source.id,
        payload.text,
        payload.source_category,
        title=display_title,
        priority=payload.priority.value,
        include_in_generation=payload.include_in_generation,
        source_origin=payload.source_origin.value if payload.source_origin else None,
    )

    return source


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
):
    from app.services.audit import record_audit

    source = course_sources.get(session, source_id)
    if source is None or source.course_id != course_id:
        raise HTTPException(status_code=404, detail="Source not found")

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
            details={"course_id": course_id, "source_id": source_id},
        )
        return {
            "applied": False,
            "dry_run": True,
            "course_id": course_id,
            "source_id": source_id,
            "message": (
                f"Dry-run: would delete source {source_id} for course {course_id}. "
                "Pass confirm=true&dry_run=false to apply."
            ),
        }

    if source.file_path:
        original = Path(source.file_path)
        safe = assert_path_under_root(original, Path(settings.storage_uploads_dir))
        safe.unlink(missing_ok=True)
        _extracted_copy_path(course_id, safe.stem).unlink(missing_ok=True)

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
