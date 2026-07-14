"""Teleprompter Readability Formatting Gate.

Formats final spoken scripts for on-camera reading: natural spoken Egyptian
Arabic lines, light punctuation, line breaks for breath/pause, blank lines
between idea blocks. Never adds stage directions like [pause]. Never changes
DOCX product shape (title / module / lesson / transcript only).
"""

from __future__ import annotations

import re

TELEPROMPTER_READABILITY_PROMPT_RULE = (
    "The final script must be formatted for teleprompter reading. Use natural "
    "spoken lines. End each complete sentence/thought with a new line. Use "
    "blank lines between idea blocks. Avoid heavy punctuation. Do not break "
    "every word into a separate line. Do not use stage directions or pause "
    "labels. The formatting itself should guide reading, breathing, and silence."
)

# Stage directions that must never appear in the spoken script.
_PAUSE_LABEL_RE = re.compile(
    r"(?i)\s*[\[\(\{]\s*(?:pause|breath|breathe|silence|beat|stop|"
    r"توقف|نفس|سكوت|صمت|استراحة)\s*[\]\)\}]\s*"
    r"|\s*(?:pause here|take a breath|breathe here)\s*:?\s*"
)

# Decorative / academic punctuation to soften (not question marks).
_HEAVY_PUNCT_RE = re.compile(r"[;؛…—–_]{1,}|,{2,}|،{2,}|\.{3,}")
_COMMAS_RE = re.compile(r"[،,]")

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?؟۔])\s+|\n+")
_WORD_RE = re.compile(r"[\w\u0600-\u06FF]+", re.UNICODE)

# Soft transition cues → prefer a blank line before the next block.
_BLOCK_SHIFT_RE = re.compile(
    r"(?i)^("
    r"دلوقتي|كده|فلو|يعني|الخطوة|يعني بإيجاز|خلينا نطبق|"
    r"مثلاً|مثلا|تحذير|خلاصة|النقطة|"
    r"now|so if|for example|warning|step\s*\d|next"
    r")"
)

_TARGET_LINE_WORDS = 14
_MAX_LINE_WORDS = 18
_MIN_LINE_WORDS = 3


def _word_count(text: str) -> int:
    return len(_WORD_RE.findall(text or ""))


def strip_pause_labels(text: str) -> str:
    return _PAUSE_LABEL_RE.sub(" ", text or "")


def _soften_punctuation(text: str) -> str:
    """Remove heavy decorative punctuation; keep ؟ ! . when needed."""
    t = _HEAVY_PUNCT_RE.sub(" ", text or "")
    # Prefer line-break semantic over comma chains: replace ،/, with soft space.
    # Remaining endings stay until sentence split.
    t = _COMMAS_RE.sub(" ", t)
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()


def _split_long_thought(thought: str) -> list[str]:
    """Break a long thought into readable teleprompter lines (~breath units)."""
    words = thought.split()
    if len(words) <= _MAX_LINE_WORDS:
        return [thought] if thought.strip() else []

    lines: list[str] = []
    buf: list[str] = []
    # Prefer soft breaks before connectors when possible.
    soft_starts = {
        "ولو", "فلو", "عشان", "لأن", "لكن", "وبعدين", "وكمان", "يعني",
        "and", "but", "because", "so", "then", "which",
    }
    for w in words:
        if buf and len(buf) >= _TARGET_LINE_WORDS and w.lower() in soft_starts:
            lines.append(" ".join(buf).rstrip(" ،,"))
            buf = [w]
            continue
        buf.append(w)
        if len(buf) >= _MAX_LINE_WORDS:
            lines.append(" ".join(buf).rstrip(" ،,"))
            buf = []
    if buf:
        # Avoid orphan 1–2 word lines: merge into previous if tiny.
        if len(buf) < _MIN_LINE_WORDS and lines:
            lines[-1] = (lines[-1] + " " + " ".join(buf)).strip()
        else:
            lines.append(" ".join(buf).rstrip(" ،,"))
    return [ln for ln in lines if ln.strip()]


def _normalize_thought(raw: str) -> str:
    t = strip_pause_labels(raw)
    t = _soften_punctuation(t)
    # Strip trailing sentence punctuation for spoken teleprompter default
    # (keep ؟ and ! which carry spoken intonation).
    t = t.strip()
    if t.endswith(".") or t.endswith("۔"):
        t = t[:-1].rstrip()
    return t


def format_script_for_teleprompter(text: str) -> str:
    """Return teleprompter-ready spoken script with readable line breaks.

    - One sentence/thought per line (or soft breath split for long thoughts)
    - Blank line between idea blocks
    - No [pause]/[breath] labels
    - Minimal punctuation
    - Never one-word-per-line drama
    - Preserves educational meaning (no content deletion beyond labels/punct)
    """
    if not (text or "").strip():
        return ""

    cleaned = strip_pause_labels(text)
    # Preserve existing intentional blank lines as block separators later.
    chunks = re.split(r"\n\s*\n+", cleaned)
    out_lines: list[str] = []

    for chunk_i, chunk in enumerate(chunks):
        chunk = chunk.strip()
        if not chunk:
            continue
        # Flatten inner newlines first, then re-split by sentence endings.
        flat = " ".join(ln.strip() for ln in chunk.splitlines() if ln.strip())
        flat = _soften_punctuation(flat)
        thoughts = [
            _normalize_thought(p)
            for p in _SENTENCE_SPLIT_RE.split(flat)
            if p and p.strip()
        ]
        if not thoughts:
            continue

        block_lines: list[str] = []
        for thought in thoughts:
            if not thought:
                continue
            block_lines.extend(_split_long_thought(thought))

        # Drop theatrical single-word lines by merging.
        merged: list[str] = []
        for ln in block_lines:
            wc = _word_count(ln)
            if wc == 0:
                continue
            if wc < _MIN_LINE_WORDS and merged:
                merged[-1] = f"{merged[-1]} {ln}".strip()
            else:
                merged.append(ln)

        # Insert blank lines between blocks and before shift cues.
        if out_lines and merged:
            out_lines.append("")
        for i, ln in enumerate(merged):
            if i > 0 and _BLOCK_SHIFT_RE.match(ln) and out_lines and out_lines[-1] != "":
                out_lines.append("")
            out_lines.append(ln)

        if chunk_i < len(chunks) - 1 and out_lines and out_lines[-1] != "":
            # Extra blank between original paragraph blocks.
            pass

    # Collapse 3+ blank lines to one.
    final: list[str] = []
    blank_run = 0
    for ln in out_lines:
        if ln == "":
            blank_run += 1
            if blank_run == 1:
                final.append("")
            continue
        blank_run = 0
        final.append(ln)

    while final and final[0] == "":
        final.pop(0)
    while final and final[-1] == "":
        final.pop()

    return "\n".join(final)


def punctuation_density(text: str) -> float:
    """Rough fraction of heavy punctuation chars — used by tests/gates."""
    if not text:
        return 0.0
    heavy = len(re.findall(r"[،,;؛…—–]", text))
    return heavy / max(len(text), 1)


def looks_like_dense_paragraph(text: str) -> bool:
    """True when script is essentially one block without readable breaks."""
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    if len(lines) <= 1 and _word_count(text) > 40:
        return True
    if len(lines) <= 2 and _word_count(text) > 80:
        return True
    return False


def looks_like_word_per_line(text: str) -> bool:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if len(lines) < 5:
        return False
    short = sum(1 for ln in lines if _word_count(ln) <= 1)
    return short / len(lines) >= 0.7
