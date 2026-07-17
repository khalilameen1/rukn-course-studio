"""Admin audit log read API (scoped to admin_knowledge:* via /admin prefix)."""

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.db import get_session
from app.services.audit import list_recent

router = APIRouter(prefix="/admin", tags=["admin-audit"])


@router.get("/audit", response_model=list[dict])
def list_audit_logs(
    session: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
):
    rows = list_recent(session, limit=limit)
    return [
        {
            "id": row.id,
            "action": row.action,
            "actor": row.actor,
            "affected_table": row.affected_table,
            "affected_count": row.affected_count,
            "dry_run": row.dry_run,
            "confirmed": row.confirmed,
            "success": row.success,
            "error_message": row.error_message,
            "details": row.details_json,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
