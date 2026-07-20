"""GENSPARK-style mission brief for pre-generate UX (never DOCX)."""

from __future__ import annotations

from typing import Any


def build_mission_brief(
    *,
    title: str,
    audience: str,
    outcome: str,
    clarity: dict[str, Any],
    included_source_count: int,
    sources_summary: str | None = None,
) -> dict[str, Any]:
    """One composition card: what we will build, for whom, confidence soft signal."""
    title_s = (title or "").strip() or "Untitled course"
    audience_s = (audience or "").strip() or "learners"
    outcome_s = (outcome or "").strip() or "a practical skill"
    score = int(clarity.get("clarity_score") or 0)
    premium_ok = bool(clarity.get("premium_recommended"))

    headline = f"Build “{title_s}” for {audience_s}"
    promise = f"Outcome: {outcome_s}"
    if included_source_count:
        grounding = f"Grounded on {included_source_count} included source(s)"
        if sources_summary:
            grounding = f"{grounding} — {sources_summary}"
    else:
        grounding = "Grounded on brief + canonical RUKN standard (no uploads included)"

    confidence = (
        "ready"
        if score >= 70
        else "ok"
        if score >= 55
        else "needs_sharpening"
    )
    tighten = None
    if score < 55:
        tighten = suggest_tighten_brief(audience=audience_s, outcome=outcome_s)

    return {
        "headline": headline,
        "promise": promise,
        "grounding": grounding,
        "clarity_score": score,
        "confidence": confidence,
        "premium_recommended": premium_ok,
        "tighten_brief_suggestion": tighten,
        "one_liner": f"{headline}. {promise}. {grounding}.",
    }


def suggest_tighten_brief(*, audience: str, outcome: str) -> str:
    """Single actionable rewrite hint — user edits brief, then regenerates."""
    aud = (audience or "your learners").strip()
    out = (outcome or "a concrete result").strip()
    if len(out) < 40 or out.lower().startswith(("learn", "understand", "know", "تعلم", "فهم")):
        return (
            f"Try a sharper goal: “After this course, {aud} can {out} "
            f"in a real workflow within 30 days.”"
        )
    return (
        f"Add who + starting level + measurable finish line. "
        f"Example: “{aud} who are beginners will ship one working result: {out}.”"
    )
