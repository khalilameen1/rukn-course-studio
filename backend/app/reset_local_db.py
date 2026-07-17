"""Compatibility entrypoint — prefer `python -m app.scripts.reset_local_db`."""

from app.scripts.reset_local_db import *  # noqa: F403
from app.scripts.reset_local_db import reset_local_db

if __name__ == "__main__":
    from app.scripts.reset_local_db import main

    raise SystemExit(main())
