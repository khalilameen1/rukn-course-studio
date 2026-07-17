"""Coerce str Enum inputs that clients / legacy DBs often send wrong.

Accepts member NAME (`RUNNING`) or value (`running`), plus optional aliases.
Unrecognized values are returned unchanged so Pydantic can raise normally.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Type, TypeVar

from app.db.types import resolve_str_enum_member
from app.services.source_category_migrate import SOURCE_CATEGORY_LEGACY_ALIASES

E = TypeVar("E", bound=Enum)


def coerce_str_enum(
    enum_cls: Type[E],
    value: Any,
    *,
    aliases: dict[str, str] | None = None,
) -> Any:
    if value is None or isinstance(value, enum_cls):
        return value
    raw = getattr(value, "value", value)
    if isinstance(raw, enum_cls):
        return raw
    text = str(raw).strip()
    if not text:
        return value
    if aliases and text in aliases:
        text = aliases[text]
    try:
        return resolve_str_enum_member(enum_cls, text)
    except LookupError:
        pass
    lowered = text.lower()
    for member in enum_cls:
        if member.value.lower() == lowered or member.name.lower() == lowered:
            return member
    return value


def coerce_source_category(value: Any) -> Any:
    from app.models.enums import SourceCategory

    return coerce_str_enum(
        SourceCategory, value, aliases=SOURCE_CATEGORY_LEGACY_ALIASES
    )


def coerce_priority(value: Any) -> Any:
    from app.models.enums import Priority

    return coerce_str_enum(Priority, value)


def coerce_source_origin(value: Any) -> Any:
    from app.models.enums import SourceOrigin

    if value is None or value == "":
        return None
    return coerce_str_enum(SourceOrigin, value)
