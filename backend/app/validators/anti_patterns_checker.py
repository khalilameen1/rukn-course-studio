"""Anti-pattern and quality-check validators (rejection layer only).

No positive golden samples — flags bad patterns for review/final rewrite.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.generation.teleprompter_readability import (
    looks_like_dense_paragraph,
    looks_like_word_per_line,
)
from app.schemas.generation import GeneratedReel
from app.validators.anti_template_checker import check_anti_template
from app.validators.creator_persona_checker import flat_machine_script_flagged
from app.validators.high_signal_checker import check_high_signal

# Extra template-hook bait beyond high_signal OVERHYPED_PATTERNS.
TEMPLATE_HOOK_PATTERNS: tuple[str, ...] = (
    r"محدش قالك",
    r"هتتصدم",
    r"في ناس لسه",
    r"المشكلة مش في .+ المشكلة في",
    r"nobody told you",
    r"you will be shocked",
)

# Admin Knowledge labels that must never leak into teleprompter DOCX.
ADMIN_KNOWLEDGE_LEAK_PHRASES: tuple[str, ...] = (
    "anti-patterns to reject",
    "rejected patterns and diagnostic",
    "quality checks before final rewrite",
    "rukn_anti_patterns_quality_checks",
    "rejection layer only",
    "do not copy as a style template",
)


@dataclass
class AntiPatternIssue:
    reason_code: str
    target_id: str
    detail: str


def _find_template_hook(text: str) -> str | None:
    for pattern in TEMPLATE_HOOK_PATTERNS:
        match = re.search(pattern, text or "", flags=re.IGNORECASE)
        if match:
            return match.group(0)
    return None


def check_anti_patterns_script(
    script_text: str,
    *,
    reel_id: str = "reel",
) -> list[AntiPatternIssue]:
    """Per-script rejection checks aligned with rukn_anti_patterns_quality_checks."""
    text = script_text or ""
    issues: list[AntiPatternIssue] = []

    hit = _find_template_hook(text)
    if hit:
        issues.append(
            AntiPatternIssue(
                reason_code="template_hook",
                target_id=reel_id,
                detail=(
                    f"Mechanical template hook '{hit}' — open from this lesson's "
                    "real tension, not a reusable bait formula."
                ),
            )
        )

    if looks_like_word_per_line(text):
        issues.append(
            AntiPatternIssue(
                reason_code="teleprompter_over_formatting",
                target_id=reel_id,
                detail=(
                    "One-word-per-line teleprompter formatting — use readable "
                    "spoken lines and natural breath breaks."
                ),
            )
        )

    if looks_like_dense_paragraph(text):
        issues.append(
            AntiPatternIssue(
                reason_code="teleprompter_dense_paragraph",
                target_id=reel_id,
                detail=(
                    "Dense paragraph block — break into teleprompter-readable "
                    "lines with natural pauses."
                ),
            )
        )

    if re.search(r"(?i)\[\s*(?:pause|breath|silence)\s*\]|\(\s*(?:pause|breath)\s*\)", text):
        issues.append(
            AntiPatternIssue(
                reason_code="teleprompter_pause_labels",
                target_id=reel_id,
                detail=(
                    "Stage-direction pause labels — formatting should guide "
                    "breath; never speak [pause] or [breath]."
                ),
            )
        )

    # Delegate doctrine-aligned anti-patterns already covered elsewhere.
    for hs in check_high_signal(text):
        if hs.reason_code in ("overhyped_hook", "forced_loop", "academic_tone"):
            issues.append(
                AntiPatternIssue(
                    reason_code=hs.reason_code,
                    target_id=reel_id,
                    detail=hs.detail,
                )
            )

    return issues


def find_admin_knowledge_leaks(plain_docx_text: str) -> list[str]:
    """Phrases from anti-pattern admin guidance that must not appear in DOCX."""
    hay = (plain_docx_text or "").lower()
    return [p for p in ADMIN_KNOWLEDGE_LEAK_PHRASES if p.lower() in hay]


def scripts_avoid_template_writing(reels: list[GeneratedReel]) -> bool:
    """True when scripts vary openings/length and avoid mechanical devices."""
    if len(reels) < 2:
        return True
    if flat_machine_script_flagged(reels):
        return False
    return not check_anti_template(reels)


def article_has_no_positive_golden_samples(text: str) -> bool:
    """Anti-pattern article must not ship reusable good examples."""
    lower = (text or "").lower()
    if "example spoken-style lines" in lower:
        return False
    if re.search(r'^-\s*".+"', text or "", flags=re.MULTILINE):
        return False
    if "add more real examples here" in lower:
        return False
    return True
