"""Stringified JSON columns must not crash generation source loading."""

from __future__ import annotations

import json

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.crud import course_sources, courses, source_analyses
from app.generation.orchestrator import _load_usable_sources_with_memory, _usable_memory
from app.generation.source_memory_store import build_source_memory_payload, compute_source_hash
from app.models.enums import Priority, SourceCategory, StructureMode, ExplanationLevel
from app.services.json_coerce import coerce_json_dict, coerce_json_list


def test_coerce_json_dict_and_list():
    assert coerce_json_dict(None) is None
    assert coerce_json_dict({"a": 1}) == {"a": 1}
    assert coerce_json_dict('{"a": 1}') == {"a": 1}
    assert coerce_json_dict("[]") is None
    assert coerce_json_dict("not-json") is None
    assert coerce_json_list(None) == []
    assert coerce_json_list([1]) == [1]
    assert coerce_json_list("[1,2]") == [1, 2]
    assert coerce_json_list("{}") == []


@pytest.fixture()
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'coerce.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_load_usable_sources_tolerates_stringified_source_memory(session: Session):
    course = courses.create(
        session,
        title="Meta Ads",
        audience="Shop owners",
        outcome="Run ads",
        structure_mode=StructureMode.CONNECTED_NO_MODULES,
        explanation_level=ExplanationLevel.FINAL_ONLY,
    )
    text = "Meta ads campaign setup for Egyptian boutique shops with ROAS tracking."
    source = course_sources.create(
        session,
        course_id=course.id,
        source_category=SourceCategory.USER_NOTES,
        priority=Priority.MEDIUM,
        status="ready",
        extracted_text=text,
        include_in_generation=True,
        title="notes.txt",
    )
    memory = build_source_memory_payload(
        title="notes.txt",
        category=SourceCategory.USER_NOTES.value,
        extracted_text=text,
        summary="Meta ads notes",
        chunks=[{"text": text[:40], "index": 0}],
        key_points=["ROAS"],
        avoid_points=[],
    )
    # Simulate Postgres TEXT JSON column: stored as a JSON string, not a dict.
    source_analyses.create(
        session,
        source_id=source.id,
        chunks_json=json.dumps([{"text": text[:40], "index": 0}]),
        source_summary="Meta ads notes",
        key_points_json=json.dumps(["ROAS"]),
        avoid_points_json="[]",
        source_memory_json=json.dumps(memory),
        source_hash=compute_source_hash(text),
        extraction_version=memory.get("extraction_version"),
        tokens_used=1,
    )

    usable, tele = _load_usable_sources_with_memory(session, course.id)
    assert len(usable) == 1
    assert tele.reused_source_memory_count == 1
    mem = _usable_memory(usable[0])
    assert isinstance(mem, dict)
    assert mem.get("raw_source_hash") or mem.get("source_hash")
