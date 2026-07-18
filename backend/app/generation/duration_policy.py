"""Content-based lesson duration / word-count policy (internal).

Lesson type and content drive length — never a mechanical reel-index curve.
Quality is not more lessons or more words.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import LessonDeliveryMode

# Spoken teleprompter pace for camera lessons (words per minute).
DEFAULT_SPOKEN_WPM = 135.0


@dataclass(frozen=True)
class WordRange:
    """Soft target + hard clamps for spoken words."""

    target_min: int
    target_max: int
    soft_min: int
    soft_max: int
    hard_min: int
    hard_max: int


# Ranges from the rebuild brief (approximate spoken words).
_DURATION_BY_MODE: dict[LessonDeliveryMode, WordRange] = {
    LessonDeliveryMode.CAMERA_EXPLAINER: WordRange(150, 280, 120, 320, 100, 360),
    LessonDeliveryMode.MICRO_CONCEPT: WordRange(100, 160, 90, 180, 80, 200),
    LessonDeliveryMode.SCREEN_DEMO: WordRange(180, 520, 160, 560, 140, 600),
    LessonDeliveryMode.PROJECT_BUILD: WordRange(180, 520, 160, 560, 140, 600),
    LessonDeliveryMode.DESIGN_CRITIQUE: WordRange(170, 360, 150, 400, 120, 450),
    LessonDeliveryMode.CRITIQUE: WordRange(170, 360, 150, 400, 120, 450),
    LessonDeliveryMode.BEFORE_AFTER: WordRange(170, 360, 150, 400, 120, 450),
    LessonDeliveryMode.CASE_STUDY: WordRange(170, 360, 150, 400, 120, 450),
    LessonDeliveryMode.ERROR_FIX: WordRange(150, 320, 130, 360, 100, 400),
}


def word_range_for(mode: LessonDeliveryMode | str | None) -> WordRange:
    resolved = _coerce_mode(mode)
    return _DURATION_BY_MODE[resolved]


def _coerce_mode(mode: LessonDeliveryMode | str | None) -> LessonDeliveryMode:
    if isinstance(mode, LessonDeliveryMode):
        return mode
    if not mode:
        return LessonDeliveryMode.CAMERA_EXPLAINER
    try:
        return LessonDeliveryMode(str(mode).strip().lower())
    except ValueError:
        return LessonDeliveryMode.CAMERA_EXPLAINER


def count_spoken_words(text: str) -> int:
    return len([w for w in (text or "").split() if w.strip()])


def estimate_spoken_minutes(
    text: str,
    *,
    delivery_mode: LessonDeliveryMode | str | None = None,
    visual_step_seconds: float = 0.0,
    wpm: float = DEFAULT_SPOKEN_WPM,
) -> float:
    """Estimate duration: spoken words / WPM + visual/demo pause time."""
    words = count_spoken_words(text)
    spoken_min = words / max(wpm, 1.0)
    mode = _coerce_mode(delivery_mode)
    extra = visual_step_seconds / 60.0
    if mode in (LessonDeliveryMode.SCREEN_DEMO, LessonDeliveryMode.PROJECT_BUILD):
        # Screen lessons need execution pauses beyond pure speech.
        if extra <= 0:
            extra = max(0.5, spoken_min * 0.35)
    return spoken_min + extra


def words_within_hard_range(
    text: str,
    *,
    delivery_mode: LessonDeliveryMode | str | None,
) -> bool:
    rng = word_range_for(delivery_mode)
    n = count_spoken_words(text)
    return rng.hard_min <= n <= rng.hard_max


def words_outside_hard_range_reason(
    text: str,
    *,
    delivery_mode: LessonDeliveryMode | str | None,
) -> str | None:
    rng = word_range_for(delivery_mode)
    n = count_spoken_words(text)
    if n < rng.hard_min:
        return f"spoken_words={n} below hard_min={rng.hard_min} for {rng}"
    if n > rng.hard_max:
        return f"spoken_words={n} above hard_max={rng.hard_max}"
    return None
