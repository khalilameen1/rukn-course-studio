"""Compatibility entrypoint for Admin Knowledge seed data.

Canonical package: `app.data.admin_knowledge`.
Run: `python -m app.seed_admin_knowledge`
"""

from app.data.admin_knowledge import *  # noqa: F403
from app.data.admin_knowledge.seed_loader import main
from app.db import engine, init_db  # noqa: F401 — tests monkeypatch these

if __name__ == "__main__":
    raise SystemExit(main())
