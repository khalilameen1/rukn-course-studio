from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Column, true as sa_true
from sqlmodel import Field, SQLModel

from app.db_enums import sa_str_enum
from app.models.enums import Priority, SourceCategory


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CourseSource(SQLModel, table=True):
    """An optional uploaded source file (or note) linked to one course."""

    __tablename__ = "course_sources"

    id: Optional[int] = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="courses.id", index=True)
    source_category: SourceCategory = Field(
        sa_column=Column(sa_str_enum(SourceCategory), nullable=False)
    )
    # Display title (filename fallback). Course-specific — never the canonical standard.
    title: Optional[str] = Field(default=None)
    original_filename: Optional[str] = None
    file_path: Optional[str] = None
    mime_type: Optional[str] = None
    extracted_text: Optional[str] = None
    priority: Priority = Field(
        default=Priority.MEDIUM,
        sa_column=Column(
            sa_str_enum(Priority),
            nullable=False,
            server_default=Priority.MEDIUM.value,
        ),
    )
    status: str = Field(default="uploaded")
    # Cost hygiene: when False, source is kept but not injected into generation.
    # DB default must be TRUE (not integer 1) for Postgres compatibility.
    include_in_generation: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default=sa_true()),
    )
    # Content hash of extracted/pasted text (aligned with Source Memory).
    source_hash: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=_utcnow)
