"""Simple (no-AI, no-embeddings) analysis of one source's extracted text.

Produces a short extractive summary, a handful of key points, and any
obvious category-driven "avoid" notes - purely from chunk structure (see
app/services/chunking.py). Intentionally simple, per scope: if higher
quality is ever needed, swap this module's output for something smarter
without changing its callers (same `SourceAnalysisResult` shape).

Also provides `select_relevant_chunks`: plain keyword-overlap scoring (set
intersection counts) used by the generation pipeline to pick a few
relevant chunks for a specific reel instead of a source's full text - no
embeddings, no vector search, no RAG framework.
"""

import re
from dataclasses import dataclass

from app.services.chunking import Chunk, chunk_text

# Below this length, a source is "short enough" to pass in full rather than
# summarizing/chunk-selecting - see app/generation/orchestrator.py.
SHORT_SOURCE_MAX_CHARS = 1500

SUMMARY_MAX_CHARS = 300
MAX_KEY_POINTS = 8
MAX_RELEVANT_CHUNKS = 3

# Only populated when there's an obvious, category-driven reason - never
# fabricated from content analysis we can't actually do without AI/NLP.
CATEGORY_AVOID_POINTS: dict[str, list[str]] = {
    "flow_reference": [
        "Natural Colloquial Calibration only — language naturalness sample, not facts/hooks/structure.",
    ],
    "old_course": [
        "Mixed-quality previous draft — candidates only; do not copy hooks/loops/wording; verify claims elsewhere.",
    ],
    "mixed_quality_ai_course_draft": [
        "Mixed-quality previous AI course draft — extract useful candidates only; never quality reference; rebuild in ROKN.",
        "Do not copy wording, hooks, artificial loops, or examples verbatim.",
        "Important claims from this draft alone are ungrounded until verified elsewhere.",
    ],
    "raw_material": ["Mixed/unclear material - treat as uncertain, verify before reuse."],
    "transcript": ["Spoken transcript — extract teaching value; do not copy filler or verbatim rambles."],
}

_WORD_RE = re.compile(r"[a-zA-Z\u0600-\u06FF]+")
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "is", "are", "this", "that", "it", "be", "as", "by", "at", "from",
}


@dataclass
class SourceAnalysisResult:
    chunks: list[Chunk]
    source_summary: str
    key_points: list[str]
    avoid_points: list[str]


def analyze_source_text(text: str, source_category: str) -> SourceAnalysisResult:
    chunks = chunk_text(text)
    return SourceAnalysisResult(
        chunks=chunks,
        source_summary=_build_summary(text),
        key_points=_build_key_points(chunks),
        avoid_points=list(CATEGORY_AVOID_POINTS.get(source_category, [])),
    )


def _build_summary(text: str) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= SUMMARY_MAX_CHARS:
        return cleaned

    truncated = cleaned[:SUMMARY_MAX_CHARS]
    last_period = truncated.rfind(". ")
    if last_period > SUMMARY_MAX_CHARS * 0.5:
        return truncated[: last_period + 1]
    return truncated.rstrip() + "..."


def _build_key_points(chunks: list[Chunk]) -> list[str]:
    points: list[str] = []
    for chunk in chunks:
        point = chunk.heading or _first_sentence(chunk.text)
        if point:
            points.append(point)
        if len(points) >= MAX_KEY_POINTS:
            break
    return points


def _first_sentence(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    for terminator in (". ", ".\n", "! ", "!\n", "? ", "?\n"):
        idx = stripped.find(terminator)
        if idx != -1:
            return stripped[: idx + 1].strip()
    return stripped[:150].strip()


def _keywords(text: str) -> set[str]:
    words = _WORD_RE.findall((text or "").lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


def select_relevant_chunks(
    chunks: list[dict], query_text: str, max_chunks: int = MAX_RELEVANT_CHUNKS
) -> list[dict]:
    """Rank `chunks` (as plain dicts: {"heading", "text", ...}) by simple
    keyword overlap with `query_text`, returning at most `max_chunks`.

    Deliberately not semantic search: exact-word overlap only. Good enough
    for "find the couple of chunks that mention what this reel covers"
    without a vector database.
    """
    query_keywords = _keywords(query_text)
    if not query_keywords:
        return []

    scored: list[tuple[int, dict]] = []
    for chunk in chunks:
        chunk_text_full = f"{chunk.get('heading') or ''} {chunk.get('text') or ''}"
        overlap = len(query_keywords & _keywords(chunk_text_full))
        if overlap > 0:
            scored.append((overlap, chunk))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [chunk for _, chunk in scored[:max_chunks]]
