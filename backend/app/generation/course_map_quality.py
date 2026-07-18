"""Course map quality: hard max caps, shallow detection, local review hints.

Used between first-draft map and Final Course Map rebuild. Never appears in
DOCX. No padding instruction — depth must come from real educational content.

Quality is NOT more minutes or more lessons. There is no Premium minimum
duration floor that inflates maps.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.enums import GenerationQualityMode, TargetMarket
from app.schemas.generation import CourseMap, CourseThesis, ReelPlan
from app.generation.market_evergreen import map_market_evergreen_feedback

# Educational reel norms (estimates on the plan, not padded scripts).
# Soft guidance only — MICRO_CONCEPT may be under 2 minutes when complete.
LESSON_SOFT_MIN_MINUTES = 0.7
LESSON_SOFT_MAX_MINUTES = 6.0

PROGRESS_MAP_FIRST_DRAFT = "Building course map"
PROGRESS_MAP_STUDENT = "Building course map"
PROGRESS_MAP_CRITIC = "Building course map"
PROGRESS_MAP_MENTOR = "Building course map"
PROGRESS_MAP_REBUILD = "Rebuilding final course map"
PROGRESS_START_LESSONS = "Writing first draft"

MAP_LEAK_SUBSTRINGS: tuple[str, ...] = (
    "map_review",
    "first course map draft",
    "student map objection",
    "specialist map review notes",
    "mentor map notes",
    "estimated duration table",
)

# Backward-compat alias — must NEVER be used to inflate maps.
# Kept so older imports don't crash; value unused for floors.
PREMIUM_MIN_TOTAL_MINUTES = 0.0


@dataclass
class MapDurationReport:
    total_minutes: float
    lesson_count: int
    under_two_minute_lessons: int
    over_five_minute_lessons: int
    too_short_for_premium: bool  # always False — inflation floor removed
    over_hard_max_lessons: bool
    over_hard_max_minutes: bool
    shallow_signals: list[str]


def parse_estimated_minutes(estimated_length: str) -> float:
    """Best-effort parse of free-form estimated_length → minutes."""
    text = (estimated_length or "").strip().lower()
    if not text:
        return 2.0  # neutral default when missing (camera explainer mid)

    # Ranges like "2-5 minutes" / "45-60 seconds"
    range_match = re.search(
        r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*(second|sec|minute|min|ساع|دق)",
        text,
    )
    if range_match:
        a, b = float(range_match.group(1)), float(range_match.group(2))
        mid = (a + b) / 2.0
        unit = range_match.group(3)
        if unit.startswith("sec") or unit.startswith("second"):
            return mid / 60.0
        return mid

    single = re.search(
        r"(\d+(?:\.\d+)?)\s*(second|sec|minute|min|ساع|دق|m\b)",
        text,
    )
    if single:
        value = float(single.group(1))
        unit = single.group(2)
        if unit.startswith("sec") or unit.startswith("second"):
            return value / 60.0
        if unit.startswith("ساع"):
            return value * 60.0
        return value

    # Bare number → assume minutes if large, seconds if small heuristically
    bare = re.search(r"(\d+(?:\.\d+)?)", text)
    if bare:
        value = float(bare.group(1))
        if value >= 15:  # likely seconds when "45" or "60"
            return value / 60.0 if value <= 180 else value
        return value

    if "short" in text:
        return 1.2
    if "long" in text or "extended" in text:
        return 5.0
    return 2.0


def reel_estimated_minutes(reel: ReelPlan) -> float:
    if reel.target_spoken_words_min and reel.target_spoken_words_max:
        mid = (reel.target_spoken_words_min + reel.target_spoken_words_max) / 2.0
        return mid / 135.0
    return parse_estimated_minutes(reel.estimated_length)


def total_estimated_minutes(course_map: CourseMap) -> float:
    total = 0.0
    for module in course_map.modules:
        for reel in module.reels:
            total += reel_estimated_minutes(reel)
    return total


def analyze_map_duration(
    course_map: CourseMap,
    *,
    quality_mode: GenerationQualityMode,
    relax_floor: bool,
    thesis: CourseThesis | None = None,
) -> MapDurationReport:
    del quality_mode  # no premium minute floor
    lessons = [r for m in course_map.modules for r in m.reels]
    mins = [reel_estimated_minutes(r) for r in lessons]
    total = sum(mins) if mins else 0.0
    under_two = sum(1 for m in mins if m < 1.0)
    over_five = sum(1 for m in mins if m > LESSON_SOFT_MAX_MINUTES)
    shallow: list[str] = []
    thesis = thesis or course_map.thesis
    over_lessons = bool(
        thesis
        and not thesis.human_override_hard_limits
        and len(lessons) > thesis.hard_max_lessons
    )
    over_minutes = bool(
        thesis
        and not thesis.human_override_hard_limits
        and total > thesis.hard_max_minutes
    )
    if over_lessons:
        shallow.append(
            f"Map has {len(lessons)} lessons over hard_max_lessons="
            f"{thesis.hard_max_lessons} — compress/merge before generation."
        )
    if over_minutes:
        shallow.append(
            f"Map estimates ~{total:.0f} min over hard_max_minutes="
            f"{thesis.hard_max_minutes} — compress before generation."
        )
    if under_two and len(lessons) > 8 and not relax_floor:
        shallow.append(
            f"{under_two} lesson(s) look thinner than a complete micro-concept — "
            "merge only when they lack a distinct teaching outcome (never pad)."
        )
    return MapDurationReport(
        total_minutes=total,
        lesson_count=len(lessons),
        under_two_minute_lessons=under_two,
        over_five_minute_lessons=over_five,
        too_short_for_premium=False,
        over_hard_max_lessons=over_lessons,
        over_hard_max_minutes=over_minutes,
        shallow_signals=shallow,
    )


def is_mini_or_preview_request(
    *,
    quality_mode: GenerationQualityMode,
    special_notes: str | None,
    title: str = "",
) -> bool:
    if quality_mode == GenerationQualityMode.PREVIEW:
        return True
    blob = f"{special_notes or ''} {title}".lower()
    return any(
        k in blob
        for k in ("mini-course", "mini course", "minicourse", "preview only", "short preview")
    )


def local_map_review_feedback(
    course_map: CourseMap,
    *,
    quality_mode: GenerationQualityMode,
    relax_floor: bool,
    target_market: TargetMarket = TargetMarket.EGYPT,
    official_tool_store: object | None = None,
    thesis: CourseThesis | None = None,
) -> list[str]:
    """Compact Student / Critic / Mentor shaped map feedback (no essays)."""
    from app.generation.official_tool_docs import (
        OfficialToolMemoryStore,
        map_official_tool_feedback,
    )

    feedback: list[str] = []
    report = analyze_map_duration(
        course_map,
        quality_mode=quality_mode,
        relax_floor=relax_floor,
        thesis=thesis or course_map.thesis,
    )
    feedback.extend(report.shallow_signals)
    feedback.extend(
        map_market_evergreen_feedback(course_map, target_market=target_market)
    )
    store = official_tool_store
    if isinstance(store, dict):
        store = OfficialToolMemoryStore.model_validate(store)
    if isinstance(store, OfficialToolMemoryStore):
        feedback.extend(map_official_tool_feedback(course_map, store))

    # Student Confusion Layer — progression / projects.
    if len(course_map.modules) >= 1:
        for module in course_map.modules:
            if module.module_project is None and not (module.bridge_project or "").strip():
                feedback.append(
                    "Student: module "
                    f"'{module.title}' needs a practical Module Project so "
                    "learners apply what they learned (not a numbered lesson)."
                )
                break

    if not (course_map.main_thread or "").strip():
        feedback.append(
            "Mentor: course lacks a clear playlist spine (main_thread) — "
            "rebuild so reels feel connected, not a chopped book."
        )

    # Specialist — shallow titles / empty must_cover / missing outcomes.
    empty_cover = sum(
        1 for m in course_map.modules for r in m.reels if not r.must_cover
    )
    if empty_cover:
        feedback.append(
            f"Specialist: {empty_cover} lesson(s) have empty must_cover — "
            "add core teaching points or delete weak shells."
        )
    missing_outcome = sum(
        1
        for m in course_map.modules
        for r in m.reels
        if not (r.distinct_teaching_outcome or "").strip()
    )
    if missing_outcome:
        feedback.append(
            f"Specialist: {missing_outcome} lesson(s) lack distinctTeachingOutcome — "
            "merge or give each lesson a unique skill/decision."
        )

    # Mentor — variety / energy from content roles, not index curves.
    if len(course_map.modules) >= 2:
        purposes = [m.purpose[:40] for m in course_map.modules]
        if len(set(purposes)) < len(purposes):
            feedback.append(
                "Mentor: modules feel samey — vary educational roles "
                "(foundation / correction / application) across the playlist."
            )

    if not feedback:
        feedback.append(
            "Preserve the strongest spine; rebuild Final Course Map with clear "
            "module projects, distinct teaching outcomes, and content-based "
            "lesson lengths. Never inflate lesson count for 'premium' feel."
        )
    return feedback
