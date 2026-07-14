"""Deactivate duplicate active Admin Knowledge items (CLI).

Usage (from backend/):
  .venv/Scripts/python.exe -m scripts.dedupe_admin_knowledge
"""

from __future__ import annotations

import json

from app.db import get_session, init_db
from app.generation.admin_knowledge_cleanup import dedupe_admin_knowledge


def main() -> None:
    init_db()
    session = next(get_session())
    try:
        report = dedupe_admin_knowledge(session)
        print(json.dumps(report, indent=2, default=str))
    finally:
        session.close()


if __name__ == "__main__":
    main()
