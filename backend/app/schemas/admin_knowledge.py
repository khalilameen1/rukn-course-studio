from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import ItemType


class AdminKnowledgeCreate(BaseModel):
    key: str
    title: str
    item_type: ItemType
    content_text: Optional[str] = None
    file_path: Optional[str] = None
    version: int = 1
    is_active: bool = True


class AdminKnowledgeUpdate(BaseModel):
    """All fields optional: only fields the client sends are changed."""

    title: Optional[str] = None
    item_type: Optional[ItemType] = None
    content_text: Optional[str] = None
    file_path: Optional[str] = None
    version: Optional[int] = None
    is_active: Optional[bool] = None


class AdminKnowledgeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    title: str
    item_type: ItemType
    content_text: Optional[str]
    file_path: Optional[str]
    version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
