from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel

from app.models.enums import Priority, SourceCategory


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CourseSource(SQLModel, table=True):
    """An optional uploaded source file (or note) linked to one course."""

    __tablename__ = "course_sources"

    id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="courses.id", index=True)
    source_category: SourceCategory
    original_filename: Optional[str] = None
    file_path: Optional[str] = None
    mime_type: Optional[str] = None
    extracted_text: Optional[str] = None
    priority: Priority = Field(default=Priority.MEDIUM)
    status: str = Field(default="uploaded")
    created_at: datetime = Field(default_factory=_utcnow)
