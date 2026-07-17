"""CORS / FRONTEND_ORIGIN normalization (connectivity only)."""

from __future__ import annotations

from urllib.parse import urlparse


def normalize_origin(value: str | None) -> str | None:
    """Normalize a browser Origin / FRONTEND_ORIGIN for CORS allowlists.

    Strips whitespace, trailing slashes, and accidental path segments
    (e.g. `/health`). Returns `scheme://host[:port]` only, or None if empty.
    CORS comparisons are exact — a trailing slash on FRONTEND_ORIGIN would
    fail to match the browser's Origin header and surface as a generic
    Network/CORS/API URL error in the frontend.
    """
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    raw = raw.rstrip("/")
    lower = raw.lower()
    for suffix in ("/health", "/auth/login", "/auth/diagnostics"):
        if lower.endswith(suffix):
            raw = raw[: -len(suffix)].rstrip("/")
            lower = raw.lower()
            break
    parsed = urlparse(raw)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return raw


def normalize_cors_origins(origins: list[str]) -> list[str]:
    """Dedupe while preserving order; drop empties and unsafe wildcards.

    `Access-Control-Allow-Origin: *` with `allow_credentials=True` is invalid
    and a common AI misconfig — reject bare `*` / `null` origins.
    """
    seen: set[str] = set()
    out: list[str] = []
    for item in origins:
        normalized = normalize_origin(item)
        if not normalized or normalized in seen:
            continue
        if normalized in {"*", "null"}:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out
