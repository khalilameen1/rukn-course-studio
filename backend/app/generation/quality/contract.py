"""CourseQualityContract — language, pedagogy, evidence, delivery per course."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import AddressForm, CourseMixType, LessonDeliveryMode


class CourseLanguageProfile(BaseModel):
    presenter_language: str = "ar"
    presenter_dialect: str = "egyptian"  # egyptian | msa | none | en_neutral
    subject_language: str = "ar"
    learner_native_language: str = "ar"
    learner_level: str = "beginner"
    bilingual_policy: str = "presenter_primary"  # presenter_primary | mixed_spans | subject_primary
    pronunciation_standard: str = ""
    address_form: AddressForm = AddressForm.MASCULINE
    script_direction: str = "rtl"
    punctuation_policy: str = "none"  # none | natural | protected_examples
    protected_example_policy: str = "preserve_literal"
    apply_egyptian_spoken_qa: bool = True
    apply_english_spoken_qa: bool = False


class DomainPedagogyProfile(BaseModel):
    course_domain: str = "generic"
    course_type: str = "practical_skill"
    learner_profile: str = ""
    prior_knowledge: str = ""
    learning_promises: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    practice_types: list[str] = Field(default_factory=list)
    assessment_types: list[str] = Field(default_factory=list)
    project_types: list[str] = Field(default_factory=list)
    allowed_delivery_modes: list[LessonDeliveryMode] = Field(default_factory=list)
    depth_level: str = "applied"
    domain_specific_validators: list[str] = Field(default_factory=list)
    mix_type: CourseMixType = CourseMixType.PRACTICAL
    target_theory_ratio: float | None = None
    target_practice_ratio: float | None = None
    early_practice_required: bool = False
    early_practice_within_fraction: float = 0.10
    early_practice_within_lessons: int = 7


class EvidenceAndRiskProfile(BaseModel):
    risk_level: str = "low"  # low | medium | high | critical
    source_authority_requirements: list[str] = Field(default_factory=list)
    freshness_requirements: list[str] = Field(default_factory=list)
    expert_review_requirements: list[str] = Field(default_factory=list)
    protected_content_types: list[str] = Field(default_factory=list)
    claim_verification_policy: str = "standard"  # standard | strict | expert_gate
    require_expert_review_before_export: bool = False


class DeliveryContract(BaseModel):
    spoken_only: bool = True
    pattern: str = "teleprompter_standard"  # teleprompter_standard | teleprompter_micro_reel
    target_reel_words_min: int = 120
    target_reel_words_max: int = 180
    minimum_reel_words: int = 80
    maximum_reel_words: int = 360
    speaking_rate_wpm: int = 135
    minimum_duration_seconds: int = 40
    teleprompter_line_target_min: int = 6
    teleprompter_line_target_max: int = 10
    teleprompter_line_hard_max: int = 12
    block_word_min: int = 7
    block_word_max: int = 46
    block_line_min: int = 2
    block_line_max: int = 4
    punctuation_policy: str = "none"
    module_checkpoint_policy: str = "required_for_practical"
    forbid_filming_cues: bool = True
    forbid_internal_labels: bool = True
    forbid_metadata: bool = True
    hard_max_lessons: int = 60
    hard_max_minutes: int = 240
    allow_micro_reel_maps: bool = False


class CourseQualityContract(BaseModel):
    language: CourseLanguageProfile = Field(default_factory=CourseLanguageProfile)
    pedagogy: DomainPedagogyProfile = Field(default_factory=DomainPedagogyProfile)
    evidence: EvidenceAndRiskProfile = Field(default_factory=EvidenceAndRiskProfile)
    delivery: DeliveryContract = Field(default_factory=DeliveryContract)
    adapter_id: str = "generic"
    version: str = "1.0"

    def fingerprint_payload(self) -> dict:
        return self.model_dump(mode="json")
