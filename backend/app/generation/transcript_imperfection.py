"""Transcript imperfection hygiene — STT/OCR noise is raw material, not literal truth."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

TRANSCRIPT_IMPERFECTION_VERSION = "1.1"

TRANSCRIPT_IMPERFECTION_NOTE = (
    "AI-generated transcripts are noisy raw material — extract meaning, not wording. "
    "Correct only obvious transcription noise; do not guess unclear terms. "
    "Official documentation and verified educational sources override transcript claims."
)

_TIMESTAMP_RE = re.compile(
    r"(?:\[[\d:]+\]|\([\d:]+\)|\b\d{1,2}:\d{2}(?::\d{2})?\b(?:\s*-->\s*\d{1,2}:\d{2}(?::\d{2})?\b)?)"
)
_SPEAKER_TAG_RE = re.compile(r"(?im)^(?:speaker\s*\d*|host|guest)\s*:\s*")

# Obvious OCR/character-substitution only — not semantic guessing.
_OCR_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"Faceb00k", re.I), "Facebook"),
    (re.compile(r"Faceb[o0]ok", re.I), "Facebook"),
    (re.compile(r"Metа\s+Ads", re.I), "Meta Ads"),  # Cyrillic а
    (re.compile(r"R0AS", re.I), "ROAS"),
    (re.compile(r"lnstagram", re.I), "Instagram"),
)

_DUPLICATE_PHRASE_RE = re.compile(r"(.+?)(?:\s+\1)+", re.I)


@dataclass
class TranscriptNormalizationResult:
    original_text: str
    cleaned_text: str
    corrections: list[str] = field(default_factory=list)
    uncertain_fragments: list[str] = field(default_factory=list)


def strip_transcript_timestamps(text: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    cleaned = text or ""
    if _TIMESTAMP_RE.search(cleaned):
        notes.append("removed embedded timestamps/speaker tags")
        cleaned = _TIMESTAMP_RE.sub(" ", cleaned)
    if _SPEAKER_TAG_RE.search(cleaned) or re.search(
        r"(?i)(?:speaker\s*\d*|host|guest)\s*:", cleaned
    ):
        if "removed embedded timestamps/speaker tags" not in notes:
            notes.append("removed embedded timestamps/speaker tags")
        cleaned = _SPEAKER_TAG_RE.sub("", cleaned)
        cleaned = re.sub(r"(?i)(?:speaker\s*\d*|host|guest)\s*:\s*", "", cleaned)
    return re.sub(r"\s{2,}", " ", cleaned).strip(), notes


def dedupe_transcript_fragments(text: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    if not text:
        return text, notes

    sentences = [s.strip() for s in re.split(r"(?<=[.!?؟])\s+", text) if s.strip()]
    deduped: list[str] = []
    for sentence in sentences:
        if deduped and sentence.lower() == deduped[-1].lower():
            notes.append("removed duplicated sentence fragment")
            continue
        deduped.append(sentence)

    joined = " ".join(deduped)
    shortened = _DUPLICATE_PHRASE_RE.sub(r"\1", joined)
    if shortened != joined:
        notes.append("collapsed repeated inline phrase")
    return shortened, notes


def fix_obvious_ocr_substitutions(text: str) -> tuple[str, list[str]]:
    """Digit/character confusions in known tokens only — no semantic guessing."""
    notes: list[str] = []
    out = text
    for pattern, replacement in _OCR_REPLACEMENTS:
        if pattern.search(out):
            notes.append(f"corrected obvious OCR token -> {replacement}")
            out = pattern.sub(replacement, out)
    return out, notes


def normalize_transcript_text(text: str) -> TranscriptNormalizationResult:
    """Conservative transcript cleanup before extraction — never invent meaning."""
    original = text or ""
    current = original
    corrections: list[str] = []

    for step in (
        strip_transcript_timestamps,
        dedupe_transcript_fragments,
        fix_obvious_ocr_substitutions,
    ):
        current, notes = step(current)
        corrections.extend(notes)

    return TranscriptNormalizationResult(
        original_text=original,
        cleaned_text=current.strip(),
        corrections=corrections,
    )


def apply_transcript_imperfection(
    memory: dict[str, Any],
    *,
    normalization: TranscriptNormalizationResult,
) -> dict[str, Any]:
    """Attach transcript mistrust metadata after normalization."""
    memory["transcript_imperfection_version"] = TRANSCRIPT_IMPERFECTION_VERSION
    memory["transcript_normalized"] = normalization.cleaned_text != normalization.original_text
    if normalization.corrections:
        memory["transcript_corrections"] = normalization.corrections[:12]
    if normalization.uncertain_fragments:
        memory["uncertain_terms"] = normalization.uncertain_fragments[:8]
    notes = list(memory.get("relevance_notes") or [])
    if TRANSCRIPT_IMPERFECTION_NOTE not in notes:
        notes.insert(0, TRANSCRIPT_IMPERFECTION_NOTE)
    memory["relevance_notes"] = notes[:10]
    blocked = list(memory.get("blocked_content_warnings") or [])
    extra = (
        "Transcript wording is not trusted literally — extract meaning only; "
        "official docs beat transcript claims"
    )
    if extra not in blocked:
        blocked.append(extra)
    memory["blocked_content_warnings"] = blocked[:12]
    return memory
