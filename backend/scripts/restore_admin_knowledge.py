"""Restore Admin Knowledge from a JSON backup snapshot.

Usage (from backend/):
  .venv/Scripts/python.exe -m scripts.restore_admin_knowledge --latest --dry-run
  .venv/Scripts/python.exe -m scripts.restore_admin_knowledge --path NAME.json --confirm
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.db import get_session, init_db
from app.services.admin_knowledge_backup import (
    admin_knowledge_backup_dir,
    list_admin_knowledge_backups,
    resolve_backup_path,
    restore_admin_knowledge,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Restore Admin Knowledge active rows from a JSON backup."
    )
    parser.add_argument(
        "--path",
        help="Backup filename or absolute path under storage/backups/admin_knowledge/.",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Use the newest backup file in the backup directory.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available backups and exit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview only (default when --confirm is omitted).",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Apply restore (creates new versions; keeps prior rows inactive).",
    )
    args = parser.parse_args(argv)

    init_db()

    if args.list:
        print(json.dumps(list_admin_knowledge_backups(), indent=2))
        return 0

    try:
        if args.path and not Path(args.path).is_absolute():
            path = resolve_backup_path(admin_knowledge_backup_dir() / args.path)
        else:
            path = resolve_backup_path(args.path, latest=args.latest)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    dry_run = args.dry_run or not args.confirm
    session = next(get_session())
    try:
        report = restore_admin_knowledge(
            session,
            path,
            dry_run=dry_run,
            confirm=args.confirm and not dry_run,
            actor="cli",
        )
        print(json.dumps(report, indent=2, default=str))
        return 0 if report.get("applied") or report.get("dry_run") else 1
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
