from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import (
    ExplanationLevel,
    GenerationPreset,
    GenerationQualityMode,
    TargetMarket,
    WebResearchMode,
)
from app.schemas.validators import (
    ExplanationLevelLoose,
    GenerationPresetLoose,
    GenerationQualityModeLoose,
    StructureModeLoose,
    TargetMarketLoose,
    WebResearchModeLoose,
)


class CourseCreate(BaseModel):
    title: str
    audience: str
    outcome: str
    special_notes: Optional[str] = None
    course_type: str = "practical_skill"
    course_domain: Optional[str] = None
    structure_mode: StructureModeLoose
    manual_map_text: Optional[str] = None
    explanation_level: ExplanationLevelLoose = ExplanationLevel.FINAL_ONLY
    generation_preset: GenerationPresetLoose = GenerationPreset.BALANCED
    generation_quality_mode: GenerationQualityModeLoose = GenerationQualityMode.PREMIUM
    web_research_mode: WebResearchModeLoose = WebResearchMode.AUTONOMOUS_GAP_FILL
    target_market: TargetMarketLoose = TargetMarket.EGYPT


class CourseUpdate(BaseModel):
    """All fields optional: only fields the client sends are changed."""

    title: Optional[str] = None
    audience: Optional[str] = None
    outcome: Optional[str] = None
    special_notes: Optional[str] = None
    course_domain: Optional[str] = None
    structure_mode: Optional[StructureModeLoose] = None
    manual_map_text: Optional[str] = None
    explanation_level: Optional[ExplanationLevelLoose] = None
    generation_preset: Optional[GenerationPresetLoose] = None
    generation_quality_mode: Optional[GenerationQualityModeLoose] = None
    web_research_mode: Optional[WebResearchModeLoose] = None
    target_market: Optional[TargetMarketLoose] = None
    status: Optional[str] = None


class CourseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    audience: str
    outcome: str
    special_notes: Optional[str]
    course_type: str
    course_domain: Optional[str] = None
    structure_mode: StructureModeLoose
    manual_map_text: Optional[str]
    explanation_level: ExplanationLevelLoose
    generation_preset: GenerationPresetLoose
    generation_quality_mode: GenerationQualityModeLoose = GenerationQualityMode.PREMIUM
    web_research_mode: WebResearchModeLoose = WebResearchMode.AUTONOMOUS_GAP_FILL
    target_market: TargetMarketLoose = TargetMarket.EGYPT
    status: str
    created_at: datetime
    updated_at: datetime
