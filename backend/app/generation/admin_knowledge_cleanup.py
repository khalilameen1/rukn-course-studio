"""Admin Knowledge cleanup — keep one active primary per key; hide backups.

Admin Knowledge is global ROKN rules only. Never stores course-specific PDFs,
transcripts, or maps.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlmodel import Session

from app.crud import admin_knowledge_items
from app.models.admin_knowledge import AdminKnowledgeItem


def filter_active_primary(items: list[AdminKnowledgeItem]) -> list[AdminKnowledgeItem]:
    """One active row per key (highest id / newest if multiple active)."""
    by_key: dict[str, list[AdminKnowledgeItem]] = defaultdict(list)
    for item in items:
        if item.is_active:
            by_key[item.key].append(item)
    primary: list[AdminKnowledgeItem] = []
    for _key, group in by_key.items():
        group_sorted = sorted(group, key=lambda i: (i.updated_at or i.created_at, i.id or 0))
        primary.append(group_sorted[-1])
    primary.sort(key=lambda i: i.key)
    return primary


def dedupe_admin_knowledge(session: Session) -> dict[str, Any]:
    """Deactivate duplicate active items for the same key; keep the newest.

    Does not delete rows (archives remain for history). Returns a report.
    """
    items = admin_knowledge_items.list(session)
    by_key: dict[str, list[AdminKnowledgeItem]] = defaultdict(list)
    for item in items:
        if item.is_active:
            by_key[item.key].append(item)

    deactivated: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    for key, group in by_key.items():
        if len(group) <= 1:
            if group:
                kept.append({"id": group[0].id, "key": key, "title": group[0].title})
            continue
        group_sorted = sorted(group, key=lambda i: (i.updated_at or i.created_at, i.id or 0))
        winner = group_sorted[-1]
        kept.append({"id": winner.id, "key": key, "title": winner.title})
        for loser in group_sorted[:-1]:
            admin_knowledge_items.update(session, loser.id, is_active=False)
            deactivated.append(
                {
                    "id": loser.id,
                    "key": key,
                    "title": loser.title,
                    "version": loser.version,
                    "action": "deactivated_duplicate",
                }
            )

    return {
        "deactivated_count": len(deactivated),
        "deactivated": deactivated,
        "kept_active": kept,
        "message": (
            f"Deactivated {len(deactivated)} duplicate active item(s). "
            "Inactive backups stay hidden from the default Admin Knowledge list."
        ),
    }
