from __future__ import annotations

import pytest

from app.ai.fake_provider import FakeProvider
from app.generation.contracts.lesson_semantic import (
    attach_lesson_semantic_contracts,
    inspect_script_against_semantic_contract,
    remove_safe_semantic_filler,
    validate_lesson_semantic_contract,
)
from app.generation.errors import UnusableOutputError
from app.generation.orchestrator import _write_and_review_reel
from app.schemas.generation import (
    CourseMap,
    LessonSemanticContract,
    ModulePlan,
    ReelPlan,
)


def _reel(
    reel_id: str = "m1-r1",
    *,
    contract: LessonSemanticContract | None = None,
) -> ReelPlan:
    return ReelPlan(
        reel_id=reel_id,
        title="تحديد وزن العنوان",
        purpose="اختيار وزن بصري يوضح أولوية العنوان",
        must_cover=["وزن العنوان", "ترتيب النظر"],
        must_avoid=["تكبير كل العناصر بنفس الدرجة"],
        distinct_teaching_outcome="يميّز العنوان الأساسي من أول نظرة",
        new_skill_or_decision="يقرر وزن العنوان حسب أولوية الرسالة",
        student_can_do_after="يضبط وزن العنوان باستقلال",
        project_contribution="تسليم تصميم واضح الأولوية",
        lesson_semantic_contract=contract,
    )


def _contract(tag: str = "العنوان") -> LessonSemanticContract:
    return LessonSemanticContract(
        learner_before=f"المتعلم يكبّر كل عناصر {tag} بالتساوي",
        learner_after=f"المتعلم يقرر وزن {tag} حسب أولوية الرسالة",
        exact_capability_change=f"ينتقل من التكبير العشوائي إلى وزن {tag} المقصود",
        strongest_non_obvious_meaning=f"وزن {tag} يوجّه القرار قبل ما يجمّل الشكل",
        misconception_or_failure=f"تكبير كل عناصر {tag} يلغي ترتيب النظر",
        causal_explanation=f"اختلاف وزن {tag} يصنع نقطة دخول ثم مسار قراءة",
        proof_example_or_demonstration=f"قارن تصميمين يختلف فيهما وزن {tag} فقط",
        learner_test_or_action=f"عدّل وزن {tag} واختبر أول عنصر تقع عليه العين",
        boundary_or_exception=f"لا تزود وزن {tag} لو الرسالة الثانوية هي الأهم في الحالة",
        real_tension=f"وازن بين وضوح {tag} وعدم ابتلاع باقي الرسالة",
        complete_payoff=f"ينتهي الدرس بتصميم يثبت أولوية {tag} من أول نظرة",
        earned_next_need=f"بعد ثبات وزن {tag} نحتاج ضبط المسافة حوله",
        escalation_role=f"ينقل المتعلم من ملاحظة {tag} إلى التحكم في أثره",
        sequence_dependency=f"يعتمد قرار وزن {tag} على أولوية الرسالة المحددة قبله",
    )


def _course(reel: ReelPlan) -> tuple[CourseMap, ModulePlan]:
    module = ModulePlan(
        module_id="m1",
        title="الهرمية البصرية",
        purpose="بناء مسار قراءة مقصود",
        reels=[reel],
    )
    return (
        CourseMap(
            course_title="تصميم منشور واضح",
            main_thread="كل قرار بصري يخدم أولوية الرسالة",
            modules=[module],
        ),
        module,
    )


def test_contract_schema_contains_every_required_semantic_field() -> None:
    assert set(LessonSemanticContract.model_fields) == {
        "learner_before",
        "learner_after",
        "exact_capability_change",
        "strongest_non_obvious_meaning",
        "misconception_or_failure",
        "causal_explanation",
        "proof_example_or_demonstration",
        "learner_test_or_action",
        "boundary_or_exception",
        "real_tension",
        "complete_payoff",
        "earned_next_need",
        "escalation_role",
        "sequence_dependency",
    }


