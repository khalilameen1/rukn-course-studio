"""Hardened source upload: validation, storage/DB cleanup, legacy enums, processing."""

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

import app.db as db_module
from app.config import settings
from app.db import _normalize_str_enum_storage
from app.main import app

SAMPLE = (
    "This is a reasonably long sample paragraph of real text used to "
    "validate the sources upload hardening path end to end. "
).encode("utf-8")

ARABIC = ("نص عربي تجريبي طويل بما يكفي لاستخراج النص من الملف المرفوع. " * 8).encode(
    "utf-8"
)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'upload.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(settings, "storage_uploads_dir", tmp_path / "uploads")
    monkeypatch.setattr(settings, "storage_extracted_dir", tmp_path / "extracted")
    settings.storage_uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.storage_extracted_dir.mkdir(parents=True, exist_ok=True)
    with TestClient(app) as test_client:
        yield test_client, engine, tmp_path


def _create_course(client: TestClient) -> int:
    response = client.post(
        "/courses",
        json={
            "title": "Upload harden course",
            "audience": "testers",
            "outcome": "test uploads",
            "structure_mode": "connected_no_modules",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_supported_upload_succeeds(client):
    test_client, _, _ = client
    cid = _create_course(test_client)
    res = test_client.post(
        f"/courses/{cid}/sources/upload",
        data={"source_category": "scientific_reference", "priority": "medium"},
        files={"file": ("note.txt", SAMPLE, "text/plain")},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "ready"
    assert Path(body["file_path"]).is_file()


def test_arabic_filename_upload(client):
    test_client, _, _ = client
    cid = _create_course(test_client)
    res = test_client.post(
        f"/courses/{cid}/sources/upload",
        data={"source_category": "scientific_reference", "priority": "high"},
        files={"file": ("مرجع علمي (١).txt", ARABIC, "text/plain")},
    )
    assert res.status_code == 201, res.text
    assert "مرجع" in (res.json()["original_filename"] or "")


def test_spaces_and_symbols_in_filename(client):
    test_client, _, _ = client
    cid = _create_course(test_client)
    res = test_client.post(
        f"/courses/{cid}/sources/upload",
        data={"source_category": "raw_material", "priority": "low"},
        files={"file": ("my file @# name (v2).txt", SAMPLE, "text/plain")},
    )
    assert res.status_code == 201, res.text
    assert Path(res.json()["file_path"]).is_file()


def test_missing_extension_rejected(client):
    test_client, _, _ = client
    cid = _create_course(test_client)
    res = test_client.post(
        f"/courses/{cid}/sources/upload",
        data={"source_category": "scientific_reference", "priority": "medium"},
        files={"file": ("noext", SAMPLE, "text/plain")},
    )
    assert res.status_code == 415


def test_unsupported_type_415(client):
    test_client, _, _ = client
    cid = _create_course(test_client)
    res = test_client.post(
        f"/courses/{cid}/sources/upload",
        data={"source_category": "scientific_reference", "priority": "medium"},
        files={"file": ("x.exe", b"MZ", "application/octet-stream")},
    )
    assert res.status_code == 415


def test_oversized_413(client, monkeypatch):
    test_client, _, _ = client
    monkeypatch.setattr(settings, "max_upload_bytes", 64)
    cid = _create_course(test_client)
    res = test_client.post(
        f"/courses/{cid}/sources/upload",
        data={"source_category": "scientific_reference", "priority": "medium"},
        files={"file": ("big.txt", b"x" * 200, "text/plain")},
    )
    assert res.status_code == 413


def test_missing_file_400(client):
    test_client, _, _ = client
    cid = _create_course(test_client)
    res = test_client.post(
        f"/courses/{cid}/sources/upload",
        data={"source_category": "scientific_reference", "priority": "medium"},
    )
    assert res.status_code in (400, 422)


def test_storage_failure_no_db_row(client):
    test_client, engine, _ = client
    cid = _create_course(test_client)
    with patch("pathlib.Path.write_bytes", side_effect=OSError(28, "No space left")):
        res = test_client.post(
            f"/courses/{cid}/sources/upload",
            data={"source_category": "scientific_reference", "priority": "medium"},
            files={"file": ("ok.txt", SAMPLE, "text/plain")},
        )
    assert res.status_code == 500
    assert "disk" in res.json()["detail"].lower() or "store" in res.json()["detail"].lower()
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM course_sources WHERE course_id = :cid"),
            {"cid": cid},
        ).scalar()
    assert count == 0


def test_db_failure_after_storage_cleans_file(client):
    test_client, engine, _ = client
    cid = _create_course(test_client)

    def boom(session, **fields):
        raise RuntimeError("db down")

    with patch("app.routers.sources.course_sources.create", side_effect=boom):
        res = test_client.post(
            f"/courses/{cid}/sources/upload",
            data={"source_category": "scientific_reference", "priority": "medium"},
            files={"file": ("ok.txt", SAMPLE, "text/plain")},
        )
    assert res.status_code == 500
    upload_dir = settings.storage_uploads_dir / str(cid)
    leftovers = list(upload_dir.glob("*")) if upload_dir.exists() else []
    assert leftovers == [], leftovers
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM course_sources WHERE course_id = :cid"),
            {"cid": cid},
        ).scalar()
    assert count == 0


def test_analysis_failure_still_returns_uploaded_source(client):
    test_client, engine, _ = client
    cid = _create_course(test_client)
    with patch(
        "app.routers.sources._create_source_analysis",
        side_effect=RuntimeError("analysis boom"),
    ):
        res = test_client.post(
            f"/courses/{cid}/sources/upload",
            data={"source_category": "scientific_reference", "priority": "medium"},
            files={"file": ("ok.txt", SAMPLE, "text/plain")},
        )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "processing_failed"
    assert Path(body["file_path"]).is_file()
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM course_sources WHERE course_id = :cid"),
            {"cid": cid},
        ).scalar()
    assert count == 1


