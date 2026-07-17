"""Serialize Admin Knowledge activate / version switches per key."""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import text
from sqlmodel import Session

_KEY_LOCKS: dict[str, threading.Lock] = {}
_KEY_LOCKS_GUARD = threading.Lock()


def _lock_for(key: str) -> threading.Lock:
    with _KEY_LOCKS_GUARD:
        lock = _KEY_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _KEY_LOCKS[key] = lock
        return lock


def _pg_advisory_key(key: str) -> int:
    digest = hashlib.sha256(f"admin_knowledge:{key}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


@contextmanager
def admin_knowledge_key_guard(session: Session, key: str) -> Iterator[None]:
    """Hold a process lock (and PG advisory lock when available) for `key`."""
    lock = _lock_for(key)
    with lock:
        dialect = session.get_bind().dialect.name
        if dialect == "postgresql":
            session.execute(
                text("SELECT pg_advisory_xact_lock(:k)"),
                {"k": _pg_advisory_key(key)},
            )
        yield
