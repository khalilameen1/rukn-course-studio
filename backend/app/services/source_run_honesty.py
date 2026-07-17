"""Coarse source-use honesty for the Generate UI (never DOCX citations)."""

from __future__ import annotations

from typing import Any

from app.services.source_status import (
    EXTRACTION_BLOCKED,
    FAILED,
    PASSWORD_REQUIRED,
    POOR_EXTRACTION,
    PROCESSING_FAILED,
    READY,
    SCANNED_NO_TEXT,
)

# Soft tip when included extractable text exceeds prompt budget.
OVERLOAD_CHAR_BUDGET = 6000

SKIPPED_STATUSES = frozenset(
    {
        PASSWORD_REQUIRED,
        SCANNED_NO_TEXT,
        EXTRACTION_BLOCKED,
        FAILED,
        PROCESSING_FAILED,
        "uploaded",
        "processing",
    }
)


def classify_sources_for_run(sources: list[Any]) -> dict[str, Any]:
    """Return counts + short labels for UI (no source bodies)."""
    used: list[str] = []
    skipped: list[str] = []
    weak: list[str] = []
    excluded: list[str] = []
    included_chars = 0

    for source in sources:
        label = (
            getattr(source, "title", None)
            or getattr(source, "original_filename", None)
            or f"source-{getattr(source, 'id', '?')}"
        )
        status = getattr(source, "status", "") or ""
        included = bool(getattr(source, "include_in_generation", True))
        text = getattr(source, "extracted_text", None) or ""

        if not included:
            excluded.append(str(label))
            continue
        if status == POOR_EXTRACTION and text:
            weak.append(str(label))
            included_chars += len(text)
            continue
        if status == READY and text:
            used.append(str(label))
            included_chars += len(text)
            continue
        if status in SKIPPED_STATUSES or not text:
            reason = status or "unusable"
            skipped.append(f"{label} ({reason})")
            continue
        # Unknown but included with text → treat as used
        if text:
            used.append(str(label))
            included_chars += len(text)
        else:
            skipped.append(f"{label} ({status or 'empty'})")

    overload = included_chars > OVERLOAD_CHAR_BUDGET
    summary = (
        f"Used {len(used)} · Weak {len(weak)} · Skipped {len(skipped)}"
        + (f" · Excluded {len(excluded)}" if excluded else "")
    )
    if overload:
        summary += (
            f" · Large library (~{included_chars} chars); lower-priority "
            f"material may be trimmed (budget ~{OVERLOAD_CHAR_BUDGET})."
        )

    return {
        "used_count": len(used),
        "weak_count": len(weak),
        "skipped_count": len(skipped),
        "excluded_count": len(excluded),
        "used": used[:12],
        "weak": weak[:12],
        "skipped": skipped[:12],
        "excluded": excluded[:12],
        "included_chars": included_chars,
        "overload": overload,
        "summary": summary,
    }


def format_sources_run_summary(sources: list[Any]) -> str:
    return str(classify_sources_for_run(sources)["summary"])
