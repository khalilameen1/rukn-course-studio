from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_serializer


class CourseVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    version_number: int
    output_docx_path: str
    summary_text: Optional[str]
    report_text: Optional[str]
    created_at: datetime

    @field_serializer("output_docx_path")
    @classmethod
    def _basename_only(cls, value: object) -> str:
        # Never expose absolute server paths to the browser.
        return Path(str(value or "")).name
