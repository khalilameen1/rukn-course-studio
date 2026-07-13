from collections.abc import Generator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

if settings.sqlite_db_path:
    # Render's disk is a fresh mount - the directory containing the DB file
    # (e.g. .../backend/storage/) doesn't exist until created. Must happen
    # before create_engine() below, which SQLite otherwise fails against a
    # missing parent directory.
    Path(settings.sqlite_db_path).parent.mkdir(parents=True, exist_ok=True)

# check_same_thread=False is required for SQLite when accessed from FastAPI's
# threaded request handling; SQLite itself still serializes writes.
connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(settings.database_url, echo=False, connect_args=connect_args)


def init_db() -> None:
    """Create tables for all registered SQLModel models.

    MVP uses plain `create_all` instead of a migration tool (e.g. Alembic):
    fine while the schema only ever grows and there's no production data to
    migrate. Revisit once real migrations are needed (see docs/BUILD_PLAN.md).
    """
    from app import models  # noqa: F401  (import registers tables on metadata)

    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
