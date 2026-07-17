"""Course create idempotency (double-click / retry safety).

Process-local map: Idempotency-Key → course_id. Same pattern as generation
locks — good enough for single-worker V1; multi-worker needs shared store.
"""

from __future__ import annotations

import threading
import time

_LOCK = threading.Lock()
# key → (expires_at_epoch, course_id)
_CACHE: dict[str, tuple[float, int]] = {}
_TTL_SECONDS = 24 * 3600


def lookup_idempotent_course(key: str) -> int | None:
    now = time.time()
    with _LOCK:
        _prune(now)
        entry = _CACHE.get(key)
        if entry is None:
            return None
        return entry[1]


def remember_idempotent_course(key: str, course_id: int) -> None:
    with _LOCK:
        _CACHE[key] = (time.time() + _TTL_SECONDS, course_id)


def _prune(now: float) -> None:
    expired = [k for k, (exp, _) in _CACHE.items() if exp < now]
    for k in expired:
        del _CACHE[k]
