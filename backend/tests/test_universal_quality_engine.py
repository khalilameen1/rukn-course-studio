"""Credit-safe tests for universal CourseQualityContract engine.

Uses FakeProvider + fixtures only. Network and real providers are blocked.
"""

from __future__ import annotations

import os

import pytest
from sqlmodel import Session, SQLModel, create_engine

# Activate credit-safe mode before importing factory-dependent modules.
os.environ["RUKN_CREDIT_SAFE_TESTS"] = "1"

from app.ai.fake_provider import FakeProvider
from app.ai.provider import CourseBrief
from app.generation.domain_adapters import (
    build_course_quality_contract,
    resolve_domain_adapter_id,
)
from app.generation.map_compression import compress_course_map, enforce_map_hard_limits
from app.generation.quality.content_atoms import (
    ContentAtom,
    ContentAtomLedger,
    build_ledger_from_course_map,
)
from app.generation.quality.context_snapshot import (
    build_generation_context_snapshot,
    compare_snapshots,
)
from app.generation.quality.coverage_matrix import evaluate_coverage_matrix
from app.generation.quality.english_spoken_gate import run_english_spoken_gate
from app.generation.quality.export_helpers import status_blocks_export
from app.generation.quality.issue_codes import IssueCode, LessonQualityStatus
from app.generation.quality.mutation_guard import MutationGuard
from app.generation.quality.network_guard import (
    NetworkBlockedError,
    RealProviderBlockedError,
    assert_credit_safe,
    block_network,
    real_provider_call_count,
    reset_real_provider_call_count,
    unblock_network,
)
from app.generation.quality.protected_spans import (
    assert_protected_spans_unchanged,
    punctuation_strip_preserving_protected,
    wrap_protected,
)
from app.generation.quality.teleprompter_blocks import (
    build_teleprompter_doc,
    evaluate_teleprompter_layout,
)
from app.generation.contracts.spoken_final_master import strip_punctuation_from_spoken_body
from app.generation.export_blockers import evaluate_export_blockers
from app.models.enums import (
    AddressForm,
    CourseMixType,
    ExplanationLevel,
    LessonDeliveryMode,
    StructureMode,
)
from app.schemas.generation import (
    CourseMap,
    CourseThesis,
    FinalCourse,
    FinalModule,
    FinalReel,
    ModulePlan,
    ModuleProject,
    ReelPlan,
)


@pytest.fixture(autouse=True)
def _credit_safe():
    reset_real_provider_call_count()
    block_network()
    yield
    unblock_network()
    assert_credit_safe(provider_name="fake")
    assert real_provider_call_count() == 0


def _brief(**kwargs) -> CourseBrief:
    base = dict(
        title="Test",
        audience="learners",
        outcome="can do X",
        structure_mode=StructureMode.CONNECTED_MODULES_WITH_BRIDGE_PROJECTS,
        explanation_level=ExplanationLevel.FINAL_ONLY,
    )
    base.update(kwargs)
    return CourseBrief(**base)


def test_network_is_blocked():
    import socket

    with pytest.raises(NetworkBlockedError):
        socket.socket()


def test_real_provider_blocked_by_factory():
    from app.ai.factory import get_ai_provider
    from app.config import Settings

    # Even if settings say anthropic, credit-safe forces fake / blocks.
    cfg = Settings(ai_provider="anthropic", anthropic_api_key="x", ai_model_name="claude")
    with pytest.raises(RealProviderBlockedError):
        get_ai_provider(cfg)
    reset_real_provider_call_count()


def test_domain_adapters_do_not_cross_contaminate():
    lang = build_course_quality_contract(_brief(title="تعلم الإنجليزية", outcome="speak"))
    tool = build_course_quality_contract(_brief(title="Figma tool", course_domain="software"))
    income = build_course_quality_contract(_brief(title="Freelance income", outcome="دخل"))
    religious = build_course_quality_contract(_brief(title="فقه", course_domain="religious"))
    health = build_course_quality_contract(_brief(title="medical finance law", course_domain="health"))

    assert lang.adapter_id == "language_learning"
    assert tool.adapter_id == "software_and_tools"
    assert "screen_plan_when_needed" in tool.pedagogy.domain_specific_validators
    assert "screen_plan_when_needed" not in lang.pedagogy.domain_specific_validators
    assert "no_guaranteed_income" in income.pedagogy.domain_specific_validators
    assert "no_invented_texts" in religious.pedagogy.domain_specific_validators
    assert health.evidence.require_expert_review_before_export is True
    # Egyptian QA only when presenter Arabic Egyptian
    en = build_course_quality_contract(
        _brief(title="English speaking"),
        presenter_language="en",
        presenter_dialect="none",
    )
    assert en.language.apply_egyptian_spoken_qa is False
    assert en.language.apply_english_spoken_qa is True


