"""Phase 10: per-mode limits, accepted fingerprints, evidence, and recovery."""

from types import SimpleNamespace

from app.generation.export_blockers import evaluate_export_blockers
from app.generation.quality.context_snapshot import fingerprint_value
from app.generation.quality.contract import CourseQualityContract
from app.models.enums import JobStatus, LessonDeliveryMode
from app.schemas.generation import (
    CourseMap,
    CourseThesis,
    FinalCourse,
    FinalModule,
    FinalReel,
    GeneratedReel,
    LessonSemanticContract,
    ModulePlan,
    ReelPlan,
    ReviewStatus,
)
from app.services.finalize_saved_job import (
    inspect_saved_lessons,
    job_eligible_for_saved_finalize,
)


def _script(word_count: int) -> str:
    words = [
        f"قرار{i}"
        if i % 5
        else "طبّق"
        for i in range(word_count)
    ]
    return "\n".join(
        " ".join(words[index : index + 10])
        for index in range(0, len(words), 10)
    )


def _quality_report(text: str) -> dict:
    text_fingerprint = fingerprint_value(text)
    return {
        "notes": [],
        "semantic_contract": {"missing_fields": [], "remaining_filler_count": 0},
        "language_rewrite_record": {
            "after_text_fingerprint": text_fingerprint,
            "semantic_preserved": True,
        },
        "final_text_acceptance": {
            "text_fingerprint": text_fingerprint,
            "semantic_gate_passed": True,
            "terminology_gate_passed": True,
            "spoken_variety_gate_passed": True,
            "teleprompter_gate_passed": True,
            "term_ledger_fingerprint": fingerprint_value({"terms": "v1"}),
            "phrase_ledger_after_fingerprint": fingerprint_value({"phrases": "v1"}),
            "accepted": True,
        },
    }


def _course_and_generated(
    *,
    word_count: int = 120,
    mode: LessonDeliveryMode = LessonDeliveryMode.CAMERA_EXPLAINER,
) -> tuple[FinalCourse, GeneratedReel]:
    text = _script(word_count)
    generated = GeneratedReel(
        reel_id="r1",
        module_id="m1",
        title="قرار عملي",
        script_text=text,
        spoken_beats=text.splitlines(),
        self_check_status=ReviewStatus.PASS,
        delivery_mode=mode,
        quality_status="pass",
        quality_report=_quality_report(text),
    )
    course = FinalCourse(
        title="كورس القرار",
        full_text="",
        modules=[
            FinalModule(
                module_id="m1",
                title="التطبيق",
                reels=[
                    FinalReel(
                        reel_id="r1",
                        title="قرار عملي",
                        script_text=text,
                        spoken_beats=text.splitlines(),
                        delivery_mode=mode,
                    )
                ],
            )
        ],
    )
    return course, generated


def test_export_enforces_real_delivery_mode_hard_min_not_legacy_40_words():
    course, generated = _course_and_generated(word_count=60)
    report = evaluate_export_blockers(
        final_course=course,
        generated_reels=[generated],
    )
    blockers = [blocker for blocker in report.blockers if blocker.code == "WORD_RANGE"]
    assert blockers
    assert "hard_min=100" in blockers[0].detail


def test_export_blocks_mutation_after_final_text_acceptance():
    course, generated = _course_and_generated()
    acceptance = generated.quality_report["final_text_acceptance"]
    acceptance["text_fingerprint"] = fingerprint_value("older accepted text")
    report = evaluate_export_blockers(
        final_course=course,
        generated_reels=[generated],
    )
    assert any(
        blocker.code == "accepted_text_fingerprint_mismatch"
        for blocker in report.blockers
    )


def test_export_blocks_unresolved_serious_finding_and_high_stakes_claim():
    course, generated = _course_and_generated()
    generated.quality_report["notes"] = [
        {"severity": "serious", "code": "factual_failure"}
    ]
    course.modules[0].reels[0].script_text += (
        "\nقرار الميزانية يحمي النتيجة الواقعية من خسارة مؤكدة"
    )
    generated.script_text = course.modules[0].reels[0].script_text
    generated.spoken_beats = generated.script_text.splitlines()
    acceptance = _quality_report(generated.script_text)
    acceptance["notes"] = generated.quality_report["notes"]
    generated.quality_report = acceptance
    course.modules[0].reels[0].spoken_beats = generated.spoken_beats

    report = evaluate_export_blockers(
        final_course=course,
        generated_reels=[generated],
        evidence_ledger={
            "entries": [
                {
                    "claim_or_gap": "قرار الميزانية يحمي النتيجة الواقعية من خسارة مؤكدة",
                    "support_status": "weak",
                    "risk_flag": "sensitive_domain",
                }
            ]
        },
    )
    codes = {blocker.code for blocker in report.blockers}
    assert "unresolved_review_findings" in codes
    assert "UNSUPPORTED_CLAIM" in codes
    assert "unresolved_high_stakes_claim" in codes


def test_hard_limit_override_requires_reason_scope_and_matching_fingerprint():
    course, generated = _course_and_generated(word_count=60)
    course.thesis = CourseThesis(
        final_student_outcome="قرار",
        audience_and_starting_level="مبتدئ",
        practical_deliverable="تطبيق",
        human_override_hard_limits=True,
    )
    generated.quality_report["hard_limit_override"] = {
        "reason": "A necessary short safety demonstration",
        "scope": "r1",
        "recorded_in_config_fingerprint": "approved-fingerprint",
    }
    mismatch = evaluate_export_blockers(
        final_course=course,
        generated_reels=[generated],
        expected_config_fingerprint="different-fingerprint",
    )
    assert any(blocker.code == "WORD_RANGE" for blocker in mismatch.blockers)

    matching = evaluate_export_blockers(
        final_course=course,
        generated_reels=[generated],
        expected_config_fingerprint="approved-fingerprint",
    )
    assert not any(blocker.code == "WORD_RANGE" for blocker in matching.blockers)


