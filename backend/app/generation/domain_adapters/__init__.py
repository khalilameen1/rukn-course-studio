"""Domain adapters — add domain rules onto CourseQualityContract without replacing globals."""

from __future__ import annotations

from app.ai.provider import CourseBrief
from app.generation.quality.contract import (
    CourseLanguageProfile,
    CourseQualityContract,
    DeliveryContract,
    DomainPedagogyProfile,
    EvidenceAndRiskProfile,
)
from app.models.enums import AddressForm, CourseMixType, LessonDeliveryMode

ADAPTER_IDS = (
    "language_learning",
    "software_and_tools",
    "professional_or_income_skill",
    "religious_studies",
    "academic_or_general_knowledge",
    "hands_on_practical_skill",
    "high_stakes_health_legal_financial",
    "generic",
)


def resolve_domain_adapter_id(
    *,
    course_domain: str | None,
    course_type: str | None,
    title: str = "",
    outcome: str = "",
) -> str:
    blob = " ".join(
        [
            (course_domain or "").lower(),
            (course_type or "").lower(),
            (title or "").lower(),
            (outcome or "").lower(),
        ]
    )
    if any(
        k in blob
        for k in (
            "language",
            "لغة",
            "english",
            "انجليز",
            "إنجليز",
            "arabic grammar",
            "ielts",
            "grammar",
            "مفردات",
        )
    ):
        return "language_learning"
    if any(k in blob for k in ("software", "tool", "figma", "excel", "canva", "برنامج", "أداة")):
        return "software_and_tools"
    if any(
        k in blob
        for k in ("income", "freelance", "دخل", "بيع", "sales", "marketing", "تسويق")
    ):
        return "professional_or_income_skill"
    if any(k in blob for k in ("دين", "فقه", "قرآن", "حديث", "religious", "islam")):
        return "religious_studies"
    if any(
        k in blob
        for k in ("medical", "health", "legal", "law", "finance", "طبي", "قانون", "مال")
    ):
        return "high_stakes_health_legal_financial"
    if any(k in blob for k in ("academic", "history", "علوم", "أكاديم", "نظرية")):
        return "academic_or_general_knowledge"
    if any(k in blob for k in ("hands", "craft", "يدوي", "نجار", "طبخ", "practical skill")):
        return "hands_on_practical_skill"
    return "generic"


def _base_modes() -> list[LessonDeliveryMode]:
    return [
        LessonDeliveryMode.CAMERA_EXPLAINER,
        LessonDeliveryMode.MICRO_CONCEPT,
        LessonDeliveryMode.BEFORE_AFTER,
        LessonDeliveryMode.ERROR_FIX,
        LessonDeliveryMode.CASE_STUDY,
    ]


def build_course_quality_contract(
    brief: CourseBrief,
    *,
    course_domain: str | None = None,
    course_type: str | None = None,
    address_form: AddressForm = AddressForm.MASCULINE,
    presenter_language: str = "ar",
    presenter_dialect: str = "egyptian",
    delivery_pattern: str = "teleprompter_standard",
    human_override_hard_limits: bool = False,
) -> CourseQualityContract:
    adapter = resolve_domain_adapter_id(
        course_domain=course_domain or brief.course_domain,
        course_type=course_type,
        title=brief.title,
        outcome=brief.outcome,
    )
    language = CourseLanguageProfile(
        presenter_language=presenter_language,
        presenter_dialect=presenter_dialect if presenter_language.startswith("ar") else "none",
        subject_language=presenter_language,
        learner_native_language=presenter_language,
        address_form=address_form,
        script_direction="rtl" if presenter_language.startswith("ar") else "ltr",
        punctuation_policy="none",
        apply_egyptian_spoken_qa=(
            presenter_language.startswith("ar") and presenter_dialect == "egyptian"
        ),
        apply_english_spoken_qa=presenter_language.startswith("en"),
    )
    pedagogy = DomainPedagogyProfile(
        course_domain=adapter,
        course_type=course_type or "practical_skill",
        learner_profile=brief.audience or "",
        learning_promises=[p for p in [brief.outcome] if p],
        allowed_delivery_modes=_base_modes(),
        mix_type=CourseMixType.PRACTICAL,
    )
    evidence = EvidenceAndRiskProfile(risk_level="low")
    delivery = DeliveryContract(
        pattern=delivery_pattern,
        hard_max_lessons=60,
        hard_max_minutes=240,
    )
    if delivery_pattern == "teleprompter_micro_reel":
        delivery.target_reel_words_min = 120
        delivery.target_reel_words_max = 180
        delivery.minimum_reel_words = 100
        delivery.maximum_reel_words = 220
        delivery.hard_max_lessons = 120  # capacity for short-reel maps (e.g. 90)
        delivery.hard_max_minutes = 240
        delivery.allow_micro_reel_maps = True
        delivery.block_word_min = 7
        delivery.block_word_max = 46

    _apply_adapter(adapter, language, pedagogy, evidence, delivery)
    if human_override_hard_limits:
        # Size override only — never quality/source bypass.
        pass
    return CourseQualityContract(
        language=language,
        pedagogy=pedagogy,
        evidence=evidence,
        delivery=delivery,
        adapter_id=adapter,
    )


