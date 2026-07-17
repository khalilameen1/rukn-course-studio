"""Generation quality guards: empty Final Master and meta-leak scrubbing."""

from app.ai.fake_provider import FakeProvider
from app.generation.orchestrator import _local_review_single_reel, _write_and_review_reel
from app.generation.teleprompter_checks import (
    find_forbidden_substrings,
    strip_meta_instruction_lines,
)
from app.schemas.generation import (
    CourseMap,
    GeneratedReel,
    ModulePlan,
    ReelPlan,
    ReviewStatus,
)


def test_strip_meta_instruction_lines_removes_review_narration():
    raw = (
        "يلا نثبت فرق عملي في الاستهداف.\n"
        "بعد المراجعة: وضّحنا الخطوة.\n"
        "جرّب الخطوة دي على حساب تجريبي.\n"
        "Critic said: rewrite the hook.\n"
    )
    cleaned = strip_meta_instruction_lines(raw)
    assert "بعد المراجعة" not in cleaned
    assert "Critic said" not in cleaned
    assert "يلا نثبت فرق عملي" in cleaned
    assert "جرّب الخطوة دي" in cleaned
    assert "بعد المراجعة" in find_forbidden_substrings(raw)


def test_local_review_flags_empty_script():
    reel = GeneratedReel(
        reel_id="m1-r1",
        module_id="m1",
        title="Empty",
        script_text="   ",
        used_ideas=[],
        used_examples=[],
        self_check_status=ReviewStatus.PASS,
    )
    result = _local_review_single_reel(reel, [], {})
    assert result is not None
    assert any(a.reason_code == "empty_script" for a in result.actions)


def test_empty_final_master_raises_instead_of_saving_junk():
    class EmptyFinalProvider(FakeProvider):
        def write_single_reel(self, input):  # noqa: ANN001
            if input.write_phase == "final_master":
                return GeneratedReel(
                    reel_id=input.reel.reel_id,
                    module_id=input.module.module_id,
                    title=input.reel.title,
                    script_text="",
                    used_ideas=["x"],
                    used_examples=["y"],
                    self_check_status=ReviewStatus.PASS,
                )
            return super().write_single_reel(input)

    module = ModulePlan(module_id="m1", title="Module", purpose="p", reels=[])
    reel_plan = ReelPlan(
        reel_id="m1-r1",
        title="Reel",
        purpose="p",
        estimated_length="30s",
        must_cover=["targeting"],
    )
    course_map = CourseMap(course_title="Course", main_thread="thread", modules=[module])

    try:
        _write_and_review_reel(
            provider=EmptyFinalProvider(),
            course_map=course_map,
            module=module,
            reel_plan=reel_plan,
            prior_reels=[],
            all_reels_so_far=[],
            sources=[],
            rules_context={},
        )
        raised = False
    except RuntimeError as exc:
        raised = True
        assert "empty" in str(exc).lower()
    assert raised


def test_fake_final_master_does_not_narrate_review():
    provider = FakeProvider()
    module = ModulePlan(module_id="m1", title="Module", purpose="p", reels=[])
    reel = ReelPlan(
        reel_id="m1-r1",
        title="الاستهداف",
        purpose="p",
        must_cover=["narrow targeting"],
        estimated_length="30s",
    )
    from app.ai.provider import WriteSingleReelInput

    out = provider.write_single_reel(
        WriteSingleReelInput(
            course_title="t",
            main_thread="m",
            module=module,
            reel=reel,
            prior_reels_in_module=[],
            sources=[],
            rules_context={},
            write_phase="final_master",
            previous_review_feedback=["Expand clarity on the practical step."],
        )
    )
    assert "بعد المراجعة" not in out.script_text
    assert "بعد المراجعه" not in out.script_text
