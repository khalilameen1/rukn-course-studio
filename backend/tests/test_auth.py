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
