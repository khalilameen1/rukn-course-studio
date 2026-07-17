"""Admin Knowledge Center list/cleanup — global ROKN rules only."""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session

from app.crud import admin_knowledge_items
from app.data.admin_knowledge_registry import (
    ALL_SYSTEM_KEYS,
    STABLE_RULE_KEYS,
    key_info_public,
)
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
from app.schemas.admin_knowledge_content import validate_admin_knowledge_content
from app.services.admin_knowledge_backup import snapshot_admin_knowledge
from app.services.admin_knowledge_versions import (
    activate_version,
    create_new_active_version,
    deactivate_sibling_actives,
    next_version_for_key,
)
from app.services.audit import record_audit

router = APIRouter(prefix="/admin/knowledge", tags=["admin-knowledge"])

# High-trust keys require confirm=true on content save (change control).
HIGH_TRUST_KEYS: frozenset[str] = frozenset(STABLE_RULE_KEYS) | {
    "rukn_teleprompter_docx_contract"
}


def _actor(request: Request) -> str | None:
    return getattr(request.state, "username", None)


def _content_fingerprint(text: str | None) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


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


@router.get("/catalog", response_model=list[dict])
def knowledge_key_catalog():
    """System key metadata for Admin UI (titles, refreshable, stage/stable flags)."""
    return key_info_public()


@router.get("/keys/{key}/versions", response_model=list[AdminKnowledgeRead])
def list_key_versions(key: str, session: Session = Depends(get_session)):
    """All versions for one key (newest first) — for Admin history UI."""
    items = admin_knowledge_items.list(session, key=key)
    return sorted(items, key=lambda i: (i.version, i.id or 0), reverse=True)


@router.post("/refresh-defaults", response_model=dict)
def refresh_system_defaults(
    request: Request,
    session: Session = Depends(get_session),
    dry_run: bool = Query(True, description="Default true: preview only."),
    confirm: bool = Query(
        False,
        description="Required true with dry_run=false to replace refreshable defaults.",
    ),
):
    """Replace refreshable system defaults from code seed (same as CLI).

    Always snapshots first on apply. Never touches core voice / presets /
    custom keys outside REFRESHABLE_DEFAULT_KEYS.
    """
    from app.data.admin_knowledge_registry import REFRESHABLE_DEFAULT_KEYS
    from app.data.admin_knowledge.seed_items import _SEED_BY_KEY
    from app.seed_admin_knowledge import refresh_defaults

    preview_keys = [k for k in REFRESHABLE_DEFAULT_KEYS if k in _SEED_BY_KEY]
    if dry_run or not confirm:
        record_audit(
            session,
            action="admin_knowledge_refresh_defaults",
            actor=_actor(request),
            affected_table="admin_knowledge_items",
            affected_count=len(preview_keys),
            dry_run=True,
            confirmed=False,
            success=True,
            details={"would_refresh": preview_keys},
        )
        return {
            "applied": False,
            "dry_run": True,
            "would_refresh_count": len(preview_keys),
            "would_refresh": preview_keys,
            "message": (
                f"Dry-run: would refresh {len(preview_keys)} system key(s) from seed. "
                "Pass confirm=true&dry_run=false to apply (snapshot written first)."
            ),
        }

    refreshed = refresh_defaults(session, confirmed=True)
    return {
        "applied": True,
        "dry_run": False,
        "refreshed_count": len(refreshed),
        "refreshed": refreshed,
        "message": f"Refreshed {len(refreshed)} system default key(s) from seed.",
    }


@router.get("/backups", response_model=list[dict])
def list_knowledge_backups():
    """List JSON snapshots under storage/backups/admin_knowledge/."""
    from app.services.admin_knowledge_backup import list_admin_knowledge_backups

    return list_admin_knowledge_backups()


