"""Brief clarity heuristics before expensive generation (no LLM)."""

from __future__ import annotations

import re
from typing import Any

_VAGUE_OUTCOME = re.compile(
    r"^(learn|learning|understand|know|study|تعلم|فهم|معرفة)\b",
    re.I,
)
_TOOLISH = re.compile(
    r"\b(ads?|meta|facebook|google|tiktok|shopify|canva|excel|figma|"
    r"wordpress|seo|crm|api|dashboard|campaign)\b",
    re.I,
)


def score_brief_clarity(
    *,
    title: str,
    audience: str,
    outcome: str,
    special_notes: str | None = None,
) -> dict[str, Any]:
    """Return clarity score 0–100, warnings, and soft gates.

    Never blocks provider-ready starts by itself — callers decide hard vs soft.
    """
    title_s = (title or "").strip()
    audience_s = (audience or "").strip()
    outcome_s = (outcome or "").strip()
    notes_s = (special_notes or "").strip()

    score = 0
    warnings: list[str] = []
    blockers: list[str] = []

    if len(title_s) >= 8:
        score += 20
    else:
        warnings.append("Course title is very short — add a clearer topic name.")

    if len(audience_s) >= 8:
        score += 25
    else:
        warnings.append(
            "Target learner is vague — say who they are and their starting level."
        )

    if len(outcome_s) >= 20:
        score += 30
    elif len(outcome_s) >= 8:
        score += 15
        warnings.append("Goal is thin — make the outcome specific and measurable.")
    else:
        warnings.append("Goal is missing or too short for a premium run.")

    if _VAGUE_OUTCOME.search(outcome_s) and len(outcome_s) < 40:
        score = max(0, score - 10)
        warnings.append(
            "Goal starts with a vague verb (learn/understand) — specify what they can do."
        )

    blob = f"{title_s} {outcome_s} {notes_s}"
    if _TOOLISH.search(blob):
        score += 15
    elif len(outcome_s) >= 40:
        score += 10

    if len(notes_s) >= 20:
        score += 10

    score = max(0, min(100, score))
    premium_ok = score >= 55
    if not premium_ok:
        warnings.append(
            "Brief clarity is low for Premium — consider Preview, or sharpen audience + goal."
        )
    if len(title_s) < 3 or len(audience_s) < 3 or len(outcome_s) < 3:
        blockers.append("Title, audience, and outcome are required.")

    return {
        "clarity_score": score,
        "premium_recommended": premium_ok,
        "warnings": warnings,
        "blockers": blockers,
        "message": f"Brief clarity {score}/100"
        + (" — Premium OK" if premium_ok else " — sharpen before Premium"),
    }
