"""Lesson Blueprint helpers — every map lesson must justify independence."""

from __future__ import annotations

from dataclasses import dataclass

from app.generation.duration_policy import word_range_for
from app.models.enums import LessonDeliveryMode
from app.schemas.generation import ReelPlan


@dataclass
class BlueprintValidation:
    ok: bool
    errors: list[str]


def ensure_reel_blueprint_defaults(reel: ReelPlan) -> ReelPlan:
    """Fill missing blueprint fields for older maps / FakeProvider shells."""
    mode = reel.delivery_mode or LessonDeliveryMode.CAMERA_EXPLAINER
    rng = word_range_for(mode)
    updates: dict = {}
    if not reel.distinct_teaching_outcome:
        updates["distinct_teaching_outcome"] = (
            reel.purpose or reel.title or "teaching outcome"
        ).strip()
    if not reel.new_skill_or_decision:
        updates["new_skill_or_decision"] = (
            (reel.must_cover[0] if reel.must_cover else reel.purpose) or reel.title
        )
    if not reel.why_standalone:
        updates["why_standalone"] = (
            "Adds a distinct skill/decision that would be diluted if merged."
        )
    if not reel.student_can_do_after:
        updates["student_can_do_after"] = (
            f"يطبق: {reel.distinct_teaching_outcome or reel.purpose or reel.title}"
        )
    if reel.delivery_mode is None:
        updates["delivery_mode"] = LessonDeliveryMode.CAMERA_EXPLAINER
    if reel.target_spoken_words_min is None:
        updates["target_spoken_words_min"] = rng.target_min
    if reel.target_spoken_words_max is None:
        updates["target_spoken_words_max"] = rng.target_max
    if not reel.estimated_length:
        mid = (rng.target_min + rng.target_max) // 2
        # ~135 wpm → minutes label for legacy parsers
        minutes = max(1.0, mid / 135.0)
        updates["estimated_length"] = f"{minutes:.1f} minutes"
    if updates:
        return reel.model_copy(update=updates)
    return reel


def validate_lesson_blueprint(reel: ReelPlan) -> BlueprintValidation:
    errors: list[str] = []
    if not (reel.distinct_teaching_outcome or "").strip():
        errors.append(f"{reel.reel_id}: missing distinct_teaching_outcome")
    if not (reel.new_skill_or_decision or "").strip():
        errors.append(f"{reel.reel_id}: missing new_skill_or_decision")
    if not (reel.why_standalone or "").strip():
        errors.append(f"{reel.reel_id}: missing why_standalone")
    if not (reel.student_can_do_after or "").strip():
        errors.append(f"{reel.reel_id}: missing student_can_do_after")
    mode = reel.delivery_mode or LessonDeliveryMode.CAMERA_EXPLAINER
    needs_visual = mode in {
        LessonDeliveryMode.SCREEN_DEMO,
        LessonDeliveryMode.PROJECT_BUILD,
        LessonDeliveryMode.BEFORE_AFTER,
        LessonDeliveryMode.DESIGN_CRITIQUE,
        LessonDeliveryMode.CRITIQUE,
    }
    if needs_visual and reel.needs_screen_or_visual is False:
        errors.append(f"{reel.reel_id}: delivery_mode {mode.value} requires visual")
    if needs_visual and not reel.internal_visual_plan and not reel.required_assets:
        errors.append(
            f"{reel.reel_id}: screen/critique lesson needs internal_visual_plan "
            "or required_assets"
        )
    if mode == LessonDeliveryMode.MICRO_CONCEPT:
        # Micro concepts are narrow; empty must_cover is a shell.
        if not reel.must_cover:
            errors.append(f"{reel.reel_id}: MICRO_CONCEPT needs a concrete must_cover")
    return BlueprintValidation(ok=not errors, errors=errors)
