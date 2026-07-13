from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CourseVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    version_number: int
    output_docx_path: str
    summary_text: Optional[str]
    report_text: Optional[str]
    created_at: datetime
