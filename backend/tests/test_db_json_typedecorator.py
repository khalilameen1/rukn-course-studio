"""ORM JSON TypeDecorators must coerce TEXT-stored JSON to dict/list."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import Column, create_engine, text
from sqlmodel import Field, Session, SQLModel

from app.db_json import sa_json_array, sa_json_object
from app.schemas.generation_job import GenerationJobRead


def test_sa_json_object_and_array_roundtrip_from_text(tmp_path):
    """Simulate Postgres TEXT JSON: insert raw strings, ORM must return dict/list."""
    engine = create_engine(f"sqlite:///{tmp_path / 'json_td.db'}")

    class Row(SQLModel, table=True):
        __tablename__ = "json_td_row"
        id: int | None = Field(default=None, primary_key=True)
        obj: dict | None = Field(default=None, sa_column=Column(sa_json_object()))
        arr: list = Field(default_factory=list, sa_column=Column(sa_json_array()))

    SQLModel.metadata.create_all(engine)
    with engine.begin() as conn:
        # Bypass ORM bind processors: store as literal TEXT JSON strings.
        conn.execute(
            text(
                "INSERT INTO json_td_row (id, obj, arr) VALUES "
                "(1, :obj, :arr)"
            ),
            {"obj": json.dumps({"a": 1}), "arr": json.dumps(["x", "y"])},
        )

    with Session(engine) as session:
        row = session.get(Row, 1)
        assert row is not None
        assert row.obj == {"a": 1}
        assert row.arr == ["x", "y"]
        assert isinstance(row.obj, dict)
        assert isinstance(row.arr, list)


def test_generation_job_read_still_accepts_string_json():
    """Schema validators remain as a second line of defense for API responses."""
    now = datetime.now(timezone.utc)
    read = GenerationJobRead.model_validate(
        {
            "id": 1,
            "course_id": 1,
            "status": "failed",
            "cancel_requested": False,
            "current_stage": "failed",
            "progress_percent": 0,
            "output_docx_path": None,
            "error_message": "x",
            "last_completed_step": None,
            "error_category": "unknown",
            "partial_docx_path": None,
            "generation_quality_mode": "premium",
            "web_research_mode": "autonomous_gap_fill",
            "waste_warnings_json": '["dup"]',
            "usage_by_stage_json": '{"map": 1}',
            "created_at": now,
            "updated_at": now,
        }
    )
    assert read.waste_warnings_json == ["dup"]
    assert read.usage_by_stage_json == {"map": 1}
