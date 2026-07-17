"""JSON snapshot export/restore of Admin Knowledge before destructive mutations.

Snapshots live under STORAGE_DIR/backups/admin_knowledge/ — never overwrite
an existing file; each export gets a unique timestamped name.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlmodel import Session

from app.config import settings
from app.crud import admin_knowledge_items


def admin_knowledge_backup_dir() -> Path:
    root = Path(settings.storage_dir) / "backups" / "admin_knowledge"
    root.mkdir(parents=True, exist_ok=True)
    return root


def snapshot_admin_knowledge(
    session: Session, *, reason: str = "manual"
) -> dict[str, Any]:
    """Write a full JSON export of every Admin Knowledge row (active + inactive).

    Returns metadata including path and row count. Does not mutate DB rows.
    """
    items = admin_knowledge_items.list(session)
    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "count": len(items),
        "items": [
            {
                "id": item.id,
                "key": item.key,
                "title": item.title,
                "item_type": getattr(item.item_type, "value", item.item_type),
                "content_text": item.content_text,
                "file_path": item.file_path,
                "version": item.version,
                "is_active": item.is_active,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            }
            for item in items
        ],
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_reason = "".join(c if c.isalnum() or c in "-_" else "_" for c in reason)[:40]
    path = admin_knowledge_backup_dir() / f"admin_knowledge_{stamp}_{safe_reason}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "path": str(path),
        "count": len(items),
        "reason": reason,
        "exported_at": payload["exported_at"],
    }


def list_admin_knowledge_backups() -> list[dict[str, Any]]:
    """Newest-first backup file listing (metadata only)."""
    root = admin_knowledge_backup_dir()
    files = sorted(
        root.glob("admin_knowledge_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    out: list[dict[str, Any]] = []
    for path in files:
        out.append(
            {
                "path": str(path),
                "name": path.name,
                "size_bytes": path.stat().st_size,
                "modified_at": datetime.fromtimestamp(
                    path.stat().st_mtime, tz=timezone.utc
                ).isoformat(),
            }
        )
    return out


def resolve_backup_path(path: str | Path | None = None, *, latest: bool = False) -> Path:
    if latest:
        listings = list_admin_knowledge_backups()
        if not listings:
            raise FileNotFoundError("No Admin Knowledge backups found.")
        return Path(listings[0]["path"])
    if path is None:
        raise ValueError("Provide a backup path or latest=True.")
    resolved = Path(path)
    if not resolved.is_file():
        raise FileNotFoundError(f"Backup not found: {resolved}")
    backup_root = admin_knowledge_backup_dir().resolve()
    try:
        resolved.resolve().relative_to(backup_root)
    except ValueError as exc:
        raise ValueError(
            "Backup path must be under storage/backups/admin_knowledge/."
        ) from exc
    return resolved


def load_backup_payload(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "items" not in data:
        raise ValueError("Backup JSON must be an object with an 'items' array.")
    if not isinstance(data["items"], list):
        raise ValueError("Backup 'items' must be a list.")
    return data


def restore_admin_knowledge(
    session: Session,
    path: Path | str,
    *,
    dry_run: bool = True,
    confirm: bool = False,
    actor: str | None = None,
) -> dict[str, Any]:
    """Restore active rows from a snapshot as new versions (never wipe history)."""
    from app.services.admin_knowledge_versions import create_new_active_version
    from app.services.audit import record_audit

    path = Path(path)
    payload = load_backup_payload(path)
    candidates = [
        item
        for item in payload["items"]
        if isinstance(item, dict) and item.get("is_active") and item.get("key")
    ]
    plan = [
        {
            "key": item["key"],
            "title": item.get("title"),
            "item_type": item.get("item_type"),
            "version_in_backup": item.get("version"),
        }
        for item in candidates
    ]

    if dry_run or not confirm:
        record_audit(
            session,
            action="admin_knowledge_restore",
            actor=actor,
            affected_table="admin_knowledge_items",
            affected_count=len(plan),
            dry_run=True,
            confirmed=False,
            success=True,
            details={"path": str(path), "would_restore": plan},
        )
        return {
            "applied": False,
            "dry_run": True,
            "path": str(path),
            "would_restore_count": len(plan),
            "would_restore": plan,
            "message": (
                f"Dry-run: would restore {len(plan)} active key(s) from {path.name} "
                "as new versions. Pass confirm=true&dry_run=false to apply."
            ),
        }

    backup = snapshot_admin_knowledge(session, reason="before_restore")
    restored: list[dict[str, Any]] = []
    for item in candidates:
        created = create_new_active_version(
            session,
            key=str(item["key"]),
            title=str(item.get("title") or item["key"]),
            item_type=item.get("item_type") or "markdown",
            content_text=item.get("content_text"),
            file_path=item.get("file_path"),
            reason="restore_from_backup",
            snapshot=False,
        )
        restored.append(
            {"key": created.key, "id": created.id, "version": created.version}
        )

    record_audit(
        session,
        action="admin_knowledge_restore",
        actor=actor,
        affected_table="admin_knowledge_items",
        affected_count=len(restored),
        dry_run=False,
        confirmed=True,
        success=True,
        details={
            "path": str(path),
            "restored": restored,
            "pre_restore_backup": backup["path"],
        },
    )
    return {
        "applied": True,
        "dry_run": False,
        "path": str(path),
        "restored_count": len(restored),
        "restored": restored,
        "pre_restore_backup": backup,
        "message": (
            f"Restored {len(restored)} key(s) from {path.name} as new versions. "
            f"Pre-restore snapshot: {backup['path']}"
        ),
    }
