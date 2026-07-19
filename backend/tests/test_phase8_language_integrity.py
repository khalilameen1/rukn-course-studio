"""Phase 8 language profile, term ledger, and spoken-variety integrity tests.

The only writer-path test generates one fake lesson; no complete course or
external provider is used.
"""

import pytest

from app.ai.fake_provider import FakeProvider
from app.ai.provider import CourseBrief
from app.generation.domain_adapters import build_course_quality_contract
from app.generation.egyptian_arabic_gate import (
    compile_language_profile_guidance,
    run_spoken_variety_integrity_gate,
)
from app.generation.orchestrator import _write_and_review_reel
from app.generation.quality.context_snapshot import build_generation_context_snapshot
from app.generation.terminology_map import (
    build_term_ledger,
    compile_term_ledger_guidance,
)
from app.models.enums import (
    AddressForm,
    ExplanationLevel,
    StructureMode,
    TargetMarket,
)
from app.schemas.generation import CourseMap, CourseThesis, ModulePlan, ReelPlan


def _brief() -> CourseBrief:
    return CourseBrief(
        title="Design decisions",
        audience="beginner designers",
        outcome="choose hierarchy intentionally",
        structure_mode=StructureMode.CONNECTED_NO_MODULES,
        explanation_level=ExplanationLevel.FINAL_ONLY,
        target_market=TargetMarket.EGYPT,
        course_domain="graphic_design",
        realistic_student_budget="EGP 500 monthly",
        available_tools=["Figma"],
    )


def _thesis() -> CourseThesis:
    return CourseThesis(
        final_student_outcome="choose hierarchy intentionally",
        audience_and_starting_level="beginner designers",
        practical_deliverable="one revised layout",
        course_domain="graphic_design",
        target_market="egypt",
        realistic_student_budget="EGP 500 monthly",
        available_tools=["Figma"],
    )


def test_language_profile_and_term_ledger_exist_before_lesson_writing():
    brief = _brief()
    thesis = _thesis()
    contract = build_course_quality_contract(brief)
    snapshot = build_generation_context_snapshot(
        course_id=1,
        brief=brief,
        contract=contract,
        thesis=thesis,
        course_map=None,
    )
    assert snapshot.LANGUAGE_PROFILE["presenter_dialect"] == "egyptian"
    assert snapshot.LANGUAGE_PROFILE["address_form"] == "masculine"
    assert snapshot.TERM_LEDGER["built_before_writing"] is True
    assert snapshot.TERM_LEDGER["course_domain"] == "graphic_design"
    assert snapshot.TERM_LEDGER["available_tools"] == ["Figma"]


def test_language_and_term_prompts_require_direct_spoken_composition():
    profile = {
        "presenter_language": "ar",
        "presenter_dialect": "egyptian",
        "address_form": "masculine",
        "bilingual_policy": "presenter_primary",
    }
    language = compile_language_profile_guidance(profile)
    ledger = build_term_ledger(
        language_profile=profile,
        course_domain="marketing",
        target_market="egypt",
        available_tools=["Meta Ads Manager"],
    )
    terms = compile_term_ledger_guidance(ledger)
    assert "Never draft in English or MSA then translate" in language
    assert "Code-switch only for conventional" in language
    assert "misleading Arabic calque" in language
    assert "natural meaning on first use" in terms
    assert "corporate ethics/governance" in terms


def test_standalone_thumma_is_serious_except_protected_or_approved_evidence():
    text = "اختار الهدف ثم راجع الإعدادات"
    ordinary = run_spoken_variety_integrity_gate(text)
    assert any(
        issue.code == "standalone_thumma_connector" and issue.severity == "serious"
        for issue in ordinary.issues
    )

    protected = run_spoken_variety_integrity_gate(
        text,
        protected_spans=["اختار الهدف ثم راجع الإعدادات"],
    )
    assert "standalone_thumma_connector" not in {
        issue.code for issue in protected.issues
    }

    approved = run_spoken_variety_integrity_gate(
        text,
        approved_voice_evidence=["مقطع صوتي معتمد يستخدم ثم بقصد واضح"],
    )
    assert "standalone_thumma_connector" not in {
        issue.code for issue in approved.issues
    }


