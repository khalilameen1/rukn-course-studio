"""Job runner: never leave a claimed job RUNNING after an unexpected exit."""

from __future__ import annotations

import logging

from app.ai.factory import AIProviderConfigError
from app.crud import generation_jobs
from app.db import engine
from app.generation.errors import classify_provider_error, error_message_for
from app.generation.orchestrator import run_generation_job
from app.models.enums import GenerationQualityMode, JobStatus, WebResearchMode
from app.security.secret_redaction import redact_secrets
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
        _fail_job(
            job_id,
            error_message_for("provider_unavailable", has_saved_work=False),
            category="provider_unavailable",
            detail=str(exc),
        )
    except Exception as exc:  # noqa: BLE001 — last-resort fail closed
        logger.exception("Generation job %s failed unexpectedly", job_id)
        category = classify_provider_error(exc)
        _fail_job(
            job_id,
            error_message_for(category, has_saved_work=False),
            category=category,
            detail=redact_secrets(str(exc)[:300]),
        )


def _fail_job(
    job_id: int,
    message: str,
    *,
    category: str,
    detail: str | None = None,
) -> None:
    with Session(engine) as session:
        job = generation_jobs.get(session, job_id)
        if job is None:
            return
        if job.status in (
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.PARTIAL,
            JobStatus.CANCELED,
        ):
            return
        # If map/reels already exist, prefer PARTIAL so user can download.
        has_saved = bool(job.course_map_json) or bool(job.completed_reels_json)
        status = JobStatus.PARTIAL if has_saved else JobStatus.FAILED
        user_message = message
        if has_saved:
            user_message = error_message_for(category, has_saved_work=True)
        generation_jobs.update(
            session,
            job_id,
            status=status,
            current_stage="partial" if has_saved else "failed",
            error_message=user_message,
            error_category=category,
            last_progress_message=(
                "Generation stopped with saved work"
                if has_saved
                else "Generation could not finish"
            ),
            log_json=list(job.log_json or [])
            + (
                [
                    {
                        "step": "job_runner_fail",
                        "category": category,
                        "detail": detail or "",
                    }
                ]
                if detail
                else []
            ),
        )
