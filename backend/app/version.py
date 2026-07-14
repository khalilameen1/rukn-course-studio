"""Safe, cached app-commit helper (used by app/generation/run_snapshot.py).

Never raises and never blocks startup/generation: if this isn't a git
checkout (some deploy environments), or `git` itself isn't available, the
result is just the string "unknown" - this is diagnostic/traceability
metadata only, never something a run should fail over.
"""

from __future__ import annotations

import os
import subprocess
from functools import lru_cache

from app.config import REPO_ROOT

UNKNOWN_COMMIT = "unknown"


@lru_cache(maxsize=1)
def get_app_commit() -> str:
    """Short git commit hash, env override (Render/CI), or "unknown".

    Prefer `GIT_COMMIT_SHA` / `RENDER_GIT_COMMIT` when present so deploys
    without a `.git` directory still report a useful hash.
    """
    for key in ("GIT_COMMIT_SHA", "RENDER_GIT_COMMIT"):
        env_commit = (os.environ.get(key) or "").strip()
        if env_commit:
            return env_commit[:40]

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:  # noqa: BLE001 - must never raise, see module docstring
        return UNKNOWN_COMMIT

    if result.returncode != 0:
        return UNKNOWN_COMMIT
    commit = result.stdout.strip()
    return commit or UNKNOWN_COMMIT
