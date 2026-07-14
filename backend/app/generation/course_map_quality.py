"""Course map quality: duration floors, shallow detection, local review hints.

Used between first-draft map and Final Course Map rebuild. Never appears in
DOCX. No padding instruction — depth must come from real educational content.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.enums import GenerationQualityMode, TargetMarket
from app.schemas.generation import CourseMap, ReelPlan
from app.generation.market_evergreen import map_market_evergreen_feedback

# Premium seriousness floor (spoken estimate from estimated_length fields).
PREMIUM_MIN_TOTAL_MINUTES = 120.0
# Educational reel norms (estimates on the plan, not padded scripts).
LESSON_MIN_MINUTES = 2.0
LESSON_SOFT_MAX_MINUTES = 5.0

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


@dataclass
class MapDurationReport:
    total_minutes: float
    lesson_count: int
    under_two_minute_lessons: int
    over_five_minute_lessons: int
    too_short_for_premium: bool
    shallow_signals: list[str]


def parse_estimated_minutes(estimated_length: str) -> float:
    """Best-effort parse of free-form estimated_length → minutes."""
    text = (estimated_length or "").strip().lower()
    if not text:
        return 3.0  # neutral default when missing

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
        return 1.5
    if "long" in text or "extended" in text:
        return 6.0
    return 3.0


def reel_estimated_minutes(reel: ReelPlan) -> float:
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
) -> MapDurationReport:
    lessons = [r for m in course_map.modules for r in m.reels]
    mins = [reel_estimated_minutes(r) for r in lessons]
    total = sum(mins) if mins else 0.0
    under_two = sum(1 for m in mins if m < LESSON_MIN_MINUTES)
    over_five = sum(1 for m in mins if m > LESSON_SOFT_MAX_MINUTES)
    shallow: list[str] = []
    too_short = (
        quality_mode == GenerationQualityMode.PREMIUM
        and not relax_floor
        and total < PREMIUM_MIN_TOTAL_MINUTES
    )
    if too_short:
        shallow.append(
            f"Total estimated spoken time ~{total:.0f} min is under the "
            f"{PREMIUM_MIN_TOTAL_MINUTES:.0f}-minute Premium seriousness floor — "
            "rebuild with real depth, bridges, examples, and practical steps "
            "(no motivational padding)."
        )
    if under_two and len(lessons) > 1:
        shallow.append(
            f"{under_two} lesson(s) estimated under {LESSON_MIN_MINUTES:.0f} minutes — "
            "merge tiny related lessons or expand only with real value "
            "(never pad)."
        )
    if len(lessons) < 4 and not relax_floor:
        shallow.append(
            "Course plan has very few lessons for a serious outcome — "
            "check missing concepts, bridges, and application steps."
        )
    return MapDurationReport(
        total_minutes=total,
        lesson_count=len(lessons),
        under_two_minute_lessons=under_two,
        over_five_minute_lessons=over_five,
        too_short_for_premium=too_short,
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
) -> list[str]:
    """Compact Student / Critic / Mentor shaped map feedback (no essays)."""
    from app.generation.official_tool_docs import (
        OfficialToolMemoryStore,
        map_official_tool_feedback,
    )

    feedback: list[str] = []
    report = analyze_map_duration(
        course_map, quality_mode=quality_mode, relax_floor=relax_floor
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

    # Student Confusion Layer — progression / prerequisites.
    if len(course_map.modules) >= 2:
        for i, module in enumerate(course_map.modules[:-1]):
            if not (module.bridge_project or "").strip():
                feedback.append(
                    "Student: module "
                    f"'{module.title}' needs a practical bridge before "
                    f"'{course_map.modules[i + 1].title}' so 80% of learners "
                    "do not jump blindly."
                )
                break

    if not (course_map.main_thread or "").strip():
        feedback.append(
            "Mentor: course lacks a clear playlist spine (main_thread) — "
            "rebuild so reels feel connected, not a chopped book."
        )

    # Specialist — shallow titles / empty must_cover.
    empty_cover = sum(
        1 for m in course_map.modules for r in m.reels if not r.must_cover
    )
    if empty_cover:
        feedback.append(
            f"Specialist: {empty_cover} lesson(s) have empty must_cover — "
            "add core teaching points or delete weak shells."
        )

    # Mentor — variety / energy.
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
            "module roles, learnable progression, and realistic "
            f"{LESSON_MIN_MINUTES:.0f}–{LESSON_SOFT_MAX_MINUTES:.0f} minute lesson "
            "estimates (longer only when a connected idea needs it). No padding."
        )
    return feedback
