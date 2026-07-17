"""Source upload post-processing: extract text, persist analysis + memory."""

from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path

from sqlmodel import Session

from app.config import settings
from app.crud import course_sources, source_analyses
from app.models.enums import Priority, SourceCategory, SourceOrigin
from app.services.extraction import extract_text
from app.services.source_analysis import analyze_source_text
from app.services.source_status import FAILED, POOR_EXTRACTION, PROCESSING_FAILED, READY

logger = logging.getLogger(__name__)

USABLE_EXTRACTION_STATUSES = {READY, POOR_EXTRACTION}


def extracted_copy_path(course_id: int, stem: str) -> Path:
    return settings.storage_extracted_dir / str(course_id) / f"{stem}.txt"


def create_source_analysis(
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
    for existing in source_analyses.list(session, source_id=source_id):
        source_analyses.delete(session, existing.id)

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
        extracted_at=None,
        tokens_used=int(memory.get("tokens_used") or 0),
    )


def cleanup_stored_paths(*paths: Path | None) -> None:
    for path in paths:
        if path is None:
            continue
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to cleanup stored file %s", path, exc_info=True)


def process_stored_source(
    session: Session,
    *,
    source,
    dest_path: Path,
    suffix: str,
    password: str | None,
    source_category: SourceCategory,
    priority: Priority,
    include_in_generation: bool,
    display_title: str,
    safe_name: str,
    mime_type: str | None,
    source_origin: SourceOrigin | None,
) -> object:
    """Extract text + optional analysis after the file/DB row already exist.

    Extraction/analysis failures update status but never raise — upload already
    succeeded. Callers may still reprocess later from the stored file.
    """
    result = extract_text(dest_path, suffix, password=password)
    extracted_text = None
    source_hash = None
    extracted_path = None
    final_status = result.status or FAILED

    if result.status in USABLE_EXTRACTION_STATUSES and result.text:
        extracted_text = result.text
        from app.generation.source_memory_store import compute_source_hash

        source_hash = compute_source_hash(extracted_text)
        extracted_path = extracted_copy_path(source.course_id, Path(dest_path).stem)
        try:
            extracted_path.parent.mkdir(parents=True, exist_ok=True)
            extracted_path.write_text(result.text, encoding="utf-8")
        except OSError:
            logger.exception(
                "Failed writing extracted text copy for source %s", source.id
            )
            extracted_path = None

    source = course_sources.update(
        session,
        source.id,
        extracted_text=extracted_text,
        source_hash=source_hash,
        status=final_status,
    )

    # Weak extracts stay available but must be opted into generation.
    effective_include = include_in_generation
    if final_status == POOR_EXTRACTION:
        effective_include = False

    # Same content already on this course → exclude duplicate by default.
    if source_hash:
        for sibling in course_sources.list(session, course_id=source.course_id):
            if sibling.id == source.id:
                continue
            if sibling.source_hash == source_hash and sibling.include_in_generation:
                effective_include = False
                break

    if effective_include != bool(getattr(source, "include_in_generation", True)):
        source = course_sources.update(
            session, source.id, include_in_generation=effective_include
        ) or source

    if extracted_text:
        try:
            create_source_analysis(
                session,
                source.id,
                extracted_text,
                source_category,
                title=display_title or f"source-{source.id}",
                priority=priority.value,
                include_in_generation=bool(
                    getattr(source, "include_in_generation", effective_include)
                ),
                original_filename=safe_name,
                mime_type=mime_type,
                source_origin=source_origin.value if source_origin else None,
            )
        except Exception:
            logger.exception(
                "Source analysis failed after upload for source %s", source.id
            )
            source = course_sources.update(
                session,
                source.id,
                status=PROCESSING_FAILED,
            ) or source

    return source


# Private aliases for older tests/patches that targeted router helpers.
_create_source_analysis = create_source_analysis
_process_stored_source = process_stored_source
_cleanup_stored_paths = cleanup_stored_paths
_extracted_copy_path = extracted_copy_path
