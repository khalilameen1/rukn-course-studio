"""GET /build-info — public, secret-free deploy identity."""

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.routers.build_info import build_info_payload

client = TestClient(app)


def test_build_info_payload_has_required_fields_no_secrets():
    payload = build_info_payload()
    assert payload["app_name"]
    assert "environment" in payload
    assert "git_commit" in payload
    assert "build_time" in payload
    assert isinstance(payload["database_type"], str)
    assert isinstance(payload["auth_enabled"], bool)
    assert isinstance(payload["ai_provider"], str)
    blob = " ".join(str(v).lower() for v in payload.values())
    for secret_hint in (
        "anthropic_api_key",
        "auth_secret",
        "password",
        "postgresql://",
        "postgres://",
        "sk-ant",
        "database_url",
    ):
        assert secret_hint not in blob


def test_build_info_route_public_even_with_auth(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "admin_username", "admin")
    monkeypatch.setattr(settings, "admin_password", "s3cret")
    monkeypatch.setattr(settings, "auth_secret_key", "test-secret-key")

    response = client.get("/build-info")
    assert response.status_code == 200
    body = response.json()
    assert "git_commit" in body
    assert "database_type" in body
    assert isinstance(body.get("api_routes"), list)
    assert "ANTHROPIC_API_KEY" not in response.text
    assert "AUTH_SECRET_KEY" not in response.text
    assert "DATABASE_URL" not in response.text


def test_health_still_public(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "auth_secret_key", "test-secret-key")
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