def test_micro_reel_pattern_allows_90_lessons_hard_max():
    contract = build_course_quality_contract(
        _brief(),
        delivery_pattern="teleprompter_micro_reel",
    )
    assert contract.delivery.hard_max_lessons >= 90
    thesis = CourseThesis(
        final_student_outcome="o",
        audience_and_starting_level="a",
        practical_deliverable="d",
        hard_max_lessons=contract.delivery.hard_max_lessons,
        hard_max_minutes=240,
    )
    reels = [
        ReelPlan(
            reel_id=f"r{i}",
            title=f"Unique skill {i} lesson",
            purpose=f"teach skill-{i}",
            distinct_teaching_outcome=f"executes skill-{i} alone",
            new_skill_or_decision=f"skill-{i}",
            must_cover=[f"skill-{i}-core"],
            estimated_length="1.2 minutes",
            delivery_mode=LessonDeliveryMode.MICRO_CONCEPT,
        )
        for i in range(90)
    ]
    # Capacity/structure only — no provider, no spoken generation.
    cmap = CourseMap(
        course_title="Cap",
        main_thread="t",
        thesis=thesis,
        modules=[
            ModulePlan(
                module_id=f"m{m}",
                title=f"M{m}",
                purpose="p",
                module_project=ModuleProject(name=f"P{m}", brief="do"),
                reels=reels[m * 8 : (m + 1) * 8] if m < 11 else reels[88:],
            )
            for m in range(12)
        ],
    )
    # Ensure 90 lessons distributed
    assert sum(len(m.reels) for m in cmap.modules) == 90
    compressed, report = enforce_map_hard_limits(cmap, thesis=thesis)
    assert report.ok, report.errors
    assert sum(len(m.reels) for m in compressed.modules) == 90


def test_content_atom_loss_fails_compression():
    thesis = CourseThesis(
        final_student_outcome="o",
        audience_and_starting_level="a",
        practical_deliverable="d",
        hard_max_lessons=60,
    )
    a = ReelPlan(
        reel_id="r1",
        title="ألوان",
        purpose="ألوان",
        distinct_teaching_outcome="يختار ألوان",
        must_cover=["atom-critical-contrast"],
        estimated_length="2 minutes",
    )
    b = ReelPlan(
        reel_id="r2",
        title="الوان",
        purpose="ألوان",
        distinct_teaching_outcome="يختار ألوان مناسبة",
        must_cover=["atom-critical-contrast"],
        estimated_length="2 minutes",
    )
    cmap = CourseMap(
        course_title="C",
        main_thread="t",
        thesis=thesis,
        modules=[ModulePlan(module_id="m1", title="M", purpose="p", reels=[a, b])],
    )
    compressed, report = compress_course_map(cmap, thesis=thesis)
    # Merge is OK if atom label preserved on keeper.
    assert report.ok or not report.atom_errors
    labels = {
        x
        for m in compressed.modules
        for r in m.reels
        for x in (r.must_cover or [])
    }
    assert "atom-critical-contrast" in labels


def test_egyptian_rules_not_applied_to_english_presenter():
    contract = build_course_quality_contract(
        _brief(title="English tools"),
        presenter_language="en",
        presenter_dialect="none",
    )
    assert contract.language.apply_egyptian_spoken_qa is False
    eng = run_english_spoken_gate("Furthermore you must click the button carefully today.")
    assert not eng.ok


def test_protected_span_survives_punctuation_strip():
    raw = "قول الجملة " + wrap_protected("ex1", "I'm happy!") + " بعد كده"
    out = punctuation_strip_preserving_protected(
        raw,
        punctuation_policy="protected_examples",
        strip_fn=strip_punctuation_from_spoken_body,
    )
    assert "I'm happy!" in out
    errs = assert_protected_spans_unchanged({"ex1": "I'm happy!"}, out)
    assert errs == []


