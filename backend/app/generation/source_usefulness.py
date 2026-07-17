"""Source usefulness / credit hygiene — mistrust means cheap distillation, not rejection.

Every source starts as raw material. High-risk / low-quality sources stay usable as
small candidate signals; they are not dumped into expensive lesson prompts.
"""

from __future__ import annotations

from typing import Any, Literal

UsefulnessLevel = Literal["high", "medium", "low"]
IncludeMode = Literal[
    "full_distilled",
    "brief_candidates",
    "colloquial_only",
    "notes_protected",
]

SOURCE_USEFULNESS_VERSION = "1.0"

LOW_SIGNAL_BRIEF_MAX_CHARS = 420
MEDIUM_SIGNAL_MAX_CHARS = 900

_RISK_PENALTY = {
    "outdated_possible": 1,
    "ocr_noise_possible": 1,
    "transcript_noise_possible": 1,
    "foreign_market_context": 1,
    "academic_theory_heavy": 1,
    "shallow_or_generic": 2,
    "translated_or_stiff": 1,
    "repetitive_or_filler": 1,
    "tool_ui_may_be_old": 1,
    "uncertain_terms": 1,
}


def _signal_count(memory: dict[str, Any]) -> int:
    bags = (
        memory.get("useful_concepts")
        or memory.get("extracted_facts")
        or memory.get("facts")
        or []
    )
    rebuild = memory.get("rebuild_candidates") or []
    objections = memory.get("learner_objections") or []
    warnings = memory.get("practical_warnings") or []
    terms = memory.get("terminology_if_current") or memory.get("terminology") or []
    return (
        len([x for x in bags if x])
        + len([x for x in rebuild if x])
        + len([x for x in objections if x])
        + len([x for x in warnings if x])
        + min(len([x for x in terms if x]), 3)
    )


def assess_source_usefulness(memory: dict[str, Any] | None) -> dict[str, Any]:
    """Infer usefulness / risk / include mode from existing memory signals."""
    from app.services.json_coerce import coerce_json_dict

    mem = coerce_json_dict(memory) or {}
    category = str(mem.get("source_type") or mem.get("category") or "")
    if category == "user_notes":
        return {
            "source_usefulness_version": SOURCE_USEFULNESS_VERSION,
            "source_usefulness": "high",
            "source_risk_level": "low",
            "freshness_risk": "low",
            "extraction_quality": "direct",
            "has_unique_useful_material": True,
            "low_signal": False,
            "include_mode": "notes_protected",
            "relevance_to_promise": mem.get("topic_relevance") or "user_intent",
        }

    if mem.get("transcript_colloquial_only"):
        return {
            "source_usefulness_version": SOURCE_USEFULNESS_VERSION,
            "source_usefulness": "low",
            "source_risk_level": "high",
            "freshness_risk": "n/a",
            "extraction_quality": "transcript",
            "has_unique_useful_material": False,
            "low_signal": True,
            "include_mode": "colloquial_only",
            "relevance_to_promise": "off_topic",
        }

    signals = _signal_count(mem)
    risk_flags = list(mem.get("source_risk_flags") or [])
    risk_score = sum(_RISK_PENALTY.get(f, 0) for f in risk_flags)
    if mem.get("shallow_source_flag"):
        risk_score += 2
    if mem.get("outdated_warnings"):
        risk_score += 1

    freshness = "high" if (mem.get("outdated_warnings") or "outdated_possible" in risk_flags) else "low"
    if "tool_ui_may_be_old" in risk_flags:
        freshness = "high"

    extraction = str(mem.get("extraction_method") or "unknown")
    extraction_quality = "good"
    if extraction == "ocr" or "ocr_noise_possible" in risk_flags:
        extraction_quality = "noisy"
    elif "transcript" in str(mem.get("source_origin") or ""):
        extraction_quality = "transcript"

    # Unique useful material = some distilled candidates after filters.
    unique = signals >= 2

    # Prefer keeping useful-but-flawed sources as full distilled candidates.
    # low_signal is for truly thin / high-waste sources only.
    shallow = bool(mem.get("shallow_source_flag"))
    if shallow and signals <= 3:
        usefulness = "low"
        include = "brief_candidates"
        low_signal = True
    elif signals >= 3:
        usefulness: UsefulnessLevel = "high" if risk_score <= 3 else "medium"
        include: IncludeMode = "full_distilled"
        low_signal = False
    elif signals >= 2:
        usefulness = "medium"
        include = "full_distilled"
        low_signal = False
        if shallow and risk_score >= 4:
            include = "brief_candidates"
            low_signal = True
            usefulness = "low"
    elif signals == 1:
        usefulness = "medium" if not shallow else "low"
        include = "brief_candidates" if (shallow or risk_score >= 3) else "full_distilled"
        low_signal = include == "brief_candidates"
    else:
        usefulness = "low"
        include = "brief_candidates"
        low_signal = True

    risk_level = "low"
    if risk_score >= 4:
        risk_level = "high"
    elif risk_score >= 2:
        risk_level = "medium"

    return {
        "source_usefulness_version": SOURCE_USEFULNESS_VERSION,
        "source_usefulness": usefulness,
        "source_risk_level": risk_level,
        "freshness_risk": freshness,
        "extraction_quality": extraction_quality,
        "has_unique_useful_material": unique,
        "low_signal": low_signal,
        "include_mode": include,
        "relevance_to_promise": mem.get("topic_relevance") or "unclear",
        "useful_signal_count": signals,
        "usefulness_risk_score": risk_score,
    }


