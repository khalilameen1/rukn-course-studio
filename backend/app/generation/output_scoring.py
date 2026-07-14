"""Output Scoring Gates (§4): observational quality checks over the final
(or partial) rendered course text.

`score_final_course` runs once, after a course's DOCX has been rendered
(success or partial - the caller decides which rendered text to pass in),
and produces an `OutputScoreReport`. Every check here is READ-ONLY over
already-rendered plain text (see `app/services/docx_export.py
extract_plain_text`) - nothing here inspects, modifies, or re-renders the
DOCX itself, and the report is stored only on `GenerationJob.
output_score_json`, never inside the DOCX.

Blocking decision (documented per the request): none of these checks ever
block export. Even `teleprompter_clean == False` (the closest thing to a
"severe contract violation" this pass defines) still exports normally -
the report is attached to the job so a failure is visible and can be
flagged prominently in the UI (see §11), but skipping/blocking export
outright is a materially bigger behavior change than this hardening pass
is meant to make. If a future pass wants a hard block, `teleprompter_clean`
is the field to gate on.

`internal_notes_absent` is intentionally computed as exactly the same
value as `teleprompter_clean` - both are driven by the same
`TELEPROMPTER_FORBIDDEN_SUBSTRINGS` list (see
app/generation/teleprompter_checks.py). Kept as two separate report fields
only because the originating request named them separately; consolidating
into two genuinely different implementations would be over-engineering for
what is, in practice, one signal.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.generation.prompt_compiler import connector_word_density, split_sentences_for_scoring
from app.generation.teleprompter_checks import (
    find_forbidden_substrings,
    module_lesson_structure_present,
)
from app.validators.forbidden_phrase_checker import check_forbidden_phrases
from app.validators.similarity import text_similarity

# Mirrors app/generation/prompt_compiler.py's own flow-profile connector-
# density threshold (`_CONNECTOR_DENSITY_THRESHOLD`) - kept as a separate
# constant rather than importing a private module attribute, but
# deliberately the same value so "sounds conversational" means the same
# thing in both places.
CONNECTOR_DENSITY_THRESHOLD = 0.15

# Two paragraphs at/above this similarity ratio (difflib, same approach as
# app/validators/repetition_checker.py) are flagged as a possible
# whole-document repeat. Slightly higher than the per-reel repetition
# checker's 0.8 threshold since this scans the *whole* document rather
# than comparing one new reel against its immediate predecessors, so it
# should only flag genuinely near-duplicate paragraphs, not just similarly
# short ones.
REPETITION_SIMILARITY_THRESHOLD = 0.85
_MIN_PARAGRAPH_LEN_FOR_REPETITION_CHECK = 20

# A source-text word must be at least this long to count as a "signal"
# word for the (deliberately crude) source-grounding heuristic below -
# keeps short/common words from producing meaningless false "grounded"
# matches.
MIN_SOURCE_SIGNAL_WORD_LEN = 6


class ReadabilityScore(BaseModel):
    avg_words_per_sentence: float
    avg_words_per_paragraph: float


class SpokenStyleScore(BaseModel):
    connector_word_density: float
    reads_conversationally: bool


class OutputScoreReport(BaseModel):
    """Purely observational - see module docstring. Never blocks export."""

    teleprompter_clean: bool
    internal_notes_absent: bool
    forbidden_phrases_absent: bool
    paragraph_readability: ReadabilityScore
    spoken_style_score: SpokenStyleScore
    module_lesson_structure_present: bool
    source_grounding_warning: str | None = None
    repetition_warning: str | None = None
    forbidden_substrings_found: list[str] = Field(default_factory=list)
    forbidden_phrases_found: list[str] = Field(default_factory=list)


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in (text or "").split("\n") if p.strip()]


def _paragraph_readability(text: str) -> ReadabilityScore:
    paragraphs = _paragraphs(text)
    sentences = split_sentences_for_scoring(text)
    avg_sentence = sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0.0
    avg_paragraph = (
        sum(len(p.split()) for p in paragraphs) / len(paragraphs) if paragraphs else 0.0
    )
    return ReadabilityScore(
        avg_words_per_sentence=round(avg_sentence, 1),
        avg_words_per_paragraph=round(avg_paragraph, 1),
    )


def _spoken_style(text: str) -> SpokenStyleScore:
    density = connector_word_density(text)
    return SpokenStyleScore(
        connector_word_density=round(density, 3),
        reads_conversationally=density >= CONNECTOR_DENSITY_THRESHOLD,
    )


def _repetition_warning(text: str) -> str | None:
    """Simple O(n^2) whole-document near-duplicate-paragraph scan - fine
    for one course's worth of paragraphs (tens, not thousands)."""
    paragraphs = [p for p in _paragraphs(text) if len(p) >= _MIN_PARAGRAPH_LEN_FOR_REPETITION_CHECK]
    for i, first in enumerate(paragraphs):
        for second in paragraphs[i + 1 :]:
            if text_similarity(first, second) >= REPETITION_SIMILARITY_THRESHOLD:
                return (
                    "Two or more paragraphs in the final document are nearly identical - "
                    "possible repeated content."
                )
    return None


