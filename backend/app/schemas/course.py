from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import ExplanationLevel, GenerationPreset, StructureMode


class CourseCreate(BaseModel):
    title: str
    audience: str
    outcome: str
    special_notes: Optional[str] = None
    course_type: str = "practical_skill"
    structure_mode: StructureMode
    manual_map_text: Optional[str] = None
    explanation_level: ExplanationLevel = ExplanationLevel.FINAL_ONLY
    generation_preset: GenerationPreset = GenerationPreset.BALANCED


class CourseUpdate(BaseModel):
    """All fields optional: only fields the client sends are changed."""

    title: Optional[str] = None
    audience: Optional[str] = None
    outcome: Optional[str] = None
    special_notes: Optional[str] = None
    structure_mode: Optional[StructureMode] = None
    manual_map_text: Optional[str] = None
    explanation_level: Optional[ExplanationLevel] = None
    generation_preset: Optional[GenerationPreset] = None
    status: Optional[str] = None


class CourseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    audience: str
    outcome: str
    special_notes: Optional[str]
    course_type: str
    structure_mode: StructureMode
    manual_map_text: Optional[str]
    explanation_level: ExplanationLevel
    generation_preset: GenerationPreset
    status: str
    created_at: datetime
    updated_at: datetime
