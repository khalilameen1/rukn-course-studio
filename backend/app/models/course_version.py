from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CourseVersion(SQLModel, table=True):
    """A completed, downloadable DOCX output for a course.

    A course can be regenerated (per docs/ARCHITECTURE.md's "regeneration
    over live editing" principle); each successful run adds one version
    here rather than overwriting the previous DOCX.
    """

    __tablename__ = "course_versions"

    id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="courses.id", index=True)
    version_number: int
    output_docx_path: str
    summary_text: Optional[str] = None
    # Only populated when the course's explanation_level is "full_report"
    # (see app/generation/orchestrator.py `_build_course_report`) - null for
    # "final_only"/"short_summary".
    report_text: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)
