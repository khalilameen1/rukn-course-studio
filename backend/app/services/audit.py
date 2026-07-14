"""Record and query audit_logs rows."""

from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from app.crud.base import CRUDBase
from app.models.audit_log import AuditLog

audit_logs = CRUDBase(AuditLog)


def record_audit(
    session: Session,
    *,
    action: str,
    actor: str | None = None,
    affected_table: str | None = None,
    affected_count: int = 0,
    dry_run: bool = True,
    confirmed: bool = False,
    success: bool = True,
    error_message: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    """Persist one audit row. Never rolls back the caller's prior work.

    On failure returns an unsaved stub (success=False, error audit_write_failed).
    """
    try:
        return audit_logs.create(
            session,
            action=action,
            actor=actor,
            affected_table=affected_table,
            affected_count=affected_count,
            dry_run=dry_run,
            confirmed=confirmed,
            success=success,
            error_message=(error_message or "")[:500] or None,
            details_json=details,
        )
    except Exception:  # noqa: BLE001
        return AuditLog(
            action=action,
            actor=actor,
            affected_table=affected_table,
            affected_count=affected_count,
            dry_run=dry_run,
            confirmed=confirmed,
            success=False,
            error_message="audit_write_failed",
            details_json=details,
        )


def list_recent(session: Session, *, limit: int = 50) -> list[AuditLog]:
    statement = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    return list(session.exec(statement))
