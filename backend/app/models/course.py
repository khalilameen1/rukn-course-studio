from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.models.enums import ExplanationLevel, GenerationPreset, StructureMode


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Course(SQLModel, table=True):
    """A course brief plus its generation configuration and current status.

    `active_rules_snapshot_json` (deprecated, unused): the docstring below
    originally described intended behavior that was never actually wired
    up anywhere in the codebase (confirmed by grep - nothing ever writes to
    this field). It's also the wrong model for a per-run snapshot: `Course`
    is one mutable row reused across every run for that course, so writing
    a snapshot here on each run would silently overwrite the previous
    run's snapshot the next time generation runs - exactly what "old
    generation runs should still show which snapshot they used" rules out.
    The real, immutable, per-run snapshot lives on
    `GenerationJob.run_snapshot_json` instead - see
    app/generation/run_snapshot.py. This field is left in place (nothing
    references it, so removing it isn't necessary) but should be
    considered dead/reserved, not a source of truth for anything.
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
    generation_preset: GenerationPreset = Field(default=GenerationPreset.BALANCED)
    status: str = Field(default="draft")
    active_rules_snapshot_json: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
