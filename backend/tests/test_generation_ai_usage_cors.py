"""CORS / preflight / auth for generation + AI usage endpoints.

Regression guards for browser failures that surface as a generic
Network/CORS/API URL error on the Course Generation and AI Usage pages
when Auth short-circuits a 401 without CORS headers, or when OPTIONS
preflight is blocked on Authorization-bearing POSTs/GETs.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)

ORIGIN = "http://localhost:3000"


@pytest.fixture(autouse=True)
def _configure_auth(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "admin_username", "admin")
    monkeypatch.setattr(settings, "admin_password", "s3cret")
    monkeypatch.setattr(settings, "auth_secret_key", "test-secret-key")


def _auth_header() -> dict[str, str]:
    login = client.post("/auth/login", json={"username": "admin", "password": "s3cret"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_generate_options_preflight_returns_cors_headers():
    response = client.options(
        "/courses/1/generate",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type,accept",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN
    allow_headers = response.headers.get("access-control-allow-headers", "").lower()
    assert "authorization" in allow_headers
    assert "content-type" in allow_headers


def test_generate_unauthenticated_post_returns_401_with_cors():
    response = client.post(
        "/courses/1/generate",
        json={"generation_quality_mode": "premium"},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert response.json()["detail"] == "Not authenticated"


def test_generate_authenticated_post_returns_real_backend_status_with_cors():
    """With a valid token, auth must pass and CORS must still apply.
    Status may be 404 (missing course), 201/200 (started), or 500 from
    a handler error — never a bare 401, and CORS headers must be present
    even on 500 (see unhandled_exception_handler in app/main.py).
    """
    soft_client = TestClient(app, raise_server_exceptions=False)
    login = soft_client.post("/auth/login", json={"username": "admin", "password": "s3cret"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    response = soft_client.post(
        "/courses/999999/generate",
        json={"generation_quality_mode": "premium"},
        headers={"Authorization": f"Bearer {token}", "Origin": ORIGIN},
    )
    assert response.status_code != 401
    assert response.headers["access-control-allow-origin"] == ORIGIN


def test_unhandled_500_still_carries_cors_headers():
    """Regression: uncaught handler errors must not look like CORS failures."""
    from app.db import get_session

    def _failing_session():
        raise RuntimeError("forced failure for cors regression")
        yield  # pragma: no cover

    app.dependency_overrides[get_session] = _failing_session
    try:
        soft_client = TestClient(app, raise_server_exceptions=False)
        login = soft_client.post("/auth/login", json={"username": "admin", "password": "s3cret"})
        assert login.status_code == 200
        token = login.json()["access_token"]
        response = soft_client.get(
            "/ai-usage/summary",
            headers={"Authorization": f"Bearer {token}", "Origin": ORIGIN},
        )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert response.json()["detail"] == "Internal server error"


def test_ai_usage_summary_options_preflight_returns_cors_headers():
    response = client.options(
        "/ai-usage/summary",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,accept",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN


def test_ai_usage_summary_unauthenticated_returns_401_with_cors():
    response = client.get("/ai-usage/summary", headers={"Origin": ORIGIN})
    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert response.json()["detail"] == "Not authenticated"


def test_ai_usage_summary_authenticated_works():
    response = client.get(
        "/ai-usage/summary",
        headers={**_auth_header(), "Origin": ORIGIN},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN
    body = response.json()
    assert "estimated_cost_today_usd" in body
    assert "provider" in body


def test_course_ai_usage_unauthenticated_returns_401_with_cors():
    response = client.get("/courses/1/ai-usage", headers={"Origin": ORIGIN})
    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == ORIGIN


def test_build_info_lists_generation_and_ai_usage_routes_without_secrets():
    response = client.get("/build-info")
    assert response.status_code == 200
    body = response.json()
    routes = body.get("api_routes") or []
    assert "POST /courses/{course_id}/generate" in routes
    assert "GET /ai-usage/summary" in routes
    assert "GET /courses/{course_id}/ai-usage" in routes
    text = response.text.lower()
    for secret_hint in (
        "anthropic_api_key",
        "auth_secret",
        "password",
        "sk-ant",
        "database_url",
        "postgresql://",
    ):
        assert secret_hint not in text
