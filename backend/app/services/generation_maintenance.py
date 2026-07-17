"""Generation job maintenance helpers (not HTTP)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.crud import generation_jobs
from app.generation.generation_state import ACTIVE_LOCK_STATUSES
from app.models.enums import JobStatus
from app.models.generation_job import GenerationJob


def _as_utc(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def release_stale_active_jobs(session: Session, *, max_age_minutes: float = 90.0) -> int:
    """Mark abandoned pending/running/paused jobs failed so Generate is not stuck.

    Sync Generate cannot remain RUNNING after the HTTP worker dies (crash,
    deploy, proxy timeout). Cancel only works while the worker is alive.

    Heartbeat = max(updated_at, last_saved_at). Threshold is long on purpose:
    a single premium LLM call can exceed 15 minutes.

    Also: jobs stuck in `queued`/`pending` with no progress for a shorter
    window (boot orphans) are released after max(15, max_age/3) minutes.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=max_age_minutes)
    orphan_cutoff = now - timedelta(minutes=max(15.0, max_age_minutes / 3.0))
    statement = select(GenerationJob).where(
        GenerationJob.status.in_(tuple(ACTIVE_LOCK_STATUSES)),
    )
    released = 0
    for job in list(session.exec(statement)):
        heartbeat = max(_as_utc(job.updated_at), _as_utc(job.last_saved_at))
        stage = (job.current_stage or "").lower()
        is_orphan_queue = stage in {"", "queued", "pending"} and not job.course_map_json
        limit = orphan_cutoff if is_orphan_queue else cutoff
        if heartbeat >= limit:
            continue
        generation_jobs.update(
            session,
            job.id,
            status=JobStatus.FAILED,
            current_stage="failed",
            cancel_requested=False,
            error_message=(
                "Previous generation run was abandoned (server restart, timeout, "
                "or crash). Start Generate again."
            ),
            error_category="abandoned_run",
            last_progress_message="Previous run abandoned — ready to retry",
        )
        released += 1
    return released


# Back-compat for tests that imported the private router helper name.
_release_stale_active_jobs = release_stale_active_jobs
