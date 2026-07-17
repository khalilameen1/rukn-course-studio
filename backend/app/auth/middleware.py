"""Global request gate for the single-admin-user MVP.

Protects every route except the ones explicitly listed in `PUBLIC_ROUTES`.
Runs as ASGI middleware (registered in app/main.py) rather than a
per-router `Depends(...)`, so no route can accidentally be left
unprotected as new routers get added.
"""

from __future__ import annotations

import re

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.auth.tokens import InvalidTokenError, verify_token
from app.config import settings

# (method, path) pairs that never require a token.
PUBLIC_ROUTES: set[tuple[str, str]] = {
    ("GET", "/health"),
    ("GET", "/build-info"),
    ("POST", "/auth/login"),
    # Minimal public probe only — full diagnostics require auth
    # (GET /auth/diagnostics/full).
    ("GET", "/auth/diagnostics"),
}

_REPEATED_SLASHES = re.compile(r"/+")


def _normalize_path(path: str) -> str:
    """Collapse repeated/trailing slashes so a misconfigured frontend base
    URL with a trailing slash (producing e.g. "//auth/login") still matches
    PUBLIC_ROUTES instead of being wrongly treated as protected."""
    normalized = _REPEATED_SLASHES.sub("/", path)
    if len(normalized) > 1:
        normalized = normalized.rstrip("/")
    return normalized


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Normalize repeated/trailing slashes on the ASGI scope itself (not
        # just for the PUBLIC_ROUTES check below) so a misconfigured
        # frontend base URL with a trailing slash - producing requests like
        # "//auth/login" - still reaches the right route instead of 404ing
        # once past this middleware.
        normalized_path = _normalize_path(request.url.path)
        if normalized_path != request.url.path:
            request.scope["path"] = normalized_path

        # Fail closed outside local development: never serve AI/cost routes
        # without auth when ENVIRONMENT looks like production.
        env = (settings.environment or "").strip().lower()
        productionish = env not in {"development", "dev", "test", "local", ""}
        if not settings.auth_enabled:
            if productionish:
                return JSONResponse(
                    {
                        "detail": (
                            "AUTH_ENABLED is false but ENVIRONMENT is "
                            f"{settings.environment!r}. Refusing unauthenticated "
                            "access — set AUTH_ENABLED=true for production."
                        )
                    },
                    status_code=503,
                )
            return await call_next(request)

        # CORS preflight requests carry no Authorization header and must
        # reach CORSMiddleware (registered outside this one) unimpeded.
        if request.method == "OPTIONS":
            return await call_next(request)

        if (request.method, normalized_path) in PUBLIC_ROUTES:
            return await call_next(request)

        if not settings.auth_secret_key:
            return JSONResponse(
                {"detail": "AUTH_SECRET_KEY is not configured on the server."},
                status_code=503,
            )

        auth_header = request.headers.get("authorization", "")
        scheme, _, token = auth_header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)

        try:
            payload = verify_token(token, settings.auth_secret_key)
        except InvalidTokenError:
            # Never echo token-parser details to clients (AI-typical info leak).
            return JSONResponse(
                {"detail": "Invalid or expired token"},
                status_code=401,
            )

        jti = payload.get("jti")
        if jti:
            try:
                from sqlmodel import Session

                from app.auth.token_denylist import is_jti_revoked
                from app.db import engine

                with Session(engine) as session:
                    if is_jti_revoked(session, jti):
                        return JSONResponse(
                            {"detail": "Invalid or expired token"},
                            status_code=401,
                        )
            except Exception:
                # Denylist check must not take the API down if the table is
                # mid-migration; fail open only for the denylist lookup.
                pass

        from app.auth.scopes import has_scope, required_scope_for_path

        scopes = payload.get("scopes") or []
        request.state.username = payload["sub"]
        request.state.scopes = scopes
        request.state.token_jti = jti
        request.state.token_exp = payload.get("exp")

        needed = required_scope_for_path(request.method, normalized_path)
        if needed and not has_scope(scopes, needed):
            return JSONResponse(
                {
                    "detail": (
                        f"Missing scope {needed!r} for this route. "
                        "Sign in with an account that has Admin Knowledge access."
                        if needed.endswith("admin_knowledge:*")
                        else f"Missing scope {needed!r} for this route."
                    )
                },
                status_code=403,
            )

        return await call_next(request)
