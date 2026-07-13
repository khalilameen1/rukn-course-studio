"""Tests for FakeProvider - determinism plus a full pipeline dry run."""

from app.ai.fake_provider import FakeProvider
from app.ai.provider import (
    BuildCourseMapInput,
    CourseBrief,
    FinalReviewInput,
    ModuleWithReels,
    RebuildFinalCourseInput,
    ReviewFiveReelsInput,
    ReviewModuleInput,
    ReviewSingleReelInput,
    ReviewTwoModulesInput,
    WriteSingleReelInput,
)
from app.models.enums import ExplanationLevel, StructureMode
from app.schemas.generation import GeneratedReel, ReviewStatus

provider = FakeProvider()


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
    # Last module has no bridge project; earlier ones do.
    assert first.modules[-1].bridge_project is None
    assert all(m.bridge_project for m in first.modules[:-1])


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


def _full_pipeline_run():
    """Build a map, write every reel, then run every review stage + rebuild."""
    course_map = provider.build_course_map(BuildCourseMapInput(brief=_brief()))

    all_reels: list[GeneratedReel] = []
    for module in course_map.modules:
        for reel_plan in module.reels:
            generated = provider.write_single_reel(
                WriteSingleReelInput(
                    course_title=course_map.course_title,
                    main_thread=course_map.main_thread,
                    module=module,
                    reel=reel_plan,
                )
            )
            all_reels.append(generated)

    return course_map, all_reels


def test_review_single_reel_passes_for_normal_reel():
    course_map, all_reels = _full_pipeline_run()
    reel = all_reels[0]
    reel_plan = course_map.modules[0].reels[0]

    result = provider.review_single_reel(
        ReviewSingleReelInput(reel_plan=reel_plan, generated_reel=reel)
    )

    assert result.status == ReviewStatus.PASS
    assert result.actions == []


def test_review_single_reel_flags_empty_script():
    course_map, all_reels = _full_pipeline_run()
    reel_plan = course_map.modules[0].reels[0]
    broken_reel = all_reels[0].model_copy(update={"script_text": ""})

    result = provider.review_single_reel(
        ReviewSingleReelInput(reel_plan=reel_plan, generated_reel=broken_reel)
    )

    assert result.status == ReviewStatus.NEEDS_REVISION
    assert len(result.actions) == 1
    assert result.actions[0].action == "rewrite"
    assert result.actions[0].target_id == broken_reel.reel_id


def test_review_five_reels_and_module_pass_for_normal_reels():
    course_map, all_reels = _full_pipeline_run()
    module = course_map.modules[0]
    module_reels = [r for r in all_reels if r.module_id == module.module_id]

    five_result = provider.review_five_reels(ReviewFiveReelsInput(reels=module_reels))
    module_result = provider.review_module(
        ReviewModuleInput(module=module, reels=module_reels)
    )

    assert five_result.status == ReviewStatus.PASS
    assert module_result.status == ReviewStatus.PASS


def test_review_two_modules_and_final_review_pass_for_full_course():
    course_map, all_reels = _full_pipeline_run()

    module_reels = [
        ModuleWithReels(
            module=module,
            reels=[r for r in all_reels if r.module_id == module.module_id],
        )
        for module in course_map.modules
    ]

    two_module_result = provider.review_two_modules(
        ReviewTwoModulesInput(first=module_reels[0], second=module_reels[1])
    )
    final_result = provider.final_review(
        FinalReviewInput(course_map=course_map, all_reels=all_reels)
    )

    assert two_module_result.status == ReviewStatus.PASS
    assert final_result.status == ReviewStatus.PASS


def test_rebuild_final_course_assembles_all_reel_text():
    course_map, all_reels = _full_pipeline_run()
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
    for module in course_map.modules:
        if module.bridge_project:
            assert module.bridge_project in final_course.full_text
