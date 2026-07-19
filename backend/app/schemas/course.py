from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import (
    AddressForm,
    CourseFamily,
    ExplanationLevel,
    GenerationPreset,
    GenerationQualityMode,
    TargetMarket,
    WebResearchMode,
)
from app.schemas.validators import (
    AddressFormLoose,
    CourseFamilyLoose,
    ExplanationLevelLoose,
    GenerationPresetLoose,
    GenerationQualityModeLoose,
    StructureModeLoose,
    TargetMarketLoose,
    WebResearchModeLoose,
)


def _clean_string_list(value: object) -> list[str]:
    """Normalize user-entered constraints without inventing any content."""
    if value is None:
        return []
    if isinstance(value, str):
        values = [part for part in value.splitlines() if part.strip()]
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        raise ValueError("expected a list of text values")
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = str(item).strip()
        if not text or text in seen:
            continue
        if len(text) > 500:
            raise ValueError("each intake constraint must be at most 500 characters")
        seen.add(text)
        cleaned.append(text)
    if len(cleaned) > 50:
        raise ValueError("at most 50 values are allowed")
    return cleaned


class CourseCreate(BaseModel):
    title: str
    audience: str
    outcome: str
    special_notes: Optional[str] = None
    course_type: str = "practical_skill"
    course_domain: Optional[str] = None
    course_specialty: Optional[str] = None
    primary_course_family: CourseFamilyLoose = CourseFamily.GENERAL_SKILL
    secondary_course_families: list[CourseFamilyLoose] = Field(default_factory=list)
    structure_mode: StructureModeLoose
    manual_map_text: Optional[str] = None
    explanation_level: ExplanationLevelLoose = ExplanationLevel.FINAL_ONLY
    generation_preset: GenerationPresetLoose = GenerationPreset.BALANCED
    generation_quality_mode: GenerationQualityModeLoose = GenerationQualityMode.PREMIUM
    web_research_mode: WebResearchModeLoose = WebResearchMode.AUTONOMOUS_GAP_FILL
    target_market: TargetMarketLoose = TargetMarket.EGYPT
    student_language: str = "ar"
    spoken_variety: str = "egyptian_colloquial"
    address_form: AddressFormLoose = AddressForm.MASCULINE
    learner_starting_state: str = ""
    required_final_performance: str = ""
    required_independence_level: str = "independent_with_checklist"
    instructor_responsibility_boundaries: list[str] = Field(default_factory=list)
    verified_instructor_experience: list[str] = Field(default_factory=list)
    forbidden_first_person_claims: list[str] = Field(default_factory=list)
    realistic_student_budget: Optional[str] = None
    available_tools: list[str] = Field(default_factory=list)
    professional_constraints: list[str] = Field(default_factory=list)
    high_stakes_constraints: list[str] = Field(default_factory=list)

    @field_validator(
        "instructor_responsibility_boundaries",
        "verified_instructor_experience",
        "forbidden_first_person_claims",
        "available_tools",
        "professional_constraints",
        "high_stakes_constraints",
        mode="before",
    )
    @classmethod
    def clean_text_lists(cls, value: object) -> list[str]:
        return _clean_string_list(value)

    @model_validator(mode="after")
    def complete_intake_contract(self) -> "CourseCreate":
        self.learner_starting_state = (
            self.learner_starting_state.strip() or self.audience.strip()
        )
        self.required_final_performance = (
            self.required_final_performance.strip() or self.outcome.strip()
        )
        self.student_language = self.student_language.strip() or "ar"
        self.spoken_variety = self.spoken_variety.strip() or "neutral"
        self.required_independence_level = (
            self.required_independence_level.strip() or "independent_with_checklist"
        )
        self.secondary_course_families = [
            family
            for family in dict.fromkeys(self.secondary_course_families)
            if family != self.primary_course_family
        ]
        return self


