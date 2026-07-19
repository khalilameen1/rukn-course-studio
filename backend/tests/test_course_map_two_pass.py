"""Course map two-pass + hard-max / compression tests (no Premium minute floor)."""

from app.ai.fake_provider import FakeProvider
from app.ai.provider import BuildCourseMapInput, CourseBrief
from app.generation.contracts.course_thesis import build_course_thesis_from_brief
from app.generation.course_map_quality import (
    PREMIUM_MIN_TOTAL_MINUTES,
    PROGRESS_MAP_FIRST_DRAFT,
    PROGRESS_MAP_REBUILD,
    PROGRESS_MAP_STUDENT,
    analyze_map_duration,
    local_map_review_feedback,
    parse_estimated_minutes,
    total_estimated_minutes,
)
from app.generation.map_compression import enforce_map_hard_limits
from app.generation.orchestrator import _build_and_review_course_map
from app.models.enums import (
    ExplanationLevel,
    GenerationQualityMode,
    StructureMode,
)
from app.prompts.prompt_registry import PipelineStage, load_prompt
from app.schemas.generation import CourseMap, CourseThesis, ModulePlan, ReelPlan
from app.services.docx_export import extract_plain_text, render_final_course_docx
from app.generation.teleprompter_checks import find_forbidden_substrings


def _brief(**kwargs) -> CourseBrief:
    base = dict(
        title="Meta Ads",
        audience="shops",
        outcome="profitable ads",
        special_notes=None,
        structure_mode=StructureMode.CONNECTED_MODULES_WITH_BRIDGE_PROJECTS,
        explanation_level=ExplanationLevel.FINAL_ONLY,
    )
    base.update(kwargs)
    return CourseBrief(**base)


def test_map_prompt_defines_two_pass_phases():
    text = load_prompt(PipelineStage.BUILD_COURSE_MAP).lower()
    assert "first_draft" in text
    assert "final_master" in text
    assert "padding" in text or "filler" in text or "compress" in text


def test_premium_minute_floor_removed():
    """Quality must not inflate maps via a Premium minute floor."""
    assert PREMIUM_MIN_TOTAL_MINUTES == 0.0
    shallow = CourseMap(
        course_title="C",
        main_thread="t",
        modules=[
            ModulePlan(
                module_id="m1",
                title="M",
                purpose="p",
                reels=[
                    ReelPlan(
                        reel_id="m1-r1",
                        title="L",
                        purpose="p",
                        estimated_length="90 seconds",
                        distinct_teaching_outcome="one skill",
                        new_skill_or_decision="decide X",
                        why_standalone="narrow",
                        student_can_do_after="do X",
                    )
                ],
            )
        ],
    )
    report = analyze_map_duration(
        shallow, quality_mode=GenerationQualityMode.PREMIUM, relax_floor=False
    )
    assert report.too_short_for_premium is False
    assert parse_estimated_minutes("90 seconds") == 1.5


def test_hard_max_lessons_flags_oversize_map():
    thesis = CourseThesis(
        final_student_outcome="o",
        audience_and_starting_level="a",
        practical_deliverable="d",
        in_scope=["x"],
        out_of_scope=["y"],
        hard_max_lessons=60,
        hard_max_minutes=240,
        final_project="p",
    )
    stems = [f"capability{chr(97 + i % 26)}{i}topic" for i in range(61)]
    reels = [
        ReelPlan(
            reel_id=f"m1-r{i}",
            title=f"{stems[i-1]} workshop",
            purpose=f"Teach {stems[i-1]} only",
            distinct_teaching_outcome=f"Execute {stems[i-1]} solo",
            new_skill_or_decision=f"decide-{stems[i-1]}",
            why_standalone=f"{stems[i-1]} is independent",
            student_can_do_after=f"do {stems[i-1]}",
            estimated_length="3 minutes",
            must_cover=[f"{stems[i-1]}-a"],
        )
        for i in range(1, 62)
    ]
    oversized = CourseMap(
        course_title="C",
        main_thread="t",
        thesis=thesis,
        modules=[ModulePlan(module_id="m1", title="M", purpose="p", reels=reels)],
    )
    report = analyze_map_duration(
        oversized, quality_mode=GenerationQualityMode.PREMIUM, relax_floor=False, thesis=thesis
    )
    assert report.over_hard_max_lessons is True
    _, creport = enforce_map_hard_limits(oversized, thesis=thesis)
    assert not creport.ok


