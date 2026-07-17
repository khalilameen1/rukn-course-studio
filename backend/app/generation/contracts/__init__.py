"""Domain content contracts for the course generation engine."""

from app.generation.contracts.course_thesis import (
    PRACTICAL_DEFAULTS,
    build_course_thesis_from_brief,
    validate_course_thesis,
)
from app.generation.contracts.lesson_blueprint import (
    ensure_reel_blueprint_defaults,
    validate_lesson_blueprint,
)
from app.generation.contracts.spoken_final_master import (
    METADATA_LEAK_PATTERNS,
    beats_to_plain_script,
    ensure_spoken_beats,
    strip_spoken_metadata,
    validate_spoken_export_text,
)

__all__ = [
    "PRACTICAL_DEFAULTS",
    "build_course_thesis_from_brief",
    "validate_course_thesis",
    "ensure_reel_blueprint_defaults",
    "validate_lesson_blueprint",
    "METADATA_LEAK_PATTERNS",
    "beats_to_plain_script",
    "ensure_spoken_beats",
    "strip_spoken_metadata",
    "validate_spoken_export_text",
]
