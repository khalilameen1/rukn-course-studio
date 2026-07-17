from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_serializer, field_validator

from app.models.enums import Priority, SourceCategory, SourceOrigin
from app.schemas.validators import (
    PriorityLoose,
    SourceCategoryLoose,
    SourceOriginLoose,
)
from app.services.source_status import SOURCE_STATUS_MESSAGES


class CourseSourceNotesCreate(BaseModel):
    """Body for adding a free-text note / transcript as a source (no file)."""

    text: str
    title: Optional[str] = None
    source_category: SourceCategoryLoose = SourceCategory.USER_NOTES
    source_origin: SourceOriginLoose = None
    priority: PriorityLoose = Priority.MEDIUM
    include_in_generation: bool = True


class CourseSourcePatch(BaseModel):
    """Patch category / include_in_generation / priority / title."""

    source_category: Optional[SourceCategoryLoose] = None
    include_in_generation: Optional[bool] = None
    priority: Optional[PriorityLoose] = None
    title: Optional[str] = None


class SourceAnalysisPreview(BaseModel):
    """Coarse understanding preview for the Sources UI (never full extract / DOCX)."""

    source_id: int
    source_summary: Optional[str] = None
    key_points: list[str] = []


class CourseSourceRead(BaseModel):
    """Public source row — never returns full extracted_text (data minimization)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    source_category: SourceCategoryLoose
    title: Optional[str] = None
    original_filename: Optional[str]
    file_path: Optional[str]
    mime_type: Optional[str]
    # Loaded from ORM for computed fields only — excluded from JSON.
    extracted_text: Optional[str] = Field(default=None, exclude=True)
    priority: PriorityLoose
    status: str
    include_in_generation: bool = True
    source_hash: Optional[str] = None
    created_at: datetime

    @field_serializer("file_path")
    @classmethod
    def _basename_file_path(cls, value: object) -> str | None:
        if value is None or value == "":
            return None
        return Path(str(value)).name or None

    @field_validator("include_in_generation", mode="before")
    @classmethod
    def _null_include_true(cls, value: object) -> object:
        return True if value is None else value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_extracted_text(self) -> bool:
        return bool((self.extracted_text or "").strip())

    @computed_field  # type: ignore[prop-decorator]
    @property
    def extract_char_count(self) -> int:
        return len(self.extracted_text or "")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status_message(self) -> str:
        """Human-readable explanation of `status`, for display in the UI."""
        return SOURCE_STATUS_MESSAGES.get(self.status, "Unknown status.")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def display_title(self) -> str:
        return self.title or self.original_filename or f"source-{self.id}"
