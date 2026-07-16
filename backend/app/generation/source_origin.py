"""Source origin detection — file format ≠ intent ≠ origin ≠ authority."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.models.enums import SourceCategory, SourceOrigin

SOURCE_ORIGIN_VERSION = "2.0"

TRANSCRIPT_LIKE_ORIGINS: frozenset[str] = frozenset(
    {
        SourceOrigin.AI_GENERATED_TRANSCRIPT.value,
        SourceOrigin.HUMAN_TRANSCRIPT.value,
        SourceOrigin.COURSE_TRANSCRIPT.value,
        SourceOrigin.OLD_COURSE_TRANSCRIPT.value,
        SourceOrigin.MEETING_OR_WEBINAR_TRANSCRIPT.value,
    }
)

VALID_SOURCE_ORIGINS: frozenset[str] = frozenset({o.value for o in SourceOrigin})

TRANSCRIPT_DERIVED_LABEL = (
    "This source appears to be transcript-derived. It may contain ASR/transcription "
    "errors, wrong terms, broken punctuation, repeated fragments, and mixed "
    "Arabic/English mistakes. Clean and interpret cautiously before extracting "
    "useful ideas. Do not copy wording, structure, hooks, examples, or speaker "
    "style. Verify important current/tool-related claims."
)

COURSE_TRANSCRIPT_RAW_LABEL = (
    "This is a course transcript raw material, not a course template. Extract "
    "useful candidates only and rebuild in ROKN teleprompter format. Do not "
    "clone the original course."
)

OLD_COURSE_TRANSCRIPT_LABEL = (
    "This transcript is from an old course. Verify tool/platform/current-market "
    "claims against official docs; preserve durable principles only; do not let "
    "old structure dictate the new map."
)

_TIMESTAMP_CUE = re.compile(
    r"(?:\[[\d:]+\]|\b\d{1,2}:\d{2}(?::\d{2})?\b(?:\s*-->\s*\d{1,2}:\d{2}(?::\d{2})?\b)?)"
)
_SPEAKER_CUE = re.compile(r"(?im)^(?:speaker\s*\d*|host|guest|moderator)\s*:")
_AI_TRANSCRIPT_CUE = re.compile(
    r"(?i)(?:whisper|otter\.ai|descript|speech[\s-]?to[\s-]?text|auto[\s-]?generated|"
    r"\basr\b|transcribed automatically|youtube auto[\s-]?captions)"
)
_MEETING_CUE = re.compile(
    r"(?i)(?:zoom meeting|webinar|google meet|teams meeting|panel discussion|"
    r"q\s*&\s*a session|live session recording)"
)
_COURSE_SPOKEN_CUE = re.compile(
    r"(?i)(?:module\s+(?:one|two|three|\d+)|lesson\s+(?:one|two|three|\d+)|"
    r"في الريل|في الدرس|خلينا|خليني|هنتكلم|هنشرح)"
)
_FILLER_CUE = re.compile(r"(?:\bيعني\b|\bاه\b|\bum\b|\buh\b|\blike\b)", re.I)

_FILE_FORMAT_BY_SUFFIX: dict[str, str] = {
    ".txt": "txt",
    ".md": "md",
    ".docx": "docx",
    ".pdf": "pdf",
}


def detect_file_format(
    *,
    original_filename: str | None = None,
    mime_type: str | None = None,
) -> str:
    """File container/format only — not reliability or origin."""
    if original_filename:
        suffix = Path(original_filename).suffix.lower()
        if suffix in _FILE_FORMAT_BY_SUFFIX:
            return _FILE_FORMAT_BY_SUFFIX[suffix]
    mime = (mime_type or "").lower()
    if "pdf" in mime:
        return "pdf"
    if "wordprocessingml" in mime or mime.endswith("msword"):
        return "docx"
    if "markdown" in mime:
        return "md"
    if "text/plain" in mime:
        return "txt"
    return "pasted" if not original_filename else "unknown"


def has_transcript_cues(text: str) -> bool:
    """Heuristic spoken-transcript signals — extension-agnostic."""
    blob = text or ""
    if not blob.strip():
        return False
    if _TIMESTAMP_CUE.search(blob) or _SPEAKER_CUE.search(blob):
        return True
    if _AI_TRANSCRIPT_CUE.search(blob):
        return True
    if _MEETING_CUE.search(blob):
        return True
    lines = [ln.strip() for ln in blob.splitlines() if ln.strip()]
    if len(lines) >= 8:
        short = sum(1 for ln in lines if len(ln.split()) <= 6)
        if short >= max(4, len(lines) // 3):
            return True
    if len(_FILLER_CUE.findall(blob)) >= 6:
        return True
    if _COURSE_SPOKEN_CUE.search(blob) and len(blob) > 400:
        return True
    return False


def infer_source_origin(
    text: str,
    *,
    category: str,
    original_filename: str | None = None,
    mime_type: str | None = None,
    declared_origin: str | None = None,
    title: str | None = None,
) -> str:
    """Infer source_origin — never treat file extension as authority.

    Prefer the expanded provenance classifier; fall back to transcript heuristics.
    """
    if declared_origin and declared_origin in VALID_SOURCE_ORIGINS:
        return declared_origin

    # Expanded classifier covers books/OCR/articles/etc.
    try:
        from app.generation.source_imperfection import infer_expanded_source_origin

        return infer_expanded_source_origin(
            text,
            category=category,
            original_filename=original_filename,
            mime_type=mime_type,
            declared_origin=declared_origin,
            title=title,
        )
    except Exception:
        pass

    cues = has_transcript_cues(text)
    title_blob = f"{title or ''} {original_filename or ''}"
    file_format = detect_file_format(
        original_filename=original_filename,
        mime_type=mime_type,
    )

    if category == SourceCategory.TRANSCRIPT.value:
        return SourceOrigin.COURSE_TRANSCRIPT.value

    if category == SourceCategory.OLD_COURSE.value:
        if cues or _COURSE_SPOKEN_CUE.search(text or ""):
            return SourceOrigin.OLD_COURSE_TRANSCRIPT.value
        return SourceOrigin.OLD_COURSE_MATERIAL.value

    if _MEETING_CUE.search(f"{text[:1200]} {title_blob}"):
        return SourceOrigin.MEETING_OR_WEBINAR_TRANSCRIPT.value

    if _AI_TRANSCRIPT_CUE.search(text or ""):
        return SourceOrigin.AI_GENERATED_TRANSCRIPT.value

    if cues:
        if _COURSE_SPOKEN_CUE.search(text or ""):
            return SourceOrigin.COURSE_TRANSCRIPT.value
        if category in (
            SourceCategory.RAW_MATERIAL.value,
            SourceCategory.FLOW_REFERENCE.value,
        ):
            return SourceOrigin.AI_GENERATED_TRANSCRIPT.value
        if file_format in ("docx", "txt", "md"):
            return SourceOrigin.HUMAN_TRANSCRIPT.value
        return SourceOrigin.AI_GENERATED_TRANSCRIPT.value

    if category == SourceCategory.SCIENTIFIC_REFERENCE.value:
        return SourceOrigin.WRITTEN_DOCUMENT.value

    if category == SourceCategory.USER_NOTES.value:
        return SourceOrigin.USER_NOTES.value

    return SourceOrigin.UNKNOWN.value


def is_transcript_like_origin(origin: str | None) -> bool:
    return bool(origin and origin in TRANSCRIPT_LIKE_ORIGINS)


def is_transcript_derived_memory(memory: dict[str, Any] | None) -> bool:
    if not memory:
        return False
    if is_transcript_like_origin(str(memory.get("source_origin") or "")):
        return True
    category = str(memory.get("source_type") or memory.get("category") or "")
    return category == SourceCategory.TRANSCRIPT.value


def prompt_labels_for_origin(origin: str) -> list[str]:
    labels: list[str] = []
    if is_transcript_like_origin(origin):
        labels.append(TRANSCRIPT_DERIVED_LABEL)
    if origin in (
        SourceOrigin.COURSE_TRANSCRIPT.value,
        SourceOrigin.OLD_COURSE_TRANSCRIPT.value,
    ):
        labels.append(COURSE_TRANSCRIPT_RAW_LABEL)
    if origin == SourceOrigin.OLD_COURSE_TRANSCRIPT.value:
        labels.append(OLD_COURSE_TRANSCRIPT_LABEL)
    return labels


def apply_source_origin(
    memory: dict[str, Any],
    *,
    text: str,
    category: str,
    original_filename: str | None = None,
    mime_type: str | None = None,
    declared_origin: str | None = None,
    title: str | None = None,
    course_promise: dict[str, Any] | None = None,
    cleaned_text: str | None = None,
    transcript_normalization: Any | None = None,
) -> tuple[str, Any | None]:
    """Resolve provenance and apply general source imperfection for every source."""
    from app.generation.source_imperfection import apply_source_imperfection

    file_format = detect_file_format(
        original_filename=original_filename,
        mime_type=mime_type,
    )
    memory["file_format"] = file_format
    memory["source_intent"] = category

    working, normalization = apply_source_imperfection(
        memory,
        raw_text=text,
        category=category,
        original_filename=original_filename,
        mime_type=mime_type,
        declared_origin=declared_origin,
        title=title,
        course_promise=course_promise,
        pre_cleaned_text=cleaned_text,
    )
    memory["source_origin_version"] = SOURCE_ORIGIN_VERSION

    # Preserve pre-normalized transcript result if caller already cleaned.
    if transcript_normalization is not None and normalization is None:
        return working, transcript_normalization
    return working, normalization


def should_apply_transcript_topic_relevance(memory: dict[str, Any] | None) -> bool:
    return is_transcript_derived_memory(memory)
