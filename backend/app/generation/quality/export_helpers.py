"""Small export/status helpers shared by gates and tests."""

from __future__ import annotations

from app.generation.quality.issue_codes import EXPORT_BLOCKING_STATUSES


def status_blocks_export(status: str | None) -> bool:
    return (status or "").strip().lower() in EXPORT_BLOCKING_STATUSES
