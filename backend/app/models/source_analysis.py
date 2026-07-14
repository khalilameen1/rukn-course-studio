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
    # Persistent Source Memory (facts/examples/terminology/summary) — built once.
    # Generation prompts use this; full CourseSource.extracted_text is not resent.
    source_memory_json: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    # Content hash of extracted_text at memory-build time (fast skip check).
    source_hash: Optional[str] = Field(default=None, index=True)
    extraction_version: Optional[str] = Field(default=None)
    extracted_at: Optional[datetime] = Field(default=None)
    tokens_used: int = Field(default=0)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
