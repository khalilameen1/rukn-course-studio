from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import (
    ExplanationLevel,
    GenerationPreset,
    GenerationQualityMode,
    StructureMode,
    TargetMarket,
    WebResearchMode,
)


class CourseCreate(BaseModel):
    title: str
    audience: str
    outcome: str
    special_notes: Optional[str] = None
    course_type: str = "practical_skill"
    course_domain: Optional[str] = None
    structure_mode: StructureMode
    manual_map_text: Optional[str] = None
    explanation_level: ExplanationLevel = ExplanationLevel.FINAL_ONLY
    generation_preset: GenerationPreset = GenerationPreset.BALANCED
    generation_quality_mode: GenerationQualityMode = GenerationQualityMode.PREMIUM
    web_research_mode: WebResearchMode = WebResearchMode.AUTONOMOUS_GAP_FILL
    target_market: TargetMarket = TargetMarket.EGYPT


class CourseUpdate(BaseModel):
    """All fields optional: only fields the client sends are changed."""

    title: Optional[str] = None
    audience: Optional[str] = None
    outcome: Optional[str] = None
    special_notes: Optional[str] = None
    course_domain: Optional[str] = None
    structure_mode: Optional[StructureMode] = None
    manual_map_text: Optional[str] = None
    explanation_level: Optional[ExplanationLevel] = None
    generation_preset: Optional[GenerationPreset] = None
    generation_quality_mode: Optional[GenerationQualityMode] = None
    web_research_mode: Optional[WebResearchMode] = None
    target_market: Optional[TargetMarket] = None
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
    structure_mode: StructureMode
    manual_map_text: Optional[str]
    explanation_level: ExplanationLevel
    generation_preset: GenerationPreset
    generation_quality_mode: GenerationQualityMode = GenerationQualityMode.PREMIUM
    web_research_mode: WebResearchMode = WebResearchMode.AUTONOMOUS_GAP_FILL
    target_market: TargetMarket = TargetMarket.EGYPT
    status: str
    created_at: datetime
    updated_at: datetime