def test_generic_or_interchangeable_contract_is_rejected() -> None:
    reel = _reel()
    generic = LessonSemanticContract(
        **{name: "important concept" for name in LessonSemanticContract.model_fields}
    )
    generic_result = validate_lesson_semantic_contract(generic, reel)
    assert not generic_result.ok
    assert any("generic or empty" in error for error in generic_result.errors)

    unrelated = _contract("إدارة ميزانية إعلانية").model_copy(
        update={
            "exact_capability_change": "ينتقل من صرف عشوائي إلى توزيع ميزانية الحملة",
            "strongest_non_obvious_meaning": "تكلفة الاكتساب أهم من عدد النقرات الخام",
            "causal_explanation": "سقف المزايدة يغير معدل استهلاك ميزانية الحملة",
            "proof_example_or_demonstration": "قارن حملتين تختلفان في سقف المزايدة فقط",
            "learner_test_or_action": "وزع ميزانية حملة جديدة واحسب تكلفة الاكتساب",
            "complete_payoff": "ينتهي التطبيق بخطة إنفاق إعلاني قابلة للقياس",
        }
    )
    unrelated_result = validate_lesson_semantic_contract(unrelated, reel)
    assert not unrelated_result.ok
    assert any("interchangeable" in error for error in unrelated_result.errors)


def test_duplicate_capability_is_rejected_across_lessons() -> None:
    contract = _contract()
    result = validate_lesson_semantic_contract(
        contract,
        _reel("m1-r2"),
        peer_contracts=[contract],
    )
    assert not result.ok
    assert any("duplicates another lesson" in error for error in result.errors)


def test_contracts_are_attached_to_the_map_before_writing() -> None:
    course, _ = _course(_reel())
    frozen = attach_lesson_semantic_contracts(course)
    contract = frozen.modules[0].reels[0].lesson_semantic_contract
    assert contract is not None
    assert "وزن العنوان" in contract.exact_capability_change
    assert validate_lesson_semantic_contract(
        contract,
        frozen.modules[0].reels[0],
    ).ok


def test_invalid_contract_stops_before_provider_write() -> None:
    class TrackingFake(FakeProvider):
        def __init__(self) -> None:
            super().__init__()
            self.write_calls = 0

        def write_single_reel(self, input):  # noqa: ANN001
            self.write_calls += 1
            return super().write_single_reel(input)

    generic = LessonSemanticContract(
        **{name: "important concept" for name in LessonSemanticContract.model_fields}
    )
    reel = _reel(contract=generic)
    course, module = _course(reel)
    provider = TrackingFake()

    with pytest.raises(UnusableOutputError, match="rejected before prose"):
        _write_and_review_reel(
            provider=provider,
            course_map=course,
            module=module,
            reel_plan=reel,
            prior_reels=[],
            all_reels_so_far=[],
            sources=[],
            rules_context={},
        )

    assert provider.write_calls == 0


def test_script_must_realize_meaning_proof_action_boundary_and_payoff() -> None:
    contract = _contract()
    complete_script = "\n".join(contract.model_dump().values())
    complete = inspect_script_against_semantic_contract(complete_script, contract)
    assert complete.ok

    incomplete = inspect_script_against_semantic_contract(
        contract.exact_capability_change,
        contract,
    )
    assert not incomplete.ok
    assert "proof_example_or_demonstration" in incomplete.missing_fields
    assert "learner_test_or_action" in incomplete.missing_fields
    assert "complete_payoff" in incomplete.missing_fields


def test_filler_removal_is_conservative_and_preserves_semantic_payload() -> None:
    contract = _contract()
    semantic_lines = list(contract.model_dump().values())
    script = "\n".join(["خلينا نبدأ", *semantic_lines, semantic_lines[0]])

    cleaned, removed = remove_safe_semantic_filler(script, contract)

    assert "خلينا نبدأ" in removed
    assert semantic_lines[0] in cleaned
    assert cleaned.count(semantic_lines[0]) == 1
    assert inspect_script_against_semantic_contract(cleaned, contract).ok
