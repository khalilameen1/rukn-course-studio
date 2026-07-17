from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import ItemType
from app.schemas.validators import ItemTypeLoose


class AdminKnowledgeCreate(BaseModel):
    key: str
    title: str
    item_type: ItemTypeLoose
    content_text: Optional[str] = None
    file_path: Optional[str] = None
    version: int = 1
    is_active: bool = True


class AdminKnowledgeUpdate(BaseModel):
    """All fields optional: only fields the client sends are changed.

    By default, content edits create a new version (deactivate previous active).
    Set `in_place=true` only for emergency overwrite of the current row.
    """

    title: Optional[str] = None
    item_type: Optional[ItemTypeLoose] = None
    content_text: Optional[str] = None
    file_path: Optional[str] = None
    version: Optional[int] = None
    is_active: Optional[bool] = None
    in_place: bool = False


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
