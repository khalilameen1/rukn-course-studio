"""Spoken Final Master — primary source is spoken_beats, not an essay paragraph."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.generation import GeneratedReel

# Labels / metadata that must never appear in user-facing spoken text / DOCX body.
METADATA_LEAK_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bhook\s*:",
        r"\bloop\s*:",
        r"\[hook\]",
        r"\[loop\]",
        r"ملاحظات?\s*للمحاضر",
        r"تعليمات\s*تصوير",
        r"critic\s*note",
        r"student\s*note",
        r"mentor\s*note",
        r"needs?\s*confirmation",
        r"source\s*:",
        r"citation",
        r"timestamp",
        r"\bTODO\b",
        r"```",
        r"^\s*[-*•]\s+",
        r"\{\s*\"",
        r"production\s*note",
    )
)

_PUNCTUATION_RE = re.compile(
    "[" + "،,.;؛:؟!?" + "\"'" + "`«»()\\[\\]{}…\\-–—/\\\\" + "]+"
)


@dataclass
class SpokenValidation:
    ok: bool
    errors: list[str]


def strip_spoken_metadata(text: str) -> str:
    """Remove known metadata labels from spoken lines (deterministic cleanup)."""
    lines: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        # Drop pure label lines.
        if re.match(r"^(hook|loop)\s*[:：]", line, re.I):
            continue
        if re.match(r"^\[(hook|loop)\]", line, re.I):
            continue
        line = re.sub(r"^(hook|loop)\s*[:：]\s*", "", line, flags=re.I)
        lines.append(line)
    return "\n".join(lines)


def beats_to_plain_script(beats: list[str]) -> str:
    """Join spoken beats with newlines — teleprompter body source."""
    cleaned = [strip_spoken_metadata(b).strip() for b in beats if (b or "").strip()]
    return "\n".join(b for b in cleaned if b)


def text_to_spoken_beats(text: str) -> list[str]:
    """Split existing script_text into natural spoken beats."""
    cleaned = strip_spoken_metadata(text or "")
    beats: list[str] = []
    for para in re.split(r"\n+", cleaned):
        para = para.strip()
        if not para:
            continue
        # Split long paragraphs on sentence-ish boundaries without keeping punct.
        parts = re.split(r"(?<=[.!?؟！。])\s+|(?<=[،,;؛:])\s+", para)
        for part in parts:
            part = part.strip()
            if part:
                beats.append(part)
    return beats or ([cleaned] if cleaned else [])


def ensure_spoken_beats(reel: GeneratedReel) -> GeneratedReel:
    """Ensure spoken_beats exist; derive script_text from them when present."""
    beats = list(reel.spoken_beats or [])
    if not beats and (reel.script_text or "").strip():
        beats = text_to_spoken_beats(reel.script_text)
    if not beats:
        return reel
    plain = beats_to_plain_script(beats)
    return reel.model_copy(update={"spoken_beats": beats, "script_text": plain})


def strip_punctuation_from_spoken_body(text: str) -> str:
    """Remove punctuation from spoken body; keep natural line breaks.

    Intentional blank lines (teleprompter pauses) are preserved.
    """
    out_lines: list[str] = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            out_lines.append("")
            continue
        cleaned = _PUNCTUATION_RE.sub(" ", stripped)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned:
            out_lines.append(cleaned)
    return "\n".join(out_lines)


def validate_spoken_export_text(text: str) -> SpokenValidation:
    errors: list[str] = []
    body = text or ""
    for pat in METADATA_LEAK_PATTERNS:
        if pat.search(body):
            errors.append(f"metadata_leak:{pat.pattern}")
    return SpokenValidation(ok=not errors, errors=errors)