def test_legacy_source_category_rows_list_after_normalize(client, monkeypatch):
    test_client, engine, _ = client
    monkeypatch.setattr(db_module, "engine", engine)
    cid = _create_course(test_client)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO course_sources ("
                "course_id, source_category, priority, status, include_in_generation, "
                "original_filename, created_at"
                ") VALUES ("
                ":cid, 'NOTES', 'medium', 'ready', 1, 'old.txt', CURRENT_TIMESTAMP"
                ")"
            ),
            {"cid": cid},
        )
        conn.execute(
            text(
                "INSERT INTO course_sources ("
                "course_id, source_category, priority, status, include_in_generation, "
                "original_filename, created_at"
                ") VALUES ("
                ":cid, 'MAIN_CONTENT', 'medium', 'ready', 1, 'old2.txt', CURRENT_TIMESTAMP"
                ")"
            ),
            {"cid": cid},
        )

    broken = test_client.get(f"/courses/{cid}/sources")
    assert broken.status_code == 500

    _normalize_str_enum_storage()

    ok = test_client.get(f"/courses/{cid}/sources")
    assert ok.status_code == 200, ok.text
    cats = {row["source_category"] for row in ok.json()}
    assert "user_notes" in cats
    assert "scientific_reference" in cats
    assert "NOTES" not in cats
    assert "MAIN_CONTENT" not in cats


def test_reprocess_without_reupload(client):
    test_client, _, _ = client
    cid = _create_course(test_client)
    uploaded = test_client.post(
        f"/courses/{cid}/sources/upload",
        data={"source_category": "scientific_reference", "priority": "medium"},
        files={"file": ("ok.txt", SAMPLE, "text/plain")},
    )
    assert uploaded.status_code == 201
    sid = uploaded.json()["id"]
    path = Path(uploaded.json()["file_path"])
    assert path.is_file()

    again = test_client.post(f"/courses/{cid}/sources/{sid}/reprocess")
    assert again.status_code == 200, again.text
    assert again.json()["status"] == "ready"
    assert Path(again.json()["file_path"]).is_file()
