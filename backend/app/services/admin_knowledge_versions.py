"""Version / active-primary helpers for Admin Knowledge rows."""

from __future__ import annotations

from typing import Any

from sqlmodel import Session

from app.crud import admin_knowledge_items
from app.services.admin_knowledge_backup import snapshot_admin_knowledge
from app.services.admin_knowledge_lock import admin_knowledge_key_guard


def deactivate_sibling_actives(
    session: Session,
    key: str,
    *,
    keep_id: int | None = None,
) -> list[int]:
    """Deactivate every active row for `key` except `keep_id`. Returns deactivated ids."""
    deactivated: list[int] = []
    for sibling in admin_knowledge_items.list(session, key=key):
        if keep_id is not None and sibling.id == keep_id:
            continue
        if not sibling.is_active:
            continue
        admin_knowledge_items.update(session, sibling.id, is_active=False)
        if sibling.id is not None:
            deactivated.append(sibling.id)
    return deactivated


def next_version_for_key(session: Session, key: str) -> int:
    existing = admin_knowledge_items.list(session, key=key)
    if not existing:
        return 1
    return max(int(row.version or 0) for row in existing) + 1


def create_new_active_version(
    session: Session,
    *,
    key: str,
    title: str,
    item_type: Any,
    content_text: str | None = None,
    file_path: str | None = None,
    reason: str = "save_as_new_version",
    snapshot: bool = True,
) -> Any:
    """Archive current actives for `key` and insert a new active versioned row.

    Writes a JSON snapshot first unless `snapshot=False` (caller already did).
    Serialized per key to avoid concurrent double-actives.
    """
    with admin_knowledge_key_guard(session, key):
        if snapshot:
            snapshot_admin_knowledge(session, reason=reason)
        deactivate_sibling_actives(session, key)
        return admin_knowledge_items.create(
            session,
            key=key,
            title=title,
            item_type=item_type,
            content_text=content_text,
            file_path=file_path,
            version=next_version_for_key(session, key),
            is_active=True,
        )


def activate_version(session: Session, item_id: int) -> Any:
    """Activate one row and deactivate siblings under a per-key lock."""
    item = admin_knowledge_items.get(session, item_id)
    if item is None:
        return None
    with admin_knowledge_key_guard(session, item.key):
        deactivate_sibling_actives(session, item.key, keep_id=item.id)
        return admin_knowledge_items.update(session, item.id, is_active=True)
