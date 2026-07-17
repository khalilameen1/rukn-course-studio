"""Single-admin-user credential check.

No user table, no registration, no roles - by design (this is an internal
single-user MVP). Credentials come only from ADMIN_USERNAME/ADMIN_PASSWORD
in the environment (see app/config.py).
"""

from __future__ import annotations

import hmac

from app.config import Settings
from app.config import settings as default_settings


class AuthConfigError(RuntimeError):
    """Raised when AUTH_ENABLED is true but ADMIN_USERNAME/ADMIN_PASSWORD/
    AUTH_SECRET_KEY are not set - a server misconfiguration, not a login
    failure, so callers should surface this as a 503, not a 401."""


def verify_credentials(
    username: str, password: str, config: Settings = default_settings
) -> bool:
    """Timing-safe comparison against the configured admin credentials."""
    if not config.admin_username or not config.admin_password:
        raise AuthConfigError(
            "ADMIN_USERNAME and ADMIN_PASSWORD must be set in the environment "
            "to enable login."
        )

    try:
        username_ok = hmac.compare_digest(username, config.admin_username)
        password_ok = hmac.compare_digest(password, config.admin_password)
    except (TypeError, ValueError):
        # Non-str inputs or rare length edge cases must never 500 the login path.
        return False
    return username_ok and password_ok
