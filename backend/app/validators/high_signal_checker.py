"""Local checks for rukn_high_signal_reel_doctrine failures.

Plain substring / regex heuristics - no AI. Used before the AI review call
(see orchestrator `_local_review_single_reel`) and by golden tests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Overhyped / bait openers and claims (Arabic + a few English clickbait
# strings that should never leak into a Rukn teleprompter script).
OVERHYPED_PATTERNS: tuple[str, ...] = (
    r"السر اللي محدش",
    r"هيغير حيات",
    r"أخطر حاجة",
    r"أكبر غلط",
    r"أكبر سر",
    r"أكتر حاجة",
    r"this will destroy",
    r"secret no one knows",
    r"most dangerous",
    r"biggest mistake",
    r"you won't believe",
)

# Forced next-reel / cliffhanger announcements.
FORCED_LOOP_PATTERNS: tuple[str, ...] = (
    r"في الريل الجاي",
    r"في الجزء الجاي",
    r"في الفيديو الجاي",
    r"استنوا الجزء",
    r"خليكم معانا في",
    r"in the next reel",
    r"in the next video",
    r"wait for the next",
    r"stay tuned",
)

# Blatantly imported / luxury contexts that usually fail locality for
# Egyptian/Arab practical-skill students (soft heuristic - a real Shopify
# course may name Shopify; the golden suite plants these intentionally).
UNREALISTIC_EXAMPLE_PATTERNS: tuple[str, ...] = (
    r"\bFortune 500\b",
    r"\bSilicon Valley\b",
    r"Ferrari",
    r"يخت فخم",
    r"مليون دولار ميزانية إعلان",
)

# Academic / essay markers that should not dominate spoken script.
ACADEMIC_TONE_PATTERNS: tuple[str, ...] = (
    r"في ضوء ما سبق",
    r"ومن ثمَّ? فإنه",
    r"يتضح مما سبق",
    r"learning objectives",
    r"as aforementioned",
    r"in conclusion,? it can be said",
)

# Generic low-signal platitudes.
GENERIC_ADVICE_PATTERNS: tuple[str, ...] = (
    r"مهم إنك تركز",
    r"خلّيك إيجابي",
    r"اسعى للنجاح",
    r"just be consistent",
    r"believe in yourself",
    r"work hard and you will succeed",
)


@dataclass
class HighSignalIssue:
    reason_code: str
    detail: str


def _find(patterns: tuple[str, ...], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(0)
    return None


def check_high_signal(script_text: str) -> list[HighSignalIssue]:
    """Fail-loud local doctrine violations for one reel script."""
    text = script_text or ""
    issues: list[HighSignalIssue] = []

    hit = _find(OVERHYPED_PATTERNS, text)
    if hit:
        issues.append(
            HighSignalIssue(
                reason_code="overhyped_hook",
                detail=(
                    f"Overhyped / bait language '{hit}' - open with a "
                    "meaningful idea, not hype."
                ),
            )
        )

    hit = _find(FORCED_LOOP_PATTERNS, text)
    if hit:
        issues.append(
            HighSignalIssue(
                reason_code="forced_loop",
                detail=(
                    f"Forced next-part announcement '{hit}' - end on a "
                    "natural cut, never announce the next reel."
                ),
            )
        )

    hit = _find(UNREALISTIC_EXAMPLE_PATTERNS, text)
    if hit:
        issues.append(
            HighSignalIssue(
                reason_code="unrealistic_example",
                detail=(
                    f"Unrealistic / imported example context '{hit}' - use "
                    "local Egyptian/Arab learner reality instead."
                ),
            )
        )

    hit = _find(ACADEMIC_TONE_PATTERNS, text)
    if hit:
        issues.append(
            HighSignalIssue(
                reason_code="academic_tone",
                detail=(
                    f"Academic / essay tone '{hit}' - rewrite as clean "
                    "spoken lecturer Arabic."
                ),
            )
        )

    hit = _find(GENERIC_ADVICE_PATTERNS, text)
    if hit:
        issues.append(
            HighSignalIssue(
                reason_code="generic_advice",
                detail=(
                    f"Generic low-signal advice '{hit}' - replace with a "
                    "non-obvious distinction or practical correction."
                ),
            )
        )

    # Removable filler: very short padding sentences used repeatedly.
    sentences = [s.strip() for s in re.split(r"[.!?؟\n]+", text) if s.strip()]
    fillerish = [
        s
        for s in sentences
        if len(s.split()) <= 4
        and re.search(r"(مهم|ظبط|يلا|بكده|okay|so yeah)", s, re.IGNORECASE)
    ]
    if len(fillerish) >= 3:
        issues.append(
            HighSignalIssue(
                reason_code="removable_filler",
                detail=(
                    "Multiple short filler sentences look removable without "
                    "loss - tighten to high-signal speech only."
                ),
            )
        )

    return issues
