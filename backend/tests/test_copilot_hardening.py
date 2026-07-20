"""Copilot-scale hardening: scopes, denylist, job IDOR, source DTO, diagnostics."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

import app.db as db_module
from app.auth.password_hash import hash_password, verify_password
from app.auth.scopes import (
    SCOPE_AI_USAGE,
    SCOPE_COURSES,
    normalize_scopes,
    required_scope_for_path,
)
from app.auth.token_denylist import is_jti_revoked, revoke_jti
from app.auth.tokens import create_token, verify_token
from app.config import settings
from app.crud import generation_jobs
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
    monkeypatch.setattr(settings, "ai_provider", "fake")
    monkeypatch.setattr(settings, "auth_enabled", False)

    with TestClient(app) as test_client:
        yield test_client, engine


def _create_course(client: TestClient) -> int:
    response = client.post(
        "/courses",
        json={
            "title": "Hardening course",
            "audience": "testers",
            "outcome": "copilot touches",
            "structure_mode": "connected_no_modules",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_normalize_scopes_fail_closed():
    assert normalize_scopes(None) == [SCOPE_COURSES]
    assert normalize_scopes([]) == [SCOPE_COURSES]
    assert SCOPE_AI_USAGE in normalize_scopes(
        [SCOPE_COURSES, SCOPE_AI_USAGE, "nope"]
    )


def test_ai_usage_paths_require_ai_scope():
    assert required_scope_for_path("GET", "/ai-usage/summary") == SCOPE_AI_USAGE
    assert required_scope_for_path("GET", "/courses/3/ai-usage") == SCOPE_AI_USAGE


def test_password_hash_roundtrip():
    stored = hash_password("secret-value")
    assert stored.startswith("pbkdf2_sha256$")
    assert verify_password("secret-value", stored)
    assert not verify_password("wrong", stored)
    assert verify_password("plain", "plain")


def test_token_jti_and_denylist(client):
    _, engine = client
    token = create_token("admin", "test-secret", scopes=[SCOPE_COURSES])
    payload = verify_token(token, "test-secret")
    assert payload["jti"]
    with Session(engine) as session:
        assert not is_jti_revoked(session, payload["jti"])
        revoke_jti(
            session,
            payload["jti"],
            expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            username="admin",
        )
        assert is_jti_revoked(session, payload["jti"])


def test_source_list_omits_extracted_text(client):
    test_client, _ = client
    course_id = _create_course(test_client)
    uploaded = test_client.post(
        f"/courses/{course_id}/sources/upload",
        data={"source_category": "scientific_reference", "priority": "medium"},
        files={"file": ("note.txt", SAMPLE_TEXT.encode("utf-8"), "text/plain")},
    )
    assert uploaded.status_code == 201
    body = uploaded.json()
    assert "extracted_text" not in body
    assert body["has_extracted_text"] is True
    assert body["extract_char_count"] > 0

    listed = test_client.get(f"/courses/{course_id}/sources").json()
    assert "extracted_text" not in listed[0]


def test_job_requires_course_id(client):
    test_client, engine = client
    course_id = _create_course(test_client)
    # This is an IDOR/DTO test, not a generation test. Create the row
    # directly so the canonical map-confirmation gate is not bypassed and
    # no complete-course pipeline runs during the test suite.
    with Session(engine) as session:
        job_id = generation_jobs.create(session, course_id=course_id).id

    missing = test_client.get(f"/jobs/{job_id}")
    assert missing.status_code == 422

    wrong = test_client.get(f"/jobs/{job_id}?course_id={course_id + 999}")
    assert wrong.status_code == 404

    ok = test_client.get(f"/jobs/{job_id}?course_id={course_id}")
    assert ok.status_code == 200
    data = ok.json()
    assert "waste_warnings_json" not in data
    assert "needs_review_count" not in data


def test_public_diagnostics_is_minimal(client):
    test_client, _ = client
    res = test_client.get("/auth/diagnostics")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "cors_origins" not in data
    assert "last_error_message" not in data
    assert "ai_model_name" not in data
