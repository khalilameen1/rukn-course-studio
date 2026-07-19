"""Canonical course-family adapters for the unified quality contract.

The primary family is an explicit intake field. Keyword inference exists only
to migrate legacy courses whose stored family is ``general_skill``; it never
invents instructor experience, constraints, or personal claims.
"""

from __future__ import annotations

from app.ai.provider import CourseBrief
from app.generation.quality.contract import (
    CourseLanguageProfile,
    CourseQualityContract,
    DeliveryContract,
    DomainPedagogyProfile,
    EvidenceAndRiskProfile,
)
from app.models.enums import AddressForm, CourseFamily, CourseMixType, LessonDeliveryMode

ADAPTER_IDS = tuple(family.value for family in CourseFamily)


def _family(value: CourseFamily | str | None) -> CourseFamily:
    if isinstance(value, CourseFamily):
        return value
    try:
        return CourseFamily(str(value or ""))
    except ValueError:
        return CourseFamily.GENERAL_SKILL


def resolve_domain_adapter_id(
    *,
    primary_course_family: CourseFamily | str | None = None,
    course_domain: str | None,
    course_type: str | None,
    title: str = "",
    outcome: str = "",
) -> str:
    """Resolve one canonical family, with a migration fallback for old rows."""
    if primary_course_family is not None:
        return _family(primary_course_family).value

    blob = " ".join(
        [course_domain or "", course_type or "", title or "", outcome or ""]
    ).lower()
    family_keywords: tuple[tuple[CourseFamily, tuple[str, ...]], ...] = (
        (
            CourseFamily.HIGH_STAKES_AUTHORITY_SENSITIVE,
            (
                "medical",
                "health",
                "legal",
                "law",
                "finance",
                "religious",
                "islam",
                "طبي",
                "صحي",
                "قانون",
                "مالي",
                "فقه",
                "حديث",
                "قرآن",
            ),
        ),
        (
            CourseFamily.LANGUAGES_COMMUNICATION,
            (
                "language",
                "english",
                "arabic",
                "grammar",
                "ielts",
                "لغة",
                "إنجليز",
                "انجليز",
                "تواصل",
                "مفردات",
            ),
        ),
        (
            CourseFamily.PROGRAMMING_TECHNICAL,
            (
                "programming",
                "software",
                "developer",
                "coding",
                "api",
                "excel",
                "برمجة",
                "تقني",
                "تطوير",
            ),
        ),
        (
            CourseFamily.SALES_MARKETING_BUSINESS,
            (
                "sales",
                "marketing",
                "business",
                "freelance",
                "income",
                "بيع",
                "تسويق",
                "أعمال",
                "دخل",
            ),
        ),
        (
            CourseFamily.CREATIVE_PRODUCTION,
            (
                "design",
                "figma",
                "canva",
                "video",
                "photo",
                "craft",
                "تصميم",
                "مونتاج",
                "تصوير",
                "إبداع",
            ),
        ),
        (
            CourseFamily.ANALYTICAL_OPERATIONAL,
            (
                "analytics",
                "operations",
                "process",
                "data",
                "تحليل",
                "تشغيل",
                "عمليات",
                "بيانات",
            ),
        ),
        (
            CourseFamily.PROFESSIONAL_SERVICE,
            (
                "consulting",
                "client",
                "service",
                "coach",
                "استشار",
                "عميل",
                "خدمة مهنية",
            ),
        ),
    )
    for family, keywords in family_keywords:
        if any(keyword in blob for keyword in keywords):
            return family.value
    return CourseFamily.GENERAL_SKILL.value


def _base_modes() -> list[LessonDeliveryMode]:
    return [
        LessonDeliveryMode.CAMERA_EXPLAINER,
        LessonDeliveryMode.MICRO_CONCEPT,
        LessonDeliveryMode.BEFORE_AFTER,
        LessonDeliveryMode.ERROR_FIX,
        LessonDeliveryMode.CASE_STUDY,
    ]


def _spoken_dialect(language: str, variety: str) -> str:
    if not language.lower().startswith("ar"):
        return "none"
    lowered = variety.lower()
    if "egypt" in lowered or "مصري" in lowered:
        return "egyptian"
    if lowered in {"msa", "modern_standard_arabic", "fusha", "فصحى"}:
        return "msa"
    return variety or "neutral"


