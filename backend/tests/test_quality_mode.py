"""Generation quality mode (Preview vs Premium) + agency lock tests."""

from app.ai.fake_provider import FakeProvider
from app.generation.orchestrator import (
    MAX_FINAL_REBUILD_ATTEMPTS,
    WRITES_PER_REEL,
    _write_and_review_reel,
    run_generation,
)
from app.models.enums import (
    ExplanationLevel,
    GenerationQualityMode,
    JobStatus,
    StructureMode,
)
from app.crud import courses
from app.schemas.generation import CourseMap, GeneratedReel, ModulePlan, ReelPlan, ReviewStatus
from app.schemas.generation_job import GenerationJobRead
from sqlmodel import Session, SQLModel, create_engine
import pytest


@pytest.fixture()
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _course(session: Session, **overrides):
    kwargs = dict(
        title="Course",
        audience="a",
        outcome="o",
        structure_mode=StructureMode.CONNECTED_MODULES_WITH_BRIDGE_PROJECTS,
        explanation_level=ExplanationLevel.FINAL_ONLY,
        generation_quality_mode=GenerationQualityMode.PREMIUM,
    )
    kwargs.update(overrides)
    return courses.create(session, **kwargs)


def test_premium_runs_ai_draft_bundle_review():
    class Tracking(FakeProvider):
        def __init__(self) -> None:
            super().__init__()
            self.review_calls = 0
            self.phases: list[str] = []

        def write_single_reel(self, input):  # noqa: ANN001
            self.phases.append(input.write_phase)
            return super().write_single_reel(input)

        def review_single_reel(self, input):  # noqa: ANN001
            self.review_calls += 1
            assert input.review_mode == "draft_bundle"
            return super().review_single_reel(input)

    module = ModulePlan(module_id="m1", title="M", purpose="p", reels=[])
    reel = ReelPlan(reel_id="m1-r1", title="R", purpose="p", estimated_length="30s")
    cmap = CourseMap(course_title="C", main_thread="t", modules=[module])
    provider = Tracking()

    master, attempts, _, needs_review = _write_and_review_reel(
        provider=provider,
        course_map=cmap,
        module=module,
        reel_plan=reel,
        prior_reels=[],
        all_reels_so_far=[],
        sources=[],
        rules_context={},
        quality_mode=GenerationQualityMode.PREMIUM,
    )
    assert provider.review_calls == 1
    assert provider.phases[0] == "first_draft"
    assert "final_master" in provider.phases
    assert attempts >= WRITES_PER_REEL
    assert attempts <= 1 + MAX_FINAL_REBUILD_ATTEMPTS
    assert needs_review is False
    assert master.script_text


def test_preview_skips_ai_draft_bundle_review():
    class Tracking(FakeProvider):
        def __init__(self) -> None:
            super().__init__()
            self.review_calls = 0
            self.phases: list[str] = []

        def write_single_reel(self, input):  # noqa: ANN001
            self.phases.append(input.write_phase)
            return super().write_single_reel(input)

        def review_single_reel(self, input):  # noqa: ANN001
            self.review_calls += 1
            return super().review_single_reel(input)

    module = ModulePlan(module_id="m1", title="M", purpose="p", reels=[])
    reel = ReelPlan(reel_id="m1-r1", title="R", purpose="p", estimated_length="30s")
    cmap = CourseMap(course_title="C", main_thread="t", modules=[module])
    provider = Tracking()

    _write_and_review_reel(
        provider=provider,
        course_map=cmap,
        module=module,
        reel_plan=reel,
        prior_reels=[],
        all_reels_so_far=[],
        sources=[],
        rules_context={},
        quality_mode=GenerationQualityMode.PREVIEW,
    )
    assert provider.review_calls == 0
    assert provider.phases == ["first_draft", "final_master"]


def test_no_infinite_rebuild_loop_when_fatal_remains():
    class AlwaysFatal(FakeProvider):
        def __init__(self) -> None:
            super().__init__()
            self.write_calls = 0

        def write_single_reel(self, input):  # noqa: ANN001
            self.write_calls += 1
            return GeneratedReel(
                reel_id=input.reel.reel_id,
                module_id=input.module.module_id,
                title=input.reel.title,
                script_text="في الريل ده هنشرح حاجة",
                used_ideas=["x"],
                used_examples=["y"],
                self_check_status=ReviewStatus.PASS,
            )

    module = ModulePlan(module_id="m1", title="M", purpose="p", reels=[])
    reel = ReelPlan(reel_id="m1-r1", title="R", purpose="p", estimated_length="30s")
    cmap = CourseMap(course_title="C", main_thread="t", modules=[module])
    provider = AlwaysFatal()
    rules = {
        "rukn_forbidden_phrases": '{"phrases": [{"phrase": "في الريل ده", "severity": "high"}]}'
    }

    master, attempts, _, needs_review = _write_and_review_reel(
        provider=provider,
        course_map=cmap,
        module=module,
        reel_plan=reel,
        prior_reels=[],
        all_reels_so_far=[],
        sources=[],
        rules_context=rules,
        quality_mode=GenerationQualityMode.PREMIUM,
    )
    assert needs_review is True
    assert master.self_check_status == ReviewStatus.NEEDS_REVISION
    # draft + at most MAX_FINAL_REBUILD_ATTEMPTS finals — never open-ended
    assert attempts <= 1 + MAX_FINAL_REBUILD_ATTEMPTS
    assert provider.write_calls == attempts


def test_job_read_exposes_progress_aliases_not_internal_reviews(session):
    course = _course(session)
    job = run_generation(session, course.id, provider=FakeProvider())
    assert job.status == JobStatus.COMPLETED
    assert job.generation_quality_mode == GenerationQualityMode.PREMIUM
    assert job.total_lessons_count == job.completed_reels_count
    read = GenerationJobRead.model_validate(job)
    dumped = read.model_dump()
    assert dumped["run_status"] == JobStatus.COMPLETED
    assert dumped["completed_lessons_count"] == job.completed_reels_count
    assert dumped["partial_docx_available"] is False
    assert "log_json" not in dumped
    assert "student_review" not in str(dumped).lower()
    assert "mentor_review" not in str(dumped).lower()


def test_preview_run_persists_quality_mode(session):
    course = _course(session, generation_quality_mode=GenerationQualityMode.PREVIEW)
    job = run_generation(
        session,
        course.id,
        provider=FakeProvider(),
        generation_quality_mode=GenerationQualityMode.PREVIEW,
    )
    assert job.status == JobStatus.COMPLETED
    assert job.generation_quality_mode == GenerationQualityMode.PREVIEW
    assert job.run_snapshot_json
    assert job.run_snapshot_json.get("generation_quality_mode") == "preview"
