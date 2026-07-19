from __future__ import annotations

import pytest

from app.generation.errors import UnusableOutputError
from app.generation.orchestrator import (
    _assemble_final_course,
    _assert_final_review_actions_applied,
)
from app.schemas.generation import (
    CourseMap,
    GeneratedReel,
    ModulePlan,
    ReelPlan,
    ReviewAction,
    ReviewActionType,
    ReviewResult,
    ReviewScope,
    ReviewStatus,
)


def _case():
    plan = ReelPlan(
        reel_id="m1-r1",
        title="قرار واضح",
        purpose="تعليم قرار محدد",
        must_cover=["الشرط", "المثال"],
    )
    module = ModulePlan(
        module_id="m1",
        title="الموديول",
        purpose="تطبيق القرار",
        reels=[plan],
    )
    course_map = CourseMap(
        course_title="الكورس",
        main_thread="قرار ثم تطبيق",
        modules=[module],
    )
    reel = GeneratedReel(
        reel_id=plan.reel_id,
        module_id=module.module_id,
        title=plan.title,
        script_text="النص الأصلي يحتاج إصلاحا واضحا",
        self_check_status=ReviewStatus.PASS,
        quality_status="pass",
    )
    review = ReviewResult(
        scope=ReviewScope.FINAL,
        status=ReviewStatus.NEEDS_REVISION,
        actions=[
            ReviewAction(
                action=ReviewActionType.REWRITE,
                target_id=plan.reel_id,
                reason_code="serious_gap",
                instruction="أصلح الفجوة في النص",
                severity="serious",
                requires_rewrite=True,
            )
        ],
    )
    return course_map, reel, review


def test_final_review_cannot_pass_when_rebuild_leaves_target_unchanged() -> None:
    course_map, reel, review = _case()
    unchanged = _assemble_final_course(course_map, [reel])

    with pytest.raises(UnusableOutputError, match="were not applied"):
        _assert_final_review_actions_applied(
            course_map=course_map,
            original_reels=[reel],
            final_review=review,
            rebuilt_course=unchanged,
        )


def test_final_review_accepts_a_rebuild_that_changes_the_requested_target() -> None:
    course_map, reel, review = _case()
    changed = _assemble_final_course(
        course_map,
        [reel.model_copy(update={"script_text": "النص المعدل يطبق الإصلاح المطلوب"})],
    )

    _assert_final_review_actions_applied(
        course_map=course_map,
        original_reels=[reel],
        final_review=review,
        rebuilt_course=changed,
    )


def test_needs_revision_without_actionable_repairs_fails_closed() -> None:
    course_map, reel, review = _case()
    actionless = review.model_copy(update={"actions": []})

    with pytest.raises(UnusableOutputError, match="without an actionable repair"):
        _assert_final_review_actions_applied(
            course_map=course_map,
            original_reels=[reel],
            final_review=actionless,
            rebuilt_course=_assemble_final_course(course_map, [reel]),
        )