@pytest.mark.parametrize(
    ("text", "expected_code"),
    [
        ("إنت تختار الهدف وبناءً عليه تراجع القرار", "written_connector_residue"),
        ("إذا اخترت الهدف فإنه يتعين عليك المراجعة", "formal_syntax_morphology"),
        ("قم بتعديل التصميم واحرص على أن تحفظه", "formal_command_or_question"),
        ("وبالتالي فإنه فبمجرد أن تحفظ الملف راجعه", "attached_prefix_residue"),
        (
            "Open campaign dashboard then choose audience settings and launch preview",
            "uncontrolled_code_switching",
        ),
        ("مانيبوليت العميل عشان يشتري", "hostile_or_strange_calque"),
    ],
)
def test_gate_reviews_structure_morphology_order_prefixes_and_code_switching(
    text: str,
    expected_code: str,
):
    report = run_spoken_variety_integrity_gate(text)
    assert expected_code in {issue.code for issue in report.issues}
    assert not report.ok


def test_register_mixing_and_irrelevant_corporate_ethics_are_contextual():
    mixed = run_spoken_variety_integrity_gate(
        "إنت عندك اختيار وبالإضافة إلى ذلك يتعين عليك تنفيذه"
    )
    assert "unjustified_register_mixing" in {issue.code for issue in mixed.issues}

    irrelevant = run_spoken_variety_integrity_gate(
        "ابدأ بميثاق الأخلاقيات المؤسسية قبل تعديل الصورة",
        course_domain="graphic_design",
    )
    justified = run_spoken_variety_integrity_gate(
        "راجع ميثاق الأخلاقيات المؤسسية قبل القرار",
        course_domain="corporate ethics and compliance",
    )
    assert "irrelevant_corporate_ethics_register" in {
        issue.code for issue in irrelevant.issues
    }
    assert "irrelevant_corporate_ethics_register" not in {
        issue.code for issue in justified.issues
    }


def test_single_fake_lesson_receives_frozen_language_and_term_packs_and_rechecks():
    class CapturingFake(FakeProvider):
        def __init__(self) -> None:
            super().__init__()
            self.rule_keys: list[set[str]] = []

        def write_single_reel(self, input):  # noqa: ANN001
            self.rule_keys.append(set(input.rules_context))
            return super().write_single_reel(input)

    thesis = _thesis()
    reel = ReelPlan(
        reel_id="m1-r1",
        title="وزن العنوان",
        purpose="اختيار وزن عنوان يوضح أول نقطة قراءة",
        distinct_teaching_outcome="اختيار وزن عنوان مناسب",
        new_skill_or_decision="تحديد وزن العنوان حسب أولوية الرسالة",
        must_cover=["اختيار وزن العنوان حسب أولوية الرسالة"],
    )
    module = ModulePlan(
        module_id="m1",
        title="الهرمية",
        purpose="قرارات الهرمية",
        reels=[reel],
    )
    course_map = CourseMap(
        course_title="Design decisions",
        main_thread="قرار بصري قابل للتطبيق",
        modules=[module],
        thesis=thesis,
    )
    provider = CapturingFake()
    master, _writes, _caught, needs_review = _write_and_review_reel(
        provider=provider,
        course_map=course_map,
        module=module,
        reel_plan=reel,
        prior_reels=[],
        all_reels_so_far=[],
        sources=[],
        rules_context={},
        address_form=AddressForm.MASCULINE,
        target_market=TargetMarket.EGYPT,
        available_tools=["Figma"],
        language_profile={
            "presenter_language": "ar",
            "presenter_dialect": "egyptian",
            "address_form": "masculine",
            "bilingual_policy": "presenter_primary",
            "apply_egyptian_spoken_qa": True,
        },
    )
    assert all("rukn_language_profile_runtime" in keys for keys in provider.rule_keys)
    assert all("rukn_term_ledger_runtime" in keys for keys in provider.rule_keys)
    post = master.quality_report["spoken_variety_integrity"]
    assert post["teleprompter_recheck_passed"] is True
    assert post["semantic_recheck_passed"] is True
    assert master.script_text == "\n".join(master.spoken_beats)
    assert "؛" not in master.script_text
    assert needs_review is False, (master.quality_report, master.script_text)