def test_over_five_minutes_allowed_when_present():
    longish = CourseMap(
        course_title="C",
        main_thread="spine",
        modules=[
            ModulePlan(
                module_id="m1",
                title="M",
                purpose="p",
                bridge_project="bridge",
                reels=[
                    ReelPlan(
                        reel_id="m1-r1",
                        title="Deep idea",
                        purpose="p",
                        must_cover=["a"],
                        estimated_length="8 minutes",
                    )
                ]
                * 15,
            )
        ],
    )
    report = analyze_map_duration(
        longish, quality_mode=GenerationQualityMode.PREMIUM, relax_floor=False
    )
    assert report.over_five_minute_lessons >= 1
    assert report.too_short_for_premium is False


def test_two_pass_map_before_lessons_and_not_first_draft_alone():
    class Tracking(FakeProvider):
        def __init__(self) -> None:
            super().__init__()
            self.map_phases: list[str] = []
            self.write_count = 0

        def build_course_map(self, input: BuildCourseMapInput) -> CourseMap:
            self.map_phases.append(input.map_phase)
            return super().build_course_map(input)

        def write_single_reel(self, input):  # noqa: ANN001
            assert "final_master" in self.map_phases
            self.write_count += 1
            return super().write_single_reel(input)

    progress: list[str] = []
    provider = Tracking()
    thesis = build_course_thesis_from_brief(_brief())
    final_map, meta = _build_and_review_course_map(
        provider=provider,
        brief=_brief(),
        sources=[],
        rules_context={},
        course_creator_persona={},
        quality_mode=GenerationQualityMode.PREMIUM,
        on_progress=progress.append,
        thesis=thesis,
    )
    assert provider.map_phases[0] == "first_draft"
    assert "final_master" in provider.map_phases
    assert meta["map_builds"] >= 2
    assert meta.get("map_phases", "").endswith("compress")
    assert final_map.thesis is not None
    assert total_estimated_minutes(final_map) > 0
    assert PROGRESS_MAP_FIRST_DRAFT in progress
    assert PROGRESS_MAP_STUDENT in progress
    assert PROGRESS_MAP_REBUILD in progress


def test_preview_does_not_use_premium_floor():
    draftish = CourseMap(
        course_title="C",
        main_thread="t",
        modules=[
            ModulePlan(
                module_id="m1",
                title="M",
                purpose="p",
                reels=[
                    ReelPlan(
                        reel_id="m1-r1",
                        title="L",
                        purpose="p",
                        must_cover=["x"],
                        estimated_length="3 minutes",
                    )
                ],
            )
        ],
    )
    report = analyze_map_duration(
        draftish, quality_mode=GenerationQualityMode.PREVIEW, relax_floor=True
    )
    assert report.too_short_for_premium is False


def test_final_docx_hides_map_reviews():
    from app.schemas.generation import FinalCourse, FinalModule, FinalReel

    _course_map, log = _build_and_review_course_map(
        provider=FakeProvider(),
        brief=_brief(),
        sources=[],
        rules_context={},
        course_creator_persona={},
        quality_mode=GenerationQualityMode.PREMIUM,
        thesis=build_course_thesis_from_brief(_brief()),
    )
    assert log.get("map_builds", 0) >= 2
    assert "map_review" not in str(log).lower()

    final = FinalCourse(
        title="Course",
        full_text="# M\n## L\nSpoken.",
        modules=[
            FinalModule(
                module_id="m1",
                title="Module",
                reels=[
                    FinalReel(
                        reel_id="m1-r1",
                        title="Lesson",
                        script_text="جرب الاستهداف الضيق قبل التوسيع",
                    )
                ],
            )
        ],
    )
    text = extract_plain_text(render_final_course_docx(final)).lower()
    assert find_forbidden_substrings(text) == []
    assert "map_review" not in text
    assert "estimated duration table" not in text
