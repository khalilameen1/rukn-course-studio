"""Shared teleprompter-contract text checks.

Extracted so `tests/test_docx_export.py`, `tests/golden/`, and
`app/generation/output_scoring.py` all check against exactly the same
forbidden-vocabulary list and module/lesson pattern instead of duplicating
- and silently drifting apart - across multiple files.

Nothing here touches the DOCX file itself or changes export behavior; it
only inspects already-rendered plain text (see
`app/services/docx_export.py` `extract_plain_text`) - purely observational,
per the "scoring checks observe the DOCX/teleprompter contract, they don't
change it" constraint on this pass.
"""

from __future__ import annotations

import re

# Substrings that must never appear anywhere in a rendered teleprompter
# DOCX, per the `rukn_teleprompter_docx_contract` admin knowledge item -
# the DOCX must hide every internal-pipeline artifact (review notes,
# validation notes, quality checks, etc.), never show credit/methodology
# text, and never address the lecturer with meta-instructions instead of
# actual lines to say. Checked case-insensitively.
TELEPROMPTER_FORBIDDEN_SUBSTRINGS: tuple[str, ...] = (
    "internal_review",
    "validation",
    "quality_check",
    "prepared by ai",
    "methodology",
    "note to instructor",
    "say this",
    "explain that",
)

# Matches exactly the numbering docx_export.py's render functions produce
# ("Module {n} — {title}" / "Lesson {n} — {title}") - the em dash (U+2014),
# not a hyphen.
_MODULE_HEADING_PATTERN = re.compile(r"Module\s+\d+\s+\u2014\s+\S")
_LESSON_HEADING_PATTERN = re.compile(r"Lesson\s+\d+\s+\u2014\s+\S")


def find_forbidden_substrings(text: str) -> list[str]:
    """Every entry of `TELEPROMPTER_FORBIDDEN_SUBSTRINGS` found (case-
    insensitively) in `text` - empty list means clean."""
    lowered = (text or "").lower()
    return [substring for substring in TELEPROMPTER_FORBIDDEN_SUBSTRINGS if substring in lowered]


def module_lesson_structure_present(text: str) -> bool:
    """True only if `text` contains at least one numbered "Module N — "
    heading AND at least one numbered "Lesson N — " heading - the expected
    shape of a rendered teleprompter DOCX (see app/services/docx_export.py)."""
    body = text or ""
    return bool(_MODULE_HEADING_PATTERN.search(body)) and bool(_LESSON_HEADING_PATTERN.search(body))
