from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session

from app.config import settings
from app.crud import course_sources, source_analyses
from app.db import get_session
from app.models.enums import Priority, SourceCategory
from app.routers.deps import get_course_or_404
from app.schemas.course_source import CourseSourceNotesCreate, CourseSourceRead
from app.services.extraction import extract_text
from app.services.source_analysis import analyze_source_text
from app.services.source_status import POOR_EXTRACTION, READY

router = APIRouter(prefix="/courses/{course_id}/sources", tags=["sources"])

ALLOWED_SOURCE_EXTENSIONS = {".docx", ".pdf", ".txt", ".md"}

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
) -> None:
    """Simple, no-embeddings analysis (see app/services/source_analysis.py):
    chunks + a short summary + key points + any obvious avoid points."""
    analysis = analyze_source_text(extracted_text, source_category.value)
    source_analyses.create(
        session,
        source_id=source_id,
        chunks_json=[asdict(chunk) for chunk in analysis.chunks],
        source_summary=analysis.source_summary,
        key_points_json=analysis.key_points,
        avoid_points_json=analysis.avoid_points,
    )


@router.post("/upload", response_model=CourseSourceRead, status_code=201)
async def upload_source(
    course_id: int,
    file: UploadFile = File(...),
    source_category: SourceCategory = Form(SourceCategory.MAIN_CONTENT),
    priority: Priority = Form(Priority.MEDIUM),
    password: str | None = Form(None),
    session: Session = Depends(get_session),
):
    """Save the uploaded file, then extract its text (see app/services/extraction.py).

    `password` is only used for encrypted PDFs and only ever tried as-is -
    never used to attempt to break/bypass protection.
    """
    get_course_or_404(session, course_id)

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SOURCE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{suffix or 'unknown'}'. "
                f"Allowed: {sorted(ALLOWED_SOURCE_EXTENSIONS)}"
            ),
        )

    course_dir = settings.storage_uploads_dir / str(course_id)
    course_dir.mkdir(parents=True, exist_ok=True)
    stem = uuid4().hex
    dest_path = course_dir / f"{stem}{suffix}"
    dest_path.write_bytes(await file.read())

    result = extract_text(dest_path, suffix, password=password)

    extracted_text = None
    if result.status in USABLE_EXTRACTION_STATUSES and result.text:
        extracted_text = result.text
        extracted_path = _extracted_copy_path(course_id, stem)
        extracted_path.parent.mkdir(parents=True, exist_ok=True)
        extracted_path.write_text(result.text, encoding="utf-8")

    source = course_sources.create(
        session,
        course_id=course_id,
        source_category=source_category,
        original_filename=file.filename,
        file_path=str(dest_path),
        mime_type=file.content_type,
        extracted_text=extracted_text,
        priority=priority,
        status=result.status,
    )

    if extracted_text:
        _create_source_analysis(session, source.id, extracted_text, source_category)

    return source


@router.post("/notes", response_model=CourseSourceRead, status_code=201)
def add_source_notes(
    course_id: int,
    payload: CourseSourceNotesCreate,
    session: Session = Depends(get_session),
):
    get_course_or_404(session, course_id)

    source = course_sources.create(
        session,
        course_id=course_id,
        source_category=payload.source_category,
        extracted_text=payload.text,
        priority=payload.priority,
        status="ready",
    )

    _create_source_analysis(session, source.id, payload.text, payload.source_category)

    return source


@router.get("", response_model=list[CourseSourceRead])
def list_sources(course_id: int, session: Session = Depends(get_session)):
    get_course_or_404(session, course_id)
    return course_sources.list(session, course_id=course_id)


@router.delete("/{source_id}", status_code=204)
def delete_source(
    course_id: int, source_id: int, session: Session = Depends(get_session)
):
    source = course_sources.get(session, source_id)
    if source is None or source.course_id != course_id:
        raise HTTPException(status_code=404, detail="Source not found")

    if source.file_path:
        original = Path(source.file_path)
        original.unlink(missing_ok=True)
        _extracted_copy_path(course_id, original.stem).unlink(missing_ok=True)

    for analysis in source_analyses.list(session, source_id=source_id):
        source_analyses.delete(session, analysis.id)

    course_sources.delete(session, source_id)
