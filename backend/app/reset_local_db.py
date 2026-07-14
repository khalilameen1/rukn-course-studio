"""Reset the local SQLite dev database to match the current schema.

Deletes the SQLite file (and any -wal / -shm sidecars), then recreates all
tables via `init_db()`. Use this when an older dev database is missing columns
that were added after the file was first created (`create_all` does not alter
existing tables).

Local dev only: refuses non-SQLite URLs and `ENVIRONMENT=production`.
Requires `--confirm` (destructive).

Run from `backend/`:

    python -m app.reset_local_db --confirm
    python -m app.reset_local_db --confirm --seed
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy.engine import make_url

from app.config import BACKEND_DIR, settings
from app.db import init_db


def _sqlite_db_path(database_url: str) -> Path:
    url = make_url(database_url)
    if url.drivername != "sqlite":
        raise ValueError(f"Not a SQLite URL: {database_url!r}")
    if not url.database:
        raise ValueError("In-memory SQLite databases cannot be reset with this script.")

    path = Path(url.database)
    if not path.is_absolute():
        path = (BACKEND_DIR / path).resolve()
    return path


def reset_local_db(*, seed: bool = False, confirmed: bool = False) -> None:
    if settings.environment.lower() == "production":
        print("Refusing to reset: ENVIRONMENT is production.", file=sys.stderr)
        sys.exit(1)

    if not confirmed:
        print(
            "Refusing to reset without --confirm.\n"
            "This permanently deletes the local SQLite file and recreates empty tables.\n"
            "Exact command:\n"
            "  python -m app.reset_local_db --confirm\n"
            "  python -m app.reset_local_db --confirm --seed",
            file=sys.stderr,
        )
        sys.exit(2)

    db_path = _sqlite_db_path(settings.database_url)

    for path in (db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")):
        if path.exists():
            try:
                path.unlink()
            except OSError as exc:
                print(
                    f"Could not delete {path}: {exc}\n"
                    "Stop the backend (uvicorn) and any other process using this "
                    "database, then run this command again.",
                    file=sys.stderr,
                )
                sys.exit(1)
            print(f"removed  {path}")

    init_db()
    print(f"created  {db_path} (tables from current schema)")

    if seed:
        from app.seed_admin_knowledge import main as seed_main

        seed_main()
        print("seeded  admin knowledge items")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset the local SQLite dev database.")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required. Acknowledge permanent deletion of the local SQLite file.",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Re-run python -m app.seed_admin_knowledge after recreating tables.",
    )
    args = parser.parse_args()
    reset_local_db(seed=args.seed, confirmed=args.confirm)


if __name__ == "__main__":
    main()
