"""Preflight checks so Generate fails clearly *before* a doomed run starts."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any

from app.ai.factory import get_ai_provider, missing_openai_config
from app.config import settings

# Strings that are clearly placeholders — never call a paid provider with these.
_BAD_MODEL_MARKERS = (
    "your-model",
    "changeme",
    "example",
    "placeholder",
    "<",
    ">",
)

_MODEL_OK = re.compile(r"^gpt-5\.6(?:-sol)?$", re.I)


def validate_ai_model_name(model_name: str | None) -> str | None:
    """Return a user-safe error string if the model slug looks unusable."""
    name = (model_name or "").strip()
    if not name:
        return "AI_MODEL_NAME is empty."
    low = name.lower()
    if any(m in low for m in _BAD_MODEL_MARKERS):
        return (
            f"AI_MODEL_NAME '{name}' looks invalid or is a placeholder. "
            "Set AI_MODEL_NAME=gpt-5.6-sol in the Render dashboard."
        )
    if not _MODEL_OK.match(name):
        return (
            f"AI_MODEL_NAME '{name}' is not the approved ROKN model "
            "(expected gpt-5.6-sol or alias gpt-5.6)."
        )
    return None


def check_storage_disk(*, min_free_mb: int = 50) -> str | None:
    """Return error if outputs disk is critically low.

    Skipped when GENERATION_SKIP_DISK_CHECK is truthy (tests / constrained CI).
    Uses the storage root's drive; never fails closed on probe errors alone.
    """
    if getattr(settings, "generation_skip_disk_check", False):
        return None
    try:
        path = Path(settings.storage_outputs_dir)
        path.mkdir(parents=True, exist_ok=True)
        # Probe with a tiny write — more reliable than free-bytes on some hosts.
        probe = path / ".rukn_disk_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        usage = shutil.disk_usage(path)
        free_mb = usage.free / (1024 * 1024)
        # Ignore absurd readings (some mounts report 0 incorrectly).
        if free_mb < 1:
            return None
        if free_mb < min_free_mb:
            return (
                f"Storage disk is nearly full (~{int(free_mb)} MB free). "
                "Free space before generating."
            )
    except OSError as exc:
        return f"Storage disk is not writable ({exc})."
    return None


def generation_preflight() -> dict[str, Any]:
    """Coarse readiness for Generate — never starts a job."""
    blockers: list[str] = []
    warnings: list[str] = []
    provider = (settings.ai_provider or "fake").strip().lower()

    try:
        get_ai_provider()
    except Exception as exc:  # noqa: BLE001
        blockers.append(str(exc))

    if provider == "openai":
        missing = missing_openai_config(settings)
        if missing:
            blockers.append(
                "OpenAI config missing: " + ", ".join(missing)
            )
        model_err = validate_ai_model_name(settings.ai_model_name)
        if model_err:
            blockers.append(model_err)
        # Live probe only after static config looks sane — catches bad keys /
        # model IDs / client kwargs before CourseMap Pro+max can spend.
        if not blockers and os.environ.get("RUKN_CREDIT_SAFE_TESTS") != "1":
            from app.ai.openai_provider import probe_openai_responses_api

            probe_err = probe_openai_responses_api()
            if probe_err:
                blockers.append(probe_err)

    disk_err = check_storage_disk()
    if disk_err:
        blockers.append(disk_err)

    if provider == "fake":
        warnings.append(
            "AI_PROVIDER=fake — runs succeed with placeholder scripts, not real OpenAI generation."
        )
    if provider == "openai" and not (settings.ai_runaway_hard_cap_usd or 0):
        warnings.append(
            "AI_RUNAWAY_HARD_CAP_USD is unset — a stuck/retrying run can keep spending. "
            "Set a USD hard cap in Render for bug protection."
        )

    return {
        "ok": not blockers,
        "provider": provider,
        "blockers": blockers,
        "warnings": warnings,
        "model_name_set": bool((settings.ai_model_name or "").strip()),
    }
