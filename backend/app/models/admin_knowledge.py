from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel

from app.models.enums import ItemType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AdminKnowledgeItem(SQLModel, table=True):
    """One fixed piece of Rukn knowledge (a rule section, template, etc.).

    `key` identifies which knowledge section this is (e.g. "structure_rules",
    "style_rules"). It is intentionally not unique on its own: versioning
    means multiple rows can share a `key` over time, with `is_active`
    marking the one currently used by new generation runs.
    """

    __tablename__ = "admin_knowledge_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True)
    title: str
    item_type: ItemType
    content_text: Optional[str] = None
    file_path: Optional[str] = None
    version: int = Field(default=1)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
