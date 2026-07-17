"""Engine construction and session factory."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlmodel import Session, create_engine

from app.config import settings

# Postgres rejects INTEGER literals as BOOLEAN defaults (DatatypeMismatch).
# Always use TRUE/FALSE in raw DDL — never DEFAULT 1 / DEFAULT 0 for booleans.
BOOLEAN_NOT_NULL_DEFAULT_TRUE = "BOOLEAN NOT NULL DEFAULT TRUE"
BOOLEAN_NOT_NULL_DEFAULT_FALSE = "BOOLEAN NOT NULL DEFAULT FALSE"


def build_engine():
    if settings.sqlite_db_path and settings.database_url.startswith("sqlite"):
        Path(settings.sqlite_db_path).parent.mkdir(parents=True, exist_ok=True)
    connect_args = (
        {"check_same_thread": False}
        if settings.database_url.startswith("sqlite")
        else {}
    )
    return create_engine(settings.database_url, echo=False, connect_args=connect_args)


# Default process engine. Tests monkeypatch `app.db.engine` (package attr).
engine = build_engine()


def get_session() -> Generator[Session, None, None]:
    """Yield a session bound to the *current* `app.db.engine`.

    Resolves via the package so `monkeypatch.setattr(app.db, "engine", …)`
    works — binding `from app.db.engine import engine` would freeze the
    default engine and break the test suite.
    """
    import app.db as db_pkg

    with Session(db_pkg.engine) as session:
        yield session
