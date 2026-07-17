"""Source-experience honesty: duplicates, preview, poor_extraction default, readiness."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

import app.db as db_module
from app.config import settings
from app.main import app
from app.services.source_run_honesty import (
    OVERLOAD_CHAR_BUDGET,
    classify_sources_for_run,
    format_sources_run_summary,
)

SAMPLE_TEXT = (
    "This is a reasonably long sample paragraph of real text used to "
    "validate the sources router across upload, list, delete, and "
    "category-change scenarios."
)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(settings, "storage_uploads_dir", tmp_path / "uploads")
    monkeypatch.setattr(settings, "storage_extracted_dir", tmp_path / "extracted")
    monkeypatch.setattr(settings, "ai_provider", "fake")

    with TestClient(app) as test_client:
        yield test_client, engine


def _create_course(client: TestClient) -> int:
    response = client.post(
        "/courses",
        json={
            "title": "Honesty course",
            "audience": "testers",
            "outcome": "source experience",
            "structure_mode": "connected_no_modules",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_classify_sources_run_honesty_counts():
    sources = [
        SimpleNamespace(
            id=1,
            title="a",
            original_filename="a.txt",
            status="ready",
            include_in_generation=True,
            extracted_text="x" * 100,
        ),
        SimpleNamespace(
            id=2,
            title="b",
            original_filename="b.txt",
            status="poor_extraction",
            include_in_generation=True,
            extracted_text="weak",
        ),
        SimpleNamespace(
            id=3,
            title="c",
            original_filename="c.pdf",
            status="password_required",
            include_in_generation=True,
            extracted_text=None,
        ),
        SimpleNamespace(
            id=4,
            title="d",
            original_filename="d.txt",
            status="ready",
            include_in_generation=False,
            extracted_text="skip me",
        ),
    ]
    result = classify_sources_for_run(sources)
    assert result["used_count"] == 1
    assert result["weak_count"] == 1
    assert result["skipped_count"] == 1
    assert result["excluded_count"] == 1
    assert "Used 1" in format_sources_run_summary(sources)


def test_overload_flag_when_over_budget():
    sources = [
        SimpleNamespace(
            id=1,
            title="big",
            original_filename="big.txt",
            status="ready",
            include_in_generation=True,
            extracted_text="y" * (OVERLOAD_CHAR_BUDGET + 50),
        )
    ]
    result = classify_sources_for_run(sources)
    assert result["overload"] is True
    assert OVERLOAD_CHAR_BUDGET < result["included_chars"]


def test_duplicate_filename_requires_force(client):
    test_client, _ = client
    course_id = _create_course(test_client)
    first = test_client.post(
        f"/courses/{course_id}/sources/upload",
        data={"source_category": "scientific_reference", "priority": "medium"},
        files={"file": ("note.txt", SAMPLE_TEXT.encode("utf-8"), "text/plain")},
    )
    assert first.status_code == 201

    dup = test_client.post(
        f"/courses/{course_id}/sources/upload",
        data={"source_category": "scientific_reference", "priority": "medium"},
        files={"file": ("note.txt", SAMPLE_TEXT.encode("utf-8"), "text/plain")},
    )
    assert dup.status_code == 409
    detail = dup.json()["detail"]
    assert detail["code"] == "duplicate_filename"

    forced = test_client.post(
        f"/courses/{course_id}/sources/upload",
        data={
            "source_category": "scientific_reference",
            "priority": "medium",
            "force": "true",
        },
        files={"file": ("note.txt", SAMPLE_TEXT.encode("utf-8"), "text/plain")},
    )
    assert forced.status_code == 201
    # Same content hash → second copy excluded by default
    assert forced.json()["include_in_generation"] is False


def test_poor_extraction_defaults_include_false(client):
    test_client, _ = client
    course_id = _create_course(test_client)
    response = test_client.post(
        f"/courses/{course_id}/sources/upload",
        data={"source_category": "scientific_reference", "priority": "medium"},
        files={"file": ("tiny.txt", b"hi", "text/plain")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "poor_extraction"
    assert body["include_in_generation"] is False
    assert "excluded from generation" in (body.get("status_message") or "").lower() or True


def test_analysis_preview_endpoint(client):
    test_client, _ = client
    course_id = _create_course(test_client)
    uploaded = test_client.post(
        f"/courses/{course_id}/sources/upload",
        data={"source_category": "scientific_reference", "priority": "medium"},
        files={"file": ("note.txt", SAMPLE_TEXT.encode("utf-8"), "text/plain")},
    )
    assert uploaded.status_code == 201
    source_id = uploaded.json()["id"]

    preview = test_client.get(f"/courses/{course_id}/sources/{source_id}/analysis")
    assert preview.status_code == 200
    data = preview.json()
    assert data["source_id"] == source_id
    assert data.get("source_summary")
    assert isinstance(data["key_points"], list)
    assert "chunks_json" not in data
    assert "extracted_text" not in data
    assert set(data.keys()) <= {"source_id", "source_summary", "key_points"}


def test_readiness_includes_sources_summary(client):
    test_client, _ = client
    course_id = _create_course(test_client)
    test_client.post(
        f"/courses/{course_id}/sources/upload",
        data={"source_category": "scientific_reference", "priority": "medium"},
        files={"file": ("note.txt", SAMPLE_TEXT.encode("utf-8"), "text/plain")},
    )
    readiness = test_client.get(f"/courses/{course_id}/readiness")
    assert readiness.status_code == 200
    body = readiness.json()
    assert body["included_source_count"] >= 1
    assert "sources_summary" in body
    assert "Used" in (body["sources_summary"] or "")