class CourseUpdate(BaseModel):
    """All fields optional: only fields the client sends are changed."""

    title: Optional[str] = None
    audience: Optional[str] = None
    outcome: Optional[str] = None
    special_notes: Optional[str] = None
    course_type: Optional[str] = None
    course_domain: Optional[str] = None
    course_specialty: Optional[str] = None
    primary_course_family: Optional[CourseFamilyLoose] = None
    secondary_course_families: Optional[list[CourseFamilyLoose]] = None
    structure_mode: Optional[StructureModeLoose] = None
    manual_map_text: Optional[str] = None
    explanation_level: Optional[ExplanationLevelLoose] = None
    generation_preset: Optional[GenerationPresetLoose] = None
    generation_quality_mode: Optional[GenerationQualityModeLoose] = None
    web_research_mode: Optional[WebResearchModeLoose] = None
    target_market: Optional[TargetMarketLoose] = None
    student_language: Optional[str] = None
    spoken_variety: Optional[str] = None
    address_form: Optional[AddressFormLoose] = None
    learner_starting_state: Optional[str] = None
    required_final_performance: Optional[str] = None
    required_independence_level: Optional[str] = None
    instructor_responsibility_boundaries: Optional[list[str]] = None
    verified_instructor_experience: Optional[list[str]] = None
    forbidden_first_person_claims: Optional[list[str]] = None
    realistic_student_budget: Optional[str] = None
    available_tools: Optional[list[str]] = None
    professional_constraints: Optional[list[str]] = None
    high_stakes_constraints: Optional[list[str]] = None
    status: Optional[str] = None

    @field_validator(
        "instructor_responsibility_boundaries",
        "verified_instructor_experience",
        "forbidden_first_person_claims",
        "available_tools",
        "professional_constraints",
        "high_stakes_constraints",
        mode="before",
    )
    @classmethod
    def clean_optional_text_lists(cls, value: object) -> list[str] | None:
        if value is None:
            return None
        return _clean_string_list(value)

    @model_validator(mode="after")
    def normalize_family_selection(self) -> "CourseUpdate":
        if self.secondary_course_families is not None:
            self.secondary_course_families = list(
                dict.fromkeys(self.secondary_course_families)
            )
            if self.primary_course_family is not None:
                self.secondary_course_families = [
                    family
                    for family in self.secondary_course_families
                    if family != self.primary_course_family
                ]
        return self


class CourseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    audience: str
    outcome: str
    special_notes: Optional[str]
    course_type: str
    course_domain: Optional[str] = None
    course_specialty: Optional[str] = None
    primary_course_family: CourseFamilyLoose = CourseFamily.GENERAL_SKILL
    secondary_course_families: list[CourseFamilyLoose] = Field(default_factory=list)
    structure_mode: StructureModeLoose
    manual_map_text: Optional[str]
    explanation_level: ExplanationLevelLoose
    generation_preset: GenerationPresetLoose
    generation_quality_mode: GenerationQualityModeLoose = GenerationQualityMode.PREMIUM
    web_research_mode: WebResearchModeLoose = WebResearchMode.AUTONOMOUS_GAP_FILL
    target_market: TargetMarketLoose = TargetMarket.EGYPT
    student_language: str = "ar"
    spoken_variety: str = "egyptian_colloquial"
    address_form: AddressFormLoose = AddressForm.MASCULINE
    learner_starting_state: str = ""
    required_final_performance: str = ""
    required_independence_level: str = "independent_with_checklist"
    instructor_responsibility_boundaries: list[str] = Field(default_factory=list)
    verified_instructor_experience: list[str] = Field(default_factory=list)
    forbidden_first_person_claims: list[str] = Field(default_factory=list)
    realistic_student_budget: Optional[str] = None
    available_tools: list[str] = Field(default_factory=list)
    professional_constraints: list[str] = Field(default_factory=list)
    high_stakes_constraints: list[str] = Field(default_factory=list)
    status: str
    created_at: datetime
    updated_at: datetime