def build_course_quality_contract(
    brief: CourseBrief,
    *,
    primary_course_family: CourseFamily | str | None = None,
    course_domain: str | None = None,
    course_type: str | None = None,
    address_form: AddressForm | None = None,
    presenter_language: str | None = None,
    presenter_dialect: str | None = None,
    delivery_pattern: str = "teleprompter_standard",
    human_override_hard_limits: bool = False,
) -> CourseQualityContract:
    family_id = resolve_domain_adapter_id(
        primary_course_family=(
            primary_course_family
            if primary_course_family is not None
            else brief.primary_course_family
        ),
        course_domain=course_domain or brief.course_domain,
        course_type=course_type or brief.course_type,
        title=brief.title,
        outcome=brief.outcome,
    )
    family = CourseFamily(family_id)
    language_code = (presenter_language or brief.student_language or "ar").strip()
    spoken_variety = presenter_dialect or _spoken_dialect(
        language_code, brief.spoken_variety
    )
    language = CourseLanguageProfile(
        presenter_language=language_code,
        presenter_dialect=spoken_variety,
        subject_language=language_code,
        learner_native_language=brief.student_language or language_code,
        address_form=address_form or brief.address_form,
        script_direction="rtl" if language_code.startswith("ar") else "ltr",
        punctuation_policy="none",
        apply_egyptian_spoken_qa=(
            language_code.startswith("ar") and spoken_variety == "egyptian"
        ),
        apply_english_spoken_qa=language_code.startswith("en"),
    )
    pedagogy = DomainPedagogyProfile(
        course_domain=course_domain or brief.course_domain or family_id,
        course_type=course_type or brief.course_type or "practical_skill",
        primary_course_family=family,
        secondary_course_families=list(brief.secondary_course_families),
        learner_profile=brief.audience or "",
        prior_knowledge=brief.learner_starting_state or brief.audience or "",
        learner_starting_state=brief.learner_starting_state or brief.audience or "",
        required_final_performance=(
            brief.required_final_performance or brief.outcome or ""
        ),
        required_independence_level=brief.required_independence_level,
        realistic_student_budget=brief.realistic_student_budget or "",
        available_tools=list(brief.available_tools),
        learning_promises=[
            promise
            for promise in [brief.required_final_performance or brief.outcome]
            if promise
        ],
        allowed_delivery_modes=_base_modes(),
        mix_type=CourseMixType.PRACTICAL,
    )
    evidence = EvidenceAndRiskProfile(
        risk_level="low",
        instructor_responsibility_boundaries=list(
            brief.instructor_responsibility_boundaries
        ),
        verified_instructor_experience=list(brief.verified_instructor_experience),
        forbidden_first_person_claims=list(brief.forbidden_first_person_claims),
        professional_constraints=list(brief.professional_constraints),
        high_stakes_constraints=list(brief.high_stakes_constraints),
    )
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
        delivery.hard_max_lessons = 120
        delivery.allow_micro_reel_maps = True
        delivery.block_word_min = 7
        delivery.block_word_max = 46

    _apply_adapter(family, language, pedagogy, evidence)
    if human_override_hard_limits:
        # Size override only; evidence, language, and safety gates stay binding.
        pass
    return CourseQualityContract(
        language=language,
        pedagogy=pedagogy,
        evidence=evidence,
        delivery=delivery,
        adapter_id=family.value,
    )


