"""Tests for DATABASE_URL / SQLITE_DB_PATH resolution and related config
(see app/config.py `_resolve_database_url`, `_resolve_storage_dirs`).

Render's filesystem is ephemeral except its persistent disk mount, and
production talks to Postgres via DATABASE_URL, so this file locks down the
exact priority: DATABASE_URL > SQLITE_DB_PATH > local SQLite default.
These are pure unit tests against the config resolution logic - they never
touch a real filesystem path like /opt/render/... or a real Postgres
server, only build URL strings and construct `Settings` instances directly
(like test_ai_factory.py does), so they're safe to run anywhere, including
this Windows dev machine.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, build_sqlite_url, normalize_database_url


def test_build_sqlite_url_produces_four_slashes_for_absolute_path():
    url = build_sqlite_url("/opt/render/project/src/backend/storage/rukn_course_studio.db")

    assert url == "sqlite:////opt/render/project/src/backend/storage/rukn_course_studio.db"


def test_build_sqlite_url_rejects_relative_path():
    with pytest.raises(ValueError, match="absolute path"):
        build_sqlite_url("relative/path.db")


def test_settings_uses_sqlite_db_path_when_database_url_unset():
    settings = Settings(sqlite_db_path="/opt/render/project/src/backend/storage/rukn_course_studio.db")

    assert settings.database_url == (
        "sqlite:////opt/render/project/src/backend/storage/rukn_course_studio.db"
    )


def test_settings_local_default_unchanged_when_nothing_set():
    default_settings = Settings()
    explicit_none_settings = Settings(database_url=None, sqlite_db_path=None)

    assert explicit_none_settings.database_url == default_settings.database_url
    assert "rukn_course_studio.db" in default_settings.database_url
    # No accidental dependency on SQLITE_DB_PATH machinery for the default.
    assert default_settings.sqlite_db_path is None


def test_database_url_takes_priority_over_sqlite_db_path():
    """If both happen to be set (e.g. leftover env var from before this app
    had Postgres support), DATABASE_URL must win - SQLITE_DB_PATH is a
    SQLite-only fallback, not a general override."""
    settings = Settings(
        database_url="postgresql://user:secret@db.example.com/rukn",
        sqlite_db_path="/opt/render/project/src/backend/storage/rukn_course_studio.db",
    )

    assert settings.database_url == "postgresql://user:secret@db.example.com/rukn"


def test_database_url_used_as_is_when_sqlite_db_path_unset():
    settings = Settings(database_url="postgresql://user:secret@db.example.com/rukn")

    assert settings.database_url == "postgresql://user:secret@db.example.com/rukn"


def test_normalize_database_url_rewrites_legacy_postgres_scheme():
    assert (
        normalize_database_url("postgres://user:secret@db.example.com/rukn")
        == "postgresql://user:secret@db.example.com/rukn"
    )


def test_normalize_database_url_leaves_postgresql_scheme_unchanged():
    url = "postgresql://user:secret@db.example.com/rukn"

    assert normalize_database_url(url) == url


def test_normalize_database_url_leaves_sqlite_url_unchanged():
    url = "sqlite:///./rukn_course_studio.db"

    assert normalize_database_url(url) == url


def test_settings_normalizes_legacy_postgres_scheme_from_database_url():
    settings = Settings(database_url="postgres://user:secret@db.example.com/rukn")

    assert settings.database_url.startswith("postgresql://")


def test_storage_dir_env_var_repositions_all_four_storage_subdirs(tmp_path):
    settings = Settings(storage_dir=tmp_path)

    assert settings.storage_uploads_dir == tmp_path / "uploads"
    assert settings.storage_extracted_dir == tmp_path / "extracted"
    assert settings.storage_outputs_dir == tmp_path / "outputs"
    assert settings.storage_templates_dir == tmp_path / "templates"


def test_individual_storage_dir_override_still_wins_over_storage_dir(tmp_path):
    custom_uploads = tmp_path / "custom-uploads"
    settings = Settings(storage_dir=tmp_path, storage_uploads_dir=custom_uploads)

    assert settings.storage_uploads_dir == custom_uploads
    assert settings.storage_extracted_dir == tmp_path / "extracted"


def test_frontend_origin_is_merged_into_cors_origins():
    settings = Settings(frontend_origin="https://rukn-frontend.onrender.com")

    assert "https://rukn-frontend.onrender.com" in settings.cors_origins


def test_health_endpoint_never_exposes_database_url_or_credentials(monkeypatch):
    """Regression guard: /health must never leak DATABASE_URL (or any
    credentials embedded in it), even if a real Postgres URL with a
    password is configured on the live settings singleton."""
    import app.config as config_module

    fake_secret = "postgresql://rukn_user:super-secret-password@db.example.com/rukn"  # noqa: S105
    monkeypatch.setattr(config_module.settings, "database_url", fake_secret)

    from app.main import app

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "environment": config_module.settings.environment}
    assert "super-secret-password" not in response.text
    assert "database_url" not in response.text
