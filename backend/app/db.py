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

# Postgres rejects INTEGER literals as BOOLEAN defaults (DatatypeMismatch).
# Always use TRUE/FALSE in raw DDL — never DEFAULT 1 / DEFAULT 0 for booleans.
# SQLite accepts TRUE/FALSE as aliases for 1/0, so this form is dual-safe.
BOOLEAN_NOT_NULL_DEFAULT_TRUE = "BOOLEAN NOT NULL DEFAULT TRUE"
BOOLEAN_NOT_NULL_DEFAULT_FALSE = "BOOLEAN NOT NULL DEFAULT FALSE"


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
    _ensure_ai_usage_events_table()


def _is_postgres() -> bool:
    return getattr(engine.dialect, "name", "") == "postgresql"


def _json_safe_type(name: str, sql_type: str) -> str:
    """SQLModel JSON columns must be real JSON on Postgres so the driver
    deserializes them to dicts/lists; TEXT there would silently hand the ORM
    raw strings. SQLite stores JSON as TEXT anyway, so TEXT stays correct."""
    if name.endswith("_json") and _is_postgres():
        return "JSON"
    return sql_type


def _harden_boolean_not_null_true(conn, table: str, column: str) -> None:
    """Fix default/nullability on an existing boolean column (Postgres-focused).

    SQLite: fill NULLs only (ALTER COLUMN SET DEFAULT/NOT NULL is limited).
    """
    from sqlalchemy import text

    dialect = getattr(getattr(conn, "dialect", None), "name", None) or (
        engine.dialect.name if hasattr(engine, "dialect") else ""
    )
    if dialect == "postgresql":
        conn.execute(
            text(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT TRUE")
        )
        conn.execute(
            text(f"UPDATE {table} SET {column} = TRUE WHERE {column} IS NULL")
        )
        conn.execute(
            text(f"ALTER TABLE {table} ALTER COLUMN {column} SET NOT NULL")
        )
    else:
        # SQLite stores booleans as 0/1; TRUE works as alias.
        conn.execute(
            text(f"UPDATE {table} SET {column} = TRUE WHERE {column} IS NULL")
        )


def _ensure_course_source_columns() -> None:
    """Add CourseSource cost-hygiene columns on existing DBs.

    Critical: `include_in_generation` must use BOOLEAN … DEFAULT TRUE, never
    DEFAULT 1 (Postgres DatatypeMismatch on Render).
    """
    from sqlalchemy import inspect, text

    other_additions: dict[str, str] = {
        "title": "TEXT",
        "source_hash": "TEXT",
    }
    try:
        inspector = inspect(engine)
        if "course_sources" not in inspector.get_table_names():
            return
        existing = {col["name"]: col for col in inspector.get_columns("course_sources")}
    except Exception:
        return

    with engine.begin() as conn:
        if "include_in_generation" not in existing:
            if _is_postgres():
                conn.execute(
                    text(
                        "ALTER TABLE course_sources "
                        "ADD COLUMN IF NOT EXISTS include_in_generation "
                        f"{BOOLEAN_NOT_NULL_DEFAULT_TRUE}"
                    )
                )
            else:
                conn.execute(
                    text(
                        "ALTER TABLE course_sources "
                        "ADD COLUMN include_in_generation "
                        f"{BOOLEAN_NOT_NULL_DEFAULT_TRUE}"
                    )
                )
        else:
            # Column already present (possibly nullable / wrong default from an
            # older SQLite-era patch). Harden without failing if already correct.
            try:
                _harden_boolean_not_null_true(
                    conn, "course_sources", "include_in_generation"
                )
            except Exception:
                # Best-effort on exotic SQLite builds / locked schemas.
                pass

        for name, sql_type in other_additions.items():
            if name in existing:
                continue
            conn.execute(text(f"ALTER TABLE course_sources ADD COLUMN {name} {sql_type}"))


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
    """Add newly introduced GenerationJob columns on already-created tables.

    Must cover EVERY model column that postdates the first production deploy:
    a single missing column makes every ORM SELECT on generation_jobs fail on
    Postgres (UndefinedColumn), which cascades into 500s on any endpoint that
    touches jobs (diagnostics, AI usage, generation status).
    """
    from sqlalchemy import inspect, text

    additions: dict[str, str] = {
        "last_completed_step": "TEXT",
        "completed_modules_count": "INTEGER DEFAULT 0",
        "completed_reels_count": "INTEGER DEFAULT 0",
        "error_category": "TEXT",
        "partial_docx_path": "TEXT",
        "course_map_json": "TEXT",
        "completed_reels_json": "TEXT",
        "run_snapshot_json": "TEXT",
        "output_score_json": "TEXT",
        "budget_warning": "TEXT",
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
            conn.execute(
                text(
                    "ALTER TABLE generation_jobs ADD COLUMN "
                    f"{name} {_json_safe_type(name, sql_type)}"
                )
            )


def _ensure_course_columns() -> None:
    """Add newly introduced Course columns on already-created tables."""
    from sqlalchemy import inspect, text

    additions: dict[str, str] = {
        "special_notes": "TEXT",
        "course_type": "TEXT DEFAULT 'practical_skill'",
        "manual_map_text": "TEXT",
        "generation_preset": "TEXT DEFAULT 'balanced'",
        "active_rules_snapshot_json": "TEXT",
        "generation_quality_mode": "TEXT DEFAULT 'premium'",
        "web_research_mode": "TEXT DEFAULT 'autonomous_gap_fill'",
        "target_market": "TEXT DEFAULT 'egypt'",
        "web_source_memory_json": "TEXT",
        "course_domain": "TEXT",
        "official_tool_memory_json": "TEXT",
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
            conn.execute(
                text(
                    f"ALTER TABLE courses ADD COLUMN {name} {_json_safe_type(name, sql_type)}"
                )
            )


def _ensure_ai_usage_events_table() -> None:
    """Create `ai_usage_events` on existing Postgres/SQLite DBs and patch columns.

    `create_all` only creates missing tables at startup; this helper is a
    belt-and-suspenders guard for Render DBs that predated AI usage telemetry,
    and adds any newer nullable columns without a full migration tool.
    """
    from sqlalchemy import inspect, text

    from app.models.ai_usage_event import AIUsageEvent

    float_type = "DOUBLE PRECISION" if _is_postgres() else "REAL"
    additions: dict[str, str] = {
        "job_id": "INTEGER",
        "course_id": "INTEGER",
        "stage": "TEXT",
        "provider": "TEXT",
        "model": "TEXT",
        "preset": "TEXT",
        "input_tokens": "INTEGER",
        "output_tokens": "INTEGER",
        "cache_read_tokens": "INTEGER",
        "cache_write_tokens": "INTEGER",
        "estimated_cost_usd": float_type,
        "status": "TEXT DEFAULT 'ok'",
        "error_category": "TEXT",
        "created_at": "TIMESTAMP",
    }
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
    except Exception:
        return

    if "ai_usage_events" not in tables:
        try:
            AIUsageEvent.__table__.create(engine, checkfirst=True)
        except Exception:
            logger = __import__("logging").getLogger(__name__)
            logger.exception("Failed to create ai_usage_events table")
        return

    try:
        existing = {col["name"] for col in inspector.get_columns("ai_usage_events")}
    except Exception:
        return

    with engine.begin() as conn:
        for name, sql_type in additions.items():
            if name in existing:
                continue
            if _is_postgres():
                conn.execute(
                    text(
                        f"ALTER TABLE ai_usage_events "
                        f"ADD COLUMN IF NOT EXISTS {name} {sql_type}"
                    )
                )
            else:
                conn.execute(
                    text(f"ALTER TABLE ai_usage_events ADD COLUMN {name} {sql_type}")
                )


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
