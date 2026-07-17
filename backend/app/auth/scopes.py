"""Capability scopes for the single-admin MVP (least privilege ready).

Scopes are embedded in the signed session token. The admin login gets both
plus AI usage; an optional course-operator credential gets courses-only.
"""

from __future__ import annotations

SCOPE_COURSES = "courses:*"
SCOPE_ADMIN_KNOWLEDGE = "admin_knowledge:*"
SCOPE_AI_USAGE = "ai_usage:*"

ALL_SCOPES: tuple[str, ...] = (SCOPE_COURSES, SCOPE_ADMIN_KNOWLEDGE, SCOPE_AI_USAGE)
ADMIN_SCOPES: tuple[str, ...] = ALL_SCOPES
OPERATOR_SCOPES: tuple[str, ...] = (SCOPE_COURSES,)


def normalize_scopes(scopes: list[str] | tuple[str, ...] | None) -> list[str]:
    """Fail closed: missing/empty scopes → courses only (never full admin)."""
    if not scopes:
        return [SCOPE_COURSES]
    out: list[str] = []
    for scope in scopes:
        if scope in ALL_SCOPES and scope not in out:
            out.append(scope)
    return out or [SCOPE_COURSES]


def has_scope(scopes: list[str] | None, required: str) -> bool:
    return required in normalize_scopes(scopes)


def required_scope_for_path(method: str, path: str) -> str | None:
    """Return the scope required for this path, or None if public/any-auth.

    Public routes are handled before this runs. Authenticated routes:
    - /admin/* → admin_knowledge:*
    - /ai-usage* → ai_usage:*
    - everything else protected → courses:*
    - /auth/me, /auth/logout → any authenticated user (no specific scope)
    """
    if path.startswith("/auth/me") or path.startswith("/auth/logout"):
        return None
    if path.startswith("/auth/diagnostics/full"):
        return SCOPE_COURSES
    if path.startswith("/admin"):
        return SCOPE_ADMIN_KNOWLEDGE
    if path.startswith("/ai-usage") or path.rstrip("/").endswith("/ai-usage"):
        return SCOPE_AI_USAGE
    return SCOPE_COURSES
