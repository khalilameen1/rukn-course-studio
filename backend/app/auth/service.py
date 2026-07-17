"""Credential check for admin + optional course-operator.

No user table — credentials come from the environment (see app/config.py).
Admin gets full scopes; operator (if configured) gets courses:* only.

Passwords may be plaintext (legacy) or `pbkdf2_sha256$…` hashes produced by
`app.auth.password_hash.hash_password`. Prefer hashed values in production.
"""

from __future__ import annotations

import hmac

from app.auth.password_hash import verify_password
from app.auth.scopes import ADMIN_SCOPES, OPERATOR_SCOPES
from app.config import Settings
from app.config import settings as default_settings


class AuthConfigError(RuntimeError):
    """Raised when AUTH_ENABLED is true but ADMIN_USERNAME/ADMIN_PASSWORD/
    AUTH_SECRET_KEY are not set - a server misconfiguration, not a login
    failure, so callers should surface this as a 503, not a 401."""


def verify_credentials(
    username: str, password: str, config: Settings = default_settings
) -> bool:
    """Timing-safe comparison against admin or operator credentials."""
    return resolve_login(username, password, config) is not None


def resolve_login(
    username: str, password: str, config: Settings = default_settings
) -> list[str] | None:
    """Return scopes on success, or None when credentials do not match.

    Raises AuthConfigError when admin credentials are not configured at all.
    """
    if not config.admin_username or not config.admin_password:
        raise AuthConfigError(
            "ADMIN_USERNAME and ADMIN_PASSWORD must be set in the environment "
            "to enable login."
        )

    try:
        if hmac.compare_digest(username, config.admin_username) and verify_password(
            password, config.admin_password
        ):
            return list(ADMIN_SCOPES)

        op_user = (config.operator_username or "").strip()
        op_pass = config.operator_password or ""
        if (
            op_user
            and op_pass
            and hmac.compare_digest(username, op_user)
            and verify_password(password, op_pass)
        ):
            return list(OPERATOR_SCOPES)
    except (TypeError, ValueError):
        return None
    return None
