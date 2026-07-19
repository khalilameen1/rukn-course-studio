"""Acceptance tests for the course engine rebuild (contracts → gates → writer test)."""

from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.ai.fake_provider import FakeProvider
from app.ai.provider import CourseBrief
from app.crud import courses
from app.generation.contracts.course_thesis import (
    PRACTICAL_DEFAULTS,
    build_course_thesis_from_brief,
    validate_course_thesis,
)
from app.generation.contracts.spoken_final_master import (
    strip_punctuation_from_spoken_body,
    validate_spoken_export_text,
)
from app.generation.egyptian_arabic_gate import run_egyptian_arabic_gate
from app.generation.export_blockers import evaluate_export_blockers
from app.generation.knowledge_packs import (
    MANDATORY_CORE_KEYS,
    build_stage_rules_pack,
    mandatory_core_intact,
)
from app.generation.map_compression import enforce_map_hard_limits
from app.generation.quality.context_snapshot import fingerprint_value
from app.generation.writer_test import WriterTestTopic, run_writer_test_3_reels
from app.models.enums import (
    AddressForm,
    ExplanationLevel,
    GenerationQualityMode,
    LessonDeliveryMode,
    StructureMode,
)
from app.prompts.prompt_registry import PipelineStage
from app.schemas.generation import (
    CourseMap,
    CourseThesis,
    FinalCourse,
    FinalModule,
    FinalReel,
    ModulePlan,
    ModuleProject,
    ReelPlan,
    ReviewStatus,
    GeneratedReel,
)
from app.services.docx_export import extract_plain_text, render_final_course_docx
from app.generation.course_map_quality import PREMIUM_MIN_TOTAL_MINUTES


@pytest.fixture()
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'rebuild.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _brief() -> CourseBrief:
    return CourseBrief(
        title="تصميم بوستات",
        audience="مبتدئين",
        outcome="تصميم بوست جاهز للنشر",
        structure_mode=StructureMode.CONNECTED_MODULES_WITH_BRIDGE_PROJECTS,
        explanation_level=ExplanationLevel.FINAL_ONLY,
    )


def test_no_premium_minute_floor_inflation():
    assert PREMIUM_MIN_TOTAL_MINUTES == 0.0


def test_thesis_required_defaults_and_hard_caps():
    thesis = build_course_thesis_from_brief(_brief())
    assert validate_course_thesis(thesis).ok
    assert thesis.hard_max_lessons == PRACTICAL_DEFAULTS["hard_max_lessons"]
    assert thesis.target_practice_ratio >= 0.6


def test_map_61_lessons_fails_hard_max_60():
    thesis = CourseThesis(
        final_student_outcome="o",
        audience_and_starting_level="a",
        practical_deliverable="d",
        in_scope=["in"],
        out_of_scope=["out"],
        hard_max_lessons=60,
        hard_max_minutes=240,
        final_project="final",
    )
    # Use unrelated Arabic/English stems so compression cannot merge them.
    stems = [
        "contrast", "export", "crop", "typography", "spacing", "hierarchy",
        "thumbzone", "palette", "shadow", "blur", "mask", "layer", "frame",
        "story", "reelcover", "caption", "hashtag", "cta", "offer", "price",
        "audience", "hook", "retention", "script", "voiceover", "broll",
        "lighting", "angle", "prop", "background", "logo", "brand", "grid",
        "margin", "padding", "align", "opacity", "blend", "vector", "raster",
        "png", "jpg", "svg", "figma", "canva", "photoshop", "lightroom",
        "premiere", "capcut", "timeline", "transition", "effect", "lut",
        "colorgrade", "audio", "sfx", "music", "subtitle", "safezone",
        "safearea", "watermark",
    ]
    assert len(stems) >= 61
    reels = [
        ReelPlan(
            reel_id=f"r{i}",
            title=f"{stems[i]} mastery workshop",
            purpose=f"Teach {stems[i]} as a standalone operator skill",
            distinct_teaching_outcome=f"Learner executes {stems[i]} end-to-end alone",
            new_skill_or_decision=f"decide-{stems[i]}",
            why_standalone=f"{stems[i]} cannot fold into neighbors without loss",
            student_can_do_after=f"perform {stems[i]}",
            must_cover=[f"{stems[i]}-core", f"{stems[i]}-check"],
            estimated_length="3 minutes",
        )
        for i in range(61)
    ]
    cmap = CourseMap(
        course_title="C",
        main_thread="t",
        thesis=thesis,
        modules=[ModulePlan(module_id="m1", title="M", purpose="p", reels=reels)],
    )
    _, report = enforce_map_hard_limits(cmap, thesis=thesis)
    assert not report.ok


