"""Pure-Python text chunking - no embeddings, no vector search, no RAG
framework. Splits a source's extracted text into logical pieces by
markdown-style headings when present, otherwise by paragraph groups up to
a size limit.
"""

import re
from dataclasses import dataclass

HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")

# Heuristic bound for the paragraph-grouping fallback: keeps chunks small
# enough to be a meaningful unit, without producing hundreds of tiny ones.
MAX_CHUNK_CHARS = 800


@dataclass
class Chunk:
    index: int
    heading: str | None
    text: str


def chunk_text(text: str) -> list[Chunk]:
    text = (text or "").strip()
    if not text:
        return []

    has_headings = any(HEADING_RE.match(line) for line in text.splitlines())
    if has_headings:
        return _chunk_by_headings(text)
    return _chunk_by_paragraphs(text)


def _chunk_by_headings(text: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        body = "\n".join(current_lines).strip()
        if body or current_heading:
            chunks.append(Chunk(index=len(chunks), heading=current_heading, text=body))

    for line in text.splitlines():
        match = HEADING_RE.match(line)
        if match:
            flush()
            current_heading = match.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)
    flush()

    return chunks


def _chunk_by_paragraphs(text: str) -> list[Chunk]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[Chunk] = []
    buffer: list[str] = []
    buffer_len = 0

    def flush() -> None:
        if buffer:
            chunks.append(Chunk(index=len(chunks), heading=None, text="\n\n".join(buffer)))

    for paragraph in paragraphs:
        if buffer and buffer_len + len(paragraph) > MAX_CHUNK_CHARS:
            flush()
            buffer.clear()
            buffer_len = 0
        buffer.append(paragraph)
        buffer_len += len(paragraph)
    flush()

    return chunks
