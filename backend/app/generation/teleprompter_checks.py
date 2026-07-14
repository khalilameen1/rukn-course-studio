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
    # Dynamic Teaching Curve / creator persona / internal planning — never DOCX.
    "module_curve",
    "lesson_curve",
    "hook_strength",
    "tension_curve",
    "teaching_energy",
    "natural_length",
    "natural_depth",
    "ending_motion",
    "module_energy_curve",
    "module_depth_pattern",
    "course_creator_persona",
    "module_persona_adjustment",
    "lesson_persona_state",
    "viral_intent",
    "confidence_heat",
    "persona_review_reminders",
    "specialist_critic_report",
    "fatal_issues",
    "rebuild_direction",
    "filler_to_remove",
    "accuracy_risks",
    "student_review",
    "missing_prerequisites",
    "unclear_terms",
    "likely_student_questions",
    "mentor_review",
    "strongest_hidden_angle",
    "hook_advice",
    "pacing_advice",
    "loop_advice",
    "academic_gap",
    "content_instinct_note",
    "what_to_make_bolder",
    "what_to_make_quieter",
    "rebuild_instruction",
    "master creator-academic mentor",
    "consulting master mentor",
    "map_review",
    "first course map draft",
    "estimated duration table",
    "rebuilding final course map",
    # Research / evidence / confirmation — never spoken script or DOCX.
    "needs confirmation",
    "needs_confirmation",
    "needs review",
    "needs_review",
    "evidence ledger",
    "evidence_ledger",
    "web source memory",
    "source memory",
    "according to source",
    "according to wikipedia",
    "http://",
    "https://",
    "citation needed",
    "research note",
    "mentor advised",
    "critic said",
    "student asked",
    "market analysis",
    "evergreen review",
    "adapted from",
    "originality note",
    "copyright note",
    "paraphrased from",
    # V1: no Production Pack / asset / design leakage
    "production pack",
    "asset brief",
    "design instruction",
    "screenshot plan",
    "bridge project",
    "[bridge project]",
    # Hard leak pack (hardening)
    "specialist_review",
    "mentor_review",
    "student_review",
    "quality_score",
    "quality score",
    "first draft",
    "production notes",
    "<<<untrusted_reference_material>>>",
    "end_untrusted_reference_material",
    "ignore previous instructions",
    "reveal prompts",
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
