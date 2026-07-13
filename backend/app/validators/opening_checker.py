"""Flags a reel whose opening repeats a previous reel's opening.

Distinct from repetition_checker: this runs against every reel generated
in the course SO FAR (not just a bounded window/module), since comparing
short opening strings is cheap - openings are exactly the kind of thing
that tends to become formulaic across an entire course, not just locally.
Simple string similarity - no embeddings.
"""

from dataclasses import dataclass

from app.schemas.generation import GeneratedReel
from app.validators.similarity import opening_words, text_similarity

OPENING_WORD_COUNT = 10
OPENING_SIMILARITY_THRESHOLD = 0.85


@dataclass
class OpeningIssue:
    reel_id: str
    repeats_reel_id: str
    similarity: float
    opening: str


def check_opening(
    reel: GeneratedReel,
    all_prior_reels: list[GeneratedReel],
    threshold: float = OPENING_SIMILARITY_THRESHOLD,
) -> list[OpeningIssue]:
    opening = opening_words(reel.script_text, OPENING_WORD_COUNT)
    if not opening:
        return []

    issues: list[OpeningIssue] = []
    for prior in all_prior_reels:
        if prior.reel_id == reel.reel_id:
            continue
        prior_opening = opening_words(prior.script_text, OPENING_WORD_COUNT)
        if not prior_opening:
            continue
        similarity = text_similarity(opening, prior_opening)
        if similarity >= threshold:
            issues.append(OpeningIssue(reel.reel_id, prior.reel_id, similarity, opening))

    return issues
