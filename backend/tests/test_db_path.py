"""Tests for SQLITE_DB_PATH -> DATABASE_URL resolution (see app/config.py).

Render's filesystem is ephemeral except its persistent disk mount, so the
SQLite file must live at a fixed absolute path on that disk in production.
These are pure unit tests against the config resolution logic - they never
touch a real filesystem path like /opt/render/..., only build the URL
string and construct `Settings` instances directly (like test_ai_factory.py
does), so they're safe to run anywhere, including this Windows dev machine.
"""

import pytest

from app.config import Settings, build_sqlite_url


def test_build_sqlite_url_produces_four_slashes_for_absolute_path():
    url = build_sqlite_url("/opt/render/project/src/backend/storage/rukn_course_studio.db")

    assert url == "sqlite:////opt/render/project/src/backend/storage/rukn_course_studio.db"


def test_build_sqlite_url_rejects_relative_path():
    with pytest.raises(ValueError, match="absolute path"):
        build_sqlite_url("relative/path.db")


def test_settings_uses_sqlite_db_path_when_set():
    settings = Settings(sqlite_db_path="/opt/render/project/src/backend/storage/rukn_course_studio.db")

    assert settings.database_url == (
        "sqlite:////opt/render/project/src/backend/storage/rukn_course_studio.db"
    )


def test_settings_local_default_unchanged_when_sqlite_db_path_unset():
    default_settings = Settings()
    explicit_none_settings = Settings(sqlite_db_path=None)

    assert explicit_none_settings.database_url == default_settings.database_url
    assert "rukn_course_studio.db" in default_settings.database_url
    # No accidental dependency on SQLITE_DB_PATH machinery for the default.
    assert default_settings.sqlite_db_path is None
