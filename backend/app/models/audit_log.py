"""Durable audit trail for admin / destructive operations.

Never stores secrets, full source text, or API keys — only action metadata
and coarse counts / ids.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    action: str = Field(index=True)
    actor: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=_utcnow, index=True)
    affected_table: Optional[str] = None
    affected_count: int = Field(default=0)
    dry_run: bool = Field(default=True)
    confirmed: bool = Field(default=False)
    success: bool = Field(default=True)
    error_message: Optional[str] = None
    details_json: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
