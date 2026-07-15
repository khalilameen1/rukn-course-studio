"""Transcript topic relevance — same-topic raw material vs off-topic colloquial only."""

from __future__ import annotations

import re
from typing import Any, Literal

TopicRelevance = Literal["same_topic", "adjacent_topic", "off_topic", "unclear"]

TRANSCRIPT_RELEVANCE_VERSION = "1.0"

SAME_TOPIC_TRANSCRIPT_LABEL = (
    "This transcript is same-topic course raw material. Extract useful ideas, "
    "objections, distinctions, and practical points only. Do not copy wording, "
    "hooks, loops, structure, examples verbatim, or speaker style. Verify "
    "current/tool-related claims before use. Rebuild everything in ROKN "
    "teleprompter format."
)

OFF_TOPIC_TRANSCRIPT_LABEL = (
    "This transcript is only for natural colloquial calibration. Use it only to "
    "avoid stiff, translated, or robotic Arabic. It has zero factual, structural, "
    "hook, or example authority."
)

ADJACENT_TOPIC_TRANSCRIPT_LABEL = (
    "This transcript is adjacent-topic course raw material. Use conservatively — "
    "extract only clearly relevant ideas after verifying fit to the course promise. "
    "Do not copy wording, hooks, loops, structure, or speaker style."
)

UNCLEAR_TRANSCRIPT_LABEL = (
    "This transcript topic fit is unclear. Use conservatively — minimal extraction "
    "only; verify every point against the course promise and official docs before use. "
    "Never copy wording, hooks, loops, or structure."
)

_WORD_RE = re.compile(r"[\w\u0600-\u06FF]{3,}")
_STOP = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "this",
        "that",
        "from",
        "your",
        "you",
        "are",
        "how",
        "what",
        "when",
        "about",
        "course",
        "lesson",
        "module",
        "في",
        "من",
        "على",
        "إلى",
        "أن",
        "هذا",
        "هذه",
        "اللي",
        "كورس",
        "درس",
    }
)


_DELIVERY_ARTIFACT_RE = re.compile(
    r"(?i)(?:\bhook\b|cliffhanger|shocking|viral|catchphrase|signature line|"
    r"stay until the end|don't skip|click like|forever champions|"
    r"module\s+(?:one|two|three|\d+).{0,40}module)"
)


def _is_delivery_artifact_line(line: str) -> bool:
    return bool(_DELIVERY_ARTIFACT_RE.search(line or ""))


def scrub_transcript_delivery_artifacts(memory: dict[str, Any]) -> dict[str, Any]:
    """Remove hook/loop/structure lines from distilled transcript memory fields."""
    for key in (
        "facts",
        "extracted_facts",
        "useful_concepts",
        "rebuild_candidates",
        "useful_examples",
        "examples",
        "learner_objections",
        "practical_warnings",
        "mistakes_to_avoid",
    ):
        items = memory.get(key)
        if not isinstance(items, list):
            continue
        memory[key] = [ln for ln in items if ln and not _is_delivery_artifact_line(str(ln))]
    return memory


def _tokens(text: str) -> set[str]:
    return {
        t.lower()
        for t in _WORD_RE.findall(text or "")
        if t.lower() not in _STOP
    }


def classify_transcript_topic_relevance(
    transcript_text: str,
    *,
    course_title: str = "",
    audience: str = "",
    outcome: str = "",
    course_map_text: str = "",
    special_notes: str = "",
) -> TopicRelevance:
    """Heuristic topic relevance — not LLM; fast and deterministic."""
    promise_blob = " ".join(
        [course_title, audience, outcome, course_map_text, special_notes]
    ).strip()
    if not promise_blob:
        return "unclear"

    course_tokens = _tokens(promise_blob)
    transcript_tokens = _tokens(transcript_text)
    if not course_tokens or not transcript_tokens:
        return "unclear"

    overlap = course_tokens & transcript_tokens
    overlap_count = len(overlap)
    ratio = overlap_count / max(len(course_tokens), 1)

    if ratio >= 0.14 or overlap_count >= 10:
        return "same_topic"
    if ratio >= 0.05 or overlap_count >= 4:
        return "adjacent_topic"
    if ratio < 0.02 and overlap_count <= 1:
        return "off_topic"
    return "unclear"


def prompt_label_for_relevance(relevance: TopicRelevance) -> str:
    if relevance == "same_topic":
        return SAME_TOPIC_TRANSCRIPT_LABEL
    if relevance == "adjacent_topic":
        return ADJACENT_TOPIC_TRANSCRIPT_LABEL
    if relevance == "off_topic":
        return OFF_TOPIC_TRANSCRIPT_LABEL
    return UNCLEAR_TRANSCRIPT_LABEL


