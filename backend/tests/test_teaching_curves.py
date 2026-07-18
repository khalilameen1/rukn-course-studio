"""Tests for Dynamic Teaching Curve planning and anti-flatness checks."""

from app.ai.fake_provider import FakeProvider
from app.ai.provider import BuildCourseMapInput, CourseBrief, WriteSingleReelInput
from app.generation.teaching_curves import (
    LessonCurve,
    ModuleCurve,
    compact_lesson_curve_for_prompt,
    format_curves_for_prompt,
    plan_lesson_curve,
    plan_module_curve,
)
from app.generation.teleprompter_checks import find_forbidden_substrings
from app.models.enums import ExplanationLevel, StructureMode
from app.schemas.generation import (
    FinalCourse,
    FinalModule,
    FinalReel,
    GeneratedReel,
    ModulePlan,
    ReelPlan,
)
from app.services.docx_export import extract_plain_text, render_final_course_docx
from app.validators.teaching_curve_checker import (
    check_anti_flatness,
    check_anti_overperformance,
    length_choice_is_allowed,
    quiet_lesson_is_allowed,
)


def _module(idx: int, title: str, purpose: str, reel_count: int = 3) -> ModulePlan:
    reels = [
        ReelPlan(
            reel_id=f"m{idx}-r{r}",
            title=f"{title} lesson {r}",
            purpose=purpose,
            must_cover=[f"point {idx}.{r}"],
            estimated_length="varies",
        )
        for r in range(1, reel_count + 1)
    ]
    return ModulePlan(
        module_id=f"m{idx}",
        title=title,
        purpose=purpose,
        reels=reels,
    )


def test_module_planning_assigns_different_curves_across_modules():
    modules = [
        _module(1, "Foundations", "foundation overview intro"),
        _module(2, "Common mistakes", "correction of common mistake"),
        _module(3, "Build the offer", "practical build apply"),
        _module(4, "Deepening craft", "advanced difficult complex"),
    ]
    curves: list[ModuleCurve] = []
    prev = None
    for i, mod in enumerate(modules):
        curve = plan_module_curve(
            module=mod, module_index=i, total_modules=len(modules), previous_curve=prev
        )
        curves.append(curve)
        prev = curve

    roles = {c.module_role for c in curves}
    energies = {c.module_energy_curve for c in curves}
    assert len(roles) >= 3
    assert len(energies) >= 2
    assert curves[0].module_role == "foundation"


def test_lesson_planning_varies_length_depth_energy_inside_module():
    module = ModulePlan(
        module_id="m1",
        title="Ads basics",
        purpose="module shell",
        reels=[
            ReelPlan(
                reel_id="m1-r1",
                title="Quiet definition",
                purpose="intro overview foundation",
                must_cover=["define term"],
                estimated_length="varies",
            ),
            ReelPlan(
                reel_id="m1-r2",
                title="Build the form",
                purpose="practical apply build steps",
                must_cover=["fill fields"],
                estimated_length="varies",
            ),
            ReelPlan(
                reel_id="m1-r3",
                title="Hard edge case",
                purpose="difficult complex advanced",
                must_cover=["edge case"],
                estimated_length="varies",
            ),
            ReelPlan(
                reel_id="m1-r4",
                title="Fix the myth",
                purpose="common mistake correction",
                must_cover=["wrong default"],
                estimated_length="varies",
            ),
        ],
    )
    module_curve = plan_module_curve(
        module=module, module_index=1, total_modules=3, previous_curve=None
    )
    lessons = [
        plan_lesson_curve(
            reel=module.reels[i],
            reel_index=i,
            reels_in_module=len(module.reels),
            module_curve=module_curve,
        )
        for i in range(len(module.reels))
    ]
    assert len({c.natural_length for c in lessons}) >= 2
    assert len({c.natural_depth for c in lessons}) >= 2
    assert len({c.teaching_energy for c in lessons}) >= 2


