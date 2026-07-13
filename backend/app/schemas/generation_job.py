from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import JobStatus


class GenerationJobRead(BaseModel):
    """User-facing job status.

    Deliberately excludes `log_json`: that field holds internal per-stage
    review log entries (see docs/ARCHITECTURE.md), which must never be
    returned to the end user - only this coarse status/progress view.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    status: JobStatus
    current_stage: Optional[str]
    progress_percent: int
    output_docx_path: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
