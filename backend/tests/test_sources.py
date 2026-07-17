"""Tests for app/routers/sources.py: upload, list, delete, and the
category-change (PATCH) endpoint - run through the real FastAPI app so the
router, CRUD, and storage-cleanup logic are all exercised together."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

import app.db as db_module
from app.config import settings
from app.main import app

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

    with TestClient(app) as test_client:
        yield test_client, engine


def _create_course(client: TestClient) -> int:
    response = client.post(
        "/courses",
        json={
            "title": "Sources test course",
            "audience": "testers",
            "outcome": "test the sources router",
            "structure_mode": "connected_no_modules",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _upload_source(client: TestClient, course_id: int, category: str = "scientific_reference") -> dict:
    response = client.post(
        f"/courses/{course_id}/sources/upload",
        data={"source_category": category, "priority": "medium"},
        files={"file": ("note.txt", SAMPLE_TEXT.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 201
    return response.json()


def test_upload_and_list_sources(client):
    test_client, _ = client
    course_id = _create_course(test_client)

    uploaded = _upload_source(test_client, course_id)
    assert uploaded["source_category"] == "scientific_reference"
    assert uploaded["status"] == "ready"

    list_response = test_client.get(f"/courses/{course_id}/sources")
    assert list_response.status_code == 200
    sources = list_response.json()
    assert len(sources) == 1
    assert sources[0]["id"] == uploaded["id"]


def test_delete_source_removes_row_and_file(client):
    test_client, engine = client
    course_id = _create_course(test_client)
    uploaded = _upload_source(test_client, course_id)
    source_id = uploaded["id"]

    from app.models.course_source import CourseSource

    with Session(engine) as session:
        row = session.get(CourseSource, source_id)
        assert row is not None and row.file_path
        file_path = Path(row.file_path)
    assert file_path.exists()

    # Default call is a dry run: nothing deleted yet.
    dry_response = test_client.delete(f"/courses/{course_id}/sources/{source_id}")
    assert dry_response.status_code == 200
    assert dry_response.json()["applied"] is False
    assert file_path.exists()

    delete_response = test_client.delete(
        f"/courses/{course_id}/sources/{source_id}?confirm=true&dry_run=false"
        f"&confirm_name={uploaded['original_filename']}"
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["applied"] is True
    assert not file_path.exists()

    list_response = test_client.get(f"/courses/{course_id}/sources")
    assert list_response.json() == []


def test_delete_nonexistent_source_returns_404(client):
    test_client, _ = client
    course_id = _create_course(test_client)

    response = test_client.delete(f"/courses/{course_id}/sources/999999")
    assert response.status_code == 404


def test_patch_source_category_updates_category_and_avoid_points(client):
    test_client, engine = client
    course_id = _create_course(test_client)
    uploaded = _upload_source(test_client, course_id, category="scientific_reference")
    source_id = uploaded["id"]

    patch_response = test_client.patch(
        f"/courses/{course_id}/sources/{source_id}",
        json={"source_category": "flow_reference"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["source_category"] == "flow_reference"

    from app.crud import source_analyses

    with Session(engine) as session:
        analyses = source_analyses.list(session, source_id=source_id)
        assert len(analyses) == 1
        assert analyses[0].avoid_points_json
        assert "Natural Colloquial" in analyses[0].avoid_points_json[0] or (
            "colloquial" in analyses[0].avoid_points_json[0].lower()
        )


def test_patch_source_category_404_for_wrong_course(client):
    test_client, _ = client
    course_id = _create_course(test_client)
    other_course_id = _create_course(test_client)
    uploaded = _upload_source(test_client, course_id)

    response = test_client.patch(
        f"/courses/{other_course_id}/sources/{uploaded['id']}",
        json={"source_category": "flow_reference"},
    )
    assert response.status_code == 404


def test_patch_source_category_404_for_wrong_source_id(client):
    test_client, _ = client
    course_id = _create_course(test_client)

    response = test_client.patch(
        f"/courses/{course_id}/sources/999999",
        json={"source_category": "flow_reference"},
    )
    assert response.status_code == 404
