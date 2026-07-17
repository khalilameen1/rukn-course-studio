"""Legacy SourceCategory string remaps for existing DB rows.

Older builds stored member names (NOTES, MAIN_CONTENT) and later renamed
categories. ORM loads with validate_strings=True raise LookupError -> HTTP 500
on list/upload paths that touch course_sources.
"""

from __future__ import annotations

# Obsolete NAME / value aliases -> current SourceCategory.value
SOURCE_CATEGORY_LEGACY_ALIASES: dict[str, str] = {
    "MAIN_CONTENT": "scientific_reference",
    "SUPPORTING": "scientific_reference",
    "NOTES": "user_notes",
    "SPOKEN_STYLE": "flow_reference",
    "main_content": "scientific_reference",
    "supporting": "scientific_reference",
    "notes": "user_notes",
    "spoken_style": "flow_reference",
}
