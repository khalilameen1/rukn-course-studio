"""DB-backed login throttle (survives multi-worker; no Redis).

Falls back to process-local counts only if the DB write fails — still better
than nothing for a single-admin tool.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlmodel import Field, Session, SQLModel, select

from app.security.request_throttle import (
    DEFAULT_LOGIN_MAX_ATTEMPTS,
    DEFAULT_LOGIN_WINDOW_SECONDS,
    allow_login_attempt as _memory_allow_login,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LoginThrottleEvent(SQLModel, table=True):
    __tablename__ = "login_throttle_events"

    id: int | None = Field(default=None, primary_key=True)
    client_key: str = Field(index=True, max_length=128)
    attempted_at: datetime = Field(default_factory=_utcnow, index=True)


def allow_login_attempt_db(
    session: Session,
    key: str,
    *,
    max_attempts: int = DEFAULT_LOGIN_MAX_ATTEMPTS,
    window_seconds: float = DEFAULT_LOGIN_WINDOW_SECONDS,
) -> bool:
    """True if this client may attempt another login. Persists the attempt."""
    try:
        cutoff = _utcnow() - timedelta(seconds=window_seconds)
        recent = list(
            session.exec(
                select(LoginThrottleEvent).where(
                    LoginThrottleEvent.client_key == key,
                    LoginThrottleEvent.attempted_at >= cutoff,
                )
            ).all()
        )
        if len(recent) >= max_attempts:
            return False
        session.add(LoginThrottleEvent(client_key=key[:128]))
        session.commit()
        # Opportunistic cleanup of old rows for this key
        stale = list(
            session.exec(
                select(LoginThrottleEvent).where(
                    LoginThrottleEvent.client_key == key,
                    LoginThrottleEvent.attempted_at < cutoff,
                )
            ).all()
        )
        for row in stale[:50]:
            session.delete(row)
        if stale:
            session.commit()
        return True
    except Exception:
        return _memory_allow_login(
            key, max_attempts=max_attempts, window_seconds=window_seconds
        )
