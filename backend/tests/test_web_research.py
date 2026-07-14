"""Autonomous web research + final-script-only output."""

from app.generation.web_research import (
    PROGRESS_BUILDING_MEMORY,
    PROGRESS_FILLING_FACTS,
    PROGRESS_READING_UPLOADS,
    FakeResearchBackend,
    find_research_leaks,
    identify_factual_gaps,
    run_autonomous_gap_fill,
    strip_research_leaks_from_script,
)
from app.models.enums import (
    ExplanationLevel,
    StructureMode,
    WebResearchMode,
)
from app.generation.teleprompter_checks import find_forbidden_substrings
from app.generation.specialist_critic import PROGRESS_SPECIALIST_CRITIC
from app.schemas.generation import FinalCourse, FinalModule, FinalReel
from app.services.docx_export import extract_plain_text, render_final_course_docx
from app.crud import courses
from app.generation.orchestrator import run_generation
from app.ai.fake_provider import FakeProvider
from app.schemas.generation_job import GenerationJobRead
from sqlmodel import Session, SQLModel, create_engine
import pytest


@pytest.fixture()
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_autonomous_gap_fill_researches_without_asking():
    result = run_autonomous_gap_fill(
        course_title="Meta Ads for shops",
        audience="shop owners",
        outcome="run profitable ads",
        special_notes=None,
        uploaded_texts=[("notes", "short")],
        mode=WebResearchMode.AUTONOMOUS_GAP_FILL,
        backend=FakeResearchBackend(),
    )
    assert result.web_memory.items or result.ledger.entries
    assert "ask" not in (result.ledger.research_error or "").lower()
    # Supported facts may feed prompts; URLs must not end up as user-facing requirement.
    for item in result.web_memory.items:
        assert item.kind == "web"


def test_disabled_mode_skips_web_research():
    result = run_autonomous_gap_fill(
        course_title="Excel",
        audience="a",
        outcome="o",
        special_notes=None,
        uploaded_texts=[],
        mode=WebResearchMode.DISABLED,
        backend=FakeResearchBackend(),
    )
    assert result.web_memory.items == []
    assert result.web_excerpts_text == []


def test_unsupported_claims_are_omitted_not_confirmed():
    class EmptyBackend(FakeResearchBackend):
        def fetch_facts(self, query: str, *, sensitive: bool):
            return []

    result = run_autonomous_gap_fill(
        course_title="Miracle finance tips",
        audience="a",
        outcome="guaranteed wealth",
        special_notes="100% guaranteed secret",
        uploaded_texts=[],
        mode=WebResearchMode.AUTONOMOUS_GAP_FILL,
        backend=EmptyBackend(),
    )
    assert any(e.support_status == "omitted" for e in result.ledger.entries)
    assert all("needs confirmation" not in (e.note or "").lower() for e in result.ledger.entries)


def test_sensitive_domain_prefers_omission_when_weak():
    gaps = identify_factual_gaps(
        course_title="Medical supplement course",
        audience="patients",
        outcome="diagnose and treat yourself",
        special_notes="prescription guidance",
        upload_memory=run_autonomous_gap_fill(
            course_title="Medical supplement course",
            audience="patients",
            outcome="diagnose",
            special_notes="prescription",
            uploaded_texts=[],
            mode=WebResearchMode.DISABLED,
        ).upload_memory,
    )
    assert gaps
    assert any(g.sensitive for g in gaps)


def test_strip_and_forbid_research_leaks_in_docx():
    dirty = (
        "النقطة واضحة.\n"
        "Needs confirmation from the user.\n"
        "See https://example.com for evidence ledger.\n"
        "كمل بالشرح العملي."
    )
    clean = strip_research_leaks_from_script(dirty)
    assert "needs confirmation" not in clean.lower()
    assert "https://" not in clean.lower()
    assert "evidence ledger" not in clean.lower()
    assert find_research_leaks(clean) == []

    final = FinalCourse(
        title="Course",
        full_text="# M\n## L\nSpoken only.",
        modules=[
            FinalModule(
                module_id="m1",
                title="Module",
                reels=[
                    FinalReel(
                        reel_id="m1-r1",
                        title="Lesson",
                        script_text=clean,
                    )
                ],
            )
        ],
    )
    text = extract_plain_text(render_final_course_docx(final)).lower()
    assert find_forbidden_substrings(text) == []
    assert "needs_review" not in text
    assert "student_review" not in text
    assert "mentor_review" not in text
    assert "according to source" not in text


def test_progress_labels_are_status_only():
    # Research-stage labels stay on locked coarse map vocabulary (no evidence UI).
    assert PROGRESS_READING_UPLOADS == "Building course map"
    assert PROGRESS_FILLING_FACTS == "Building course map"
    assert PROGRESS_BUILDING_MEMORY == "Building course map"
    assert PROGRESS_SPECIALIST_CRITIC == "Running specialist critic"


def test_ledger_persists_internally_not_in_job_read(session):
    course = courses.create(
        session,
        title="Meta ads",
        audience="shops",
        outcome="profitable ads",
        structure_mode=StructureMode.CONNECTED_MODULES_WITH_BRIDGE_PROJECTS,
        explanation_level=ExplanationLevel.FINAL_ONLY,
        web_research_mode=WebResearchMode.AUTONOMOUS_GAP_FILL,
    )
    job = run_generation(session, course.id, provider=FakeProvider())
    assert job.status.value == "completed"
    assert job.web_research_mode == WebResearchMode.AUTONOMOUS_GAP_FILL
    assert job.source_memory_json is not None
    assert job.evidence_ledger_json is not None
    dumped = GenerationJobRead.model_validate(job).model_dump()
    assert "evidence_ledger_json" not in dumped
    assert "source_memory_json" not in dumped
    assert "web_source_memory_json" not in dumped
    assert dumped.get("web_research_mode") == "autonomous_gap_fill"
