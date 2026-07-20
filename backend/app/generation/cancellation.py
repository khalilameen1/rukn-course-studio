"""Cooperative generation cancel — lock-safe stop between pipeline stages."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlmodel import Session

from app.crud import generation_jobs
from app.generation.budget_guard import compute_budget_warning
from app.generation.output_scoring import OutputScoreReport, score_final_course
from app.models.enums import JobStatus
from app.models.generation_job import GenerationJob
from app.security.secret_redaction import redact_secrets
from app.services.docx_export import (
    build_partial_course_from_job,
    export_partial_course_to_docx,
    extract_plain_text,
    render_partial_course_docx,
)

CANCEL_REQUESTED_MESSAGE = (
    "Cancel requested. The current step may finish before the run stops."
)
CANCELED_MESSAGE = "Generation canceled"


class GenerationCanceled(Exception):
    """Raised when a cooperative cancel has finalized the job."""

    def __init__(self, job: GenerationJob) -> None:
        self.job = job
        super().__init__("generation canceled")


def is_cancel_requested(session: Session, job_id: int) -> bool:
    """Reload cancel flag from the DB (safe across sessions / stale ORM cache)."""
    from sqlalchemy import text

    flag = session.execute(
        text("SELECT cancel_requested FROM generation_jobs WHERE id = :job_id"),
        {"job_id": job_id},
    ).scalar_one_or_none()
    if flag is None:
        return False
    return bool(flag)


def finalize_canceled_job(
    session: Session,
    job: GenerationJob,
    course_id: int,
    logs: list[dict[str, Any]],
    flush: Callable[..., GenerationJob],
    *,
    usable_sources: list | None = None,
    rules_context: dict[str, str] | None = None,
) -> GenerationJob:
    """Stop the run cooperatively: persist saved work, release the lock."""
    has_saved_work = bool(job.course_map_json) or bool(job.completed_reels_json)
    partial_docx_path: str | None = None
    partial_score_report: OutputScoreReport | None = None

    if has_saved_work:
        try:
            from app.services.finalize_saved_job import assert_job_snapshot_current

            assert_job_snapshot_current(
                session,
                job,
                action="export canceled partial course",
            )
            partial_course = build_partial_course_from_job(
                job.course_map_json, job.completed_reels_json
            )
            saved_path = export_partial_course_to_docx(partial_course, course_id, job.id)
            partial_docx_path = str(saved_path)
            logs.append({"step": "partial_export", "path": partial_docx_path, "reason": "cancel"})
            if rules_context is not None:
                try:
                    source_texts = [
                        u.course_source.extracted_text
                        for u in (usable_sources or [])
                        if u.course_source.extracted_text
                    ]
                    partial_score_report = score_final_course(
                        extract_plain_text(render_partial_course_docx(partial_course)),
                        rules_context,
                        source_texts=source_texts,
                    )
                except Exception as score_exc:  # noqa: BLE001
                    logs.append(
                        {
                            "step": "output_scoring_failed",
                            "message": redact_secrets(str(score_exc)[:200]),
                        }
                    )
        except Exception as export_exc:  # noqa: BLE001
            logs.append(
                {
                    "step": "partial_export_failed",
                    "message": redact_secrets(str(export_exc)[:200]),
                }
            )

    logs.append({"step": "canceled", "had_saved_work": has_saved_work})
    budget_warning = compute_budget_warning(session, course_id)
    return flush(
        status=JobStatus.CANCELED,
        cancel_requested=False,
        current_stage="canceled",
        error_message=None,
        output_score_json=(
            partial_score_report.model_dump(mode="json") if partial_score_report else None
        ),
        budget_warning=budget_warning,
        partial_docx_path=partial_docx_path,
        last_progress_message=CANCELED_MESSAGE,
    )


def request_cancel(session: Session, job_id: int) -> GenerationJob:
    """Mark cancel requested while keeping the generation lock held."""
    return generation_jobs.update(
        session,
        job_id,
        cancel_requested=True,
        last_progress_message=CANCEL_REQUESTED_MESSAGE,
    )


def stop_job_if_cancel_requested(
    session: Session,
    job: GenerationJob,
    course_id: int,
    logs: list[dict[str, Any]],
    flush: Callable[..., GenerationJob],
    *,
    usable_sources: list | None = None,
    rules_context: dict[str, str] | None = None,
) -> None:
    """Finalize and stop the run when cancel was requested."""
    if not is_cancel_requested(session, job.id):
        return
    finalized = finalize_canceled_job(
        session,
        job,
        course_id,
        logs,
        flush,
        usable_sources=usable_sources,
        rules_context=rules_context,
    )
    raise GenerationCanceled(finalized)
