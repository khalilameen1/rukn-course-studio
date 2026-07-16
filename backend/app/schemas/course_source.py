from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, computed_field

from app.models.enums import Priority, SourceCategory, SourceOrigin
from app.services.source_status import SOURCE_STATUS_MESSAGES


class CourseSourceNotesCreate(BaseModel):
    """Body for adding a free-text note / transcript as a source (no file)."""

    text: str
    title: Optional[str] = None
    source_category: SourceCategory = SourceCategory.USER_NOTES
    source_origin: SourceOrigin | None = None
    priority: Priority = Priority.MEDIUM
    include_in_generation: bool = True


class CourseSourcePatch(BaseModel):
    """Patch category / include_in_generation / priority / title."""

    source_category: Optional[SourceCategory] = None
    include_in_generation: Optional[bool] = None
    priority: Optional[Priority] = None
    title: Optional[str] = None


class CourseSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    source_category: SourceCategory
    title: Optional[str] = None
    original_filename: Optional[str]
    file_path: Optional[str]
    mime_type: Optional[str]
    extracted_text: Optional[str]
    priority: Priority
    status: str
    include_in_generation: bool = True
    source_hash: Optional[str] = None
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status_message(self) -> str:
        """Human-readable explanation of `status`, for display in the UI."""
        return SOURCE_STATUS_MESSAGES.get(self.status, "Unknown status.")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def display_title(self) -> str:
        return self.title or self.original_filename or f"source-{self.id}"
