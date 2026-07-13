from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

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
