"""V1 Final scope lock: Teleprompter DOCX only."""

from app.generation.specialist_critic import (
    PROGRESS_CREATOR_DRAFT,
    PROGRESS_EXPORTING,
    PROGRESS_MAP_FIRST_DRAFT,
    PROGRESS_MAP_MASTER,
    PROGRESS_MASTER_MENTOR,
    PROGRESS_REBUILD_MASTER,
    PROGRESS_SAVING_LESSON,
    PROGRESS_SPECIALIST_CRITIC,
    PROGRESS_STUDENT_CLARITY,
)
from app.generation.teleprompter_checks import (
    TELEPROMPTER_FORBIDDEN_SUBSTRINGS,
    find_forbidden_substrings,
)
from app.generation.course_quality_gates import run_course_quality_gates
from app.ai.provider import CourseBrief
from app.models.enums import ExplanationLevel, StructureMode, TargetMarket
from app.schemas.generation import (
    CourseMap,
    FinalCourse,
    FinalModule,
    FinalReel,
    ModulePlan,
    ReelPlan,
)
from app.services.docx_export import (
    PARTIAL_DRAFT_NOTE,
    extract_plain_text,
    render_final_course_docx,
    render_partial_course_docx,
)
from app.crud import courses
from app.generation.orchestrator import run_generation
from app.ai.fake_provider import FakeProvider
from sqlmodel import Session, SQLModel, create_engine
import pytest


@pytest.fixture()
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_v1_progress_vocabulary_locked():
    assert PROGRESS_MAP_FIRST_DRAFT == "Building course map"
    assert PROGRESS_MAP_MASTER == "Rebuilding final course map"
    assert PROGRESS_CREATOR_DRAFT == "Writing first draft"
    assert PROGRESS_STUDENT_CLARITY == "Checking student clarity"
    assert PROGRESS_SPECIALIST_CRITIC == "Running specialist critic"
    assert PROGRESS_MASTER_MENTOR == "Consulting master mentor"
    assert PROGRESS_REBUILD_MASTER == "Rewriting final master version"
    assert PROGRESS_SAVING_LESSON == "Saving lesson"
    assert PROGRESS_EXPORTING == "Exporting Teleprompter DOCX"


def test_final_docx_is_script_only_no_project_or_production():
    course = FinalCourse(
        title="Ads Course",
        full_text="ignored",
        modules=[
            FinalModule(
                module_id="m1",
                title="M1",
                bridge_project="Build a starter budget sheet",
                reels=[
                    FinalReel(
                        reel_id="m1-r1",
                        title="L1",
                        script_text="قول الكلام ده على الكاميرا بثقة.",
                    )
                ],
            )
        ],
    )
    plain = extract_plain_text(render_final_course_docx(course)).lower()
    assert "ads course" in plain
    assert "module 1" in plain
    assert "lesson 1" in plain
    assert "قول الكلام" in plain
    assert "project" not in plain
    assert "build a starter budget sheet" not in plain
    assert "production pack" not in plain
    assert "asset brief" not in plain
    assert find_forbidden_substrings(plain) == []


def test_no_internal_notes_or_citations_in_docx():
    dirty = FinalCourse(
        title="T",
        full_text="",
        modules=[
            FinalModule(
                module_id="m1",
                title="M",
                reels=[
                    FinalReel(
                        reel_id="r1",
                        title="L",
                        script_text=(
                            "محتوى نظيف. "
                            # Leaks must be stripped by gates before real export;
                            # this unit check asserts the forbid list covers them.
                        ),
                    )
                ],
            )
        ],
    )
    plain = extract_plain_text(render_final_course_docx(dirty)).lower()
    for needle in (
        "needs confirmation",
        "needs review",
        "evidence ledger",
        "critic said",
        "student asked",
        "mentor advised",
        "production pack",
        "screenshot plan",
    ):
        assert needle in TELEPROMPTER_FORBIDDEN_SUBSTRINGS or needle not in plain
        assert needle not in plain


def test_partial_docx_still_script_only():
    course = FinalCourse(
        title="Partial",
        full_text="",
        modules=[
            FinalModule(
                module_id="m1",
                title="M",
                bridge_project="Should not appear",
                reels=[FinalReel(reel_id="r1", title="L", script_text="نص جزئي.")],
            )
        ],
    )
    plain = extract_plain_text(render_partial_course_docx(course))
    assert PARTIAL_DRAFT_NOTE in plain
    assert "Should not appear" not in plain
    assert "Project" not in plain


def test_gates_silent_and_export_master_not_draft(session):
    c = courses.create(
        session,
        title="Meta Ads",
        audience="shops",
        outcome="ads",
        structure_mode=StructureMode.CONNECTED_MODULES_WITH_BRIDGE_PROJECTS,
        explanation_level=ExplanationLevel.FINAL_ONLY,
    )
    job = run_generation(session, c.id, provider=FakeProvider())
    assert job.status.value == "completed"
    assert job.output_docx_path
    # Progress heartbeats used locked vocabulary at least for export.
    assert any(
        (e.get("step") == "export_docx") for e in (job.log_json or [])
    )
    # Course version must not store a full internal report.
    from app.crud import course_versions

    versions = course_versions.list(session, course_id=c.id)
    assert versions
    assert versions[0].report_text is None
    assert versions[0].summary_text
    assert "flagged during review" not in (versions[0].summary_text or "").lower()
    assert "Teleprompter DOCX" in (versions[0].summary_text or "")


def test_egyptian_evergreen_originality_gates_silent_on_script():
    brief = CourseBrief(
        title="Ads",
        audience="shops",
        outcome="ads",
        special_notes=None,
        structure_mode=StructureMode.CONNECTED_NO_MODULES,
        explanation_level=ExplanationLevel.FINAL_ONLY,
        target_market=TargetMarket.EGYPT,
    )
    cmap = CourseMap(
        course_title="Ads",
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
                        estimated_length="20 minutes",
                    )
                ],
            )
        ],
    )
    course = FinalCourse(
        title="Ads",
        full_text="",
        modules=[
            FinalModule(
                module_id="m1",
                title="M",
                reels=[
                    FinalReel(
                        reel_id="m1-r1",
                        title="L",
                        script_text=(
                            "Furthermore Silicon Valley. Click the blue button at the top left. "
                            "Like Alex Hormozi says."
                        ),
                    )
                ],
            )
        ],
    )
    out, report = run_course_quality_gates(
        final_course=course, course_map=cmap, brief=brief, source_texts=[]
    )
    script = out.modules[0].reels[0].script_text.lower()
    assert "originality note" not in script
    assert "evergreen review" not in script
    assert "market analysis" not in script
    assert report.issues  # gates acted
    plain = extract_plain_text(render_final_course_docx(out)).lower()
    assert find_forbidden_substrings(plain) == []
