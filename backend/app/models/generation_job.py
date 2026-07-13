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
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
