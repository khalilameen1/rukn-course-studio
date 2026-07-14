"""Cost hygiene helpers — identical-retry block, waste warnings, usage stages."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

# Usage stage labels (job + AIUsageEvent.stage enrichment / telemetry).
USAGE_STAGES = (
    "source_extraction",
    "web_research",
    "research_memory_reuse",
    "course_map_first_draft",
    "course_map_reviews",
    "course_map_final_rebuild",
    "lesson_first_draft",
    "student_review",
    "specialist_critic_review",
    "master_mentor_review",
    "lesson_final_rewrite",
    "final_export",
)

# Heuristic thresholds for waste warnings.
HIGH_COST_PER_LESSON_USD = 0.85
HIGH_WEB_SEARCHES = 12


@dataclass
class WasteWarningTracker:
    warnings: list[str] = field(default_factory=list)
    identical_retry_blocks: int = 0
    research_memory_reuses: int = 0
    duplicate_searches: int = 0
    full_source_dumps: int = 0
    full_admin_dumps: int = 0

    def add(self, code: str) -> None:
        if code and code not in self.warnings:
            self.warnings.append(code)

    def model_dump(self) -> dict[str, Any]:
        return {
            "warnings": list(self.warnings),
            "identical_retry_blocks": self.identical_retry_blocks,
            "research_memory_reuses": self.research_memory_reuses,
            "duplicate_searches": self.duplicate_searches,
            "full_source_dumps": self.full_source_dumps,
            "full_admin_dumps": self.full_admin_dumps,
        }


def fingerprint_retry(*, phase: str, feedback: list[str], script_text: str) -> str:
    """Fingerprint identical retry inputs — same repair must not loop."""
    fb = "\n".join((feedback or [])[:12])
    # Normalize whitespace so tiny spacing changes don't bypass the guard.
    body = re.sub(r"\s+", " ", f"{phase}|{fb}|{script_text or ''}").strip().lower()
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:24]


class IdenticalRetryGuard:
    """Blocks retrying the exact same failed prompt input."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def allow(self, *, phase: str, feedback: list[str], script_text: str) -> bool:
        fp = fingerprint_retry(phase=phase, feedback=feedback, script_text=script_text)
        if fp in self._seen:
            return False
        self._seen.add(fp)
        return True


def detect_full_source_dump(excerpt_text: str, original_chars: int) -> bool:
    """True if a lesson prompt appears to contain nearly the full long source."""
    if original_chars < 2000:
        return False
    return len(excerpt_text or "") >= int(original_chars * 0.65)


def build_usage_panel(
    *,
    estimated_cost_usd: float,
    completed_lessons: int,
    web_searches_count: int,
    source_memories_reused: int,
    waste_warnings: list[str] | None = None,
    research_memory_reuses: int = 0,
) -> dict[str, Any]:
    """Simple user-facing usage panel fields."""
    lessons = max(completed_lessons, 1) if estimated_cost_usd else max(completed_lessons, 0)
    cost_per = (
        round(estimated_cost_usd / lessons, 4) if completed_lessons > 0 else None
    )
    warnings = list(waste_warnings or [])
    if cost_per is not None and cost_per >= HIGH_COST_PER_LESSON_USD:
        if "high_cost_per_lesson" not in warnings:
            warnings.append("high_cost_per_lesson")
    if web_searches_count >= HIGH_WEB_SEARCHES:
        if "high_web_search_count" not in warnings:
            warnings.append("high_web_search_count")
    return {
        "total_estimated_cost": round(estimated_cost_usd, 4),
        "cost_per_completed_lesson": cost_per,
        "web_searches_count": web_searches_count,
        "source_memories_reused": source_memories_reused,
        "research_memory_reuses": research_memory_reuses,
        "warnings": warnings,
    }
