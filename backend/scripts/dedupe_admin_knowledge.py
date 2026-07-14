"""Deactivate duplicate active Admin Knowledge items (CLI).

Usage (from backend/):
  .venv/Scripts/python.exe -m scripts.dedupe_admin_knowledge --dry-run
  .venv/Scripts/python.exe -m scripts.dedupe_admin_knowledge --confirm
"""

from __future__ import annotations

import argparse
import json

from app.db import get_session, init_db
from app.generation.admin_knowledge_cleanup import dedupe_admin_knowledge


def main() -> None:
    parser = argparse.ArgumentParser(description="Dedupe Admin Knowledge active duplicates")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview only (default if --confirm is omitted)",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        default=False,
        help="Apply deactivations (mutates DB)",
    )
    args = parser.parse_args()
    dry_run = args.dry_run or not args.confirm

    init_db()
    session = next(get_session())
    try:
        report = dedupe_admin_knowledge(session, dry_run=dry_run, confirm=args.confirm)
        print(json.dumps(report, indent=2, default=str))
    finally:
        session.close()


if __name__ == "__main__":
    main()
