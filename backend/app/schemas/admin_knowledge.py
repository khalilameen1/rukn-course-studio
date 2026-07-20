from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.validators import ItemTypeLoose


class AdminKnowledgeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    title: str
    item_type: ItemTypeLoose
    content_text: Optional[str]
    file_path: Optional[str]
    version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