def test_recovery_requires_passed_ledgers_and_exact_saved_text_fingerprint():
    course, generated = _course_and_generated()
    course_map = {
        "course_title": "كورس القرار",
        "main_thread": "قرار",
        "modules": [
            {
                "module_id": "m1",
                "title": "التطبيق",
                "purpose": "قرار مستقل",
                "reels": [
                    {
                        "reel_id": "r1",
                        "title": "قرار عملي",
                        "purpose": "قرار مستقل",
                    }
                ],
            }
        ],
    }
    job = SimpleNamespace(
        course_map_json=course_map,
        completed_reels_json=[generated.model_dump(mode="json")],
        completed_reels_count=1,
        total_lessons_count=1,
        status=JobStatus.PARTIAL,
        output_docx_path=None,
        current_stage="reviewing",
        error_category=None,
        needs_review_count=0,
    )
    assert inspect_saved_lessons(job).ok
    assert job_eligible_for_saved_finalize(job)

    job.completed_reels_json[0]["script_text"] += " تغيير"
    inspection = inspect_saved_lessons(job)
    assert not inspection.ok
    assert inspection.fingerprint_mismatch_reel_ids == ("r1",)

    job.completed_reels_json = [generated.model_dump(mode="json")]
    job.completed_reels_json[0]["quality_status"] = "needs_review"
    inspection = inspect_saved_lessons(job)
    assert not inspection.ok
    assert inspection.nonpassing_reel_ids == ("r1",)

    job.completed_reels_json = [generated.model_dump(mode="json")]
    job.completed_reels_json[0]["quality_report"].pop("final_text_acceptance")
    inspection = inspect_saved_lessons(job)
    assert not inspection.ok
    assert inspection.missing_acceptance_reel_ids == ("r1",)

    job.completed_reels_json = [generated.model_dump(mode="json")]
    job.current_stage = "blocked"
    job.error_category = "export_blocked"
    assert not job_eligible_for_saved_finalize(job)


def test_post_course_mutation_revalidation_refreezes_one_identical_text():
    from app.generation.orchestrator import _revalidate_after_course_gate_mutations

    semantic = LessonSemanticContract(
        learner_before="المتعلم محتاج يحدد نقطة البداية",
        learner_after="المتعلم يقدر يختار القرار المناسب",
        exact_capability_change="ينفذ مقارنة واضحة بين بديلين",
        strongest_non_obvious_meaning="الفرق الحقيقي يظهر في أثر القرار",
        misconception_or_failure="الخطأ اختيار الشكل من غير قياس",
        causal_explanation="القياس يوضح سبب نجاح كل بديل",
        proof_example_or_demonstration="قارن نسختين وسجل النتيجة العملية",
        learner_test_or_action="نفذ المقارنة على حالة جديدة",
        boundary_or_exception="ما تعمم القرار لو الحالة مختلفة",
        real_tension="وازن بين الوضوح وسرعة التنفيذ",
        complete_payoff="الناتج قرار بصري قابل للدفاع",
        earned_next_need="بعدها اختبر القرار في مشروع كامل",
        escalation_role="ينقل المتعلم من التخمين للقياس",
        sequence_dependency="يعتمد على فهم الهدف قبل المقارنة",
    )
    text = "\n".join(semantic.model_dump().values())
    plan = ReelPlan(
        reel_id="r1",
        title="المقارنة",
        purpose="قرار مختلف",
        distinct_teaching_outcome="ينفذ مقارنة واضحة بين بديلين",
        new_skill_or_decision="اختيار بديل بالقياس",
        student_can_do_after="يختار القرار المناسب",
        lesson_semantic_contract=semantic,
    )
    course_map = CourseMap(
        course_title="كورس القرار",
        main_thread="قرار",
        modules=[ModulePlan(module_id="m1", title="تطبيق", purpose="قياس", reels=[plan])],
    )
    generated = GeneratedReel(
        reel_id="r1",
        module_id="m1",
        title="المقارنة",
        script_text="نص أقدم قبل بوابة الكورس",
        self_check_status=ReviewStatus.PASS,
        quality_status="pass",
        quality_report=_quality_report("نص أقدم قبل بوابة الكورس"),
    )
    final_course = FinalCourse(
        title="كورس القرار",
        full_text="",
        modules=[
            FinalModule(
                module_id="m1",
                title="تطبيق",
                reels=[FinalReel(reel_id="r1", title="المقارنة", script_text=text)],
            )
        ],
    )
    contract = CourseQualityContract()
    contract.language.apply_egyptian_spoken_qa = False
    contract.language.apply_english_spoken_qa = False

    refreshed_course, refreshed_reels, phrase_ledger = (
        _revalidate_after_course_gate_mutations(
            course_map=course_map,
            final_course=final_course,
            generated_reels=[generated],
            quality_contract=contract,
            address_form=contract.language.address_form,
            term_ledger={"version": "test"},
        )
    )
    refreshed = refreshed_reels[0]
    acceptance = refreshed.quality_report["final_text_acceptance"]
    assert refreshed.quality_status == "pass"
    assert acceptance["accepted"] is True
    assert acceptance["text_fingerprint"] == fingerprint_value(text)
    assert refreshed.spoken_beats == text.splitlines()
    assert refreshed_course.modules[0].reels[0].script_text == text
    assert phrase_ledger.openings
