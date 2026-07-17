"""Safe, secret-free runtime diagnostics for the login/CORS/storage setup,
plus AI Provider Health (§7).

Exists so a misconfigured deployment (missing FRONTEND_ORIGIN, unexpected
DATABASE_URL backend, unwritable storage dir, etc.) can be diagnosed by
hitting one public endpoint (`GET /auth/diagnostics`, see
app/routers/auth.py) instead of guessing from a generic "Network/CORS/API
URL error" in the browser. Deliberately returns only booleans/labels -
NEVER a credential, connection string, or API key value.

Provider Health (`provider_reachable`, `last_successful_request_at`,
`last_error_category`, `last_error_message`) is intentionally cheap and
passive: `provider_reachable` is derived from whether a recent successful
`AIUsageEvent` exists (see app/models/ai_usage_event.py), never from firing
a live network probe at Anthropic on every diagnostics request (which
would be slow, and would itself cost real API credits for `anthropic`).
"unknown" is an honest, acceptable value when there's simply no usage
history yet - never faked as "ok".
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.ai.factory import missing_anthropic_config
from app.config import Settings
from app.config import settings as default_settings
from app.models.ai_usage_event import AIUsageEvent
from app.models.generation_job import GenerationJob

# A successful call older than this no longer counts as evidence the
# provider is currently reachable - conservative enough to survive normal
# gaps between generation runs, short enough that a long-dead
# configuration eventually reads "unknown" again instead of "ok" forever.
_RECENT_SUCCESS_WINDOW = timedelta(days=7)


def _database_backend(database_url: str) -> str:
    return "sqlite" if database_url.startswith("sqlite") else "postgres"


def _ai_provider_ready(config: Settings) -> bool:
    """True for `fake` (always available) or for `anthropic` once
    `missing_anthropic_config` (app/ai/factory.py - the same check
    `get_ai_provider` uses) reports nothing missing. Never returns the key
    itself - only this boolean, same principle as `admin_password_configured`
    below."""
    provider_name = (config.ai_provider or "fake").strip().lower()
    if provider_name == "fake":
        return True
    return provider_name == "anthropic" and not missing_anthropic_config(config)


def _provider_health(session: Session | None, config: Settings) -> dict:
    """Never queries the DB (and returns every field as `"unknown"`/`None`)
    if `session` is `None` - keeps `build_diagnostics` usable without a DB
    session for callers/tests that don't need this part."""
    unknown = {
        "provider_reachable": "unknown",
        "last_successful_request_at": None,
        "last_error_category": None,
        "last_error_message": None,
    }
    if session is None:
        return unknown

    # A diagnostics endpoint must never 500 because of a DB schema gap -
    # that is exactly the failure it exists to help diagnose.
    from sqlalchemy.exc import SQLAlchemyError

    try:
        latest_success = session.exec(
            select(AIUsageEvent)
            .where(AIUsageEvent.status == "ok")
            .order_by(AIUsageEvent.created_at.desc())
        ).first()
    except SQLAlchemyError:
        return unknown

    if latest_success is None:
        provider_reachable = "unknown"
    else:
        now = datetime.now(timezone.utc)
        created_at = latest_success.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        provider_reachable = "ok" if (now - created_at) <= _RECENT_SUCCESS_WINDOW else "unknown"

    try:
        latest_error_job = session.exec(
            select(GenerationJob)
            .where(GenerationJob.error_category.is_not(None))
            .order_by(GenerationJob.updated_at.desc())
        ).first()
    except SQLAlchemyError:
        latest_error_job = None

    return {
        "provider_reachable": provider_reachable,
        "last_successful_request_at": latest_success.created_at if latest_success else None,
        "last_error_category": latest_error_job.error_category if latest_error_job else None,
        # Already sanitized by app/generation/errors.py - never the raw
        # exception text, same guarantee as GenerationJobRead.error_message.
        "last_error_message": latest_error_job.error_message if latest_error_job else None,
    }


def build_public_diagnostics(config: Settings = default_settings) -> dict:
    """Minimal unauthenticated probe — no CORS list, origins, or error text."""
    return {
        "ok": True,
        "auth_enabled": config.auth_enabled,
        "auth_secret_key_configured": bool(config.auth_secret_key),
        "database_backend": _database_backend(config.database_url),
        "ai_provider_ready": _ai_provider_ready(config),
    }


def build_diagnostics(config: Settings = default_settings, session: Session | None = None) -> dict:
    """Build the full diagnostics payload (authenticated callers only)."""
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
        "ai_provider": config.ai_provider,
        "ai_provider_ready": _ai_provider_ready(config),
        "ai_model_name": config.ai_model_name if (config.ai_provider or "").strip().lower() == "anthropic" else "fake",
        **_provider_health(session, config),
    }