def apply_source_usefulness(memory: dict[str, Any]) -> dict[str, Any]:
    """Attach usefulness fields onto Source Memory (internal only)."""
    assessment = assess_source_usefulness(memory)
    memory.update(assessment)
    if assessment.get("low_signal"):
        notes = list(memory.get("relevance_notes") or [])
        note = (
            "low_signal source — keep brief candidate notes only; "
            "exclude from expensive full-context lesson dumps"
        )
        if note not in notes:
            notes.append(note)
        memory["relevance_notes"] = notes[:12]
    return memory


def format_low_signal_snippet(memory: dict[str, Any], *, max_chars: int = LOW_SIGNAL_BRIEF_MAX_CHARS) -> str:
    """Cheap prompt material for low-value / high-risk sources."""
    title = memory.get("title") or "Source"
    parts = [
        f"[LOW_SIGNAL RAW MATERIAL — {title} — brief candidates only; not authority]",
    ]
    concepts = list(
        memory.get("useful_concepts")
        or memory.get("rebuild_candidates")
        or memory.get("extracted_facts")
        or memory.get("facts")
        or []
    )[:3]
    if concepts:
        parts.append("Candidates:\n- " + "\n- ".join(str(c)[:160] for c in concepts if c))
    warns = list(memory.get("outdated_warnings") or [])[:2]
    if warns:
        parts.append("Verify:\n- " + "\n- ".join(str(w)[:120] for w in warns))
    flags = list(memory.get("source_risk_flags") or [])[:4]
    if flags:
        parts.append("Risk flags: " + ", ".join(flags))
    if memory.get("map_structure_not_authority") or memory.get("map_hints_not_authority"):
        parts.append("Source headings/modules are NOT course map authority.")
    if memory.get("outdated_warnings") and "Verify:" not in "\n".join(parts):
        warns = list(memory.get("outdated_warnings") or [])[:2]
        parts.append("Verify:\n- " + "\n- ".join(str(w)[:120] for w in warns))
    text = "\n\n".join(parts).strip()
    return text[:max_chars] if len(text) > max_chars else text


def should_use_brief_candidates(memory: dict[str, Any] | None) -> bool:
    if not memory:
        return False
    if memory.get("low_signal"):
        return True
    return memory.get("include_mode") == "brief_candidates"
