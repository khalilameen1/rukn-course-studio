"""Background entry for generation jobs (off the HTTP request).

V1: FastAPI BackgroundTasks / thread on a single Uvicorn worker.
Multi-worker deploys must keep GENERATION_GLOBAL_LOCK + Postgres advisory
locks (see generation_lock.py) — do not assume shared in-process state.
"""

from __future__ import annotations

import logging

from app.ai.factory import AIProviderConfigError
from app.crud import generation_jobs
from app.db import engine
from app.generation.orchestrator import run_generation_job
from app.models.enums import GenerationQualityMode, JobStatus, WebResearchMode
from sqlmodel import Session

logger = logging.getLogger(__name__)


def run_claimed_generation_job(
    course_id: int,
    *,
    job_id: int,
    generation_quality_mode: GenerationQualityMode,
    web_research_mode: WebResearchMode,
) -> None:
    """Execute a previously claimed job. Safe to call from BackgroundTasks."""
    try:
        run_generation_job(
            course_id,
            generation_quality_mode=generation_quality_mode,
            web_research_mode=web_research_mode,
            existing_job_id=job_id,
        )
    except AIProviderConfigError as exc:
        logger.exception("Generation job %s failed: provider config", job_id)
        _fail_job(job_id, str(exc), category="provider_unavailable")
    except Exception as exc:  # noqa: BLE001 — last-resort fail closed
        logger.exception("Generation job %s failed unexpectedly", job_id)
        _fail_job(job_id, str(exc)[:300], category="unknown")


def _fail_job(job_id: int, message: str, *, category: str) -> None:
    with Session(engine) as session:
        job = generation_jobs.get(session, job_id)
        if job is None:
            return
        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.PARTIAL, JobStatus.CANCELED):
            return
        generation_jobs.update(
            session,
            job_id,
            status=JobStatus.FAILED,
            current_stage="failed",
            error_message=message,
            error_category=category,
            last_progress_message="Generation could not finish",
        )
