"""FakeProvider unit tests; no test generates a complete course."""

from app.ai.fake_provider import FakeProvider
from app.ai.provider import (
    AIProvider,
    BuildCourseMapInput,
    CourseBrief,
    FinalReviewInput,
    RebuildFinalCourseInput,
    ReviewSingleReelInput,
    WriteSingleReelInput,
)
from app.models.enums import ExplanationLevel, StructureMode
from app.schemas.generation import ReviewStatus

provider = FakeProvider()


def test_retired_no_effect_review_methods_are_not_provider_surface() -> None:
    for method in ("review_five_reels", "review_module", "review_two_modules"):
        assert not hasattr(AIProvider, method)
        assert not hasattr(FakeProvider, method)


def _brief() -> CourseBrief:
    return CourseBrief(
        title="Intro to Excel Formulas",
        audience="new hires",
        outcome="can build a basic budget sheet",
        structure_mode=StructureMode.CONNECTED_NO_MODULES,
        explanation_level=ExplanationLevel.FINAL_ONLY,
    )


def test_build_course_map_is_deterministic():
    input_ = BuildCourseMapInput(brief=_brief())

    first = provider.build_course_map(input_)
    second = provider.build_course_map(input_)

    assert first == second
    assert first.course_title == "Intro to Excel Formulas"
    assert len(first.modules) == FakeProvider.DEFAULT_MODULE_COUNT
    assert all(len(m.reels) == FakeProvider.DEFAULT_REELS_PER_MODULE for m in first.modules)
    # Structured module projects on every module; legacy bridge stays unused.
    assert first.modules[-1].bridge_project is None
    assert all(m.module_project is not None for m in first.modules)
    assert first.graduation_project is not None


def test_write_single_reel_is_deterministic_and_uses_the_plan():
    course_map = provider.build_course_map(BuildCourseMapInput(brief=_brief()))
    module = course_map.modules[0]
    reel_plan = module.reels[0]

    write_input = WriteSingleReelInput(
        course_title=course_map.course_title,
        main_thread=course_map.main_thread,
        module=module,
        reel=reel_plan,
    )

    first = provider.write_single_reel(write_input)
    second = provider.write_single_reel(write_input)

    assert first == second
    assert first.reel_id == reel_plan.reel_id
    assert first.module_id == module.module_id
    assert first.self_check_status == ReviewStatus.PASS
    assert first.script_text  # non-empty
    for point in reel_plan.must_cover:
        assert point in first.used_ideas


def _single_lesson_case():
    """Build a map but write exactly one lesson with the zero-network fake."""
    course_map = provider.build_course_map(BuildCourseMapInput(brief=_brief()))
    module = course_map.modules[0]
    reel_plan = module.reels[0]
    generated = provider.write_single_reel(
        WriteSingleReelInput(
            course_title=course_map.course_title,
            main_thread=course_map.main_thread,
            module=module,
            reel=reel_plan,
            lesson_semantic_contract=reel_plan.lesson_semantic_contract,
        )
    )
    one_reel_map = course_map.model_copy(
        update={
            "modules": [
                module.model_copy(update={"reels": [reel_plan]})
            ]
        }
    )
    return one_reel_map, generated


def test_review_single_reel_passes_for_normal_reel():
    course_map, reel = _single_lesson_case()
    reel_plan = course_map.modules[0].reels[0]

    result = provider.review_single_reel(
        ReviewSingleReelInput(reel_plan=reel_plan, generated_reel=reel)
    )

    assert result.status == ReviewStatus.PASS
    assert result.actions == []


def test_review_single_reel_flags_empty_script():
    course_map, reel = _single_lesson_case()
    reel_plan = course_map.modules[0].reels[0]
    broken_reel = reel.model_copy(update={"script_text": ""})

    result = provider.review_single_reel(
        ReviewSingleReelInput(reel_plan=reel_plan, generated_reel=broken_reel)
    )

    assert result.status == ReviewStatus.NEEDS_REVISION
    assert len(result.actions) == 1
    assert result.actions[0].action == "rewrite"
    assert result.actions[0].target_id == broken_reel.reel_id


def test_final_review_passes_for_one_normal_lesson():
    course_map, reel = _single_lesson_case()
    final_result = provider.final_review(
        FinalReviewInput(course_map=course_map, all_reels=[reel])
    )

    assert final_result.status == ReviewStatus.PASS


def test_rebuild_final_course_assembles_all_reel_text():
    course_map, reel = _single_lesson_case()
    all_reels = [reel]
    final_review = provider.final_review(
        FinalReviewInput(course_map=course_map, all_reels=all_reels)
    )

    final_course = provider.rebuild_final_course(
        RebuildFinalCourseInput(
            course_map=course_map, all_reels=all_reels, final_review=final_review
        )
    )

    assert final_course.title == course_map.course_title
    assert [m.module_id for m in final_course.modules] == [
        m.module_id for m in course_map.modules
    ]
    for final_module, planned_module in zip(final_course.modules, course_map.modules):
        assert final_module.title == planned_module.title
        assert final_module.bridge_project == planned_module.bridge_project
        assert len(final_module.reels) == len(planned_module.reels)
        for final_reel, planned_reel in zip(final_module.reels, planned_module.reels):
            assert final_reel.reel_id == planned_reel.reel_id
            assert final_reel.script_text  # non-empty

    for reel in all_reels:
        assert reel.script_text in final_course.full_text
    # Module projects are structured on FinalModule; spoken full_text is scripts only.
    for module, final_module in zip(course_map.modules, final_course.modules):
        if module.module_project is not None:
            assert final_module.module_project is not None
