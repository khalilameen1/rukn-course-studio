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
    ("POST", "/auth/login"),
    # Must stay public: it's the tool used to diagnose why login itself is
    # broken (see app/auth/diagnostics.py) - it would be useless if it also
    # required a token to reach.
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

        if not settings.auth_enabled:
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
        except InvalidTokenError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=401)

        request.state.username = payload["sub"]
        return await call_next(request)
