"""Idempotent seed + refresh-defaults loader."""

from __future__ import annotations

import argparse
from sqlmodel import Session

from app.crud import admin_knowledge_items
from app.data.admin_knowledge.seed_items import SEED_ITEMS, _SEED_BY_KEY
from app.data.admin_knowledge_registry import REFRESHABLE_DEFAULT_KEYS
from app.db import engine, init_db


def seed(session: Session) -> None:
    """Idempotent create-missing-only seed. Never overwrites existing rows."""
    for item in SEED_ITEMS:
        existing = admin_knowledge_items.list(session, key=item["key"])
        if existing:
            print(f"skip  {item['key']} (already seeded, {len(existing)} version(s))")
            continue

        admin_knowledge_items.create(
            session,
            key=item["key"],
            title=item["title"],
            item_type=item["item_type"],
            content_text=item["content_text"],
            version=1,
            is_active=True,
        )
        print(f"seed  {item['key']}")


def refresh_defaults(session: Session, *, confirmed: bool = False) -> list[str]:
    """Replace selected system defaults with current SEED_ITEMS content.

    Requires `confirmed=True` (CLI `--confirm`). Before mutation, writes a
    full Admin Knowledge JSON snapshot under storage/backups/admin_knowledge/.

    For each refreshable key that exists in SEED_ITEMS:
    - If no row exists yet, create version 1 (same as normal seed).
    - If rows exist, deactivate all siblings, keep the previous active row
      as an inactive backup (title stamped with UTC time), and create a
      new higher `version` that becomes the only active row.

    Never touches keys outside REFRESHABLE_DEFAULT_KEYS (custom knowledge
    and other system keys like rukn_core_rules stay untouched).
    """
    from datetime import datetime, timezone

    from app.services.admin_knowledge_backup import snapshot_admin_knowledge
    from app.services.audit import record_audit

    if not confirmed:
        raise RuntimeError(
            "refresh_defaults requires confirmed=True "
            "(CLI: --refresh-defaults --confirm)."
        )

    backup = snapshot_admin_knowledge(session, reason="refresh_defaults")
    refreshed: list[str] = []
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    for key in REFRESHABLE_DEFAULT_KEYS:
        item = _SEED_BY_KEY.get(key)
        if item is None:
            print(f"skip  {key} (no shipped default in this build)")
            continue

        existing = admin_knowledge_items.list(session, key=key)
        if not existing:
            admin_knowledge_items.create(
                session,
                key=item["key"],
                title=item["title"],
                item_type=item["item_type"],
                content_text=item["content_text"],
                version=1,
                is_active=True,
            )
            print(f"seed  {key} (was missing)")
            refreshed.append(key)
            continue

        max_version = max(row.version for row in existing)
        previous_active = next((row for row in existing if row.is_active), existing[-1])

        # Snapshot: keep prior content as an inactive versioned row.
        for sibling in existing:
            updates: dict = {"is_active": False}
            if sibling.id == previous_active.id:
                base_title = item["title"]
                # Avoid stacking backup stamps on repeated refreshes.
                if "(backup " not in (sibling.title or ""):
                    updates["title"] = f"{base_title} (backup {stamp})"
            admin_knowledge_items.update(session, sibling.id, **updates)

        admin_knowledge_items.create(
            session,
            key=item["key"],
            title=item["title"],
            item_type=item["item_type"],
            content_text=item["content_text"],
            version=max_version + 1,
            is_active=True,
        )
        print(
            f"refresh  {key} -> v{max_version + 1} "
            f"(previous kept inactive as backup; was v{previous_active.version})"
        )
        refreshed.append(key)

    record_audit(
        session,
        action="admin_knowledge_refresh_defaults",
        actor="cli",
        affected_table="admin_knowledge_items",
        affected_count=len(refreshed),
        dry_run=False,
        confirmed=True,
        success=True,
        details={"refreshed_keys": refreshed, "backup_path": backup["path"]},
    )
    print(f"backup  {backup['path']}")
    return refreshed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Seed missing Admin Knowledge defaults (idempotent), or "
            "intentionally refresh selected system defaults."
        )
    )
    parser.add_argument(
        "--refresh-defaults",
        action="store_true",
        help=(
            "Replace selected system-managed defaults with the current "
            "codebase seed content. Keeps the previous active row as an "
            "inactive backup version. Requires --confirm."
        ),
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required with --refresh-defaults to acknowledge backup+replace.",
    )
    args = parser.parse_args(argv)

    init_db()
    with Session(engine) as session:
        if args.refresh_defaults:
            if not args.confirm:
                print(
                    "Refusing to refresh defaults without --confirm.\n"
                    "This will deactivate current active versions for selected "
                    "system keys and create new active versions from code "
                    "defaults (previous content is kept as inactive backup "
                    "rows).\n"
                    "Keys: "
                    + ", ".join(REFRESHABLE_DEFAULT_KEYS)
                    + "\n\n"
                    "Exact command:\n"
                    "  python -m app.seed_admin_knowledge --refresh-defaults --confirm"
                )
                return 2
            refreshed = refresh_defaults(session, confirmed=True)
            print(f"done  refreshed {len(refreshed)} key(s)")
            return 0

        seed(session)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