def test_guaranteed_income_claim_blocked_by_english_gate():
    report = run_english_spoken_gate("This course gives guaranteed income in 30 days.")
    assert any(i.code == "UNSUPPORTED_CLAIM" for i in report.issues)


def test_status_variants_block_export():
    for status in (
        LessonQualityStatus.NEEDS_REVIEW,
        LessonQualityStatus.NEEDS_SOURCES,
        LessonQualityStatus.NEEDS_MAP_REVISION,
        LessonQualityStatus.NEEDS_EXPERT_REVIEW,
    ):
        assert status_blocks_export(status.value)


def test_mutation_after_pass_requires_requalify():
    guard = MutationGuard()
    guard.mark_passed("r1", "النص الأصلي الناجح هنا")
    assert guard.assert_unchanged_or_requalify("r1", "النص الأصلي الناجح هنا") == []
    errs = guard.assert_unchanged_or_requalify("r1", "النص اتغير بعد النجاح")
    assert errs and "content_mutated_after_pass" in errs[0]


def test_snapshot_drift_detected():
    brief = _brief()
    contract = build_course_quality_contract(brief)
    thesis = CourseThesis(
        final_student_outcome="o",
        audience_and_starting_level="a",
        practical_deliverable="d",
    )
    a = build_generation_context_snapshot(
        course_id=1,
        brief=brief,
        contract=contract,
        thesis=thesis,
        source_ids=[1],
        quality_mode="premium",
        model_name="fake",
    )
    b = build_generation_context_snapshot(
        course_id=1,
        brief=brief,
        contract=contract,
        thesis=thesis,
        source_ids=[1, 2],
        quality_mode="premium",
        model_name="fake",
    )
    reasons = compare_snapshots(a, b)
    assert reasons


def test_teleprompter_layout_rejects_word_per_line():
    shredded = "\n".join(["كلمة"] * 8)
    doc = build_teleprompter_doc(shredded)
    issues = evaluate_teleprompter_layout(doc, source_text=shredded)
    assert any(code == IssueCode.BAD_LINE_BREAK.value for code, _ in issues)


def test_coverage_flags_missing_checkpoint_for_practical():
    thesis = CourseThesis(
        final_student_outcome="تصميم بوست",
        audience_and_starting_level="مبتدئ",
        practical_deliverable="بوست",
        mix_type=CourseMixType.PRACTICAL,
    )
    contract = build_course_quality_contract(_brief(title="تصميم"), course_type="practical")
    cmap = CourseMap(
        course_title="C",
        main_thread="t",
        thesis=thesis,
        modules=[
            ModulePlan(
                module_id="m1",
                title="M",
                purpose="p",
                reels=[
                    ReelPlan(
                        reel_id="r1",
                        title="L",
                        purpose="p",
                        distinct_teaching_outcome="outcome",
                        estimated_length="2 minutes",
                    )
                ],
            )
        ],
    )
    report = evaluate_coverage_matrix(cmap, thesis=thesis, contract=contract)
    assert not report.ok
    assert any(i.code == IssueCode.CHECKPOINT_MISSING.value for i in report.issues)


def test_export_blocks_needs_sources_status():
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
                        script_text="كلام كويس praktikal وفيه تعليم حقيقي هنا للطالب",
                        quality_status="needs_sources",
                    )
                ],
            )
        ],
    )
    report = evaluate_export_blockers(final_course=final)
    assert not report.ok
    assert any(b.code == "needs_sources" for b in report.blockers)


def test_filler_generic_phrase_fixture_detected():
    from app.generation.egyptian_arabic_gate import run_egyptian_arabic_gate

    text = "في الفيديو ده هنتعلم حاجة وهنكمل كلام تحفيزي من غير تعليم"
    report = run_egyptian_arabic_gate(text)
    assert not report.ok


def test_literal_cold_audience_is_domain_fixture_not_global_prompt():
    from app.generation.quality.ledgers import DOMAIN_LITERAL_FIXTURES

    assert "عميل بارد" in DOMAIN_LITERAL_FIXTURES["professional_or_income_skill"]
    assert "عميل بارد" not in DOMAIN_LITERAL_FIXTURES["language_learning"]
