"""Student Confusion Layer — broad 80% serious learner (internal only).

Not a stupid student, not rare edge cases, not the top 5% genius.
Catches missing terms, skipped steps, and practical confusion that would
block most serious learners. Never appear in final teleprompter DOCX.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import BaseModel, Field


class StudentReview(BaseModel):
    """Compact internal student_review (never user-facing / never DOCX)."""

    missing_prerequisites: list[str] = Field(default_factory=list)
    unclear_terms: list[str] = Field(default_factory=list)
    skipped_steps: list[str] = Field(default_factory=list)
    needs_example: list[str] = Field(default_factory=list)
    too_fast: list[str] = Field(default_factory=list)
    too_abstract: list[str] = Field(default_factory=list)
    too_shallow: list[str] = Field(default_factory=list)
    likely_student_questions: list[str] = Field(default_factory=list)
    what_to_clarify_without_padding: list[str] = Field(default_factory=list)
    what_to_keep_unexplained_because_80_percent_do_not_need_it: list[str] = Field(
        default_factory=list
    )


STUDENT_LEAK_SUBSTRINGS: tuple[str, ...] = (
    "student_review",
    "missing_prerequisites",
    "unclear_terms",
    "skipped_steps",
    "likely_student_questions",
    "what_to_clarify_without_padding",
    "80_percent_do_not_need",
)

# Phrases that signal rare / edge-case / genius / out-of-scope objections —
# the student layer must ignore these rather than bloating the script.
RARE_OBJECTION_MARKERS: tuple[str, ...] = (
    r"philosophical",
    r"edge.?case",
    r"for the genius",
    r"top 5%",
    r"complete beginner who never",
    r"rewrite as a textbook",
    r"every possible objection",
    r"rare market",
    r"unreasonable edge",
)


@dataclass
class StudentClarityIssue:
    reason_code: str
    detail: str


def is_rare_objection(text: str) -> bool:
    """True when feedback looks like an edge-case / textbook / genius ask."""
    blob = text or ""
    return any(re.search(p, blob, re.IGNORECASE) for p in RARE_OBJECTION_MARKERS)


def should_ignore_student_feedback(item: str) -> bool:
    """80% rule: drop rare objections so they never drive Master padding."""
    return is_rare_objection(item)


def filter_student_review_to_80_percent(review: StudentReview) -> StudentReview:
    """Keep only broad-learner blockers; drop rare/genius/edge items."""

    def keep(items: list[str]) -> list[str]:
        return [i for i in items if i and not should_ignore_student_feedback(i)]

    return StudentReview(
        missing_prerequisites=keep(review.missing_prerequisites),
        unclear_terms=keep(review.unclear_terms),
        skipped_steps=keep(review.skipped_steps),
        needs_example=keep(review.needs_example),
        too_fast=keep(review.too_fast),
        too_abstract=keep(review.too_abstract),
        too_shallow=keep(review.too_shallow),
        likely_student_questions=keep(review.likely_student_questions),
        what_to_clarify_without_padding=keep(review.what_to_clarify_without_padding),
        what_to_keep_unexplained_because_80_percent_do_not_need_it=list(
            review.what_to_keep_unexplained_because_80_percent_do_not_need_it
        ),
    )


def student_clarity_hints_for_script(script_text: str) -> list[StudentClarityIssue]:
    """Lightweight local hints (no AI): unexplained dense English tech dumps."""
    text = script_text or ""
    issues: list[StudentClarityIssue] = []

    # Dense unexplained English acronym / tool token with no nearby Arabic gloss.
    lonely_terms = re.findall(
        r"\b(CTR|ROAS|KPI|CPA|LTV|API|JSON|SQL|CMS|CRM)\b",
        text,
    )
    for term in dict.fromkeys(lonely_terms):
        # If the term appears without a short nearby explanation cue, flag.
        window = re.search(
            rf".{{0,40}}\b{re.escape(term)}\b.{{0,80}}",
            text,
            re.IGNORECASE,
        )
        snippet = window.group(0) if window else ""
        if not re.search(r"(يعني|يعني إيه|معناها|اختصار|يعني ببساطة)", snippet):
            issues.append(
                StudentClarityIssue(
                    reason_code="unclear_term",
                    detail=(
                        f"Term '{term}' may confuse ~80% of serious learners without "
                        "a one-breath gloss — clarify briefly, no textbook digression."
                    ),
                )
            )

    if re.search(r"\b(just|simply|obviously|طبعاً|بديهي)\b.{0,40}\b(then|بعدين|وبعدها)\b", text, re.I):
        issues.append(
            StudentClarityIssue(
                reason_code="skipped_step",
                detail=(
                    "Teacher voice skips a practical step as 'obvious' — restore the "
                    "missing action for the broad serious learner."
                ),
            )
        )

    return issues
