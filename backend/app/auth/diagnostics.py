"""Safe, secret-free runtime diagnostics for the login/CORS/storage setup.

Exists so a misconfigured deployment (missing FRONTEND_ORIGIN, unexpected
DATABASE_URL backend, unwritable storage dir, etc.) can be diagnosed by
hitting one public endpoint (`GET /auth/diagnostics`, see
app/routers/auth.py) instead of guessing from a generic "Network/CORS/API
URL error" in the browser. Deliberately returns only booleans/labels -
NEVER a credential, connection string, or API key value.
"""

from __future__ import annotations

import os

from app.config import Settings
from app.config import settings as default_settings


def _database_backend(database_url: str) -> str:
    return "sqlite" if database_url.startswith("sqlite") else "postgres"


def build_diagnostics(config: Settings = default_settings) -> dict:
    """Build the diagnostics payload. Every value here must be safe to
    return to an unauthenticated caller - see module docstring."""
    storage_dir = config.storage_dir
    try:
        storage_dir_exists = storage_dir.exists()
    except OSError:
        storage_dir_exists = False

    storage_dir_writable = storage_dir_exists and os.access(storage_dir, os.W_OK)

    return {
        "auth_enabled": config.auth_enabled,
        "admin_username_configured": bool(config.admin_username),
        "admin_password_configured": bool(config.admin_password),
        "auth_secret_key_configured": bool(config.auth_secret_key),
        "frontend_origin_configured": bool(config.frontend_origin),
        "frontend_origin_value": config.frontend_origin,
        "cors_origins": config.cors_origins,
        "database_backend": _database_backend(config.database_url),
        "storage_dir_configured": bool(os.environ.get("STORAGE_DIR")),
        "storage_dir_exists": storage_dir_exists,
        "storage_dir_writable": storage_dir_writable,
    }