def _apply_adapter(
    adapter: str,
    language: CourseLanguageProfile,
    pedagogy: DomainPedagogyProfile,
    evidence: EvidenceAndRiskProfile,
    delivery: DeliveryContract,
) -> None:
    if adapter == "language_learning":
        pedagogy.practice_types = ["comprehension", "production", "error_correction"]
        pedagogy.assessment_types = ["oral_response", "written_prompt", "listening_check"]
        pedagogy.project_types = ["dialogue", "recording", "level_check"]
        pedagogy.domain_specific_validators = [
            "grammar_accuracy",
            "natural_examples",
            "level_fit",
            "no_invented_rules",
            "no_misleading_translation",
        ]
        pedagogy.allowed_delivery_modes = _base_modes() + [
            LessonDeliveryMode.MICRO_CONCEPT,
            LessonDeliveryMode.ERROR_FIX,
        ]
        language.protected_example_policy = "preserve_literal"
        language.punctuation_policy = "protected_examples"
        delivery.punctuation_policy = "protected_examples"
        evidence.protected_content_types = ["language_example", "ipa", "contraction"]

    elif adapter == "software_and_tools":
        pedagogy.practice_types = ["screen_walkthrough", "task_completion"]
        pedagogy.assessment_types = ["screenshot_deliverable", "checklist"]
        pedagogy.project_types = ["tool_task", "export_file"]
        pedagogy.domain_specific_validators = [
            "official_docs_freshness",
            "executable_steps",
            "screen_plan_when_needed",
        ]
        pedagogy.allowed_delivery_modes = _base_modes() + [
            LessonDeliveryMode.SCREEN_DEMO,
            LessonDeliveryMode.PROJECT_BUILD,
        ]
        pedagogy.early_practice_required = True
        pedagogy.target_practice_ratio = 0.60
        pedagogy.target_theory_ratio = 0.25
        evidence.freshness_requirements = ["ui_version", "official_changelog"]
        evidence.source_authority_requirements = ["official_docs"]

    elif adapter == "professional_or_income_skill":
        pedagogy.practice_types = ["deliverable", "case_application"]
        pedagogy.assessment_types = ["rubric", "portfolio_piece"]
        pedagogy.project_types = ["client_style_task", "capstone"]
        pedagogy.domain_specific_validators = [
            "no_guaranteed_income",
            "separates_example_from_expected_result",
            "market_claims_need_sources",
            "not_salesy",
        ]
        pedagogy.early_practice_required = True
        pedagogy.target_practice_ratio = 0.60
        pedagogy.target_theory_ratio = 0.25
        evidence.claim_verification_policy = "strict"

    elif adapter == "religious_studies":
        pedagogy.mix_type = CourseMixType.MIXED
        pedagogy.practice_types = ["close_reading", "comparison", "memorization_check"]
        pedagogy.assessment_types = ["short_answer", "source_attribution"]
        pedagogy.project_types = ["sourced_explanation"]
        pedagogy.domain_specific_validators = [
            "no_invented_texts",
            "preserve_sacred_quotes",
            "separate_text_tafsir_opinion",
            "show_considered_disagreement_when_needed",
        ]
        pedagogy.target_practice_ratio = None
        pedagogy.target_theory_ratio = None
        evidence.risk_level = "high"
        evidence.protected_content_types = ["sacred_quote", "hadith", "verse"]
        evidence.claim_verification_policy = "expert_gate"
        evidence.expert_review_requirements = ["sensitive_ruling", "unsourced_attribution"]
        evidence.require_expert_review_before_export = False  # set per claim

    elif adapter == "academic_or_general_knowledge":
        pedagogy.mix_type = CourseMixType.THEORETICAL
        pedagogy.practice_types = ["recall", "explanation", "comparison"]
        pedagogy.assessment_types = ["quiz", "short_essay"]
        pedagogy.project_types = ["knowledge_map", "summary_with_sources"]
        pedagogy.domain_specific_validators = ["no_unsupported_facts", "level_fit"]
        pedagogy.target_theory_ratio = 0.55
        pedagogy.target_practice_ratio = 0.30

    elif adapter == "hands_on_practical_skill":
        pedagogy.practice_types = ["demo", "guided_practice", "independent_task"]
        pedagogy.assessment_types = ["performance", "photo_or_video_proof"]
        pedagogy.project_types = ["finished_artifact"]
        pedagogy.domain_specific_validators = ["safety_when_needed", "step_clarity"]
        pedagogy.early_practice_required = True
        pedagogy.target_practice_ratio = 0.65
        pedagogy.target_theory_ratio = 0.20
        pedagogy.allowed_delivery_modes = _base_modes() + [
            LessonDeliveryMode.SCREEN_DEMO,
            LessonDeliveryMode.PROJECT_BUILD,
            LessonDeliveryMode.BEFORE_AFTER,
        ]

    elif adapter == "high_stakes_health_legal_financial":
        pedagogy.mix_type = CourseMixType.MIXED
        pedagogy.practice_types = ["scenario_analysis", "checklist"]
        pedagogy.assessment_types = ["case_response"]
        pedagogy.project_types = ["decision_memo_with_sources"]
        pedagogy.domain_specific_validators = [
            "no_diagnosis_or_guarantee",
            "official_or_professional_sources",
            "expert_gate_for_actionable_advice",
        ]
        evidence.risk_level = "critical"
        evidence.source_authority_requirements = ["official", "professional"]
        evidence.freshness_requirements = ["current_regulation_or_guideline"]
        evidence.claim_verification_policy = "expert_gate"
        evidence.require_expert_review_before_export = True
        evidence.protected_content_types = ["legal_article_number", "official_figure"]

    else:  # generic
        pedagogy.domain_specific_validators = ["unique_outcome", "spoken_not_essay"]
        pedagogy.project_types = ["module_checkpoint", "capstone"]
