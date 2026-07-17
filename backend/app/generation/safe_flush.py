"""Safe job field updates — never abort a run over an optional column."""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Fields added in recent hardening passes — if a deploy missed patches,
# drop them and retry rather than FAIL the whole generation.
OPTIONAL_JOB_FLUSH_KEYS: frozenset[str] = frozenset(
    {
        "provenance_summary",
        "architecture_summary",
        "grounding_confidence",
        "research_synthesis_summary",
        "improve_next_tip",
        "sources_run_summary",
        "estimated_usage_summary",
        "estimated_duration_summary",
        "budget_warning",
        "web_searches_count",
        "research_memory_reuse_count",
        "waste_warnings_json",
        "usage_by_stage_json",
        "output_score_json",
        "internal_risk_count",
    }
)


def safe_job_flush(flush: Callable[..., Any], **job_fields: Any) -> Any:
    """Call flush; on missing-column / unknown field, retry without optionals."""
    try:
        return flush(**job_fields)
    except Exception as exc:  # noqa: BLE001
        text = f"{type(exc).__name__} {exc}".lower()
        looks_like_schema = any(
            token in text
            for token in (
                "no such column",
                "undefined column",
                "unknown column",
                "does not exist",
                "has no attribute",
                "unexpected keyword",
            )
        )
        if not looks_like_schema:
            raise
        trimmed = {
            k: v for k, v in job_fields.items() if k not in OPTIONAL_JOB_FLUSH_KEYS
        }
        dropped = sorted(set(job_fields) - set(trimmed))
        logger.warning(
            "Job flush retried without optional columns %s (%s)",
            dropped,
            type(exc).__name__,
        )
        return flush(**trimmed)
