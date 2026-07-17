"""SQLAlchemy helpers for persisting str Enum columns by value.

SQLAlchemy default Enum stores member names (PREMIUM); API/Pydantic use values
(premium). Mixed rows caused LookupError -> HTTP 500 on Generate.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Type

from sqlalchemy import String, TypeDecorator


def _coerce_enum_member(enum_cls: Type[Enum], value: Any) -> Enum:
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


class _StrEnumValue(TypeDecorator):
    impl = String
    cache_ok = True

    def __init__(self, enum_cls: Type[Enum], length: int = 64):
        super().__init__(length=length)
        self.enum_cls = enum_cls

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return _coerce_enum_member(self.enum_cls, value).value

    def process_result_value(self, value: Any, dialect: Any) -> Enum | None:
        if value is None:
            return None
        return _coerce_enum_member(self.enum_cls, value)


def sa_str_enum(enum_cls: Type[Enum], *, length: int = 64) -> _StrEnumValue:
    """VARCHAR enum column that stores enum.value and tolerates legacy NAME rows."""
    return _StrEnumValue(enum_cls, length=length)
