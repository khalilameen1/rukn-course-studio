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
_reprocess_attempts: dict[int, list[float]] = defaultdict(list)

# Reject starting a *new* generation for the same course this soon after
# another start attempt (active-job reuse still returns 200 immediately).
DEFAULT_GENERATE_MIN_INTERVAL_SECONDS = 3.0

# Login: max attempts per key (IP) inside the window.
DEFAULT_LOGIN_MAX_ATTEMPTS = 20
DEFAULT_LOGIN_WINDOW_SECONDS = 300.0

# Reprocess / unlock: limit PDF password brute-force + CPU burn.
DEFAULT_REPROCESS_MAX_ATTEMPTS = 8
DEFAULT_REPROCESS_WINDOW_SECONDS = 300.0


def can_generate_start(
    course_id: int, *, min_interval_seconds: float = DEFAULT_GENERATE_MIN_INTERVAL_SECONDS
) -> bool:
    """True if a new generation start is allowed (peek only — does not stamp)."""
    now = time.monotonic()
    with _lock:
        last = _last_generate_at.get(course_id)
        if last is not None and (now - last) < min_interval_seconds:
            return False
        return True


def allow_generate_start(
    course_id: int, *, min_interval_seconds: float = DEFAULT_GENERATE_MIN_INTERVAL_SECONDS
) -> bool:
    """Backward-compatible: peek + stamp. Prefer can_generate_start + record."""
    if not can_generate_start(course_id, min_interval_seconds=min_interval_seconds):
        return False
    record_generate_start(course_id)
    return True


def record_generate_start(course_id: int) -> None:
    """Mark a successful new-job claim (call only after claim succeeds)."""
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


def allow_reprocess_attempt(
    source_id: int,
    *,
    max_attempts: int = DEFAULT_REPROCESS_MAX_ATTEMPTS,
    window_seconds: float = DEFAULT_REPROCESS_WINDOW_SECONDS,
) -> bool:
    """True if this source may be reprocessed again (process-local)."""
    now = time.monotonic()
    with _lock:
        stamps = [
            t for t in _reprocess_attempts[source_id] if (now - t) <= window_seconds
        ]
        _reprocess_attempts[source_id] = stamps
        if len(stamps) >= max_attempts:
            return False
        stamps.append(now)
        _reprocess_attempts[source_id] = stamps
        return True


def reset_for_tests() -> None:
    with _lock:
        _last_generate_at.clear()
        _login_attempts.clear()
        _reprocess_attempts.clear()
