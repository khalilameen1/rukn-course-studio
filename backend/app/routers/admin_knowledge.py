"""Read-only API for the canonical RUKN v1.3 course standard."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session

from app.data.admin_knowledge.seed_loader import canonical_items, reset_standard
from app.data.admin_knowledge_registry import key_info_public
from app.data.course_standard import standard_manifest
from app.db import get_session
from app.schemas.admin_knowledge import AdminKnowledgeRead
from app.services.audit import record_audit

router = APIRouter(prefix="/admin/knowledge", tags=["admin-knowledge"])


def _actor(request: Request) -> str | None:
    return getattr(request.state, "username", None)


@router.get("", response_model=list[AdminKnowledgeRead])
def list_knowledge_items(session: Session = Depends(get_session)):
    """Exactly 14 canonical rows in package load order."""
    return canonical_items(session)


@router.get("/catalog", response_model=list[dict])
def knowledge_key_catalog():
    return key_info_public()


@router.get("/manifest", response_model=dict)
def knowledge_manifest():
    return standard_manifest()


@router.post("/reset", response_model=dict)
def reset_knowledge_standard(
    request: Request,
    session: Session = Depends(get_session),
    confirm: bool = Query(False, description="Required for permanent replacement."),
):
    """Permanently replace all rows and retired snapshots with shipped v1.3."""
    if not confirm:
        raise HTTPException(status_code=400, detail="confirm=true is required")
    report = reset_standard(session)
    record_audit(
        session,
        action="course_standard_reset",
        actor=_actor(request),
        affected_table="admin_knowledge_items",
        affected_count=report["inserted_rows"],
        dry_run=False,
        confirmed=True,
        success=True,
        details=report,
    )
    return {**report, **standard_manifest()}
