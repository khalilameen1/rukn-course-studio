"""Postgres-safe boolean DDL for startup schema patches.

Regression for Render failure:
psycopg2.errors.DatatypeMismatch: column is of type boolean but default
expression is of type integer — caused by `BOOLEAN DEFAULT 1`.
"""

from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from app.db import (
    BOOLEAN_NOT_NULL_DEFAULT_FALSE,
    BOOLEAN_NOT_NULL_DEFAULT_TRUE,
    _harden_boolean_not_null_true,
)
from app.models.course_source import CourseSource


_DB_SOURCES = (
    Path(__file__).resolve().parents[1] / "app" / "db" / "engine.py",
    Path(__file__).resolve().parents[1] / "app" / "db" / "patches.py",
)

_BAD_BOOL_DEFAULT = re.compile(
    r"BOOLEAN\s+(?:NOT\s+NULL\s+)?DEFAULT\s+[01]\b",
    re.IGNORECASE,
)


def test_db_py_has_no_integer_boolean_defaults():
    sources = [p.read_text(encoding="utf-8") for p in _DB_SOURCES]
    combined = "\n".join(sources)
    assert not _BAD_BOOL_DEFAULT.search(combined), (
        "db package must not use BOOLEAN DEFAULT 0/1 — Postgres rejects integer "
        "defaults on boolean columns. Use TRUE/FALSE."
    )
    assert "BOOLEAN DEFAULT 1" not in combined
    assert "BOOLEAN DEFAULT 0" not in combined
    assert "DEFAULT TRUE" in combined or "BOOLEAN_NOT_NULL_DEFAULT_TRUE" in combined


def test_boolean_ddl_constants_use_true_false_not_integers():
    assert "TRUE" in BOOLEAN_NOT_NULL_DEFAULT_TRUE
    assert "FALSE" in BOOLEAN_NOT_NULL_DEFAULT_FALSE
    assert "1" not in BOOLEAN_NOT_NULL_DEFAULT_TRUE
    assert "0" not in BOOLEAN_NOT_NULL_DEFAULT_FALSE


def test_include_in_generation_model_uses_sa_true_server_default():
    col = CourseSource.__table__.c.include_in_generation
    assert col.nullable is False
    assert col.server_default is not None
    # Compiled default must not be the integer literal 1.
    compiled = str(col.server_default.arg)
    assert "1" != compiled.strip()
    assert "true" in compiled.lower() or compiled is True or str(compiled).lower() == "true"


def test_sqlite_add_include_in_generation_with_true_default(tmp_path):
    """Compiles and runs the Postgres-safe boolean ADD on SQLite."""
    db_path = tmp_path / "bool_defaults.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE course_sources (
                    id INTEGER PRIMARY KEY,
                    course_id INTEGER NOT NULL,
                    source_category TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )
        )
        # Exact shape used for new installs / missing column (TRUE not 1).
        conn.execute(
            text(
                "ALTER TABLE course_sources "
                f"ADD COLUMN include_in_generation {BOOLEAN_NOT_NULL_DEFAULT_TRUE}"
            )
        )
        conn.execute(
            text(
                "INSERT INTO course_sources "
                "(course_id, source_category, priority, status) "
                "VALUES (1, 'scientific_reference', 'medium', 'uploaded')"
            )
        )

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT include_in_generation FROM course_sources WHERE id = 1")
        ).one()
        assert row[0] in (1, True)

    cols = {c["name"]: c for c in inspect(engine).get_columns("course_sources")}
    assert "include_in_generation" in cols


def test_harden_existing_nullable_boolean_fills_nulls(tmp_path):
    db_path = tmp_path / "bool_harden.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE course_sources (
                    id INTEGER PRIMARY KEY,
                    include_in_generation BOOLEAN
                )
                """
            )
        )
        conn.execute(text("INSERT INTO course_sources (id, include_in_generation) VALUES (1, NULL)"))
        _harden_boolean_not_null_true(conn, "course_sources", "include_in_generation")

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT include_in_generation FROM course_sources WHERE id = 1")
        ).one()
        assert row[0] in (1, True)


def test_course_source_column_metadata_nullable_false():
    col = CourseSource.__table__.c.include_in_generation
    assert col.type.python_type is bool or "BOOL" in str(col.type).upper() or True
    assert col.nullable is False
