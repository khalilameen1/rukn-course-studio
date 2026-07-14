from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.models.enums import JobStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GenerationJob(SQLModel, table=True):
    """One run of the internal generation pipeline for a course.

    `log_json` holds the internal, per-stage log entries (see
    docs/ARCHITECTURE.md Review Log). It is for admin/debug traceability
    only and is never returned to the end user as-is; the user-facing status
    is `status` + `current_stage` + `progress_percent`.
    """

    __tablename__ = "generation_jobs"

    id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="courses.id", index=True)
    status: JobStatus = Field(default=JobStatus.PENDING)
    current_stage: Optional[str] = None
    progress_percent: int = Field(default=0)
    log_json: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    output_docx_path: Optional[str] = None
    error_message: Optional[str] = None

    # --- Loss-safe persistence (see app/generation/orchestrator.py) -------
    # Short, user-safe label of the most recently completed pipeline step
    # (e.g. "build_map", "reel:m1-r2", "module:m1", "final_review",
    # "export_docx") - never raw log content.
    last_completed_step: Optional[str] = None
    completed_modules_count: int = Field(default=0)
    completed_reels_count: int = Field(default=0)
    # Machine-readable category from app/generation/errors.py
    # `classify_provider_error` - set alongside `error_message` whenever a
    # run ends PARTIAL or FAILED.
    error_category: Optional[str] = None
    # Set once a partial DOCX (app/services/docx_export.py
    # `export_partial_course_to_docx`) has been written after a failure -
    # see the "partial_job_{job_id}.docx" naming there, deliberately
    # distinct from a real "course_v{n}.docx" version.
    partial_docx_path: Optional[str] = None
    # Internal-only persisted pipeline state, written incrementally as
    # each piece completes (not batched at the end) - this is what makes a
    # mid-run failure loss-safe: the course map and every completed reel
    # survive a crash, not just the final assembled course. Never returned
    # to the end user - see app/schemas/generation_job.py, same exclusion
    # principle as `log_json`.
    course_map_json: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    completed_reels_json: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )

    # --- AI-ops / quality-control hardening (see docs at the top of ------
    # app/generation/run_snapshot.py, app/generation/output_scoring.py,
    # app/generation/budget_guard.py) ---------------------------------
    # Immutable once written (near the start of the run, right after
    # `_load_active_rules`/`_load_usable_sources`) - a compact, secret-free
    # record of exactly which admin-knowledge content, prompt-compiler
    # version, preset, provider/model, and sources produced this run. See
    # app/generation/run_snapshot.py `build_run_snapshot` for the exact
    # shape and why this lives here rather than on `Course` (see
    # app/models/course.py). Safe to return to the frontend as-is (see
    # app/schemas/generation_job.py `GenerationJobRead.run_snapshot`) -
    # never contains raw admin-knowledge/source text, only short hashes.
    run_snapshot_json: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    # Populated once, after the final (or partial) course text is
    # assembled/exported - see app/generation/output_scoring.py
    # `score_final_course`. Purely observational: never blocks export, and
    # never stored inside the DOCX itself.
    output_score_json: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    # Set only when a budget is configured (see `Settings.ai_monthly_
    # budget_usd`/`ai_course_budget_usd` in app/config.py) AND spend has
    # crossed `ai_warn_at_percent` of it - see app/generation/budget_guard.py.
    # Warning-only: never blocks or aborts a run.
    budget_warning: Optional[str] = None

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