def _apply_adapter(
    family: CourseFamily,
    language: CourseLanguageProfile,
    pedagogy: DomainPedagogyProfile,
    evidence: EvidenceAndRiskProfile,
) -> None:
    """Apply materially different teaching, assessment, and risk semantics."""
    if family is CourseFamily.CREATIVE_PRODUCTION:
        pedagogy.practice_types = [
            "guided_creation",
            "design_critique",
            "before_after_revision",
        ]
        pedagogy.assessment_types = ["artifact_rubric", "portfolio_critique"]
        pedagogy.project_types = ["production_piece", "portfolio_artifact"]
        pedagogy.domain_specific_validators = [
            "demonstration_matches_artifact",
            "choices_have_craft_reasoning",
            "visual_assets_declared",
            "critique_is_actionable",
        ]
        pedagogy.allowed_delivery_modes += [
            LessonDeliveryMode.DESIGN_CRITIQUE,
            LessonDeliveryMode.PROJECT_BUILD,
            LessonDeliveryMode.SCREEN_DEMO,
        ]
        pedagogy.early_practice_required = True
        pedagogy.target_practice_ratio = 0.65
        pedagogy.target_theory_ratio = 0.20

    elif family is CourseFamily.ANALYTICAL_OPERATIONAL:
        pedagogy.practice_types = [
            "diagnosis",
            "decision_case",
            "process_execution",
            "error_analysis",
        ]
        pedagogy.assessment_types = ["case_decision", "process_checklist"]
        pedagogy.project_types = ["operating_plan", "analysis_memo"]
        pedagogy.domain_specific_validators = [
            "assumptions_are_explicit",
            "decision_follows_evidence",
            "process_is_executable",
            "edge_cases_are_handled",
        ]
        pedagogy.allowed_delivery_modes += [LessonDeliveryMode.PROJECT_BUILD]
        pedagogy.target_practice_ratio = 0.60
        pedagogy.target_theory_ratio = 0.25

    elif family is CourseFamily.PROGRAMMING_TECHNICAL:
        pedagogy.practice_types = [
            "screen_walkthrough",
            "implementation",
            "debugging",
            "error_fix",
        ]
        pedagogy.assessment_types = ["runnable_artifact", "debugging_check"]
        pedagogy.project_types = ["working_implementation", "technical_capstone"]
        pedagogy.domain_specific_validators = [
            "official_docs_freshness",
            "executable_steps",
            "screen_plan_when_needed",
            "principle_before_ui_location",
            "version_sensitive_claims_are_scoped",
        ]
        pedagogy.allowed_delivery_modes += [
            LessonDeliveryMode.SCREEN_DEMO,
            LessonDeliveryMode.PROJECT_BUILD,
        ]
        pedagogy.early_practice_required = True
        pedagogy.target_practice_ratio = 0.65
        pedagogy.target_theory_ratio = 0.20
        evidence.freshness_requirements = ["current_official_documentation"]
        evidence.source_authority_requirements = ["official_docs"]

    elif family is CourseFamily.LANGUAGES_COMMUNICATION:
        pedagogy.practice_types = [
            "comprehension",
            "production",
            "pronunciation",
            "error_correction",
            "role_play",
        ]
        pedagogy.assessment_types = [
            "oral_response",
            "listening_check",
            "live_scenario",
        ]
        pedagogy.project_types = ["conversation_performance", "communication_task"]
        pedagogy.domain_specific_validators = [
            "grammar_accuracy",
            "natural_examples",
            "level_fit",
            "no_invented_rules",
            "no_misleading_translation",
            "pronunciation_is_verifiable",
        ]
        language.protected_example_policy = "preserve_literal"
        language.punctuation_policy = "protected_examples"
        evidence.protected_content_types = [
            "language_example",
            "phonetic_notation",
            "contraction",
        ]

    elif family is CourseFamily.SALES_MARKETING_BUSINESS:
        pedagogy.practice_types = [
            "market_case",
            "role_play",
            "campaign_build",
            "offer_critique",
        ]
        pedagogy.assessment_types = ["scenario_response", "commercial_rubric"]
        pedagogy.project_types = ["campaign_brief", "sales_conversation", "offer_plan"]
        pedagogy.domain_specific_validators = [
            "no_guaranteed_income",
            "market_claims_need_sources",
            "separates_example_from_expected_result",
            "budget_and_buyer_behavior_are_market_realistic",
            "not_salesy",
        ]
        pedagogy.early_practice_required = True
        pedagogy.target_practice_ratio = 0.60
        pedagogy.target_theory_ratio = 0.25
        evidence.claim_verification_policy = "strict"

    elif family is CourseFamily.PROFESSIONAL_SERVICE:
        pedagogy.practice_types = [
            "client_case",
            "scope_diagnosis",
            "deliverable_build",
            "professional_judgment",
        ]
        pedagogy.assessment_types = ["client_deliverable_rubric", "boundary_case"]
        pedagogy.project_types = ["client_ready_deliverable", "service_workflow"]
        pedagogy.domain_specific_validators = [
            "scope_and_boundaries_are_explicit",
            "client_context_changes_recommendation",
            "professional_ethics_when_relevant",
            "no_invented_personal_experience",
        ]
        pedagogy.allowed_delivery_modes += [LessonDeliveryMode.PROJECT_BUILD]
        pedagogy.target_practice_ratio = 0.60
        pedagogy.target_theory_ratio = 0.25
        evidence.claim_verification_policy = "strict"
        evidence.risk_level = "medium"

    elif family is CourseFamily.HIGH_STAKES_AUTHORITY_SENSITIVE:
        pedagogy.mix_type = CourseMixType.MIXED
        pedagogy.practice_types = ["bounded_scenario_analysis", "safety_checklist"]
        pedagogy.assessment_types = ["sourced_case_response", "escalation_decision"]
        pedagogy.project_types = ["decision_memo_with_sources"]
        pedagogy.domain_specific_validators = [
            "no_diagnosis_ruling_or_guarantee",
            "official_or_professional_sources",
            "uncertainty_and_jurisdiction_are_explicit",
            "expert_gate_for_actionable_advice",
            "no_invented_authority_or_personal_experience",
        ]
        evidence.risk_level = "critical"
        evidence.source_authority_requirements = ["official", "professional"]
        evidence.freshness_requirements = ["current_regulation_or_guideline"]
        evidence.claim_verification_policy = "expert_gate"
        evidence.require_expert_review_before_export = True
        evidence.protected_content_types = [
            "legal_article_number",
            "official_figure",
            "sacred_or_authoritative_quote",
        ]
        evidence.expert_review_requirements = [
            "actionable_high_stakes_claim",
            "authority_sensitive_interpretation",
        ]

    else:
        pedagogy.practice_types = ["guided_practice", "independent_application"]
        pedagogy.assessment_types = ["performance_check"]
        pedagogy.project_types = ["capstone"]
        pedagogy.domain_specific_validators = [
            "unique_outcome",
            "spoken_not_essay",
            "level_fit",
            "no_invented_personal_experience",
        ]
        pedagogy.target_practice_ratio = 0.60
        pedagogy.target_theory_ratio = 0.25