def test_prompt_compiler_shape_includes_compact_curve_planning():
    module = _module(1, "Topic", "purpose")
    module_curve = plan_module_curve(
        module=module, module_index=0, total_modules=2, previous_curve=None
    )
    lesson_curve = plan_lesson_curve(
        reel=module.reels[0],
        reel_index=0,
        reels_in_module=3,
        module_curve=module_curve,
    )
    payload = format_curves_for_prompt(module_curve, lesson_curve)
    assert "module_curve" in payload
    assert "lesson_curve" in payload
    compact = compact_lesson_curve_for_prompt(lesson_curve)
    assert "natural_length" in compact
    assert "rationale" in compact
    # Compact: short labels, not essay-length blobs.
    assert len(compact["rationale"]) < 400

    write_input = WriteSingleReelInput(
        course_title="Course",
        main_thread="thread",
        module=module,
        reel=module.reels[0],
        module_curve=payload["module_curve"],
        lesson_curve=payload["lesson_curve"],
    )
    dumped = write_input.model_dump(mode="json")
    assert dumped["lesson_curve"]["natural_length"]
    assert dumped["module_curve"]["module_role"]


def test_final_docx_does_not_expose_curve_labels():
    final = FinalCourse(
        title="Clean Course",
        full_text="# Module One\n## Lesson One\nالنقطة واضحة.",
        modules=[
            FinalModule(
                module_id="m1",
                title="Module One",
                reels=[
                    FinalReel(
                        reel_id="m1-r1",
                        title="Lesson One",
                        script_text=(
                            "النقطة واضحة من غير دراما.\n"
                            "طبق الفكرة على ميزانية موبايل بسيطة."
                        ),
                    )
                ],
            )
        ],
    )
    document = render_final_course_docx(final)
    text = extract_plain_text(document)
    assert find_forbidden_substrings(text) == []
    for leak in (
        "module_curve",
        "lesson_curve",
        "hook_strength",
        "tension_curve",
        "teaching_energy",
        "natural_length",
    ):
        assert leak not in text.lower()


def test_anti_flatness_flags_repeated_same_length_and_hook():
    identical = LessonCurve(
        natural_length="medium",
        natural_depth="standard",
        teaching_energy="practical",
        tension_curve="soft_rise",
        speech_density="medium",
        explanation_mode="direct_explanation",
        hook_strength="strong",
        hook_reason="x",
        ending_motion="soft_next_need",
        compression_decision="c",
        expansion_decision="e",
    )
    curves = [identical.model_copy() for _ in range(4)]
    issues = check_anti_flatness(curves, module_id="m1")
    codes = {i.reason_code for i in issues}
    assert "flat_same_length" in codes
    assert "flat_same_hook_shape" in codes
    assert "flat_same_ending" in codes
    assert "flat_same_intensity" in codes


def test_anti_overperformance_flags_exaggerated_hooks():
    strong = LessonCurve(
        natural_length="short",
        natural_depth="light",
        teaching_energy="excited",
        tension_curve="shock_then_explain",
        speech_density="high",
        explanation_mode="direct_explanation",
        hook_strength="strong",
        hook_reason="viral",
        ending_motion="soft_next_need",
        compression_decision="c",
        expansion_decision="e",
    )
    curves = [strong.model_copy() for _ in range(3)]
    issues = check_anti_overperformance(curves, module_id="m1")
    codes = {i.reason_code for i in issues}
    assert "overperformed_hooks" in codes
    assert "overperformed_energy" in codes

    reels = [
        GeneratedReel(
            reel_id="r1",
            module_id="m1",
            title="a",
            script_text="السر اللي محدش يعرفه عن الإعلانات.",
            self_check_status="pass",
        ),
        GeneratedReel(
            reel_id="r2",
            module_id="m1",
            title="b",
            script_text="أكبر غلط بيغير حياتك في الماركتنج.",
            self_check_status="pass",
        ),
    ]
    script_issues = check_anti_overperformance(curves[:2], reels, module_id="m1")
    assert any(i.reason_code == "overperformed_sales_tone" for i in script_issues)