def _signal_words(source_text: str) -> set[str]:
    return {
        word.strip(".,!?\u061f\u060c\u061b\"'()").lower()
        for word in (source_text or "").split()
        if len(word) >= MIN_SOURCE_SIGNAL_WORD_LEN
    }


def _source_grounding_warning(text: str, source_texts: list[str] | None) -> str | None:
    """Warning-only, deliberately crude heuristic: a handful of long
    ("signal") words from each usable source, checked for a literal
    substring match in the final text. This cannot reliably confirm real
    content grounding - a source could be genuinely used after heavy
    rephrasing (which is exactly what's *supposed* to happen for
    `scientific_reference`/`flow_reference` sources, see
    app/generation/prompt_compiler.py) and still trip this warning. It
    exists only to catch the more obvious case of "sources were uploaded
    but the run clearly never touched them at all" - never treat it as a
    hard fact.
    """
    if not source_texts:
        return None

    lowered = (text or "").lower()
    for source_text in source_texts:
        if any(word and word in lowered for word in _signal_words(source_text)):
            return None

    return (
        "This course had usable source material available, but nothing in the "
        "generated content clearly reflects it. This is a crude keyword-overlap "
        "heuristic, not a real content check - treat it as a prompt to double-check "
        "manually, not a hard fact."
    )


def score_final_course(
    document_text: str,
    rules_context: dict[str, str],
    source_texts: list[str] | None = None,
) -> OutputScoreReport:
    """Score `document_text` - the plain text of an already-rendered final
    or partial DOCX (see `app/services/docx_export.py extract_plain_text`).

    `rules_context` is the active-rules dict (same shape as
    `app/generation/orchestrator.py` `_load_active_rules`'s return value) -
    used only to look up `rukn_forbidden_phrases` via the existing
    `check_forbidden_phrases` validator, exactly as the per-reel review
    path already does.
    """
    forbidden_substrings_found = find_forbidden_substrings(document_text)
    forbidden_phrase_matches = check_forbidden_phrases(document_text, rules_context)
    teleprompter_clean = not forbidden_substrings_found

    return OutputScoreReport(
        teleprompter_clean=teleprompter_clean,
        internal_notes_absent=teleprompter_clean,
        forbidden_phrases_absent=not forbidden_phrase_matches,
        paragraph_readability=_paragraph_readability(document_text),
        spoken_style_score=_spoken_style(document_text),
        module_lesson_structure_present=module_lesson_structure_present(document_text),
        source_grounding_warning=_source_grounding_warning(document_text, source_texts),
        repetition_warning=_repetition_warning(document_text),
        forbidden_substrings_found=forbidden_substrings_found,
        forbidden_phrases_found=[match.phrase for match in forbidden_phrase_matches],
    )
