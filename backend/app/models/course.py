from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.models.enums import ExplanationLevel, StructureMode


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Course(SQLModel, table=True):
    """A course brief plus its generation configuration and current status.

    `active_rules_snapshot_json` is populated when a generation run starts:
    it's a frozen copy of the active AdminKnowledgeItem set at that moment,
    kept for traceability even if the admin rules change later.
    """

    __tablename__ = "courses"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    audience: str
    outcome: str
    special_notes: Optional[str] = None
    course_type: str = Field(default="practical_skill")
    structure_mode: StructureMode
    manual_map_text: Optional[str] = None
    explanation_level: ExplanationLevel = Field(default=ExplanationLevel.FINAL_ONLY)
    status: str = Field(default="draft")
    active_rules_snapshot_json: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