def test_quiet_educational_lesson_is_allowed_to_remain_quiet():
    quiet = LessonCurve(
        natural_length="medium",
        natural_depth="standard",
        teaching_energy="calm",
        tension_curve="flat_clear",
        speech_density="low",
        explanation_mode="direct_explanation",
        hook_strength="quiet",
        hook_reason="first fact is enough",
        ending_motion="clean_close",
        compression_decision="c",
        expansion_decision="e",
    )
    assert quiet_lesson_is_allowed(quiet)
    # A single quiet lesson must not trip overperformance by itself.
    assert check_anti_overperformance([quiet], module_id="m1") == []


def test_long_and_short_lessons_are_allowed():
    long_curve = LessonCurve(
        natural_length="extended",
        natural_depth="very_deep",
        teaching_energy="analytical",
        tension_curve="confusion_to_clarity",
        speech_density="medium",
        explanation_mode="mental_model",
        hook_strength="quiet",
        hook_reason="hard idea",
        ending_motion="no_loop_needed",
        compression_decision="c",
        expansion_decision="e",
    )
    short_curve = LessonCurve(
        natural_length="short",
        natural_depth="light",
        teaching_energy="precise",
        tension_curve="flat_clear",
        speech_density="low",
        explanation_mode="direct_explanation",
        hook_strength="quiet",
        hook_reason="point complete",
        ending_motion="clean_close",
        compression_decision="c",
        expansion_decision="e",
    )
    assert length_choice_is_allowed(long_curve)
    assert length_choice_is_allowed(short_curve)

    module = _module(1, "Hard topic", "difficult complex advanced", reel_count=1)
    module.reels[0].purpose = "difficult complex advanced misunderstanding"
    module_curve = plan_module_curve(
        module=module, module_index=1, total_modules=2, previous_curve=None
    )
    hard = plan_lesson_curve(
        reel=module.reels[0],
        reel_index=0,
        reels_in_module=1,
        module_curve=module_curve,
    )
    assert hard.natural_length in ("long", "extended", "medium")
    assert hard.hook_strength != "strong" or hard.tension_curve != "shock_then_explain"


def test_fake_provider_follows_lesson_curve_length_without_leaking_labels():
    """Length follows delivery_mode content policy — not mechanical lesson curves."""
    from app.models.enums import LessonDeliveryMode

    provider = FakeProvider()
    brief = CourseBrief(
        title="T",
        audience="a",
        outcome="o",
        structure_mode=StructureMode.CONNECTED_MODULES_WITH_BRIDGE_PROJECTS,
        explanation_level=ExplanationLevel.SHORT_SUMMARY,
    )
    course_map = provider.build_course_map(BuildCourseMapInput(brief=brief))
    module = course_map.modules[0]
    reel = module.reels[0]
    module_curve = plan_module_curve(
        module=module, module_index=0, total_modules=2, previous_curve=None
    )
    planned = plan_lesson_curve(
        reel=reel, reel_index=0, reels_in_module=3, module_curve=module_curve
    )
    micro = reel.model_copy(update={"delivery_mode": LessonDeliveryMode.MICRO_CONCEPT})
    screen = reel.model_copy(
        update={
            "delivery_mode": LessonDeliveryMode.SCREEN_DEMO,
            "internal_visual_plan": "Show export panel",
            "required_assets": ["export.png"],
        }
    )

    short_out = provider.write_single_reel(
        WriteSingleReelInput(
            course_title=course_map.course_title,
            main_thread=course_map.main_thread,
            module=module,
            reel=micro,
            **format_curves_for_prompt(module_curve, planned),
        )
    )
    long_out = provider.write_single_reel(
        WriteSingleReelInput(
            course_title=course_map.course_title,
            main_thread=course_map.main_thread,
            module=module,
            reel=screen,
            **format_curves_for_prompt(module_curve, planned),
        )
    )
    assert len(long_out.script_text.split()) > len(short_out.script_text.split())
    for text in (short_out.script_text, long_out.script_text):
        assert "lesson_curve" not in text
        assert "hook_strength" not in text
        assert "natural_length" not in text