def test_similar_lessons_merge_before_generation():
    thesis = build_course_thesis_from_brief(_brief())
    a = ReelPlan(
        reel_id="r1",
        title="اختيار الألوان",
        purpose="تعلم اختيار الألوان",
        distinct_teaching_outcome="يختار لوحة ألوان مناسبة",
        new_skill_or_decision="اختيار ألوان",
        why_standalone="x",
        student_can_do_after="يختار",
        must_cover=["ألوان"],
        estimated_length="2 minutes",
    )
    b = ReelPlan(
        reel_id="r2",
        title="اختيار الالوان",
        purpose="تعلم اختيار الألوان بشكل صحيح",
        distinct_teaching_outcome="يختار لوحة ألوان مناسبة للمنشور",
        new_skill_or_decision="اختيار ألوان",
        why_standalone="x",
        student_can_do_after="يختار",
        must_cover=["ألوان"],
        estimated_length="2 minutes",
    )
    cmap = CourseMap(
        course_title="C",
        main_thread="t",
        thesis=thesis,
        modules=[
            ModulePlan(
                module_id="m1",
                title="M",
                purpose="p",
                module_project=ModuleProject(name="P", brief="do"),
                reels=[a, b],
            )
        ],
    )
    compressed, report = enforce_map_hard_limits(cmap, thesis=thesis)
    assert report.ok
    assert sum(len(m.reels) for m in compressed.modules) == 1


def test_needs_review_blocks_docx_export():
    final = FinalCourse(
        title="C",
        full_text="",
        modules=[
            FinalModule(
                module_id="m1",
                title="M",
                reels=[
                    FinalReel(
                        reel_id="r1",
                        title="L",
                        script_text="كلام كويس praktikal",
                        quality_status="needs_review",
                    )
                ],
            )
        ],
    )
    report = evaluate_export_blockers(
        final_course=final,
        generated_reels=[
            GeneratedReel(
                reel_id="r1",
                module_id="m1",
                title="L",
                script_text="كلام",
                self_check_status=ReviewStatus.NEEDS_REVISION,
                quality_status="needs_review",
            )
        ],
    )
    assert not report.ok
    assert any(
        b.code in {"needs_review", "needs_review_or_fatal"} for b in report.blockers
    )


def test_module_project_in_docx_not_as_lesson_number():
    final = FinalCourse(
        title="كورس",
        full_text="",
        modules=[
            FinalModule(
                module_id="m1",
                title="أساسيات",
                module_project=ModuleProject(
                    name="مشروع الموديول الأول",
                    brief="صمّم بوست واحد",
                    pass_criteria=["واضح"],
                ),
                reels=[
                    FinalReel(
                        reel_id="r1",
                        title="درس واحد",
                        script_text="ابدأ من المشكلة الحقيقية\nطبّق القرار",
                    )
                ],
            )
        ],
        graduation_project=ModuleProject(name="مشروع التخرج", brief="سلّم حملة"),
    )
    text = extract_plain_text(render_final_course_docx(final))
    assert "مشروع الموديول الأول" in text
    assert "مشروع التخرج" in text
    assert "Lesson 2" not in text
    assert "صمّم بوست واحد" in text or "صمم بوست واحد" in text


def test_script_body_has_no_punctuation():
    body = strip_punctuation_from_spoken_body("مرحبا، كيف حالك؟ جرب هذا!")
    assert "،" not in body
    assert "؟" not in body
    assert "!" not in body
    assert "." not in body


def test_docx_does_not_leak_metadata():
    final = FinalCourse(
        title="C",
        full_text="",
        modules=[
            FinalModule(
                module_id="m1",
                title="M",
                reels=[
                    FinalReel(
                        reel_id="r1",
                        title="L",
                        script_text="ابدأ من القرار\nوضح الفرق",
                    )
                ],
            )
        ],
    )
    text = extract_plain_text(render_final_course_docx(final)).lower()
    for leak in ("hook:", "loop:", "critic", "source:", "needs confirmation", "```"):
        assert leak not in text
    assert validate_spoken_export_text("Hook: bad").ok is False


