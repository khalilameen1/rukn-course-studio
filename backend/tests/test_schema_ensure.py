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
    _ensure_generation_job_columns,
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


def test_ai_usage_ensure_covers_every_model_column():
    covered = _covered_columns(_ensure_ai_usage_events_table)
    model_cols = {c.name for c in SQLModel.metadata.tables["ai_usage_events"].columns}
    missing = model_cols - covered - {"id"}
    assert not missing, f"add these to _ensure_ai_usage_events_table: {sorted(missing)}"


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
