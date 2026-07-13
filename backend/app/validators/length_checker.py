"""Flags a reel script that's too short or too long, by word count. No AI.

Bounds are rough (a reel is meant to be a short, single-topic script) and
deliberately generous so they only catch obviously broken output, not
stylistic length choices.
"""

from dataclasses import dataclass

from app.schemas.generation import GeneratedReel

MIN_WORDS = 15
MAX_WORDS = 500


@dataclass
class LengthIssue:
    reel_id: str
    word_count: int
    reason: str  # "too_short" | "too_long"


def check_length(
    reel: GeneratedReel, min_words: int = MIN_WORDS, max_words: int = MAX_WORDS
) -> list[LengthIssue]:
    word_count = len((reel.script_text or "").split())
    if word_count < min_words:
        return [LengthIssue(reel.reel_id, word_count, "too_short")]
    if word_count > max_words:
        return [LengthIssue(reel.reel_id, word_count, "too_long")]
    return []
