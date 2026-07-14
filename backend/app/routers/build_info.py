"""Safe deployment diagnostics — no secrets.

Exposes enough for Render/UI to confirm which backend build is live.
Never returns URLs with credentials, API keys, or env dumps.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from functools import lru_cache

from fastapi import APIRouter, Request
from starlette.routing import Route

from app.config import settings
from app.version import get_app_commit

router = APIRouter(tags=["health"])

# Optional bake time from CI / Render (ISO or free text). Falls back to process start.
_PROCESS_STARTED_AT = datetime.now(timezone.utc).isoformat()


@lru_cache(maxsize=1)
def _database_type() -> str:
    url = (settings.database_url or "").strip().lower()
    if url.startswith("postgres"):
        return "postgresql"
    if url.startswith("sqlite"):
        return "sqlite"
    if not url:
        return "unknown"
    scheme = url.split(":", 1)[0]
    return scheme or "unknown"


@lru_cache(maxsize=1)
def _build_time() -> str:
    return (
        (os.environ.get("BUILD_TIME") or "").strip()
        or (os.environ.get("RENDER_GIT_COMMIT") and _PROCESS_STARTED_AT)
        or _PROCESS_STARTED_AT
    )


def build_info_payload() -> dict:
    """Pure helper — used by the route and unit tests (no secrets)."""
    commit = (os.environ.get("GIT_COMMIT_SHA") or "").strip() or get_app_commit()
    return {
        "app_name": settings.app_name,
        "environment": settings.environment,
        "backend_version": "0.1.0",
        "git_commit": commit,
        "build_time": _build_time(),
        "database_type": _database_type(),
        "auth_enabled": bool(settings.auth_enabled),
        "ai_provider": (settings.ai_provider or "fake").strip().lower(),
        "frontend_origin_configured": bool((settings.frontend_origin or "").strip()),
    }


def _registered_api_routes(request: Request) -> list[str]:
    """Method + path templates only — no handler code, secrets, or params."""
    out: list[str] = []
    for route in request.app.routes:
        if not isinstance(route, Route):
            continue
        methods = sorted((route.methods or set()) - {"HEAD"})
        for method in methods:
            out.append(f"{method} {route.path}")
    return sorted(out)


@router.get("/build-info")
def build_info(request: Request) -> dict:
    """Liveness + deploy identity. Public and secret-free."""
    payload = build_info_payload()
    # Safe diagnostic: confirms generate / ai-usage routes are registered
    # on the live deploy (method + path templates only).
    payload["api_routes"] = _registered_api_routes(request)
    return payload
