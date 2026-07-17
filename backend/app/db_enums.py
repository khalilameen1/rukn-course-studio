"""SQLAlchemy helpers for persisting `str, Enum` columns by **value**.

SQLAlchemy's default Enum column stores member **names** (`PREMIUM`), while
our API, Pydantic, and TEXT column defaults use **values** (`premium`).
Mixed rows cause `LookupError` on ORM load → HTTP 500 on course list/open.
"""

from __future__ import annotations

from enum import Enum
from typing import Type

from sqlalchemy import Enum as SAEnum


def sa_str_enum(enum_cls: Type[Enum], *, length: int = 64) -> SAEnum:
    """VARCHAR enum column that reads and writes `enum.value`.

    `length` must cover the longest value (e.g. mixed_quality_ai_course_draft).
    Older DBs often have VARCHAR(12) sized for member *names* — widen via
    `_widen_str_enum_columns` in app/db.py on startup.
    """
    return SAEnum(
        enum_cls,
        values_callable=lambda members: [item.value for item in members],
        native_enum=False,
        validate_strings=True,
        length=length,
    )
