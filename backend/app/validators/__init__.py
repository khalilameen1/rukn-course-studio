"""Local, deterministic validators that run before an expensive AI review
call (see app/generation/orchestrator.py `_local_review_single_reel`).

No AI, no embeddings, no vector search anywhere in this package.
"""

from app.validators.anti_template_checker import check_anti_template
from app.validators.forbidden_phrase_checker import check_forbidden_phrases
from app.validators.high_signal_checker import check_high_signal
from app.validators.length_checker import check_length
from app.validators.opening_checker import check_opening
from app.validators.repetition_checker import check_repetition

__all__ = [
    "check_anti_template",
    "check_forbidden_phrases",
    "check_high_signal",
    "check_length",
    "check_opening",
    "check_repetition",
]
