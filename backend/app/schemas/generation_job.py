import json
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, computed_field, field_validator

from app.models.enums import GenerationQualityMode, JobStatus, WebResearchMode


class GenerateCourseRequest(BaseModel):
    """Optional body for POST /courses/{id}/generate.

    Never accepts raw temperature, agent knobs, or research confirmation UX.
    """

    generation_quality_mode: GenerationQualityMode = GenerationQualityMode.PREMIUM
    web_research_mode: WebResearchMode = WebResearchMode.AUTONOMOUS_GAP_FILL


class GenerationJobRead(BaseModel):
    """User-facing job status.

    Deliberately excludes `log_json`, `course_map_json`, and
    `completed_reels_json`: those hold internal per-stage review log
    entries and the persisted pipeline state used for loss-safe recovery
    (see docs/ARCHITECTURE.md and app/generation/orchestrator.py), which
    must never be returned to the end user - only this coarse
    status/progress view, plus a small set of user-safe recovery signals.
    Critic comments, student notes, mentor notes, and drafts are never
    exposed here.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    status: JobStatus
    cancel_requested: bool = False
    current_stage: Optional[str]
    progress_percent: int = 0
    output_docx_path: Optional[str]
    error_message: Optional[str]
    last_completed_step: Optional[str]
    completed_modules_count: int = 0
    completed_reels_count: int = 0
    total_lessons_count: int = 0
    needs_review_count: int = 0
    error_category: Optional[str]
    partial_docx_path: Optional[str]
    current_module_index: Optional[int] = None
    current_lesson_index: Optional[int] = None
    last_progress_message: Optional[str] = None
    last_saved_at: Optional[datetime] = None
    estimated_usage_summary: Optional[str] = None
    estimated_duration_summary: Optional[str] = None
    internal_risk_count: int = 0
    generation_quality_mode: GenerationQualityMode = GenerationQualityMode.PREMIUM
    web_research_mode: WebResearchMode = WebResearchMode.AUTONOMOUS_GAP_FILL
    run_snapshot_json: Optional[dict[str, Any]] = None
    output_score_json: Optional[dict[str, Any]] = None
    budget_warning: Optional[str] = None
    web_searches_count: int = 0
    reused_source_memory_count: int = 0
    research_memory_reuse_count: int = 0
    waste_warnings_json: list[str] = []
    usage_by_stage_json: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("waste_warnings_json", mode="before")
    @classmethod
    def _coerce_waste_warnings(cls, value: object) -> object:
        # Postgres TEXT legacy columns / drivers may hand back JSON as a string.
        if value is None:
            return []
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return []
            return parsed if isinstance(parsed, list) else []
        return value

    @field_validator(
        "run_snapshot_json",
        "output_score_json",
        "usage_by_stage_json",
        mode="before",
    )
    @classmethod
    def _coerce_optional_json_objects(cls, value: object) -> object:
        if value is None or value == "":
            return None
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return None
            return parsed if isinstance(parsed, dict) else None
        return value

    @field_validator("cancel_requested", mode="before")
    @classmethod
    def _coerce_cancel_requested(cls, value: object) -> object:
        return False if value is None else value

    @field_validator(
        "progress_percent",
        "completed_modules_count",
        "completed_reels_count",
        "total_lessons_count",
        "needs_review_count",
        "internal_risk_count",
        "web_searches_count",
        "reused_source_memory_count",
        "research_memory_reuse_count",
        mode="before",
    )
    @classmethod
    def _coerce_null_ints(cls, value: object) -> object:
        return 0 if value is None else value

    @field_validator("status", "generation_quality_mode", "web_research_mode", mode="before")
    @classmethod
    def _coerce_enum_name_or_value(cls, value: object) -> object:
        """Accept legacy NAME strings (`RUNNING`) as well as values (`running`)."""
        if value is None or not isinstance(value, str):
            return value
        for enum_cls in (JobStatus, GenerationQualityMode, WebResearchMode):
            try:
                return enum_cls(value)
            except ValueError:
                pass
            try:
                return enum_cls[value]
            except KeyError:
                pass
        return value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def run_status(self) -> JobStatus:
        """Alias for `status` — persisted operational run state."""
        return self.status

    @computed_field  # type: ignore[prop-decorator]
    @property
    def completed_lessons_count(self) -> int:
        """Alias for `completed_reels_count` (lessons == reels)."""
        return self.completed_reels_count

    @computed_field  # type: ignore[prop-decorator]
    @property
    def partial_docx_available(self) -> bool:
        return bool(self.partial_docx_path)
