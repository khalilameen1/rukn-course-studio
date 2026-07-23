"""Map preview must return actionable errors, never opaque 500s for provider failures."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine

import app.db as db_module
from app.ai.fake_provider import FakeProvider
from app.ai.openai_provider import OpenAIProviderError
from app.config import settings
from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'map_preview_errors.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(settings, "auth_enabled", False)
    monkeypatch.setattr(settings, "ai_provider", "fake")
    monkeypatch.setattr(settings, "generation_skip_disk_check", True)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _create_course(client: TestClient) -> int:
    response = client.post(
        "/courses",
        json={
            "title": "Course",
            "audience": "audience",
            "outcome": "outcome",
            "structure_mode": "connected_no_modules",
            "manual_map_text": None,
            "explanation_level": "final_only",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_map_preview_openai_error_returns_422_not_500(client, monkeypatch):
    course_id = _create_course(client)

    def boom(*_args, **_kwargs):
        raise OpenAIProviderError(
            "CourseMap output failed validation after 3 attempts: bad shape",
            public_hint="CourseMap did not match the required structure after 3 attempts.",
        )

    monkeypatch.setattr(settings, "ai_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(settings, "ai_model_name", "gpt-5.6-sol")

    with (
        patch("app.routers.generation.get_ai_provider", return_value=FakeProvider()),
        patch(
            "app.generation.generation_preflight.generation_preflight",
            return_value={"ok": True, "blockers": [], "warnings": []},
        ),
        patch("app.generation.map_preview.get_ai_provider", return_value=FakeProvider()),
        patch(
            "app.generation.map_preview._build_and_review_course_map",
            side_effect=boom,
        ),
    ):
        response = client.post(
            f"/courses/{course_id}/map-preview",
            json={"generation_quality_mode": "preview"},
        )

    assert response.status_code == 422, response.text
    assert "CourseMap" in response.json()["detail"]
    assert "X-Correlation-ID" not in response.headers


def test_map_preview_preflight_failure_returns_503(client, monkeypatch):
    course_id = _create_course(client)
    monkeypatch.setattr(settings, "ai_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(settings, "ai_model_name", "gpt-5.6-sol")

    with (
        patch("app.routers.generation.get_ai_provider", return_value=FakeProvider()),
        patch(
            "app.generation.generation_preflight.generation_preflight",
            return_value={
                "ok": False,
                "blockers": [
                    "OpenAI authentication failed. Check OPENAI_API_KEY in Render."
                ],
                "warnings": [],
            },
        ),
    ):
        response = client.post(
            f"/courses/{course_id}/map-preview",
            json={"generation_quality_mode": "preview"},
        )

    assert response.status_code == 503, response.text
    assert "OPENAI_API_KEY" in response.json()["detail"]
