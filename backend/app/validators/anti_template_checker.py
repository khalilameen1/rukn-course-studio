"""Cross-reel anti-template checks (module / five-reel window).

Deterministic heuristics for canonical course-level quality rules:
rules: same hook family, same loop move, equal lengths, mechanical devices.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from app.schemas.generation import GeneratedReel

MECHANICAL_DEVICE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("practical_application", r"تطبيق عملي|practical application"),
    ("exception", r"\bexception\b|الاستثناء"),
    ("mistake", r"الغلط الشائع|common mistake"),
    ("secret", r"\bsecret\b|السر"),
)

FORCED_LOOP_TAIL = re.compile(
    r"(في الريل الجاي|في الجزء الجاي|in the next reel|stay tuned)",
    re.IGNORECASE,
)


@dataclass
class AntiTemplateIssue:
    reason_code: str
    target_id: str
    detail: str


def _opening_family(script: str) -> str:
    first = (script or "").strip().splitlines()[0] if (script or "").strip() else ""
    words = re.findall(r"[\w\u0600-\u06FF]+", first.lower())
    return " ".join(words[:4])


def _word_count(script: str) -> int:
    return len(re.findall(r"[\w\u0600-\u06FF]+", script or ""))


def check_anti_template(reels: list[GeneratedReel]) -> list[AntiTemplateIssue]:
    """Issues visible only across a set of reels in one module/window."""
    if len(reels) < 2:
        return []

    issues: list[AntiTemplateIssue] = []

    openings = [_opening_family(r.script_text) for r in reels]
    opening_counts = Counter(o for o in openings if o)
    for opening, count in opening_counts.items():
        if count >= 2 and opening:
            targets = [r.reel_id for r, o in zip(reels, openings) if o == opening]
            issues.append(
                AntiTemplateIssue(
                    reason_code="repeated_hook_family",
                    target_id=targets[-1],
                    detail=(
                        f"Hook family '{opening}' repeats across {count} reels "
                        "- open with different idea families."
                    ),
                )
            )

    looped = [r for r in reels if FORCED_LOOP_TAIL.search(r.script_text or "")]
    if len(looped) >= 2:
        issues.append(
            AntiTemplateIssue(
                reason_code="repeated_loop_move",
                target_id=looped[-1].reel_id,
                detail=(
                    "Multiple reels use the same forced next-part loop move - "
                    "vary endings; prefer organic cuts."
                ),
            )
        )

    counts = [_word_count(r.script_text) for r in reels]
    if len(counts) >= 3:
        mean = sum(counts) / len(counts)
        if mean > 0:
            spreads = [abs(c - mean) / mean for c in counts]
            if max(spreads) < 0.08:
                issues.append(
                    AntiTemplateIssue(
                        reason_code="equal_length_padding",
                        target_id=reels[-1].reel_id,
                        detail=(
                            "Reel lengths are nearly identical - length must "
                            "follow each idea, not a fixed quota."
                        ),
                    )
                )

    for device_id, pattern in MECHANICAL_DEVICE_PATTERNS:
        hits = [r for r in reels if re.search(pattern, r.script_text or "", re.IGNORECASE)]
        if len(hits) == len(reels) and len(reels) >= 3:
            issues.append(
                AntiTemplateIssue(
                    reason_code="mechanical_device",
                    target_id=hits[-1].reel_id,
                    detail=(
                        f"Device '{device_id}' appears in every reel - do not "
                        "apply the same structural gadget mechanically."
                    ),
                )
            )

    recap_openers = 0
    for r in reels:
        first = ((r.script_text or "").strip().splitlines() or [""])[0]
        if re.search(r"(زي ما قولنا|في الريل اللي فات|as we said|previously we)", first, re.I):
            recap_openers += 1
    if recap_openers >= 2:
        issues.append(
            AntiTemplateIssue(
                reason_code="recap_openers",
                target_id=reels[-1].reel_id,
                detail=(
                    "Multiple reels open with a recap - standalone social "
                    "reels must not re-teach the previous reel at the start."
                ),
            )
        )

    return issues
