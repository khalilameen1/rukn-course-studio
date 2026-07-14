"""Draft → multi-agent review → Final Master (Creator does not self-criticize)."""

from app.ai.fake_provider import FakeProvider
from app.generation.orchestrator import WRITES_PER_REEL, _write_and_review_reel
from app.generation.specialist_critic import (
    PROGRESS_CREATOR_DRAFT,
    PROGRESS_MASTER_MENTOR,
    PROGRESS_REBUILD_MASTER,
    PROGRESS_SPECIALIST_CRITIC,
    PROGRESS_STUDENT_CLARITY,
)
from app.schemas.generation import CourseMap, ModulePlan, ReelPlan


def test_progress_labels_are_draft_then_reviews_then_final():
    assert PROGRESS_CREATOR_DRAFT == "Writing first draft"
    assert PROGRESS_STUDENT_CLARITY == "Checking student clarity"
    assert PROGRESS_SPECIALIST_CRITIC == "Running specialist critic"
    assert PROGRESS_MASTER_MENTOR == "Consulting master mentor"
    assert PROGRESS_REBUILD_MASTER == "Rewriting final master version"


def test_each_reel_is_written_twice_draft_then_final_master():
    class TrackingProvider(FakeProvider):
        def __init__(self) -> None:
            super().__init__()
            self.phases: list[str] = []

        def write_single_reel(self, input):  # noqa: ANN001
            self.phases.append(input.write_phase)
            return super().write_single_reel(input)

    module = ModulePlan(module_id="m1", title="Module", purpose="p", reels=[])
    reel_plan = ReelPlan(
        reel_id="m1-r1",
        title="Reel",
        purpose="p",
        estimated_length="30s",
        must_cover=["narrow targeting"],
    )
    course_map = CourseMap(course_title="Course", main_thread="thread", modules=[module])
    provider = TrackingProvider()
    progress: list[str] = []

    master, attempts, _caught, needs_review = _write_and_review_reel(
        provider=provider,
        course_map=course_map,
        module=module,
        reel_plan=reel_plan,
        prior_reels=[],
        all_reels_so_far=[],
        sources=[],
        rules_context={},
        on_progress=progress.append,
        lesson_n=6,
        total_reels=24,
    )

    assert attempts == WRITES_PER_REEL
    assert provider.phases == ["first_draft", "final_master"]
    assert needs_review is False
    assert master.script_text
    assert any("Writing first draft for lesson 6/24" in m for m in progress)
    assert PROGRESS_STUDENT_CLARITY in progress
    assert PROGRESS_SPECIALIST_CRITIC in progress
    assert PROGRESS_MASTER_MENTOR in progress
    assert any("Rewriting final master version" in m for m in progress)
    # Draft never returned — only final master script_text.
    assert "student_review" not in master.script_text.lower()
    assert "mentor_review" not in master.script_text.lower()
    assert "first_draft" not in master.script_text.lower()
    assert "critic said" not in master.script_text.lower()
