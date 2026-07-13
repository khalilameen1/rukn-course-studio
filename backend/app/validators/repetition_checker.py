"""Flags a reel that near-duplicates a prior reel's title, opening,
used_ideas, or used_examples. Simple string similarity (difflib) - no
embeddings, no vector search.
"""

from dataclasses import dataclass

from app.schemas.generation import GeneratedReel
from app.validators.similarity import opening_words, text_similarity

SIMILARITY_THRESHOLD = 0.8
OPENING_WORD_COUNT = 12


@dataclass
class RepetitionMatch:
    reel_id: str
    compared_to_reel_id: str
    field: str  # "title" | "opening" | "used_idea" | "used_example"
    similarity: float
    detail: str


def check_repetition(
    reel: GeneratedReel,
    prior_reels: list[GeneratedReel],
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[RepetitionMatch]:
    """Compare `reel` against every reel in `prior_reels` (already
    generated, different reel_id)."""
    matches: list[RepetitionMatch] = []
    reel_opening = opening_words(reel.script_text, OPENING_WORD_COUNT)

    for prior in prior_reels:
        if prior.reel_id == reel.reel_id:
            continue

        title_sim = text_similarity(reel.title, prior.title)
        if title_sim >= threshold:
            matches.append(
                RepetitionMatch(
                    reel.reel_id,
                    prior.reel_id,
                    "title",
                    title_sim,
                    f"Title too similar to reel '{prior.reel_id}' ('{prior.title}').",
                )
            )

        opening_sim = text_similarity(
            reel_opening, opening_words(prior.script_text, OPENING_WORD_COUNT)
        )
        if opening_sim >= threshold:
            matches.append(
                RepetitionMatch(
                    reel.reel_id,
                    prior.reel_id,
                    "opening",
                    opening_sim,
                    f"Opening too similar to reel '{prior.reel_id}'.",
                )
            )

        for idea in reel.used_ideas:
            for prior_idea in prior.used_ideas:
                sim = text_similarity(idea, prior_idea)
                if sim >= threshold:
                    matches.append(
                        RepetitionMatch(
                            reel.reel_id,
                            prior.reel_id,
                            "used_idea",
                            sim,
                            f"Idea '{idea}' repeats reel '{prior.reel_id}'.",
                        )
                    )

        for example in reel.used_examples:
            for prior_example in prior.used_examples:
                sim = text_similarity(example, prior_example)
                if sim >= threshold:
                    matches.append(
                        RepetitionMatch(
                            reel.reel_id,
                            prior.reel_id,
                            "used_example",
                            sim,
                            f"Example '{example}' repeats reel '{prior.reel_id}'.",
                        )
                    )

    return matches
