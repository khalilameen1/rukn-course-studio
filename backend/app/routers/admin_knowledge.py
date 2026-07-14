"""Admin Knowledge Center list/cleanup — global ROKN rules only."""

from fastapi import APIRouter, Depends, HTTPException, Query
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

router = APIRouter(prefix="/admin/knowledge", tags=["admin-knowledge"])


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
    return [i for i in items if i.is_active]


@router.post("/cleanup-duplicates", response_model=dict)
def cleanup_duplicate_knowledge(
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
    or what changed.
    """
    return dedupe_admin_knowledge(session, dry_run=dry_run, confirm=confirm)


@router.post("", response_model=AdminKnowledgeRead, status_code=201)
def create_knowledge_item(
    payload: AdminKnowledgeCreate, session: Session = Depends(get_session)
):
    return admin_knowledge_items.create(session, **payload.model_dump())


@router.put("/{item_id}", response_model=AdminKnowledgeRead)
def update_knowledge_item(
    item_id: int,
    payload: AdminKnowledgeUpdate,
    session: Session = Depends(get_session),
):
    updated = admin_knowledge_items.update(
        session, item_id, **payload.model_dump(exclude_unset=True)
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found")
    return updated


@router.delete("/{item_id}", status_code=204)
def delete_knowledge_item(item_id: int, session: Session = Depends(get_session)):
    if not admin_knowledge_items.delete(session, item_id):
        raise HTTPException(status_code=404, detail="Knowledge item not found")


@router.post("/{item_id}/activate", response_model=AdminKnowledgeRead)
def activate_knowledge_item(item_id: int, session: Session = Depends(get_session)):
    """Mark this version active and deactivate any other version sharing its key."""
    item = admin_knowledge_items.get(session, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found")

    for sibling in admin_knowledge_items.list(session, key=item.key):
        if sibling.id != item.id and sibling.is_active:
            admin_knowledge_items.update(session, sibling.id, is_active=False)

    return admin_knowledge_items.update(session, item.id, is_active=True)
