"""Local checks for Dynamic Teaching Curve anti-flatness / anti-overperformance.

Operates on planned lesson_curves (and optionally delivered scripts). Pure
heuristics — no AI. Internal only; never written into DOCX.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from app.generation.teaching_curves import LessonCurve
from app.schemas.generation import GeneratedReel
from app.validators.high_signal_checker import OVERHYPED_PATTERNS


@dataclass
class TeachingCurveIssue:
    reason_code: str
    target_id: str
    detail: str


def _majority_same(values: list[str], *, min_n: int = 3) -> str | None:
    if len(values) < min_n:
        return None
    value, count = Counter(values).most_common(1)[0]
    if count >= max(min_n, (len(values) + 1) // 2 + (1 if len(values) >= 4 else 0)):
        # Majority: more than half (strict for 3+: at least 2 of 3, or clear mode).
        if count / len(values) >= 0.67:
            return value
    return None


def check_anti_flatness(
    lesson_curves: list[LessonCurve],
    *,
    module_id: str = "module",
) -> list[TeachingCurveIssue]:
    """Flag a module whose planned curves are effectively one repeated machine."""
    if len(lesson_curves) < 3:
        return []

    issues: list[TeachingCurveIssue] = []
    lengths = [c.natural_length for c in lesson_curves]
    if _majority_same(lengths):
        issues.append(
            TeachingCurveIssue(
                reason_code="flat_same_length",
                target_id=module_id,
                detail=(
                    "Most lessons share the same natural_length - vary short/medium/"
                    "long/extended so the module does not feel chopped from one text."
                ),
            )
        )

    hooks = [c.hook_strength for c in lesson_curves]
    if _majority_same(hooks) and len(set(hooks)) == 1:
        issues.append(
            TeachingCurveIssue(
                reason_code="flat_same_hook_shape",
                target_id=module_id,
                detail=(
                    "Every lesson uses the same hook_strength family - rotate quiet/"
                    "medium/strong by idea, not by habit."
                ),
            )
        )

    endings = [c.ending_motion for c in lesson_curves]
    if _majority_same(endings) and len(set(endings)) == 1:
        issues.append(
            TeachingCurveIssue(
                reason_code="flat_same_ending",
                target_id=module_id,
                detail=(
                    "Every lesson uses the same ending_motion - mix clean closes, "
                    "soft next-needs, and no_loop_needed."
                ),
            )
        )

    energies = [c.teaching_energy for c in lesson_curves]
    if _majority_same(energies) and len(set(energies)) == 1:
        issues.append(
            TeachingCurveIssue(
                reason_code="flat_same_intensity",
                target_id=module_id,
                detail=(
                    "Every lesson stays at the same teaching_energy - rise and fall "
                    "unless the module truly demands calm precision throughout."
                ),
            )
        )

    modes = [c.explanation_mode for c in lesson_curves]
    if _majority_same(modes) and len(set(modes)) == 1:
        issues.append(
            TeachingCurveIssue(
                reason_code="flat_same_example_mode",
                target_id=module_id,
                detail=(
                    "Every lesson uses the same explanation_mode - do not recycle one "
                    "scenario shape for the whole module."
                ),
            )
        )

    return issues


def check_anti_overperformance(
    lesson_curves: list[LessonCurve],
    reels: list[GeneratedReel] | None = None,
    *,
    module_id: str = "module",
) -> list[TeachingCurveIssue]:
    """Flag overhyped / fake-viral planning or delivery on ordinary teaching."""
    issues: list[TeachingCurveIssue] = []
    if not lesson_curves:
        return issues

    strong_hooks = sum(1 for c in lesson_curves if c.hook_strength == "strong")
    shock_tension = sum(1 for c in lesson_curves if c.tension_curve == "shock_then_explain")
    excited = sum(1 for c in lesson_curves if c.teaching_energy == "excited")
    n = len(lesson_curves)

    if n >= 3 and strong_hooks / n >= 0.67:
        issues.append(
            TeachingCurveIssue(
                reason_code="overperformed_hooks",
                target_id=module_id,
                detail=(
                    "Too many lessons plan strong/shocking openings - ordinary points "
                    "must not be treated as viral bait."
                ),
            )
        )

    if n >= 3 and shock_tension / n >= 0.5:
        issues.append(
            TeachingCurveIssue(
                reason_code="overperformed_shock",
                target_id=module_id,
                detail=(
                    "Too many shock_then_explain tension curves - reserve shock for "
                    "ideas that deserve it."
                ),
            )
        )

    if n >= 3 and excited / n >= 0.67:
        issues.append(
            TeachingCurveIssue(
                reason_code="overperformed_energy",
                target_id=module_id,
                detail=(
                    "Teaching energy stays excited across most lessons - lecturer "
                    "sounds like performing, not teaching."
                ),
            )
        )

    if reels:
        hyped = 0
        for reel in reels:
            text = reel.script_text or ""
            if any(re.search(p, text, re.IGNORECASE) for p in OVERHYPED_PATTERNS):
                hyped += 1
        if len(reels) >= 2 and hyped >= 2:
            issues.append(
                TeachingCurveIssue(
                    reason_code="overperformed_sales_tone",
                    target_id=reels[-1].reel_id,
                    detail=(
                        "Multiple lessons use overhyped/sales openers - useful teaching "
                        "beats emotional prose and viral heat."
                    ),
                )
            )

    return issues


def quiet_lesson_is_allowed(curve: LessonCurve) -> bool:
    """Quiet educational lessons are valid planning outcomes, not defects."""
    return curve.hook_strength == "quiet" and curve.teaching_energy in (
        "calm",
        "precise",
        "restrained",
        "analytical",
        "warm",
    )


def length_choice_is_allowed(curve: LessonCurve) -> bool:
    """Short complete, long connected, and quiet deep lessons are all allowed."""
    return curve.natural_length in ("short", "medium", "long", "extended")
