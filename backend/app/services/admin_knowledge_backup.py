"""JSON snapshot export of Admin Knowledge before destructive mutations.

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
