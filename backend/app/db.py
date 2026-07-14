from collections.abc import Generator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

if settings.sqlite_db_path and settings.database_url.startswith("sqlite"):
    # Only relevant when SQLITE_DB_PATH is actually the active backend (i.e.
    # DATABASE_URL is unset - see app/config.py `_resolve_database_url`).
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

    After create_all, ensure helpers ADD any new columns on existing tables
    (create_all never ALTERs).
    """
    from app import models  # noqa: F401  (import registers tables on metadata)

    SQLModel.metadata.create_all(engine)
    _ensure_generation_job_columns()
    _ensure_course_columns()
    _ensure_source_analysis_columns()
    _ensure_course_source_columns()


def _ensure_course_source_columns() -> None:
    """Add CourseSource cost-hygiene columns on existing DBs."""
    from sqlalchemy import inspect, text

    additions: dict[str, str] = {
        "include_in_generation": "BOOLEAN DEFAULT 1",
        "title": "TEXT",
        "source_hash": "TEXT",
    }
    try:
        inspector = inspect(engine)
        if "course_sources" not in inspector.get_table_names():
            return
        existing = {col["name"] for col in inspector.get_columns("course_sources")}
    except Exception:
        return

    with engine.begin() as conn:
        for name, sql_type in additions.items():
            if name in existing:
                continue
            conn.execute(
                text(f"ALTER TABLE course_sources ADD COLUMN {name} {sql_type}")
            )


def _ensure_source_analysis_columns() -> None:
    """Add SourceAnalysis columns (persistent Source Memory) on existing DBs."""
    from sqlalchemy import inspect, text

    additions: dict[str, str] = {
        "source_memory_json": "TEXT",
        "source_hash": "TEXT",
        "extraction_version": "TEXT",
        "extracted_at": "TIMESTAMP",
        "tokens_used": "INTEGER DEFAULT 0",
    }
    try:
        inspector = inspect(engine)
        if "source_analyses" not in inspector.get_table_names():
            return
        existing = {col["name"] for col in inspector.get_columns("source_analyses")}
    except Exception:
        return

    with engine.begin() as conn:
        for name, sql_type in additions.items():
            if name in existing:
                continue
            conn.execute(
                text(f"ALTER TABLE source_analyses ADD COLUMN {name} {sql_type}")
            )


def _ensure_generation_job_columns() -> None:
    """Add newly introduced GenerationJob columns on already-created tables."""
    from sqlalchemy import inspect, text

    additions: dict[str, str] = {
        "current_module_index": "INTEGER",
        "current_lesson_index": "INTEGER",
        "last_progress_message": "TEXT",
        "last_saved_at": "TIMESTAMP",
        "estimated_usage_summary": "TEXT",
        "estimated_duration_summary": "TEXT",
        "internal_risk_count": "INTEGER DEFAULT 0",
        "total_lessons_count": "INTEGER DEFAULT 0",
        "needs_review_count": "INTEGER DEFAULT 0",
        "generation_quality_mode": "TEXT DEFAULT 'premium'",
        "web_research_mode": "TEXT DEFAULT 'autonomous_gap_fill'",
        "source_memory_json": "TEXT",
        "web_source_memory_json": "TEXT",
        "evidence_ledger_json": "TEXT",
        "source_tokens_used": "INTEGER DEFAULT 0",
        "web_searches_count": "INTEGER DEFAULT 0",
        "reused_source_memory_count": "INTEGER DEFAULT 0",
        "repeated_source_extraction_warnings": "INTEGER DEFAULT 0",
        "research_memory_reuse_count": "INTEGER DEFAULT 0",
        "waste_warnings_json": "TEXT",
        "usage_by_stage_json": "TEXT",
    }
    try:
        inspector = inspect(engine)
        if "generation_jobs" not in inspector.get_table_names():
            return
        existing = {col["name"] for col in inspector.get_columns("generation_jobs")}
    except Exception:
        return

    with engine.begin() as conn:
        for name, sql_type in additions.items():
            if name in existing:
                continue
            conn.execute(text(f"ALTER TABLE generation_jobs ADD COLUMN {name} {sql_type}"))


def _ensure_course_columns() -> None:
    """Add newly introduced Course columns on already-created tables."""
    from sqlalchemy import inspect, text

    additions: dict[str, str] = {
        "generation_quality_mode": "TEXT DEFAULT 'premium'",
        "web_research_mode": "TEXT DEFAULT 'autonomous_gap_fill'",
        "target_market": "TEXT DEFAULT 'egypt'",
        "web_source_memory_json": "TEXT",
        "course_domain": "TEXT",
    }
    try:
        inspector = inspect(engine)
        if "courses" not in inspector.get_table_names():
            return
        existing = {col["name"] for col in inspector.get_columns("courses")}
    except Exception:
        return

    with engine.begin() as conn:
        for name, sql_type in additions.items():
            if name in existing:
                continue
            conn.execute(text(f"ALTER TABLE courses ADD COLUMN {name} {sql_type}"))


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
