"""Source origin detection — file format ≠ intent ≠ origin ≠ authority."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.models.enums import SourceCategory, SourceOrigin

SOURCE_ORIGIN_VERSION = "1.0"

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
    """Infer source_origin — never treat file extension as authority."""
    if declared_origin and declared_origin in VALID_SOURCE_ORIGINS:
        return declared_origin

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
        return SourceOrigin.WRITTEN_DOCUMENT.value

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
        return SourceOrigin.UNKNOWN.value

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
    """Resolve origin, apply transcript hygiene when transcript-like."""
    origin = infer_source_origin(
        text,
        category=category,
        original_filename=original_filename,
        mime_type=mime_type,
        declared_origin=declared_origin,
        title=title,
    )
    file_format = detect_file_format(
        original_filename=original_filename,
        mime_type=mime_type,
    )

    memory["source_origin"] = origin
    memory["source_origin_version"] = SOURCE_ORIGIN_VERSION
    memory["file_format"] = file_format
    memory["source_intent"] = category
    if declared_origin and declared_origin in VALID_SOURCE_ORIGINS:
        memory["declared_source_origin"] = declared_origin

    working_text = cleaned_text if cleaned_text is not None else text
    normalization = transcript_normalization

    if is_transcript_like_origin(origin) and working_text.strip():
        if normalization is None:
            from app.generation.transcript_imperfection import normalize_transcript_text

            normalization = normalize_transcript_text(working_text)
            working_text = normalization.cleaned_text or working_text

        from app.generation.transcript_imperfection import apply_transcript_imperfection

        apply_transcript_imperfection(memory, normalization=normalization)

        from app.generation.transcript_relevance import apply_transcript_relevance

        apply_transcript_relevance(
            memory,
            extracted_text=working_text,
            course_promise=course_promise,
        )

        for label in prompt_labels_for_origin(origin):
            notes = list(memory.get("relevance_notes") or [])
            if label not in notes:
                notes.append(label)
            memory["relevance_notes"] = notes[:12]
            memory["transcript_origin_prompt_label"] = label

        blocked = list(memory.get("blocked_content_warnings") or [])
        for item in prompt_labels_for_origin(origin):
            if item not in blocked:
                blocked.append(item)
        memory["blocked_content_warnings"] = blocked[:14]

    return working_text, normalization


def should_apply_transcript_topic_relevance(memory: dict[str, Any] | None) -> bool:
    return is_transcript_derived_memory(memory)
