"""Tests for single-admin-user auth (see app/auth/, app/routers/auth.py).

Covers: login success/failure, protected routes with/without/invalid
tokens, and that /health stays public even when auth is enabled.
"""

import pytest
from fastapi.testclient import TestClient

from app.auth.tokens import create_token
from app.config import settings
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _configure_auth(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "admin_username", "admin")
    monkeypatch.setattr(settings, "admin_password", "s3cret")
    monkeypatch.setattr(settings, "auth_secret_key", "test-secret-key")


def test_login_succeeds_with_correct_credentials():
    response = client.post("/auth/login", json={"username": "admin", "password": "s3cret"})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_fails_with_wrong_credentials():
    response = client.post("/auth/login", json={"username": "admin", "password": "wrong"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


def test_login_fails_clearly_when_admin_credentials_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "admin_username", None)
    monkeypatch.setattr(settings, "admin_password", None)

    response = client.post("/auth/login", json={"username": "admin", "password": "s3cret"})

    assert response.status_code == 503
    assert "ADMIN_USERNAME" in response.json()["detail"]


def test_protected_endpoint_fails_without_token():
    response = client.get("/courses")

    assert response.status_code == 401


def test_protected_endpoint_fails_with_malformed_token():
    response = client.get("/courses", headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 401


def test_protected_endpoint_fails_with_expired_token():
    expired = create_token("admin", settings.auth_secret_key, expiry_days=-1)

    response = client.get("/courses", headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


def test_protected_endpoint_succeeds_with_valid_token():
    login_response = client.post("/auth/login", json={"username": "admin", "password": "s3cret"})
    token = login_response.json()["access_token"]

    response = client.get("/courses", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200


def test_me_returns_current_username_with_valid_token():
    login_response = client.post("/auth/login", json={"username": "admin", "password": "s3cret"})
    token = login_response.json()["access_token"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["username"] == "admin"


def test_health_remains_public():
    response = client.get("/health")

    assert response.status_code == 200


def test_login_is_public_even_with_double_slash_from_trailing_base_url():
    """A frontend NEXT_PUBLIC_API_BASE_URL with a trailing slash produces
    requests like "https://backend/.../auth/login" -> path "//auth/login" -
    this must still be treated as the public login route, not rejected with
    a generic 401 before credentials are even checked (see
    app/auth/middleware.py `_normalize_path`). Must use an absolute URL here:
    a bare "//auth/login" string is parsed by httpx as protocol-relative
    (a different host), not as a same-host double-slash path.
    """
    response = client.post(
        "http://testserver//auth/login", json={"username": "admin", "password": "s3cret"}
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_health_is_public_even_with_double_slash():
    response = client.get("http://testserver//health")

    assert response.status_code == 200


def test_protected_endpoint_still_requires_token_with_double_slash():
    response = client.get("http://testserver//courses")

    assert response.status_code == 401


def test_options_preflight_for_login_succeeds_from_allowed_origin():
    """A CORS preflight OPTIONS request must never be blocked by
    AuthMiddleware, and CORSMiddleware must actually be positioned to
    handle it (see app/main.py middleware registration order).

    Uses one of the default `cors_origins` (http://localhost:3000) rather
    than monkeypatching `settings.cors_origins`: CORSMiddleware is
    constructed once, the first time the shared `client` above handles any
    request, so changing the setting afterwards has no effect on the
    already-built middleware - the same reason app/ai/factory.py tests read
    settings dynamically instead of relying on constructor-time values.
    """
    response = client.options(
        "/auth/login",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_options_preflight_for_protected_route_succeeds_even_without_token():
    """Preflight for a *protected* route must also succeed - the browser
    sends OPTIONS before the real (token-carrying) request, and OPTIONS
    itself never carries the Authorization header."""
    response = client.options(
        "/courses",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_auth_rejected_response_still_carries_cors_headers():
    """Regression guard for the root cause of the reported login bug: if
    AuthMiddleware is ever the outermost layer again, a 401 it returns
    directly (without calling `call_next`) would skip CORSMiddleware
    entirely, so the browser would see a response with no CORS headers and
    surface a generic network/CORS error instead of the real 401."""
    response = client.get("/courses", headers={"Origin": "http://localhost:3000"})

    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_diagnostics_is_public_even_without_token():
    response = client.get("/auth/diagnostics")

    assert response.status_code == 200


def test_diagnostics_never_exposes_secrets():
    response = client.get("/auth/diagnostics")

    body = response.json()
    serialized = response.text

    for secret_field in ("admin_username", "admin_password", "auth_secret_key", "database_url"):
        assert secret_field not in body

    assert settings.admin_password not in serialized
    assert settings.auth_secret_key not in serialized


def test_diagnostics_reports_configured_booleans_accurately(monkeypatch):
    monkeypatch.setattr(settings, "frontend_origin", "https://rukn-frontend.onrender.com")

    response = client.get("/auth/diagnostics")

    assert response.status_code == 200
    body = response.json()
    assert body["auth_enabled"] is True
    assert body["admin_username_configured"] is True
    assert body["admin_password_configured"] is True
    assert body["auth_secret_key_configured"] is True
    assert body["frontend_origin_configured"] is True
    assert body["frontend_origin_value"] == "https://rukn-frontend.onrender.com"
    assert body["database_backend"] in ("sqlite", "postgres")


def test_diagnostics_reports_unconfigured_admin_credentials(monkeypatch):
    monkeypatch.setattr(settings, "admin_username", None)
    monkeypatch.setattr(settings, "admin_password", None)
    monkeypatch.setattr(settings, "frontend_origin", None)

    response = client.get("/auth/diagnostics")

    body = response.json()
    assert body["admin_username_configured"] is False
    assert body["admin_password_configured"] is False
    assert body["frontend_origin_configured"] is False
    assert body["frontend_origin_value"] is None


def test_diagnostics_reports_fake_provider_as_always_ready(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "fake")

    response = client.get("/auth/diagnostics")

    body = response.json()
    assert body["ai_provider"] == "fake"
    assert body["ai_provider_ready"] is True


def test_diagnostics_reports_anthropic_ready_once_configured(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "anthropic")
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test-should-never-leak-12345")
    monkeypatch.setattr(settings, "ai_model_name", "claude-example-model")

    response = client.get("/auth/diagnostics")

    body = response.json()
    assert body["ai_provider"] == "anthropic"
    assert body["ai_provider_ready"] is True
    # Never leak the key value itself - only the boolean above.
    assert "sk-ant-test-should-never-leak-12345" not in response.text
    assert "anthropic_api_key" not in body


def test_diagnostics_reports_anthropic_not_ready_when_misconfigured(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "anthropic")
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    monkeypatch.setattr(settings, "ai_model_name", "claude-example-model")

    response = client.get("/auth/diagnostics")

    body = response.json()
    assert body["ai_provider"] == "anthropic"
    assert body["ai_provider_ready"] is False


def test_diagnostics_reports_ai_model_name_only_for_anthropic(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "fake")
    monkeypatch.setattr(settings, "ai_model_name", "claude-example-model")

    response = client.get("/auth/diagnostics")

    assert response.json()["ai_model_name"] == "fake"

    monkeypatch.setattr(settings, "ai_provider", "anthropic")
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test-should-never-leak-99999")

    response = client.get("/auth/diagnostics")

    assert response.json()["ai_model_name"] == "claude-example-model"


def test_diagnostics_provider_health_defaults_to_unknown_with_no_usage_history(monkeypatch):
    """Provider Health (§7): with no `AIUsageEvent` history at all, the
    honest answer is "unknown", never a fabricated "ok" - and this must
    never make a real network call to find out."""
    monkeypatch.setattr(settings, "ai_provider", "anthropic")
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test-should-never-leak-11111")

    response = client.get("/auth/diagnostics")

    body = response.json()
    assert body["provider_reachable"] == "unknown"
    assert body["last_successful_request_at"] is None
    assert "sk-ant-test-should-never-leak-11111" not in response.text


def test_diagnostics_provider_health_reflects_a_recent_successful_usage_event(tmp_path, monkeypatch):
    import app.db as db_module
    from sqlmodel import Session, SQLModel, create_engine

    from app.crud import ai_usage_events

    engine = create_engine(f"sqlite:///{tmp_path / 'diagnostics_health_test.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db_module, "engine", engine)

    with Session(engine) as session:
        ai_usage_events.create(
            session,
            job_id=None,
            course_id=None,
            stage="write_single_reel",
            provider="anthropic",
            model="claude-example-model",
            preset="balanced",
            input_tokens=100,
            output_tokens=50,
            estimated_cost_usd=0.01,
            status="ok",
        )

    response = client.get("/auth/diagnostics")

    body = response.json()
    assert body["provider_reachable"] == "ok"
    assert body["last_successful_request_at"] is not None


def test_diagnostics_never_exposes_secrets_even_with_usage_and_error_history(tmp_path, monkeypatch):
    """Extends test_diagnostics_never_exposes_secrets above to also cover
    the new §7 provider-health fields, which are sourced from DB rows
    (AIUsageEvent/GenerationJob) rather than settings directly - a
    different-enough code path to warrant its own explicit check."""
    import app.db as db_module
    from sqlmodel import Session, SQLModel, create_engine

    from app.crud import ai_usage_events, courses, generation_jobs
    from app.models.enums import ExplanationLevel, JobStatus, StructureMode

    fake_key = "sk-ant-test-should-never-leak-22222"
    monkeypatch.setattr(settings, "anthropic_api_key", fake_key)

    engine = create_engine(f"sqlite:///{tmp_path / 'diagnostics_secret_test.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db_module, "engine", engine)

    with Session(engine) as session:
        ai_usage_events.create(
            session,
            job_id=None,
            course_id=None,
            stage="write_single_reel",
            provider="anthropic",
            model="claude-example-model",
            preset="balanced",
            status="ok",
        )
        course = courses.create(
            session,
            title="Course",
            audience="audience",
            outcome="outcome",
            structure_mode=StructureMode.CONNECTED_NO_MODULES,
            explanation_level=ExplanationLevel.FINAL_ONLY,
        )
        generation_jobs.create(
            session,
            course_id=course.id,
            status=JobStatus.FAILED,
            current_stage="failed",
            progress_percent=10,
            log_json=[],
            error_category="rate_limit",
            error_message="Rate limit reached - please try again shortly.",
        )

    response = client.get("/auth/diagnostics")

    assert response.status_code == 200
    assert fake_key not in response.text
    body = response.json()
    assert "anthropic_api_key" not in body
    assert body["last_error_category"] == "rate_limit"
