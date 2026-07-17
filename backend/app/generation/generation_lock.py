"""Serialize generation starts to prevent duplicate RUNNING jobs (TOCTOU).

AI-typical bug: check-then-create across two HTTP requests both see "no
active job" and both start Anthropic runs. Process-local locks close that
on a single Uvicorn worker; Postgres advisory locks cover multi-worker.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import text
from sqlmodel import Session, select

from app.config import settings
from app.crud import generation_jobs
from app.generation.generation_state import ACTIVE_LOCK_STATUSES
from app.models.enums import GenerationQualityMode, JobStatus, WebResearchMode
from app.models.generation_job import GenerationJob

_GLOBAL_START_LOCK = threading.Lock()
_COURSE_LOCKS: dict[int, threading.Lock] = {}
_COURSE_LOCKS_GUARD = threading.Lock()

# Fixed key space for pg_advisory_xact_lock (int4).
_PG_GLOBAL_GEN_LOCK_KEY = 0x524B4E47  # "RKNG"


def _course_lock(course_id: int) -> threading.Lock:
    with _COURSE_LOCKS_GUARD:
        lock = _COURSE_LOCKS.get(course_id)
        if lock is None:
            lock = threading.Lock()
            _COURSE_LOCKS[course_id] = lock
        return lock


@contextmanager
def generation_start_guard(course_id: int) -> Iterator[None]:
    """Hold process locks while claiming a generation slot."""
    course_lock = _course_lock(course_id)
    use_global = bool(getattr(settings, "generation_global_lock", True))
    if use_global:
        with _GLOBAL_START_LOCK:
            with course_lock:
                yield
    else:
        with course_lock:
            yield


def claim_generation_job(
    session: Session,
    course_id: int,
    *,
    generation_quality_mode: GenerationQualityMode,
    web_research_mode: WebResearchMode,
) -> tuple[GenerationJob, bool]:
    """Get-or-create an active job for `course_id` under the start guard.

    Returns `(job, created)`. When `created` is False, callers must return
    the existing job without starting another pipeline.
    Raises `RuntimeError` with message starting `GLOBAL_LOCK:` when another
    course holds the global generation lock.
    """
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        keys = [course_id & 0x7FFFFFFF]
        if getattr(settings, "generation_global_lock", True):
            keys.insert(0, _PG_GLOBAL_GEN_LOCK_KEY)
        for key in keys:
            session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": key})

    active = session.exec(
        select(GenerationJob).where(
            GenerationJob.course_id == course_id,
            GenerationJob.status.in_(tuple(ACTIVE_LOCK_STATUSES)),
        )
    ).first()
    if active is not None:
        return active, False

    if getattr(settings, "generation_global_lock", True):
        other = session.exec(
            select(GenerationJob).where(
                GenerationJob.status.in_(tuple(ACTIVE_LOCK_STATUSES)),
            )
        ).first()
        if other is not None and other.course_id != course_id:
            raise RuntimeError(
                f"GLOBAL_LOCK: Another course (id={other.course_id}) already has "
                "an active generation run. Wait for it to finish, then try again."
            )

    job = generation_jobs.create(
        session,
        course_id=course_id,
        status=JobStatus.PENDING,
        current_stage="queued",
        progress_percent=0,
        log_json=[],
        generation_quality_mode=generation_quality_mode,
        web_research_mode=web_research_mode,
    )
    return job, True
