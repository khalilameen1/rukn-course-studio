from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import JobStatus


class GenerationJobRead(BaseModel):
    """User-facing job status.

    Deliberately excludes `log_json`, `course_map_json`, and
    `completed_reels_json`: those hold internal per-stage review log
    entries and the persisted pipeline state used for loss-safe recovery
    (see docs/ARCHITECTURE.md and app/generation/orchestrator.py), which
    must never be returned to the end user - only this coarse
    status/progress view, plus a small set of user-safe recovery signals
    (`last_completed_step`, the completed counts, `error_category`,
    `partial_docx_path`).

    `run_snapshot_json` and `output_score_json` are safe to return as-is
    (see app/generation/run_snapshot.py / app/generation/output_scoring.py
    - both are secret-free and hash-only by construction) - used by the
    frontend's compact snapshot view and quality-warnings panel (§11).
    `budget_warning` is `None` whenever no budget is configured or spend
    hasn't crossed the configured threshold (see
    app/generation/budget_guard.py).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    status: JobStatus
    current_stage: Optional[str]
    progress_percent: int
    output_docx_path: Optional[str]
    error_message: Optional[str]
    last_completed_step: Optional[str]
    completed_modules_count: int
    completed_reels_count: int
    error_category: Optional[str]
    partial_docx_path: Optional[str]
    run_snapshot_json: Optional[dict[str, Any]] = None
    output_score_json: Optional[dict[str, Any]] = None
    budget_warning: Optional[str] = None
    created_at: datetime
    updated_at: datetime
