"""DB-backed map-generation busy lock (single-worker deploy still recommended).

Process-local set is checked first; a DB row covers multi-worker SQLite/Postgres
without Redis. Stale locks older than STALE_SECONDS are auto-cleared.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

from sqlmodel import Field, Session, SQLModel

_LOCK = threading.Lock()
_MAP_BUSY: set[int] = set()

STALE_SECONDS = 30 * 60  # 30 minutes


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CourseMapLock(SQLModel, table=True):
    __tablename__ = "course_map_locks"

    course_id: int = Field(primary_key=True)
    locked_at: datetime = Field(default_factory=_utcnow)
    locked_by: str | None = Field(default=None, max_length=64)


def try_begin_map(course_id: int, session: Session | None = None) -> bool:
    """Claim map generation for `course_id`. Returns False if already busy."""
    with _LOCK:
        if course_id in _MAP_BUSY:
            return False
        _MAP_BUSY.add(course_id)

    if session is None:
        return True

    try:
        existing = session.get(CourseMapLock, course_id)
        now = _utcnow()
        if existing is not None:
            locked_at = existing.locked_at
            if locked_at.tzinfo is None:
                locked_at = locked_at.replace(tzinfo=timezone.utc)
            if (now - locked_at) < timedelta(seconds=STALE_SECONDS):
                with _LOCK:
                    _MAP_BUSY.discard(course_id)
                return False
            session.delete(existing)
            session.commit()
        session.add(CourseMapLock(course_id=course_id, locked_at=now))
        session.commit()
        return True
    except Exception:
        # Unique violation / race → busy
        try:
            session.rollback()
        except Exception:
            pass
        with _LOCK:
            _MAP_BUSY.discard(course_id)
        return False


def end_map(course_id: int, session: Session | None = None) -> None:
    with _LOCK:
        _MAP_BUSY.discard(course_id)
    if session is None:
        return
    try:
        row = session.get(CourseMapLock, course_id)
        if row is not None:
            session.delete(row)
            session.commit()
    except Exception:
        try:
            session.rollback()
        except Exception:
            pass


def is_map_busy(course_id: int, session: Session | None = None) -> bool:
    with _LOCK:
        if course_id in _MAP_BUSY:
            return True
    if session is None:
        return False
    try:
        row = session.get(CourseMapLock, course_id)
        if row is None:
            return False
        locked_at = row.locked_at
        if locked_at.tzinfo is None:
            locked_at = locked_at.replace(tzinfo=timezone.utc)
        if (_utcnow() - locked_at) >= timedelta(seconds=STALE_SECONDS):
            session.delete(row)
            session.commit()
            return False
        return True
    except Exception:
        return False