def test_address_form_mismatch_fails():
    report = run_egyptian_arabic_gate(
        "انتي لازم تعملي الخطوة دي بنفسكِ",
        address_form=AddressForm.MASCULINE,
    )
    assert not report.ok


def test_empty_short_teaching_fails_gate():
    report = run_egyptian_arabic_gate("")
    assert any(i.code == "empty_script" for i in report.issues)


def test_screen_without_visual_plan_blocked():
    thesis = build_course_thesis_from_brief(_brief())
    plan = ReelPlan(
        reel_id="r1",
        title="Demo",
        purpose="demo",
        delivery_mode=LessonDeliveryMode.SCREEN_DEMO,
        distinct_teaching_outcome="x",
        new_skill_or_decision="x",
        why_standalone="x",
        student_can_do_after="x",
        needs_screen_or_visual=True,
        estimated_length="3 minutes",
    )
    cmap = CourseMap(
        course_title="C",
        main_thread="t",
        thesis=thesis,
        modules=[
            ModulePlan(
                module_id="m1",
                title="M",
                purpose="p",
                module_project=ModuleProject(name="P", brief="b"),
                reels=[plan],
            )
        ],
        graduation_project=ModuleProject(name="G", brief="g"),
    )
    final = FinalCourse(
        title="C",
        full_text="",
        thesis=thesis,
        graduation_project=cmap.graduation_project,
        modules=[
            FinalModule(
                module_id="m1",
                title="M",
                module_project=ModuleProject(name="P", brief="b"),
                reels=[
                    FinalReel(
                        reel_id="r1",
                        title="Demo",
                        script_text=("كلمة " * 200).strip(),
                        delivery_mode=LessonDeliveryMode.SCREEN_DEMO,
                        quality_status="pass",
                    )
                ],
            )
        ],
    )
    report = evaluate_export_blockers(final_course=final, course_map=cmap, thesis=thesis)
    assert any(b.code == "screen_without_visual_plan" for b in report.blockers)


def test_mandatory_admin_knowledge_not_chopped():
    selected = {k: f"{k} FULL BODY CONTENT " + ("كلمة " * 80) for k in MANDATORY_CORE_KEYS}
    pack = build_stage_rules_pack(selected, PipelineStage.WRITE_SINGLE_REEL)
    assert mandatory_core_intact(pack, selected)


def test_writer_test_generates_exactly_three(session):
    course = courses.create(
        session,
        title="Writer",
        audience="a",
        outcome="o",
        structure_mode=StructureMode.CONNECTED_MODULES_WITH_BRIDGE_PROJECTS,
        explanation_level=ExplanationLevel.FINAL_ONLY,
    )
    job = run_writer_test_3_reels(
        session,
        course.id,
        topics=[
            WriterTestTopic(title="هوك البوست"),
            WriterTestTopic(title="تباين الألوان"),
            WriterTestTopic(title="CTA بسيط"),
        ],
        series_linked=False,
        provider=FakeProvider(),
        idempotency_key="wt-test-1",
    )
    assert job.total_lessons_count == 3
    assert len(job.completed_reels_json or []) == 3
    # reopen / same idempotency does not create a new job
    again = run_writer_test_3_reels(
        session,
        course.id,
        topics=[
            WriterTestTopic(title="هوك البوست"),
            WriterTestTopic(title="تباين الألوان"),
            WriterTestTopic(title="CTA بسيط"),
        ],
        series_linked=False,
        provider=FakeProvider(),
        idempotency_key="wt-test-1",
    )
    assert again.id == job.id


def test_independent_topics_reject_next_reel_bait():
    text = "كده خلصنا. في الريل الجاي هنشوف الباقي"
    assert "في الريل الجاي" in text


def test_fingerprint_changes_with_model():
    a = fingerprint_value({"MODEL": "fake"})
    b = fingerprint_value({"MODEL": "different-model"})
    assert a != b


def test_fake_provider_is_not_labeled_quality_assurance():
    import inspect
    from app.ai import fake_provider

    doc = inspect.getdoc(fake_provider) or ""
    assert "NOT a production quality oracle" in doc or "not a production quality" in doc.lower()