def is_transcript_colloquial_only(memory: dict[str, Any] | None) -> bool:
    if not memory:
        return False
    if memory.get("transcript_colloquial_only"):
        return True
    return memory.get("topic_relevance") == "off_topic"


def apply_transcript_relevance(
    memory: dict[str, Any],
    *,
    extracted_text: str,
    course_promise: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify transcript and set memory fields for compiler routing."""
    promise = course_promise or {}
    relevance = classify_transcript_topic_relevance(
        extracted_text,
        course_title=str(promise.get("title") or ""),
        audience=str(promise.get("audience") or ""),
        outcome=str(promise.get("outcome") or ""),
        course_map_text=str(promise.get("course_map_text") or ""),
        special_notes=str(promise.get("special_notes") or ""),
    )
    memory["topic_relevance"] = relevance
    memory["transcript_relevance_version"] = TRANSCRIPT_RELEVANCE_VERSION
    memory["transcript_prompt_label"] = prompt_label_for_relevance(relevance)

    if relevance == "off_topic":
        memory["transcript_colloquial_only"] = True
        memory["effective_category_mode"] = "natural_colloquial_calibration"
        try:
            from app.generation.prompt_compiler import build_flow_profile

            memory["flow_profile"] = build_flow_profile(extracted_text)
        except Exception:
            memory["flow_profile"] = None
        memory["extracted_facts"] = []
        memory["facts"] = []
        memory["useful_examples"] = []
        memory["examples"] = []
        memory["useful_concepts"] = []
        memory["rebuild_candidates"] = []
        memory["terminology"] = []
        memory["terminology_if_current"] = []
        memory["relevance_notes"] = [
            "Off-topic transcript — natural colloquial calibration only",
            "Zero factual, hook, structure, example, or terminology authority",
        ]
        memory["blocked_content_warnings"] = list(memory.get("blocked_content_warnings") or []) + [
            OFF_TOPIC_TRANSCRIPT_LABEL,
        ]
        return memory

    memory["transcript_colloquial_only"] = False
    memory["effective_category_mode"] = "distilled_raw_material"

    notes = list(memory.get("relevance_notes") or [])
    notes.append(prompt_label_for_relevance(relevance))
    if relevance == "unclear":
        notes.append("Unclear topic fit — extract minimally and verify heavily")
        memory["facts"] = list(memory.get("facts") or [])[:3]
        memory["extracted_facts"] = memory["facts"]
        memory["useful_concepts"] = list(memory.get("useful_concepts") or [])[:3]
        memory["rebuild_candidates"] = list(memory.get("rebuild_candidates") or [])[:2]
    elif relevance == "adjacent_topic":
        notes.append("Adjacent topic — keep only points that clearly serve the course promise")
    else:
        notes.append("Same-topic transcript — distilled raw material only; never copy delivery")

    memory["relevance_notes"] = notes[:8]
    blocked = list(memory.get("blocked_content_warnings") or [])
    blocked.extend(
        [
            "Never copy transcript wording, hooks, loops, structure, catchphrases, or speaker style",
            "Official current documentation overrides transcript tool/platform claims",
        ]
    )
    memory["blocked_content_warnings"] = blocked[:10]
    return memory


def format_transcript_colloquial_snippet(memory: dict[str, Any], *, max_chars: int = 900) -> str:
    """Off-topic transcript — flow profile only."""
    from app.generation.prompt_compiler import (
        NATURAL_COLLOQUIAL_CALIBRATION_LABEL,
        _FLOW_PROFILE_FIELD_ORDER,
        _THINGS_NOT_TO_COPY,
    )

    parts = [OFF_TOPIC_TRANSCRIPT_LABEL]
    profile = memory.get("flow_profile")
    if isinstance(profile, dict) and profile:
        fields_text = "; ".join(
            f"{field}: {profile[field]}"
            for field in _FLOW_PROFILE_FIELD_ORDER
            if field in profile
        )
        things_not_to_copy = "; ".join(profile.get("things_not_to_copy") or _THINGS_NOT_TO_COPY)
        parts.append(
            "Natural Colloquial Calibration (language naturalness sample only — "
            "NOT a flow, teaching, pacing, hook, or professional speaking reference): "
            f"{NATURAL_COLLOQUIAL_CALIBRATION_LABEL} "
            f"{fields_text}. Things not to copy from this source: {things_not_to_copy}."
        )
    text = "\n\n".join(parts).strip()
    return text[:max_chars] if len(text) > max_chars else text
