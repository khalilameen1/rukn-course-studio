"""Compatibility shim — canonical package is `app.data.admin_knowledge`."""

from app.data.admin_knowledge import *  # noqa: F403
from app.data.admin_knowledge.seed_loader import main
from app.db import engine, init_db  # noqa: F401

if __name__ == "__main__":
    raise SystemExit(main())