@router.post("", response_model=AdminKnowledgeRead, status_code=201)
def create_knowledge_item(
    payload: AdminKnowledgeCreate,
    request: Request,
    session: Session = Depends(get_session),
    allow_custom_key: bool = Query(
        False,
        description="Required true to create a key outside the shipped catalog.",
    ),
):
    """Create a knowledge row. Active creates deactivate sibling actives for the key."""
    data = payload.model_dump()
    key = data["key"]
    if key not in ALL_SYSTEM_KEYS and not allow_custom_key:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Key {key!r} is not in the system catalog. "
                "Pass allow_custom_key=true to create an experimental custom key."
            ),
        )
    try:
        validate_admin_knowledge_content(
            key=key,
            item_type=data["item_type"],
            content_text=data.get("content_text"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    # Always advance version when siblings exist so history stays monotonic.
    data["version"] = max(int(data.get("version") or 1), next_version_for_key(session, key))
    if data.get("is_active", True):
        deactivate_sibling_actives(session, key)
    created = admin_knowledge_items.create(session, **data)
    record_audit(
        session,
        action="admin_knowledge_create",
        actor=_actor(request),
        affected_table="admin_knowledge_items",
        affected_count=1,
        dry_run=False,
        confirmed=True,
        success=True,
        details={"id": created.id, "key": created.key, "version": created.version},
    )
    return created


@router.put("/{item_id}")
def update_knowledge_item(
    item_id: int,
    payload: AdminKnowledgeUpdate,
    request: Request,
    session: Session = Depends(get_session),
    confirm: bool = Query(
        False,
        description="Required true when saving content for high-trust / stable keys.",
    ),
    dry_run: bool = Query(
        False,
        description="If true, preview high-trust content save without writing.",
    ),
    confirm_key: str | None = Query(
        None,
        description="Must equal the item key when applying a high-trust content save.",
    ),
):
    """Update metadata in place, or save content as a new version (default).

    High-trust keys require confirm=true + confirm_key=<key> on content saves
    (or return dry-run preview).
    """
    existing = admin_knowledge_items.get(session, item_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found")

    data = payload.model_dump(exclude_unset=True)
    in_place = bool(data.pop("in_place", False))
    activating = data.get("is_active") is True
    content_fields = {"title", "item_type", "content_text", "file_path"}
    touches_content = bool(content_fields & set(data))

    merged_type = data.get("item_type", existing.item_type)
    merged_content = data.get("content_text", existing.content_text)
    if "content_text" in data or "item_type" in data:
        try:
            validate_admin_knowledge_content(
                key=existing.key,
                item_type=merged_type,
                content_text=merged_content,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    high_trust = existing.key in HIGH_TRUST_KEYS
    if touches_content and not in_place and high_trust and (dry_run or not confirm):
        preview = {
            "applied": False,
            "dry_run": True,
            "high_trust": True,
            "key": existing.key,
            "from_id": existing.id,
            "from_version": existing.version,
            "would_version": next_version_for_key(session, existing.key),
            "content_fingerprint_before": _content_fingerprint(existing.content_text),
            "content_fingerprint_after": _content_fingerprint(
                str(merged_content) if merged_content is not None else None
            ),
            "message": (
                f"Dry-run: would save a new version of high-trust key {existing.key!r}. "
                "Pass confirm=true&dry_run=false&confirm_key=<exact key> to apply "
                "(snapshot written first)."
            ),
        }
        record_audit(
            session,
            action="admin_knowledge_revise",
            actor=_actor(request),
            affected_table="admin_knowledge_items",
            affected_count=1,
            dry_run=True,
            confirmed=False,
            success=True,
            details=preview,
        )
        return preview

    if touches_content and not in_place and high_trust:
        if (confirm_key or "").strip() != existing.key:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"confirm_key must exactly match high-trust key {existing.key!r}."
                ),
            )

    if touches_content and not in_place:
        created = create_new_active_version(
            session,
            key=existing.key,
            title=data.get("title", existing.title),
            item_type=merged_type,
            content_text=merged_content,
            file_path=data.get("file_path", existing.file_path),
            reason="admin_save_new_version",
        )
        record_audit(
            session,
            action="admin_knowledge_revise",
            actor=_actor(request),
            affected_table="admin_knowledge_items",
            affected_count=1,
            dry_run=False,
            confirmed=True,
            success=True,
            details={
                "previous_id": item_id,
                "id": created.id,
                "key": created.key,
                "version": created.version,
                "high_trust": high_trust,
            },
        )
        return AdminKnowledgeRead.model_validate(created)

    updated = admin_knowledge_items.update(session, item_id, **data)
    if updated is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found")
    if activating:
        updated = activate_version(session, item_id) or updated
    record_audit(
        session,
        action="admin_knowledge_update",
        actor=_actor(request),
        affected_table="admin_knowledge_items",
        affected_count=1,
        dry_run=False,
        confirmed=True,
        success=True,
        details={"id": item_id, "key": updated.key, "in_place": in_place},
    )
    return AdminKnowledgeRead.model_validate(updated)


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


@router.post("/{item_id}/activate", response_model=dict)
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
        s
        for s in admin_knowledge_items.list(session, key=item.key)
        if s.id != item.id and s.is_active
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
        return {
            "applied": False,
            "dry_run": True,
            "id": item_id,
            "key": item.key,
            "would_deactivate_ids": [s.id for s in siblings],
            "would_deactivate_count": len(siblings),
            "message": (
                f"Dry-run: would activate item {item_id} and deactivate "
                f"{len(siblings)} sibling(s). Pass confirm=true&dry_run=false."
            ),
        }

    updated = activate_version(session, item_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="Knowledge item not found")
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
    return {
        "applied": True,
        "dry_run": False,
        "id": updated.id,
        "key": updated.key,
        "version": updated.version,
        "is_active": updated.is_active,
        "item": AdminKnowledgeRead.model_validate(updated).model_dump(mode="json"),
        "message": f"Activated item {item_id} ({updated.key}).",
    }
