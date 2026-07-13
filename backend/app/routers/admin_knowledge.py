from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.crud import admin_knowledge_items
from app.db import get_session
from app.schemas.admin_knowledge import (
    AdminKnowledgeCreate,
    AdminKnowledgeRead,
    AdminKnowledgeUpdate,
)

router = APIRouter(prefix="/admin/knowledge", tags=["admin-knowledge"])


@router.get("", response_model=list[AdminKnowledgeRead])
def list_knowledge_items(session: Session = Depends(get_session)):
    return admin_knowledge_items.list(session)


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
    """Mark this version active and deactivate any other version sharing its key.

    Enforces "at most one active version per key" (see docs/ARCHITECTURE.md
    §4.1) without a DB-level constraint, since SQLite makes conditional
    unique constraints awkward for this MVP.
    """
    item = admin_knowledge_items.get(session, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found")

    for sibling in admin_knowledge_items.list(session, key=item.key):
        if sibling.id != item.id and sibling.is_active:
            admin_knowledge_items.update(session, sibling.id, is_active=False)

    return admin_knowledge_items.update(session, item.id, is_active=True)
