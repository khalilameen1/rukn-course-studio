from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, computed_field, field_validator

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


class CourseSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    source_category: SourceCategoryLoose
    title: Optional[str] = None
    original_filename: Optional[str]
    file_path: Optional[str]
    mime_type: Optional[str]
    extracted_text: Optional[str]
    priority: PriorityLoose
    status: str
    include_in_generation: bool = True
    source_hash: Optional[str] = None
    created_at: datetime

    @field_validator("include_in_generation", mode="before")
    @classmethod
    def _null_include_true(cls, value: object) -> object:
        return True if value is None else value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status_message(self) -> str:
        """Human-readable explanation of `status`, for display in the UI."""
        return SOURCE_STATUS_MESSAGES.get(self.status, "Unknown status.")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def display_title(self) -> str:
        return self.title or self.original_filename or f"source-{self.id}"
