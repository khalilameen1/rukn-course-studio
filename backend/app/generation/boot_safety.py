"""Boot-time generation safety: schema columns, stale locks, disk."""

from __future__ import annotations

import logging

from sqlmodel import Session, inspect

from app.config import settings
from app.db import engine
from app.generation.map_lock import clear_all_process_map_busy, clear_stale_map_locks
from app.generation.generation_preflight import check_storage_disk
from app.services.generation_maintenance import release_stale_active_jobs

logger = logging.getLogger(__name__)

# Columns the orchestrator may flush mid-run — missing ones cause FAILED.
CRITICAL_JOB_COLUMNS: tuple[str, ...] = (
    "course_map_json",
    "completed_reels_json",
    "provenance_summary",
    "architecture_summary",
    "grounding_confidence",
    "research_synthesis_summary",
    "improve_next_tip",
    "web_searches_count",
    "research_memory_reuse_count",
    "sources_run_summary",
    "cancel_requested",
    "generation_quality_mode",
    "web_research_mode",
)


def verify_generation_job_columns() -> list[str]:
    """Return missing critical columns (empty = ok). Re-runs patches first."""
    from app.db.patches import _ensure_generation_job_columns

    try:
        _ensure_generation_job_columns()
    except Exception as exc:  # noqa: BLE001
        logger.warning("generation_job column patch failed: %s", exc)
    try:
        insp = inspect(engine)
        if "generation_jobs" not in insp.get_table_names():
            return ["generation_jobs table missing"]
        existing = {c["name"] for c in insp.get_columns("generation_jobs")}
    except Exception as exc:  # noqa: BLE001
        return [f"could not inspect generation_jobs: {exc}"]
    return [name for name in CRITICAL_JOB_COLUMNS if name not in existing]


def run_generation_boot_safety() -> dict:
    """Call from app lifespan after init_db()."""
    clear_all_process_map_busy()
    missing = verify_generation_job_columns()
    if missing:
        logger.error("CRITICAL generation_jobs columns missing: %s", missing)

    disk = check_storage_disk(min_free_mb=30)
    if disk:
        logger.warning("Storage preflight: %s", disk)

    released_jobs = 0
    released_maps = 0
    with Session(engine) as session:
        try:
            released_jobs = release_stale_active_jobs(session, max_age_minutes=90.0)
        except Exception as exc:  # noqa: BLE001
            logger.warning("stale job release failed: %s", exc)
        try:
            released_maps = clear_stale_map_locks(session)
        except Exception as exc:  # noqa: BLE001
            logger.warning("stale map lock release failed: %s", exc)

    if released_jobs or released_maps:
        logger.info(
            "Boot safety released stale jobs=%s map_locks=%s",
            released_jobs,
            released_maps,
        )
    return {
        "missing_job_columns": missing,
        "disk_warning": disk,
        "released_jobs": released_jobs,
        "released_map_locks": released_maps,
        "environment": settings.environment,
    }
