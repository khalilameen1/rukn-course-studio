"""Generation job maintenance helpers (not HTTP)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.crud import generation_jobs
from app.generation.generation_state import ACTIVE_LOCK_STATUSES
from app.generation.export_blockers import ExportBlockedError
from app.generation.quality.context_snapshot import SnapshotMismatchError
from app.models.enums import JobStatus
from app.models.generation_job import GenerationJob
from app.services.finalize_saved_job import (
    finalize_job_from_saved_lessons,
    job_eligible_for_saved_finalize,
)


def _as_utc(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def release_stale_active_jobs(
    session: Session,
    *,
    max_age_minutes: float = 90.0,
    finalize_after_minutes: float = 8.0,
) -> int:
    """Recover or release abandoned pending/running/paused jobs.

    1. If every lesson is already saved and the worker heartbeat is stale,
       finalize to COMPLETED + DOCX **without any AI call**.
    2. Otherwise mark truly abandoned runs FAILED so Generate is not stuck.

    Sync Generate cannot remain RUNNING after the HTTP worker dies (crash,
    deploy, proxy timeout). Cancel only works while the worker is alive.

    Heartbeat = max(updated_at, last_saved_at). Threshold is long on purpose
    for in-flight lesson AI calls; finalize-after is shorter because
    post-lesson stages should only need assembly/export once lessons exist.

    Also: jobs stuck in `queued`/`pending` with no progress for a shorter
    window (boot orphans) are released after max(15, max_age/3) minutes.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=max_age_minutes)
    finalize_cutoff = now - timedelta(minutes=finalize_after_minutes)
    orphan_cutoff = now - timedelta(minutes=max(15.0, max_age_minutes / 3.0))
    statement = select(GenerationJob).where(
        GenerationJob.status.in_(tuple(ACTIVE_LOCK_STATUSES)),
    )
    released = 0

    def _finalize_or_fail_mismatch(job: GenerationJob) -> GenerationJob | None:
        nonlocal released
        try:
            return finalize_job_from_saved_lessons(session, job)
        except SnapshotMismatchError:
            generation_jobs.update(
                session,
                job.id,
                status=JobStatus.FAILED,
                current_stage="failed",
                cancel_requested=False,
                error_message=(
                    "Run configuration changed; saved lessons cannot be resumed or exported."
                ),
                error_category="config_fingerprint_mismatch",
                last_progress_message="Run stopped because its configuration changed",
            )
            released += 1
            return None
        except ExportBlockedError:
            generation_jobs.update(
                session,
                job.id,
                status=JobStatus.PARTIAL,
                current_stage="blocked",
                cancel_requested=False,
                error_message="Saved lessons still have unresolved export blockers.",
                error_category="export_blocked",
                last_progress_message="Saved lessons require review before export",
            )
            released += 1
            return None

    for job in list(session.exec(statement)):
        heartbeat = max(_as_utc(job.updated_at), _as_utc(job.last_saved_at))
        stage = (job.current_stage or "").lower()
        is_orphan_queue = stage in {"", "queued", "pending"} and not job.course_map_json

        # Prefer no-AI finalization when all lessons are already on disk/DB.
        if job_eligible_for_saved_finalize(job) and heartbeat < finalize_cutoff:
            finalized = _finalize_or_fail_mismatch(job)
            if finalized is None and job.status == JobStatus.FAILED:
                continue
            if finalized is not None and finalized.status == JobStatus.COMPLETED:
                released += 1
                continue

        limit = orphan_cutoff if is_orphan_queue else cutoff
        if heartbeat >= limit:
            continue

        # Last chance: if lessons are complete, finalize instead of failing.
        if job_eligible_for_saved_finalize(job):
            finalized = _finalize_or_fail_mismatch(job)
            if finalized is None and job.status == JobStatus.FAILED:
                continue
            if finalized is not None and finalized.status == JobStatus.COMPLETED:
                released += 1
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
