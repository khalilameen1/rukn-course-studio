from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, computed_field

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
    progress_percent: int
    output_docx_path: Optional[str]
    error_message: Optional[str]
    last_completed_step: Optional[str]
    completed_modules_count: int
    completed_reels_count: int
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
