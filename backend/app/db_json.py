"""SQLAlchemy JSON columns that always return Python dict/list.

Postgres columns added via early `ADD COLUMN … TEXT` helpers (see app/db.py)
store JSON as text. SQLAlchemy's stock `JSON` type assumes native JSON and
skips `json.loads` on Postgres — so the ORM hands callers a string. That
single mismatch caused Generate 500s (Pydantic ValidationError) and early
FAILED jobs (AttributeError on `.get`).

These TypeDecorators coerce on every read/write so call sites can treat the
fields as real dicts/lists regardless of TEXT vs JSON storage.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import JSON, TypeDecorator
from sqlalchemy.engine import Dialect

from app.services.json_coerce import coerce_json_dict, coerce_json_list


def _loads_if_str(value: Any) -> Any:
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    if isinstance(value, str):
        if not value.strip():
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return value


class _JsonObject(TypeDecorator):
    """Nullable JSON object column → `dict | None`."""

    impl = JSON
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> Any:
        if value is None or value == "":
            return None
        parsed = _loads_if_str(value)
        if parsed is None:
            return None
        return parsed if isinstance(parsed, dict) else None

    def process_result_value(self, value: Any, dialect: Dialect) -> dict[str, Any] | None:
        return coerce_json_dict(value)


class _JsonArray(TypeDecorator):
    """JSON array column → always a `list` (NULL/invalid → `[]`)."""

    impl = JSON
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> Any:
        if value is None or value == "":
            return []
        parsed = _loads_if_str(value)
        if parsed is None:
            return []
        return parsed if isinstance(parsed, list) else []

    def process_result_value(self, value: Any, dialect: Dialect) -> list[Any]:
        return coerce_json_list(value)


def sa_json_object() -> _JsonObject:
    return _JsonObject()


def sa_json_array() -> _JsonArray:
    return _JsonArray()
