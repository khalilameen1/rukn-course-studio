"""Coerce str Enum inputs that AI clients / legacy DBs often send wrong.

Typical mistakes this absorbs:
- member NAME (`RUNNING`, `NOTES`) instead of value (`running`, `user_notes`)
- renamed SourceCategory aliases (`main_content` → `scientific_reference`)
- Enum instances mixed with bare strings
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Type, TypeVar

from app.services.source_category_migrate import SOURCE_CATEGORY_LEGACY_ALIASES

E = TypeVar("E", bound=Enum)


def coerce_str_enum(
    enum_cls: Type[E],
    value: Any,
    *,
    aliases: dict[str, str] | None = None,
) -> Any:
    """Return an `enum_cls` member when possible; otherwise return `value` unchanged.

    Leaving unrecognized values untouched lets Pydantic raise a normal
    validation error instead of inventing a silent default.
    """
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
        return enum_cls(text)
    except ValueError:
        pass
    try:
        return enum_cls[text]
    except KeyError:
        pass
    # Case-insensitive value match (AI forms often send Title Case).
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
