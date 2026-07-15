"""Admin Knowledge Center list/cleanup — global ROKN rules only."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session

from app.crud import admin_knowledge_items
from app.db import get_session
from app.generation.admin_knowledge_cleanup import (
    dedupe_admin_knowledge,
    filter_active_primary,
)
from app.schemas.admin_knowledge import (
    AdminKnowledgeCreate,
    AdminKnowledgeRead,
    AdminKnowledgeUpdate,
)
from app.services.admin_knowledge_backup import snapshot_admin_knowledge
from app.services.audit import record_audit

router = APIRouter(prefix="/admin/knowledge", tags=["admin-knowledge"])


def _actor(request: Request) -> str | None:
    return getattr(request.state, "username", None)


@router.get("", response_model=list[AdminKnowledgeRead])
def list_knowledge_items(
    session: Session = Depends(get_session),
    active_only: bool = Query(
        True,
        description="Default: clean active primary items only (hides inactive backups).",
    ),
    include_inactive: bool = Query(
        False,
        description="If true with active_only=false, return all rows including archives.",
    ),
):
    """Normal Admin Knowledge Center view = active primary per key only.

    Inactive/backup versions (e.g. refresh-defaults archives) are hidden unless
    `include_inactive=true` (and `active_only=false`).
    """
    items = admin_knowledge_items.list(session)
    if include_inactive and not active_only:
        return items
    if active_only:
        return filter_active_primary(items)
    # active_only=false without include_inactive: still one primary per key.
    return filter_active_primary(items)


@router.post("/cleanup-duplicates", response_model=dict)
def cleanup_duplicate_knowledge(
    request: Request,
    session: Session = Depends(get_session),
    dry_run: bool = Query(
        True,
        description="Default true: preview deactivations without writing. "
        "Set dry_run=false&confirm=true to apply.",
    ),
    confirm: bool = Query(
        False,
        description="Required true (with dry_run=false) to deactivate duplicates.",
    ),
):
    """Deactivate duplicate active items per key; keep latest useful active row.

    Default is dry-run (no writes). Destructive apply requires confirm=true.
    Does not delete custom unique keys. Returns a report of what will change
    or what changed. Apply path writes a JSON snapshot first.
    """
    return dedupe_admin_knowledge(
        session, dry_run=dry_run, confirm=confirm, actor=_actor(request)
    )


@router.post("", response_model=AdminKnowledgeRead, status_code=201)
def create_knowledge_item(
    payload: AdminKnowledgeCreate,
    request: Request,
    session: Session = Depends(get_session),
):
    created = admin_knowledge_items.create(session, **payload.model_dump())
    record_audit(
        session,
        action="admin_knowledge_create",
        actor=_actor(request),
        affected_table="admin_knowledge_items",
        affected_count=1,
        dry_run=False,
        confirmed=True,
        success=True,
        details={"id": created.id, "key": created.key},
    )
    return created


@router.put("/{item_id}", response_model=AdminKnowledgeRead)
def update_knowledge_item(
    item_id: int,
    payload: AdminKnowledgeUpdate,
    request: Request,
    session: Session = Depends(get_session),
):
    data = payload.model_dump(exclude_unset=True)
    activating = data.get("is_active") is True
    updated = admin_knowledge_items.update(session, item_id, **data)
    if updated is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found")
    if activating:
        siblings = [
            s
            for s in admin_knowledge_items.list(session, key=updated.key)
            if s.id != updated.id and s.is_active
        ]
        for sibling in siblings:
            admin_knowledge_items.update(session, sibling.id, is_active=False)
        updated = admin_knowledge_items.get(session, item_id) or updated
    record_audit(
        session,
        action="admin_knowledge_update",
        actor=_actor(request),
        affected_table="admin_knowledge_items",
        affected_count=1,
        dry_run=False,
        confirmed=True,
        success=True,
        details={"id": item_id, "key": updated.key},
    )
    return updated


@router.delete("/{item_id}", status_code=200, response_model=dict)
def delete_knowledge_item(
    item_id: int,
    request: Request,
    session: Session = Depends(get_session),
    confirm: bool = Query(
        False,
        description="Required true to perform archive (deactivate) or purge.",
    ),
    purge: bool = Query(
        False,
        description="If true with confirm=true, permanently delete the row. "
        "Default is soft-archive (is_active=false).",
    ),
    dry_run: bool = Query(
        True,
        description="Default true: report what would happen without mutating.",
    ),
):
    """Archive (default) or permanently delete an Admin Knowledge row.

    Prefer archive: keeps the row inactive. Permanent purge requires
    confirm=true&purge=true&dry_run=false and writes a JSON snapshot first.
    """
    item = admin_knowledge_items.get(session, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found")

    plan = {
        "id": item.id,
        "key": item.key,
        "title": item.title,
        "action": "would_purge" if purge else "would_archive",
        "dry_run": dry_run or not confirm,
    }
    if dry_run or not confirm:
        record_audit(
            session,
            action="admin_knowledge_delete",
            actor=_actor(request),
            affected_table="admin_knowledge_items",
            affected_count=1,
            dry_run=True,
            confirmed=False,
            success=True,
            details=plan,
        )
        return {
            **plan,
            "applied": False,
            "message": (
                f"Dry-run: would {'permanently delete' if purge else 'archive (deactivate)'} "
                f"item {item_id} ({item.key}). Pass confirm=true&dry_run=false to apply."
            ),
        }

    backup = snapshot_admin_knowledge(
        session, reason="purge" if purge else "archive_before_delete"
    )
    if purge:
        ok = admin_knowledge_items.delete(session, item_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Knowledge item not found")
        action_done = "purged"
    else:
        admin_knowledge_items.update(session, item_id, is_active=False)
        action_done = "archived"

    record_audit(
        session,
        action="admin_knowledge_delete",
        actor=_actor(request),
        affected_table="admin_knowledge_items",
        affected_count=1,
        dry_run=False,
        confirmed=True,
        success=True,
        details={
            "id": item_id,
            "key": item.key,
            "action": action_done,
            "backup_path": backup["path"],
        },
    )
    return {
        "id": item_id,
        "key": item.key,
        "applied": True,
        "action": action_done,
        "backup": backup,
        "message": (
            f"{'Permanently deleted' if purge else 'Archived (deactivated)'} "
            f"item {item_id}. Snapshot: {backup['path']}"
        ),
    }


@router.post("/{item_id}/activate", response_model=AdminKnowledgeRead)
def activate_knowledge_item(
    item_id: int,
    request: Request,
    session: Session = Depends(get_session),
    confirm: bool = Query(
        False,
        description="Required true — activate deactivates sibling versions.",
    ),
    dry_run: bool = Query(True, description="Default preview; no writes."),
):
    """Mark this version active and deactivate any other version sharing its key."""
    item = admin_knowledge_items.get(session, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found")

    siblings = [
        s for s in admin_knowledge_items.list(session, key=item.key) if s.id != item.id and s.is_active
    ]
    if dry_run or not confirm:
        record_audit(
            session,
            action="admin_knowledge_activate",
            actor=_actor(request),
            affected_table="admin_knowledge_items",
            affected_count=1 + len(siblings),
            dry_run=True,
            confirmed=False,
            success=True,
            details={
                "id": item_id,
                "would_deactivate_ids": [s.id for s in siblings],
            },
        )
        raise HTTPException(
            status_code=400,
            detail=(
                f"Dry-run: would activate item {item_id} and deactivate "
                f"{len(siblings)} sibling(s). Pass confirm=true&dry_run=false."
            ),
        )

    for sibling in siblings:
        admin_knowledge_items.update(session, sibling.id, is_active=False)

    updated = admin_knowledge_items.update(session, item.id, is_active=True)
    record_audit(
        session,
        action="admin_knowledge_activate",
        actor=_actor(request),
        affected_table="admin_knowledge_items",
        affected_count=1 + len(siblings),
        dry_run=False,
        confirmed=True,
        success=True,
        details={"id": item_id, "deactivated_ids": [s.id for s in siblings]},
    )
    return updated
