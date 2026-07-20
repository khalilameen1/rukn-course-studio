from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from app.db_enums import sa_str_enum
from app.models.enums import ItemType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AdminKnowledgeItem(SQLModel, table=True):
    """One read-only file from the canonical RUKN standard package.

    ``key`` is the exact canonical Markdown filename. Reset permanently
    deletes every non-canonical or duplicate row before reseeding the 14-file
    package; the legacy columns remain only for existing-database compatibility.
    """

    __tablename__ = "admin_knowledge_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True)
    title: str
    item_type: ItemType = Field(
        sa_column=Column(sa_str_enum(ItemType), nullable=False)
    )
    content_text: Optional[str] = None
    file_path: Optional[str] = None
    version: int = Field(default=1)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
