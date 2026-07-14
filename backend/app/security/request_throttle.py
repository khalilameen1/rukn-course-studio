"""Simple in-process throttles for an internal single-admin tool.

No Redis — intentionally process-local. Protects against double-click cost
burn and login hammering on one instance.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict

_lock = threading.Lock()
_last_generate_at: dict[int, float] = {}
_login_attempts: dict[str, list[float]] = defaultdict(list)

# Reject starting a *new* generation for the same course this soon after
# another start attempt (active-job reuse still returns 200 immediately).
DEFAULT_GENERATE_MIN_INTERVAL_SECONDS = 3.0

# Login: max attempts per key (IP) inside the window.
DEFAULT_LOGIN_MAX_ATTEMPTS = 20
DEFAULT_LOGIN_WINDOW_SECONDS = 300.0


def allow_generate_start(
    course_id: int, *, min_interval_seconds: float = DEFAULT_GENERATE_MIN_INTERVAL_SECONDS
) -> bool:
    """True if a new generation start is allowed for this course_id."""
    now = time.monotonic()
    with _lock:
        last = _last_generate_at.get(course_id)
        if last is not None and (now - last) < min_interval_seconds:
            return False
        _last_generate_at[course_id] = now
        return True


def record_generate_start(course_id: int) -> None:
    """Mark a successful new-job start (or intentional revisit)."""
    with _lock:
        _last_generate_at[course_id] = time.monotonic()


def allow_login_attempt(
    key: str,
    *,
    max_attempts: int = DEFAULT_LOGIN_MAX_ATTEMPTS,
    window_seconds: float = DEFAULT_LOGIN_WINDOW_SECONDS,
) -> bool:
    """True if this client key may attempt another login."""
    now = time.monotonic()
    with _lock:
        stamps = [t for t in _login_attempts[key] if (now - t) <= window_seconds]
        _login_attempts[key] = stamps
        if len(stamps) >= max_attempts:
            return False
        stamps.append(now)
        _login_attempts[key] = stamps
        return True


def reset_for_tests() -> None:
    with _lock:
        _last_generate_at.clear()
        _login_attempts.clear()
