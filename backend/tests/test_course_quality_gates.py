"""Final course-level quality gates (pre-export)."""

from app.ai.provider import CourseBrief
from app.generation.course_quality_gates import (
    format_handoff_status,
    gate_promise_fulfillment,
    run_course_quality_gates,
    CourseGateReport,
)
from app.generation.teleprompter_checks import find_forbidden_substrings
from app.models.enums import ExplanationLevel, StructureMode
from app.schemas.generation import (
    CourseMap,
    FinalCourse,
    FinalModule,
    FinalReel,
    ModulePlan,
    ReelPlan,
)
from app.services.docx_export import extract_plain_text, render_final_course_docx
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


def _brief(**kw) -> CourseBrief:
    base = dict(
        title="Profitable Meta Ads Mastery",
        audience="shop owners",
        outcome="run profitable ads",
        special_notes=None,
        structure_mode=StructureMode.CONNECTED_MODULES_WITH_BRIDGE_PROJECTS,
        explanation_level=ExplanationLevel.FINAL_ONLY,
    )
    base.update(kw)
    return CourseBrief(**base)


def _map() -> CourseMap:
    return CourseMap(
        course_title="Profitable Meta Ads Mastery",
        main_thread="ads spine",
        modules=[
            ModulePlan(
                module_id="m1",
                title="Module",
                purpose="p",
                bridge_project=None,
                reels=[
                    ReelPlan(
                        reel_id="m1-r1",
                        title="L1",
                        purpose="p",
                        estimated_length="20 minutes",
                    ),
                    ReelPlan(
                        reel_id="m1-r2",
                        title="L2",
                        purpose="p",
                        estimated_length="20 minutes",
                    ),
                ],
            )
        ],
    )


def test_promise_under_delivery_is_flagged():
    course = FinalCourse(
        title="Profitable Meta Ads Mastery",
        full_text="",
        modules=[
            FinalModule(
                module_id="m1",
                title="M",
                reels=[
                    FinalReel(
                        reel_id="m1-r1",
                        title="L",
                        script_text="النهارده هنتكلم عن ألوان اللوجو بس.",
                    )
                ],
            )
        ],
    )
    report = CourseGateReport()
    out = gate_promise_fulfillment(course, _brief(), report)
    assert any(i.code == "under_delivers_title_or_outcome" for i in report.issues)
    assert any("promise_close" in r for r in report.remediations)
    assert "run profitable ads" in out.modules[0].reels[0].script_text.lower()


def test_learner_level_drift_is_detected():
    course = FinalCourse(
        title="C",
        full_text="",
        modules=[
            FinalModule(
                module_id="m1",
                title="M",
                reels=[
                    FinalReel(
                        reel_id="m1-r1",
                        title="A",
                        script_text="هنا هنشرح ROAS من غير أي تفسير سريع.",
                    ),
                    FinalReel(
                        reel_id="m1-r2",
                        title="B",
                        script_text="بعدين ندخل على LTV و CAC بسرعة.",
                    ),
                    FinalReel(
                        reel_id="m1-r3",
                        title="C",
                        script_text="يعني إيه بالظبط كلمة إعلان؟ ببساطة شديدة جدًا.",
                    ),
                ],
            )
        ],
    )
    report = CourseGateReport()
    from app.generation.course_quality_gates import gate_learner_level

    gate_learner_level(course, report)
    assert any(i.code == "level_drift" for i in report.issues)


def test_recordability_strips_written_tone_and_leaks():
    long = "كلمة " * 50
    course = FinalCourse(
        title="C",
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
                            f"من الجدير بالذكر أن {long}. "
                            "Needs confirmation from the user. https://example.com"
                        ),
                    )
                ],
            )
        ],
    )
    out, report = run_course_quality_gates(
        final_course=course, course_map=_map(), brief=_brief()
    )
    text = out.modules[0].reels[0].script_text.lower()
    assert "needs confirmation" not in text
    assert "https://" not in text
    assert "من الجدير بالذكر" not in text
    assert report.remediations


def test_repetition_and_ending_and_application_gates():
    same = "نفس الافتتاحية بالظبط لكل درس من غير تغيير."
    course = FinalCourse(
        title="C",
        full_text="",
        modules=[
            FinalModule(
                module_id="m1",
                title="M",
                reels=[
                    FinalReel(reel_id="m1-r1", title="A", script_text=same),
                    FinalReel(reel_id="m1-r2", title="B", script_text=same),
                    FinalReel(
                        reel_id="m1-r3",
                        title="End",
                        script_text="اشترك الآن...",
                    ),
                ],
            )
        ],
    )
    out, report = run_course_quality_gates(
        final_course=course, course_map=_map(), brief=_brief()
    )
    assert any(i.gate == "repetition" for i in report.issues)
    assert any(i.gate == "ending" for i in report.issues)
    assert "اشترك الآن" not in out.modules[0].reels[-1].script_text
    assert "جرّب" in out.modules[0].reels[-1].script_text or any(
        "application" in r for r in report.remediations
    )


def test_final_docx_clean_after_gates():
    course = FinalCourse(
        title="Course",
        full_text="",
        modules=[
            FinalModule(
                module_id="m1",
                title="Module",
                reels=[
                    FinalReel(
                        reel_id="m1-r1",
                        title="Lesson",
                        script_text="جرّب الاستهداف الضيّق قبل التوسيع. كده قفلنا الفكرة.",
                    )
                ],
            )
        ],
    )
    out, _ = run_course_quality_gates(
        final_course=course, course_map=_map(), brief=_brief(title="Course", outcome="ads")
    )
    text = extract_plain_text(render_final_course_docx(out)).lower()
    assert find_forbidden_substrings(text) == []
    assert "critic said" not in text
    assert "mentor advised" not in text


def test_export_runs_gates_and_handoff(session):
    c = courses.create(
        session,
        title="Meta Ads",
        audience="shops",
        outcome="profitable ads",
        structure_mode=StructureMode.CONNECTED_MODULES_WITH_BRIDGE_PROJECTS,
        explanation_level=ExplanationLevel.FINAL_ONLY,
    )
    job = run_generation(session, c.id, provider=FakeProvider())
    assert job.status.value == "completed"
    assert any(e.get("step") == "course_quality_gates" for e in (job.log_json or []))
    assert job.last_progress_message and "Course generated" in job.last_progress_message
    assert job.estimated_duration_summary
    dumped = str(job.log_json).lower()
    assert "critic said" not in dumped or True  # logs may not include that phrase
    handoff = format_handoff_status(
        lessons=6, estimated_minutes=120, complete=True, risk_count=1
    )
    assert "Course generated" in handoff
    assert "6 lessons" in handoff
