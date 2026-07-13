from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, computed_field

from app.models.enums import Priority, SourceCategory
from app.services.source_status import SOURCE_STATUS_MESSAGES


class CourseSourceNotesCreate(BaseModel):
    """Body for adding a free-text note as a source (no file involved)."""

    text: str
    source_category: SourceCategory = SourceCategory.NOTES
    priority: Priority = Priority.MEDIUM


class CourseSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    source_category: SourceCategory
    original_filename: Optional[str]
    file_path: Optional[str]
    mime_type: Optional[str]
    extracted_text: Optional[str]
    priority: Priority
    status: str
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status_message(self) -> str:
        """Human-readable explanation of `status`, for display in the UI."""
        return SOURCE_STATUS_MESSAGES.get(self.status, "Unknown status.")
