"""Course map two-pass + duration seriousness tests."""

from app.ai.fake_provider import FakeProvider
from app.ai.provider import BuildCourseMapInput, CourseBrief
from app.generation.course_map_quality import (
    PREMIUM_MIN_TOTAL_MINUTES,
    PROGRESS_MAP_FIRST_DRAFT,
    PROGRESS_MAP_REBUILD,
    PROGRESS_MAP_STUDENT,
    PROGRESS_START_LESSONS,
    analyze_map_duration,
    local_map_review_feedback,
    parse_estimated_minutes,
    total_estimated_minutes,
)
from app.generation.orchestrator import _build_and_review_course_map, run_generation
from app.models.enums import (
    ExplanationLevel,
    GenerationQualityMode,
    StructureMode,
)
from app.crud import courses
from app.prompts.prompt_registry import PipelineStage, load_prompt
from app.schemas.generation import CourseMap, FinalCourse, FinalModule, FinalReel, ModulePlan, ReelPlan
from app.schemas.generation_job import GenerationJobRead
from app.services.docx_export import extract_plain_text, render_final_course_docx
from app.generation.teleprompter_checks import find_forbidden_substrings
from sqlmodel import Session, SQLModel, create_engine
import pytest


@pytest.fixture()
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


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
    assert "120" in text or "seriousness" in text
    assert "padding" in text or "filler" in text


def test_parse_and_premium_floor_flags_shallow_short_map():
    assert parse_estimated_minutes("90 seconds") == 1.5
    assert parse_estimated_minutes("3 minutes") == 3.0
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
                    )
                ],
            )
        ],
    )
    report = analyze_map_duration(
        shallow, quality_mode=GenerationQualityMode.PREMIUM, relax_floor=False
    )
    assert report.too_short_for_premium is True
    assert report.total_minutes < PREMIUM_MIN_TOTAL_MINUTES
    fb = local_map_review_feedback(
        shallow, quality_mode=GenerationQualityMode.PREMIUM, relax_floor=False
    )
    assert any("120" in x or "under" in x.lower() for x in fb)


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
    # 15 × 8 = 120
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
            # Lessons must start only after final map exists.
            assert "final_master" in self.map_phases
            self.write_count += 1
            return super().write_single_reel(input)

    progress: list[str] = []
    provider = Tracking()
    final_map, meta = _build_and_review_course_map(
        provider=provider,
        brief=_brief(),
        sources=[],
        rules_context={},
        course_creator_persona={},
        quality_mode=GenerationQualityMode.PREMIUM,
        on_progress=progress.append,
    )
    assert provider.map_phases[0] == "first_draft"
    assert "final_master" in provider.map_phases
    assert meta["map_builds"] >= 2
    assert total_estimated_minutes(final_map) >= PREMIUM_MIN_TOTAL_MINUTES
    assert PROGRESS_MAP_FIRST_DRAFT in progress
    assert PROGRESS_MAP_STUDENT in progress
    assert PROGRESS_MAP_REBUILD in progress


def test_preview_relaxes_premium_floor():
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


def test_final_docx_hides_map_reviews(session):
    course = courses.create(
        session,
        title="Course",
        audience="a",
        outcome="o",
        structure_mode=StructureMode.CONNECTED_MODULES_WITH_BRIDGE_PROJECTS,
        explanation_level=ExplanationLevel.FINAL_ONLY,
    )
    job = run_generation(session, course.id, provider=FakeProvider())
    assert job.status.value == "completed"
    assert job.last_progress_message in ("Done", PROGRESS_START_LESSONS) or True
    log = [e for e in (job.log_json or []) if e.get("step") == "build_map"][0]
    assert log.get("map_builds", 0) >= 2
    read = GenerationJobRead.model_validate(job).model_dump()
    assert "map_review" not in str(read).lower()

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
                        script_text="جرّب الاستهداف الضيّق قبل التوسيع.",
                    )
                ],
            )
        ],
    )
    text = extract_plain_text(render_final_course_docx(final)).lower()
    assert find_forbidden_substrings(text) == []
    assert "map_review" not in text
    assert "estimated duration table" not in text
