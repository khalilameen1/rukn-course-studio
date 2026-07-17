"""SQLAlchemy column types used by models (enums + JSON coercion)."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Type

from sqlalchemy import JSON, String, TypeDecorator
from sqlalchemy.engine import Dialect

from app.services.json_coerce import coerce_json_dict, coerce_json_list


def resolve_str_enum_member(enum_cls: Type[Enum], value: Any) -> Enum:
    """Map DB/API string (value or legacy NAME) to an enum member.

    Raises LookupError when the value cannot be resolved.
    """
    if isinstance(value, enum_cls):
        return value
    raw = getattr(value, "value", value)
    if isinstance(raw, enum_cls):
        return raw
    text = str(raw)
    try:
        return enum_cls(text)
    except ValueError:
        pass
    try:
        return enum_cls[text]
    except KeyError as exc:
        raise LookupError(
            f"{text!r} is not among the defined enum values for {enum_cls.__name__}"
        ) from exc


# Back-compat alias used by older call sites / tests.
_coerce_enum_member = resolve_str_enum_member


class _StrEnumValue(TypeDecorator):
    impl = String
    cache_ok = True

    def __init__(self, enum_cls: Type[Enum], length: int = 64):
        super().__init__(length=length)
        self.enum_cls = enum_cls

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return resolve_str_enum_member(self.enum_cls, value).value

    def process_result_value(self, value: Any, dialect: Any) -> Enum | None:
        if value is None:
            return None
        return resolve_str_enum_member(self.enum_cls, value)


def sa_str_enum(enum_cls: Type[Enum], *, length: int = 64) -> _StrEnumValue:
    """VARCHAR enum column that stores enum.value and tolerates legacy NAME rows."""
    return _StrEnumValue(enum_cls, length=length)


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
