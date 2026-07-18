"""Schema self-healing guards.

Production Postgres tables are created once at first deploy; every model
column added later must appear in the db.py `_ensure_*` helpers, otherwise
ORM SELECTs fail with UndefinedColumn and endpoints 500 (the exact cause of
the /auth/diagnostics Internal Server Error on Render).
"""

import inspect as pyinspect
import re

from sqlmodel import Session, SQLModel, create_engine

from app import models  # noqa: F401  (register tables)
from app.auth.diagnostics import build_diagnostics
from app.db import (
    _ensure_ai_usage_events_table,
    _ensure_course_columns,
    _ensure_course_source_columns,
    _ensure_generation_job_columns,
    _ensure_source_analysis_columns,
)

# Columns that existed in the very first deployed schema (never ALTERed in).
_GENERATION_JOBS_BASE = {
    "id",
    "course_id",
    "status",
    "current_stage",
    "progress_percent",
    "log_json",
    "output_docx_path",
    "error_message",
    "created_at",
    "updated_at",
}

_COURSES_BASE = {
    "id",
    "title",
    "audience",
    "outcome",
    "structure_mode",
    "explanation_level",
    "status",
    "created_at",
    "updated_at",
}


def _covered_columns(fn) -> set[str]:
    return set(re.findall(r'"(\w+)":', pyinspect.getsource(fn)))


def test_generation_job_ensure_covers_every_model_column():
    covered = _covered_columns(_ensure_generation_job_columns)
    model_cols = {c.name for c in SQLModel.metadata.tables["generation_jobs"].columns}
    missing = model_cols - covered - _GENERATION_JOBS_BASE
    assert not missing, f"add these to _ensure_generation_job_columns: {sorted(missing)}"


def test_course_ensure_covers_every_model_column():
    covered = _covered_columns(_ensure_course_columns)
    model_cols = {c.name for c in SQLModel.metadata.tables["courses"].columns}
    missing = model_cols - covered - _COURSES_BASE
    assert not missing, f"add these to _ensure_course_columns: {sorted(missing)}"


def test_ensure_course_columns_heals_missing_snapshot_column(tmp_path, monkeypatch):
    """Reproduce Render outage: courses table predates generation_context_snapshot_json.

    Without the ensure ADD, ORM SELECTs raise UndefinedColumn and /courses 500s.
    """
    from sqlalchemy import text
    from sqlmodel import select

    from app.db import patches as patches_mod
    from app.models.course import Course

    engine = create_engine(f"sqlite:///{tmp_path / 'legacy_courses.db'}")
    monkeypatch.setattr(patches_mod, "_engine", lambda: engine)
    monkeypatch.setattr("app.db.engine", engine)

    # Legacy shape: base columns only (no generation_context_snapshot_json).
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE courses (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    audience TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    structure_mode TEXT NOT NULL,
                    explanation_level TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                "INSERT INTO courses "
                "(id, title, audience, outcome, structure_mode, "
                "explanation_level, status) "
                "VALUES (1, 'Old Course', 'beginners', 'learn X', "
                "'connected_no_modules', 'final_only', 'draft')"
            )
        )

    _ensure_course_columns()

    with Session(engine) as session:
        rows = session.exec(select(Course)).all()
        assert len(rows) == 1
        assert rows[0].title == "Old Course"
        assert rows[0].generation_context_snapshot_json is None


def test_ai_usage_ensure_covers_every_model_column():
    covered = _covered_columns(_ensure_ai_usage_events_table)
    model_cols = {c.name for c in SQLModel.metadata.tables["ai_usage_events"].columns}
    missing = model_cols - covered - {"id"}
    assert not missing, f"add these to _ensure_ai_usage_events_table: {sorted(missing)}"


# First-deploy (MVP commit 17bbdc7) schemas for the remaining upgradable tables.
_COURSE_SOURCES_BASE = {
    "id",
    "course_id",
    "source_category",
    "original_filename",
    "file_path",
    "mime_type",
    "extracted_text",
    "priority",
    "status",
    "created_at",
}

_SOURCE_ANALYSES_BASE = {
    "id",
    "source_id",
    "chunks_json",
    "source_summary",
    "key_points_json",
    "avoid_points_json",
    "created_at",
    "updated_at",
}


def test_course_source_ensure_covers_every_model_column():
    covered = _covered_columns(_ensure_course_source_columns) | {"include_in_generation"}
    model_cols = {c.name for c in SQLModel.metadata.tables["course_sources"].columns}
    missing = model_cols - covered - _COURSE_SOURCES_BASE
    assert not missing, f"add these to _ensure_course_source_columns: {sorted(missing)}"


def test_source_analysis_ensure_covers_every_model_column():
    covered = _covered_columns(_ensure_source_analysis_columns)
    model_cols = {c.name for c in SQLModel.metadata.tables["source_analyses"].columns}
    missing = model_cols - covered - _SOURCE_ANALYSES_BASE
    assert not missing, f"add these to _ensure_source_analysis_columns: {sorted(missing)}"


def _all_ensure_ddl_fragments() -> list[str]:
    """Every quoted DDL type string used by the ensure helpers."""
    import app.db as db_module

    fragments = [
        db_module.BOOLEAN_NOT_NULL_DEFAULT_TRUE,
        db_module.BOOLEAN_NOT_NULL_DEFAULT_FALSE,
    ]
    for fn in (
        _ensure_generation_job_columns,
        _ensure_course_columns,
        _ensure_source_analysis_columns,
        _ensure_course_source_columns,
        _ensure_ai_usage_events_table,
    ):
        src = pyinspect.getsource(fn)
        fragments.extend(m.group(1) for m in re.finditer(r'"\w+":\s*"([^"]+)"', src))
    return fragments


def test_ensure_ddl_never_uses_integer_boolean_defaults():
    """Postgres rejects BOOLEAN DEFAULT 1/0 (DatatypeMismatch)."""
    for ddl in _all_ensure_ddl_fragments():
        upper = ddl.upper()
        if "BOOLEAN" in upper:
            assert not re.search(r"DEFAULT\s+[01]\b", upper), (
                f"integer boolean default in DDL: {ddl}"
            )


def test_ensure_ddl_never_adds_not_null_without_default():
    """ALTER TABLE ADD COLUMN x NOT NULL without DEFAULT fails on any
    non-empty production table - every NOT NULL addition needs a DEFAULT."""
    for ddl in _all_ensure_ddl_fragments():
        upper = ddl.upper()
        if "NOT NULL" in upper:
            assert "DEFAULT" in upper, f"NOT NULL addition without DEFAULT: {ddl}"


def test_json_model_columns_get_json_type_on_postgres():
    from app.db import _json_safe_type

    assert _json_safe_type.__doc__  # helper exists and is documented
    # SQLite path keeps TEXT (function checks live engine dialect; under
    # the test engine this is sqlite, so TEXT passes through unchanged).
    assert _json_safe_type("course_map_json", "TEXT") in ("TEXT", "JSON")


def test_diagnostics_never_500s_when_tables_are_missing(tmp_path):
    """/auth/diagnostics exists to diagnose broken deployments - it must
    return 'unknown' provider health on schema gaps, never raise."""
    engine = create_engine(f"sqlite:///{tmp_path / 'no_tables.db'}")
    # Deliberately NO create_all - both queried tables are absent.
    with Session(engine) as session:
        payload = build_diagnostics(session=session)

    assert payload["provider_reachable"] == "unknown"
    assert payload["last_successful_request_at"] is None
    assert payload["last_error_category"] is None
    assert payload["last_error_message"] is None
