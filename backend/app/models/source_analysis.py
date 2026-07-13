from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SourceAnalysis(SQLModel, table=True):
    """Simple, no-vector-DB analysis of one CourseSource's extracted text.

    One row per source (see app/services/chunking.py and
    app/services/source_analysis.py for how these fields are computed -
    plain heuristics, no embeddings/vector search/RAG framework).
    """

    __tablename__ = "source_analyses"

    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="course_sources.id", index=True, unique=True)
    chunks_json: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    source_summary: str
    key_points_json: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    avoid_points_json: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
