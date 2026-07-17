"""Orphan upload cleanup (retention) — no cloud lifecycle infra in V1.

Removes files under STORAGE_UPLOADS that are not referenced by any
CourseSource.file_path and are older than `source_retention_days`.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

from sqlmodel import Session, select

from app.config import settings
from app.models.course_source import CourseSource

logger = logging.getLogger(__name__)


def purge_orphan_upload_files(
    session: Session,
    *,
    uploads_root: Path | None = None,
    retention_days: int | None = None,
) -> dict:
    """Delete unreferenced upload files older than the retention window."""
    root = Path(uploads_root or settings.storage_uploads_dir)
    days = int(
        retention_days
        if retention_days is not None
        else getattr(settings, "source_retention_days", 90)
    )
    if days <= 0 or not root.is_dir():
        return {"removed": 0, "skipped": 0, "retention_days": days}

    referenced: set[str] = set()
    for path in session.exec(select(CourseSource.file_path)).all():
        if path:
            try:
                referenced.add(str(Path(path).resolve()))
            except OSError:
                referenced.add(str(path))

    cutoff = time.time() - days * 86400
    removed = 0
    skipped = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            resolved = str(path.resolve())
        except OSError:
            skipped += 1
            continue
        if resolved in referenced:
            skipped += 1
            continue
        try:
            if path.stat().st_mtime > cutoff:
                skipped += 1
                continue
            path.unlink(missing_ok=True)
            removed += 1
        except OSError:
            skipped += 1
            logger.exception("Failed removing orphan upload %s", path)

    return {"removed": removed, "skipped": skipped, "retention_days": days}
