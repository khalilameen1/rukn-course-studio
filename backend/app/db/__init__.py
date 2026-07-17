"""Database package: engine, session, schema patches, column types.

Public API stays importable as `from app.db import engine, get_session, init_db`.
Private `_ensure_*` helpers are re-exported for tests that patch schema startup.
"""

from app.db.engine import (
    BOOLEAN_NOT_NULL_DEFAULT_FALSE,
    BOOLEAN_NOT_NULL_DEFAULT_TRUE,
    engine,
    get_session,
)
from app.db.patches import (
    _backfill_generation_job_json_defaults,
    _ensure_ai_usage_events_table,
    _ensure_course_columns,
    _ensure_course_source_columns,
    _ensure_course_version_unique,
    _ensure_generation_job_columns,
    _ensure_source_analysis_columns,
    _harden_boolean_not_null_true,
    _is_postgres,
    _json_safe_type,
    _normalize_str_enum_storage,
    _promote_json_text_columns,
    _widen_str_enum_columns,
    init_db,
)

__all__ = [
    "BOOLEAN_NOT_NULL_DEFAULT_FALSE",
    "BOOLEAN_NOT_NULL_DEFAULT_TRUE",
    "engine",
    "get_session",
    "init_db",
    "_backfill_generation_job_json_defaults",
    "_ensure_ai_usage_events_table",
    "_ensure_course_columns",
    "_ensure_course_source_columns",
    "_ensure_course_version_unique",
    "_ensure_generation_job_columns",
    "_ensure_source_analysis_columns",
    "_harden_boolean_not_null_true",
    "_is_postgres",
    "_json_safe_type",
    "_normalize_str_enum_storage",
    "_promote_json_text_columns",
    "_widen_str_enum_columns",
]
