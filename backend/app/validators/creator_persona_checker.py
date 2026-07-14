"""Local checks for synthetic creator-persona failures (internal only)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.generation.creator_persona import LessonPersonaState
from app.schemas.generation import GeneratedReel
from app.validators.high_signal_checker import OVERHYPED_PATTERNS

# Anti-imitation: named-creator / clone cues (generic — not pointing at anyone).
NAMED_CREATOR_IMITATION_PATTERNS: tuple[str, ...] = (
    r"زي ما بيقول\s+\w+",
    r"exactly like\s+\w+\s+says",
    r"as\s+\w+\s+always says",
    r"signature catchphrase",
    r"copy\s+\w+'s\s+style",
    r"imitate\s+creator",
)

# Stacked fake "AI Egyptian" performance slang (heuristic).
FAKE_EGYPTIAN_AI_PATTERNS: tuple[str, ...] = (
    r"يا معلم يا برنس",
    r"يا نجم السوشيال",
    r"خد عندك الكلام ده يا صاحبي يا وحش",
    r"هجيبلك الفلو ودراعك",
    r"AI Egyptian vibe",
)

# Superlative spam: "everything is biggest/most important/most dangerous".
SUPERLATIVE_SPAM_PATTERNS: tuple[str, ...] = (
    r"أكبر",
    r"أخطر",
    r"أكتر حاجة",
    r"الأهم على الإطلاق",
    r"\bbiggest\b",
    r"\bmost important\b",
    r"\bmost dangerous\b",
    r"\bnever seen before\b",
)

# Flow/source template residue that should never be spoken as style.
FLOW_TEMPLATE_LEAK_PATTERNS: tuple[str, ...] = (
    r"human_flow_profile",
    r"flow_reference",
    r"pacing_profile",
    r"as in the transcript template",
    r"following the creator template",
)


@dataclass
class CreatorPersonaIssue:
    reason_code: str
    target_id: str
    detail: str


def _find_all(patterns: tuple[str, ...], text: str) -> list[str]:
    hits: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text or "", flags=re.IGNORECASE):
            hits.append(match.group(0))
    return hits


def check_creator_persona_script(
    script_text: str,
    *,
    reel_id: str = "reel",
    lesson_persona: LessonPersonaState | None = None,
) -> list[CreatorPersonaIssue]:
    """Per-script persona / anti-imitation / anti-fake-AI checks."""
    text = script_text or ""
    issues: list[CreatorPersonaIssue] = []

    for hit in _find_all(NAMED_CREATOR_IMITATION_PATTERNS, text):
        issues.append(
            CreatorPersonaIssue(
                reason_code="named_creator_imitation",
                target_id=reel_id,
                detail=(
                    f"Imitation cue '{hit}' - persona is synthetic; never clone a "
                    "named creator, catchphrase, or signature line."
                ),
            )
        )

    for hit in _find_all(FAKE_EGYPTIAN_AI_PATTERNS, text):
        issues.append(
            CreatorPersonaIssue(
                reason_code="fake_egyptian_ai_tone",
                target_id=reel_id,
                detail=(
                    f"Fake AI-Egyptian performance slang '{hit}' - use clean spoken "
                    "lecturer Arabic, not costume slang."
                ),
            )
        )

    superlatives = _find_all(SUPERLATIVE_SPAM_PATTERNS, text)
    if len(superlatives) >= 3:
        issues.append(
            CreatorPersonaIssue(
                reason_code="superlative_spam",
                target_id=reel_id,
                detail=(
                    "Too many biggest/most-important/most-dangerous claims - "
                    "strength comes from insight, not stacked superlatives."
                ),
            )
        )

    for hit in _find_all(FLOW_TEMPLATE_LEAK_PATTERNS, text):
        issues.append(
            CreatorPersonaIssue(
                reason_code="flow_template_leak",
                target_id=reel_id,
                detail=(
                    f"Flow/template residue '{hit}' must not appear in spoken script; "
                    "flow_reference informs mechanics only."
                ),
            )
        )

    if lesson_persona is not None:
        intent = lesson_persona.viral_intent
        hyped = any(re.search(p, text, re.I) for p in OVERHYPED_PATTERNS)
        if intent in ("quiet_useful", "technical_spine") and hyped:
            issues.append(
                CreatorPersonaIssue(
                    reason_code="viral_when_should_be_quiet",
                    target_id=reel_id,
                    detail=(
                        "Lesson persona marked quiet/technical, but script uses "
                        "overhyped viral bait - keep heat off ordinary spine lessons."
                    ),
                )
            )
        if intent == "corrective_strong" and lesson_persona.confidence_heat == "quiet":
            # Planning inconsistency is rare; don't fail scripts for it.
            pass

    return issues


def check_persona_allows_calm_non_viral(state: LessonPersonaState) -> bool:
    return state.viral_intent in ("quiet_useful", "technical_spine") and state.confidence_heat in (
        "quiet",
        "measured",
    )


def check_persona_allows_strong_corrective(state: LessonPersonaState) -> bool:
    return (
        state.viral_intent == "corrective_strong"
        and state.confidence_heat in ("firm", "corrective_heat")
    )


def flat_machine_script_flagged(reels: list[GeneratedReel]) -> bool:
    """True when openings+lengths look chopped from one machine text."""
    if len(reels) < 3:
        return False
    openings: list[str] = []
    word_counts: list[int] = []
    for r in reels:
        lines = (r.script_text or "").strip().splitlines()
        first = (lines[0] if lines else "").strip().lower()
        words = re.findall(r"[\w\u0600-\u06FF]+", first)
        openings.append(" ".join(words[:4]))
        word_counts.append(len(re.findall(r"[\w\u0600-\u06FF]+", r.script_text or "")))

    nonempty = [o for o in openings if o]
    if nonempty and len(set(nonempty)) == 1:
        return True
    mean = sum(word_counts) / len(word_counts)
    if mean > 0 and max(abs(c - mean) / mean for c in word_counts) < 0.08:
        return True
    return False
