"""Creator → Specialist Critic → Master loop + progress heartbeat tests."""

from pathlib import Path

import pytest
from docx import Document
from sqlmodel import Session, SQLModel, create_engine

from app.ai.fake_provider import FakeProvider
from app.crud import courses, generation_jobs
from app.generation.orchestrator import run_generation
from app.generation.specialist_critic import (
    CRITIC_LEAK_SUBSTRINGS,
    SpecialistCriticReport,
)
from app.generation.teleprompter_checks import find_forbidden_substrings
from app.models.enums import ExplanationLevel, JobStatus, StructureMode
from app.prompts.prompt_registry import PipelineStage, load_prompt
from app.schemas.generation import FinalCourse, FinalModule, FinalReel
from app.schemas.generation_job import GenerationJobRead
from app.services.docx_export import extract_plain_text, render_final_course_docx


@pytest.fixture()
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    import app.generation.orchestrator as orchestrator_module
    import app.services.docx_export as docx_export_module

    monkeypatch.setattr(orchestrator_module.settings, "storage_outputs_dir", tmp_path)
    monkeypatch.setattr(docx_export_module.settings, "storage_outputs_dir", tmp_path)


class FailAfterNReelsProvider(FakeProvider):
    """Fails after N distinct reel_ids succeed (retry-safe)."""

    def __init__(self, fail_after: int) -> None:
        super().__init__()
        self.fail_after = fail_after
        self._seen_reel_ids: set[str] = set()

    def write_single_reel(self, input):  # noqa: ANN001
        if input.reel.reel_id not in self._seen_reel_ids and len(self._seen_reel_ids) >= self.fail_after:
            raise TimeoutError("timed out waiting for model")
        self._seen_reel_ids.add(input.reel.reel_id)
        return super().write_single_reel(input)


def test_write_prompt_defines_domain_specialist_critic_not_social_commenter():
    write = load_prompt(PipelineStage.WRITE_SINGLE_REEL).lower()
    review = load_prompt(PipelineStage.REVIEW_SINGLE_REEL).lower()
    assert "first_draft" in write
    assert "final_master" in write
    assert "master version" in write or "final master" in write
    assert "uninterrupted" in write or "do not" in write and "interrupt" in write
    assert "specialist" in review
    assert "domain" in review
    assert "social commenter" in review or "social-media commenter" in review
    assert "draft_bundle" in review


def test_map_prompt_uses_creator_critic_master():
    text = load_prompt(PipelineStage.BUILD_COURSE_MAP).lower()
    assert "specialist" in text
    assert "first_draft" in text
    assert "final_master" in text or "final course map" in text
    assert "student" in text
    assert "mentor" in text


def test_specialist_critic_report_is_compact_structured():
    report = SpecialistCriticReport(
        fatal_issues=["inaccurate claim"],
        filler_to_remove=["throat clearing"],
        rebuild_direction="Cut filler; keep the local example.",
    )
    dumped = report.model_dump()
    assert set(dumped) >= {
        "fatal_issues",
        "accuracy_risks",
        "realism_risks",
        "weak_value",
        "filler_to_remove",
        "style_risks",
        "missing_depth",
        "overperformance",
        "what_to_keep",
        "rebuild_direction",
    }


def test_final_docx_excludes_critic_and_only_exports_master_script():
    final = FinalCourse(
        title="Course",
        full_text="# M\n## L\nScript only.",
        modules=[
            FinalModule(
                module_id="m1",
                title="Module",
                reels=[
                    FinalReel(
                        reel_id="m1-r1",
                        title="Lesson",
                        script_text="النقطة واضحة وبسيطة بدون دراما.",
                    )
                ],
            )
        ],
    )
    text = extract_plain_text(render_final_course_docx(final)).lower()
    assert find_forbidden_substrings(text) == []
    for leak in CRITIC_LEAK_SUBSTRINGS:
        assert leak not in text
    assert "fatal_issues" not in text
    assert "rebuild_direction" not in text
    assert "creator draft" not in text


def test_run_persists_progress_heartbeat_fields(session):
    course = courses.create(
        session,
        title="Meta ads",
        audience="shop owners",
        outcome="usable ads",
        structure_mode=StructureMode.CONNECTED_MODULES_WITH_BRIDGE_PROJECTS,
        explanation_level=ExplanationLevel.FINAL_ONLY,
    )
    job = run_generation(session, course.id, provider=FakeProvider())
    assert job.status == JobStatus.COMPLETED
    assert job.last_completed_step == "export_docx"
    assert job.last_progress_message and "Course generated" in job.last_progress_message
    assert job.last_saved_at is not None
    assert job.completed_reels_count > 0
    assert job.estimated_usage_summary  # FakeProvider records synthetic usage

    # API schema does not expose drafts / log_json / critic text.
    read = GenerationJobRead.model_validate(job)
    dumped = read.model_dump()
    assert "log_json" not in dumped
    assert "course_map_json" not in dumped
    assert "completed_reels_json" not in dumped
    assert "fatal_issues" not in str(dumped).lower()
    assert read.last_progress_message and "Course generated" in read.last_progress_message
    assert read.last_completed_step == "export_docx"


def test_failed_generation_preserves_work_and_clear_stopped_status(session):
    course = courses.create(
        session,
        title="Course",
        audience="a",
        outcome="o",
        structure_mode=StructureMode.CONNECTED_MODULES_WITH_BRIDGE_PROJECTS,
        explanation_level=ExplanationLevel.FINAL_ONLY,
    )
    job = run_generation(session, course.id, provider=FailAfterNReelsProvider(fail_after=2))
    assert job.status == JobStatus.PARTIAL
    assert job.error_category == "timeout"
    assert job.last_completed_step is not None
    assert job.last_progress_message
    assert "paused" in (job.last_progress_message or "").lower() or "stopped" in (
        job.error_message or ""
    ).lower()
    assert job.partial_docx_path
    assert Path(job.partial_docx_path).exists()
    document = Document(job.partial_docx_path)
    body = "\n".join(p.text for p in document.paragraphs).lower()
    assert "fatal_issues" not in body
    assert "rebuild_direction" not in body

    reloaded = generation_jobs.get(session, job.id)
    assert reloaded.last_completed_step == job.last_completed_step
    assert reloaded.completed_reels_count == 2