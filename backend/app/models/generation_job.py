from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, DateTime
from sqlmodel import Field, SQLModel

from app.db_enums import sa_str_enum
from app.db_json import sa_json_array, sa_json_object
from app.models.enums import GenerationQualityMode, JobStatus, WebResearchMode


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GenerationJob(SQLModel, table=True):
    """One run of the internal generation pipeline for a course.

    `log_json` holds the internal, per-stage log entries (see
    docs/ARCHITECTURE.md Review Log). It is for admin/debug traceability
    only and is never returned to the end user as-is; the user-facing status
    is `status` + `current_stage` + `progress_percent` + heartbeat fields
    (`last_progress_message`, indices, `last_saved_at`). Critic drafts and
    specialist attack notes never live on this row in user-readable form.
    """

    __tablename__ = "generation_jobs"

    id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="courses.id", index=True)
    status: JobStatus = Field(
        default=JobStatus.PENDING,
        sa_column=Column(
            sa_str_enum(JobStatus),
            nullable=False,
            server_default=JobStatus.PENDING.value,
        ),
    )
    # Set by POST /cancel while the worker is still running; orchestrator
    # checks between stages and finalizes to canceled/partial when safe.
    cancel_requested: bool = Field(default=False)
    current_stage: Optional[str] = None
    progress_percent: int = Field(default=0)
    log_json: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(sa_json_array(), nullable=False)
    )
    output_docx_path: Optional[str] = None
    error_message: Optional[str] = None

    # --- Loss-safe persistence (see app/generation/orchestrator.py) -------
    # Short, user-safe label of the most recently completed pipeline step
    # (e.g. "build_map", "reel:m1-r2", "module:m1", "final_review",
    # "export_docx") - never raw log content or critic text.
    last_completed_step: Optional[str] = None
    completed_modules_count: int = Field(default=0)
    completed_reels_count: int = Field(default=0)
    total_lessons_count: int = Field(default=0)
    needs_review_count: int = Field(default=0)
    # Machine-readable category from app/generation/errors.py
    # `classify_provider_error` - set alongside `error_message` whenever a
    # run ends PARTIAL or FAILED.
    error_category: Optional[str] = None
    # Set once a partial DOCX (app/services/docx_export.py
    # `export_partial_course_to_docx`) has been written after a failure -
    # see the "partial_job_{job_id}.docx" naming there, deliberately
    # distinct from a real "course_v{n}.docx" version.
    partial_docx_path: Optional[str] = None
    # Heartbeat / progress panel (persisted, not memory-only).
    current_module_index: Optional[int] = None  # 1-based while running
    current_lesson_index: Optional[int] = None  # 1-based within module
    last_progress_message: Optional[str] = None  # coarse user-safe sentence
    last_saved_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    estimated_usage_summary: Optional[str] = None  # short token hint if any
    # Human review handoff (coarse — never DOCX / never critic notes).
    estimated_duration_summary: Optional[str] = None  # e.g. "~120 min"
    # Coarse used/weak/skipped source honesty for the Generate UI (never DOCX).
    sources_run_summary: Optional[str] = None
    # Coarse grounding provenance one-liner (never URLs / citations).
    provenance_summary: Optional[str] = None
    # GENSPARK-style public run signals (never agent text / never DOCX).
    architecture_summary: Optional[str] = None
    grounding_confidence: Optional[str] = None  # strong | mixed | weak
    research_synthesis_summary: Optional[str] = None
    improve_next_tip: Optional[str] = None
    internal_risk_count: int = Field(default=0)
    # Locked architecture depth for this run (Preview | Premium).
    generation_quality_mode: GenerationQualityMode = Field(
        default=GenerationQualityMode.PREMIUM,
        sa_column=Column(
            sa_str_enum(GenerationQualityMode),
            nullable=False,
            server_default=GenerationQualityMode.PREMIUM.value,
        ),
    )
    web_research_mode: WebResearchMode = Field(
        default=WebResearchMode.AUTONOMOUS_GAP_FILL,
        sa_column=Column(
            sa_str_enum(WebResearchMode),
            nullable=False,
            server_default=WebResearchMode.AUTONOMOUS_GAP_FILL.value,
        ),
    )
    # Internal-only research artifacts (admin/debug). Never in GenerationJobRead /
    # DOCX / script_text.
    source_memory_json: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(sa_json_object(), nullable=True)
    )
    web_source_memory_json: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(sa_json_object(), nullable=True)
    )
    evidence_ledger_json: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(sa_json_object(), nullable=True)
    )
    # Source / web memory telemetry for this run (internal — not DOCX).
    source_tokens_used: int = Field(default=0)
    web_searches_count: int = Field(default=0)
    reused_source_memory_count: int = Field(default=0)
    repeated_source_extraction_warnings: int = Field(default=0)
    research_memory_reuse_count: int = Field(default=0)
    # Coarse waste-warning codes for the simple usage panel (never DOCX).
    waste_warnings_json: list[str] = Field(
        default_factory=list, sa_column=Column(sa_json_array(), nullable=False)
    )
    usage_by_stage_json: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(sa_json_object(), nullable=True)
    )
    # Internal-only persisted pipeline state, written incrementally as
    # each piece completes (not batched at the end) - this is what makes a
    # mid-run failure loss-safe: the course map and every completed reel
    # survive a crash, not just the final assembled course. Never returned
    # to the end user - see app/schemas/generation_job.py, same exclusion
    # principle as `log_json`.
    course_map_json: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(sa_json_object(), nullable=True)
    )
    completed_reels_json: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(sa_json_array(), nullable=False)
    )

    # --- AI-ops / quality-control hardening ----------------------------
    run_snapshot_json: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(sa_json_object(), nullable=True)
    )
    output_score_json: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(sa_json_object(), nullable=True)
    )
    budget_warning: Optional[str] = None

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
