"""Local, deterministic validators that run before an expensive AI review
call (see app/generation/orchestrator.py `_local_review_single_reel`).

No AI, no embeddings, no vector search anywhere in this package.
"""

from app.validators.anti_patterns_checker import check_anti_patterns_script
from app.validators.anti_template_checker import check_anti_template
from app.validators.creator_persona_checker import check_creator_persona_script
from app.validators.forbidden_phrase_checker import check_forbidden_phrases
from app.validators.high_signal_checker import check_high_signal
from app.validators.length_checker import check_length
from app.validators.opening_checker import check_opening
from app.validators.repetition_checker import check_repetition
from app.validators.teaching_curve_checker import (
    check_anti_flatness,
    check_anti_overperformance,
)

__all__ = [
    "check_anti_patterns_script",
    "check_anti_template",
    "check_anti_flatness",
    "check_anti_overperformance",
    "check_creator_persona_script",
    "check_forbidden_phrases",
    "check_high_signal",
    "check_length",
    "check_opening",
    "check_repetition",
]
