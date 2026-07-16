"""General source imperfection — all course sources are untrusted raw material."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.models.enums import ExtractionMethod, SourceCategory, SourceOrigin

SOURCE_IMPERFECTION_VERSION = "1.0"

SOURCE_MISTRUST_LABEL = (
    "This source is untrusted raw material. It may contain outdated information, "
    "OCR/extraction errors, foreign-market assumptions, theoretical filler, "
    "transcription noise, or weak structure depending on its origin. Extract useful "
    "meaning only. Do not copy wording, structure, examples, hooks, or style. "
    "Verify important/current/tool-related claims. Rebuild everything in ROKN "
    "teleprompter format."
)

# Short banner for prompt excerpts — full label stays in memory metadata/warnings.
SOURCE_MISTRUST_EXCERPT_BANNER = (
    "[UNTRUSTED RAW MATERIAL — extract meaning only; verify tool claims; rebuild in ROKN.]"
)

OCR_SOURCE_LABEL = (
    "This source appears OCR/scan-derived. It may contain wrong letters, broken "
    "Arabic, merged/split words, misread numbers, header/footer artifacts, or "
    "garbled tables. Clean obvious artifacts only; do not confidently use "
    "suspicious terms; verify important claims; never let OCR artifacts into "
    "final DOCX."
)

ACADEMIC_BOOK_LABEL = (
    "This source appears academic/book-derived. Extract durable concepts, "
    "simplified definitions, frameworks, distinctions, and warnings only. Do not "
    "copy book structure or paragraphs; do not use academic wording in the final "
    "script; do not trust current tool/platform details from old books."
)

TRANSCRIPT_LIKE_ORIGINS: frozenset[str] = frozenset(
    {
        SourceOrigin.AI_GENERATED_TRANSCRIPT.value,
        SourceOrigin.HUMAN_TRANSCRIPT.value,
        SourceOrigin.COURSE_TRANSCRIPT.value,
        SourceOrigin.OLD_COURSE_TRANSCRIPT.value,
        SourceOrigin.MEETING_OR_WEBINAR_TRANSCRIPT.value,
    }
)

OCR_LIKE_ORIGINS: frozenset[str] = frozenset(
    {
        SourceOrigin.SCANNED_PDF.value,
        SourceOrigin.OCR_TEXT.value,
        SourceOrigin.SCREENSHOT_OR_IMAGE.value,
    }
)

BOOK_LIKE_ORIGINS: frozenset[str] = frozenset(
    {
        SourceOrigin.ACADEMIC_BOOK.value,
        SourceOrigin.PRACTICAL_BOOK.value,
        SourceOrigin.ARTICLE.value,
    }
)

VALID_SOURCE_ORIGINS: frozenset[str] = frozenset({o.value for o in SourceOrigin})
VALID_EXTRACTION_METHODS: frozenset[str] = frozenset({m.value for m in ExtractionMethod})

# Risk flag names (stored as strings on memory).
RISK_OUTDATED = "outdated_possible"
RISK_OCR_NOISE = "ocr_noise_possible"
RISK_TRANSCRIPT_NOISE = "transcript_noise_possible"
RISK_FOREIGN_MARKET = "foreign_market_context"
RISK_ACADEMIC = "academic_theory_heavy"
RISK_SHALLOW = "shallow_or_generic"
RISK_TRANSLATED = "translated_or_stiff"
RISK_REPETITIVE = "repetitive_or_filler"
RISK_TOOL_UI_OLD = "tool_ui_may_be_old"
RISK_UNCERTAIN_TERMS = "uncertain_terms"

ALL_RISK_FLAGS: frozenset[str] = frozenset(
    {
        RISK_OUTDATED,
        RISK_OCR_NOISE,
        RISK_TRANSCRIPT_NOISE,
        RISK_FOREIGN_MARKET,
        RISK_ACADEMIC,
        RISK_SHALLOW,
        RISK_TRANSLATED,
        RISK_REPETITIVE,
        RISK_TOOL_UI_OLD,
        RISK_UNCERTAIN_TERMS,
    }
)

_OCR_ARTIFACT_RE = re.compile(
    r"(?i)(?:\bfi\s+g\.\s*\d+|page\s+\d+\s+of\s+\d+|confidential|"
    r"scanned\s+with|ocr(?:ed)?\s+by|adobe\s+scan|"
    r"\u00ac|\ufffd|[|]{3,}|_{5,}|-{5,})"
)
_OCR_BROKEN_ARABIC_RE = re.compile(r"[\u0600-\u06FF]\s{2,}[\u0600-\u06FF]")
_OCR_MERGED_LATIN_RE = re.compile(r"(?<=[a-z])(?=[A-Z][a-z])")
_HEADER_FOOTER_LINE_RE = re.compile(
    r"(?im)^(?:page\s+\d+|chapter\s+\d+|©|\(c\)|all rights reserved|"
    r"www\.|http://|https://).*$"
)
_ACADEMIC_CUE = re.compile(
    r"(?i)(?:furthermore|moreover|in conclusion|theoretical framework|"
    r"literature review|hypothesis|methodology|peer[\s-]?reviewed|"
    r"according to the literature|scholarly)"
)
_BOOK_CUE = re.compile(
    r"(?i)(?:chapter\s+\d+|table of contents|isbn|published by|"
    r"copyright\s+\d{4}|preface|appendix\s+[a-z])"
)
_ARTICLE_CUE = re.compile(
    r"(?i)(?:abstract:|keywords:|doi:|journal of|vol\.\s*\d+|issue\s+\d+)"
)
_FOREIGN_MARKET_CUE = re.compile(
    r"(?i)(?:united states|u\.s\.|usa|irs\b|401\(k\)|sba\b|zip code|"
    r"social security|eu gdpr|hmrc|pound sterling|\$\d{1,3},\d{3})"
)
_OUTDATED_CUE = re.compile(
    r"(?i)(?:power editor|boost post|facebook ads manager 201[0-9]|"
    r"ios\s*14|before\s+att|legacy interface|deprecated|"
    r"in\s+201[0-8]\b|obsolete)"
)
_TRANSLATED_CUE = re.compile(
    r"(?i)(?:it is important to note|one must consider|in order to|"
    r"with regard to|furthermore it is)"
)
_FILLER_CUE = re.compile(r"(?i)(?:\bfurthermore\b|\bmoreover\b|\bin conclusion\b|"
                        r"\bيعني\b|\bum\b|\buh\b)")

# Obvious OCR character substitutions only.
_OCR_TOKEN_FIXES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"Faceb00k", re.I), "Facebook"),
    (re.compile(r"Faceb[o0]ok", re.I), "Facebook"),
    (re.compile(r"Metа\s+Ads", re.I), "Meta Ads"),
    (re.compile(r"R0AS", re.I), "ROAS"),
    (re.compile(r"lnstagram", re.I), "Instagram"),
    (re.compile(r"\brn\b"), "m"),  # common OCR rn→m in isolation — careful; skip broad
)

# Suspicious OCR-like tokens to mark uncertain (not rewrite).
_SUSPICIOUS_TOKEN_RE = re.compile(
    r"(?i)\b(?:[A-Za-z]*\d+[A-Za-z]+\d*[A-Za-z]*|[A-Za-z]{1,2}\d{2,}[A-Za-z]*)\b"
)


@dataclass
class SourceNormalizationResult:
    original_text: str
    cleaned_text: str
    corrections: list[str] = field(default_factory=list)
    uncertain_fragments: list[str] = field(default_factory=list)


def infer_extraction_method(
    *,
    original_filename: str | None = None,
    mime_type: str | None = None,
    declared_method: str | None = None,
    text: str = "",
) -> str:
    if declared_method and declared_method in VALID_EXTRACTION_METHODS:
        return declared_method
    name = (original_filename or "").lower()
    mime = (mime_type or "").lower()
    suffix = Path(name).suffix.lower() if name else ""

    if _OCR_ARTIFACT_RE.search(text or "") or "ocr" in name or "scanned" in name:
        return ExtractionMethod.OCR.value
    if suffix == ".pdf" or "pdf" in mime:
        return ExtractionMethod.PDF_TEXT.value
    if suffix == ".docx" or "wordprocessingml" in mime:
        return ExtractionMethod.DOCX_TEXT.value
    if suffix == ".doc" or mime.endswith("msword"):
        return ExtractionMethod.DOC_TEXT.value
    if suffix in (".txt", ".md") or "text/plain" in mime or "markdown" in mime:
        return ExtractionMethod.DIRECT_TEXT.value
    if not original_filename:
        return ExtractionMethod.PASTED_TEXT.value
    return ExtractionMethod.UNKNOWN.value


def infer_expanded_source_origin(
    text: str,
    *,
    category: str,
    original_filename: str | None = None,
    mime_type: str | None = None,
    declared_origin: str | None = None,
    title: str | None = None,
    extraction_method: str | None = None,
) -> str:
    """Infer provenance — extension never equals authority."""
    if declared_origin and declared_origin in VALID_SOURCE_ORIGINS:
        return declared_origin

    from app.generation.source_origin import (
        _AI_TRANSCRIPT_CUE,
        _COURSE_SPOKEN_CUE,
        _MEETING_CUE,
        detect_file_format,
        has_transcript_cues,
    )

    title_blob = f"{title or ''} {original_filename or ''}".lower()
    blob = text or ""
    method = extraction_method or infer_extraction_method(
        original_filename=original_filename,
        mime_type=mime_type,
        text=blob,
    )
    file_format = detect_file_format(
        original_filename=original_filename,
        mime_type=mime_type,
    )

    if category == SourceCategory.USER_NOTES.value:
        return SourceOrigin.USER_NOTES.value

    if category == SourceCategory.TRANSCRIPT.value:
        return SourceOrigin.COURSE_TRANSCRIPT.value

    if category == SourceCategory.OLD_COURSE.value:
        if has_transcript_cues(blob):
            return SourceOrigin.OLD_COURSE_TRANSCRIPT.value
        return SourceOrigin.OLD_COURSE_MATERIAL.value

    if method == ExtractionMethod.OCR.value or "scanned" in title_blob or "ocr" in title_blob:
        if Path((original_filename or "")).suffix.lower() == ".pdf":
            return SourceOrigin.SCANNED_PDF.value
        return SourceOrigin.OCR_TEXT.value

    if "screenshot" in title_blob or "image" in title_blob:
        return SourceOrigin.SCREENSHOT_OR_IMAGE.value

    if _MEETING_CUE.search(f"{blob[:1200]} {title_blob}"):
        return SourceOrigin.MEETING_OR_WEBINAR_TRANSCRIPT.value

    if _AI_TRANSCRIPT_CUE.search(blob):
        return SourceOrigin.AI_GENERATED_TRANSCRIPT.value

    if has_transcript_cues(blob):
        if _COURSE_SPOKEN_CUE.search(blob):
            return SourceOrigin.COURSE_TRANSCRIPT.value
        if category in (
            SourceCategory.RAW_MATERIAL.value,
            SourceCategory.FLOW_REFERENCE.value,
        ):
            return SourceOrigin.AI_GENERATED_TRANSCRIPT.value
        if file_format in ("docx", "txt", "md"):
            return SourceOrigin.HUMAN_TRANSCRIPT.value
        return SourceOrigin.AI_GENERATED_TRANSCRIPT.value

    if _ARTICLE_CUE.search(blob) or "article" in title_blob:
        return SourceOrigin.ARTICLE.value

    if _ACADEMIC_CUE.search(blob) and (_BOOK_CUE.search(blob) or len(blob) > 2500):
        return SourceOrigin.ACADEMIC_BOOK.value

    if _BOOK_CUE.search(blob) or "book" in title_blob:
        if _ACADEMIC_CUE.search(blob):
            return SourceOrigin.ACADEMIC_BOOK.value
        return SourceOrigin.PRACTICAL_BOOK.value

    if "translated" in title_blob or _TRANSLATED_CUE.search(blob[:800]):
        return SourceOrigin.TRANSLATED_MATERIAL.value

    if category == SourceCategory.SCIENTIFIC_REFERENCE.value:
        return SourceOrigin.WRITTEN_DOCUMENT.value

    if category == SourceCategory.MIXED_QUALITY_AI_COURSE_DRAFT.value:
        return SourceOrigin.OLD_COURSE_MATERIAL.value

    return SourceOrigin.UNKNOWN.value


def detect_source_risk_flags(
    text: str,
    *,
    origin: str,
    extraction_method: str,
) -> list[str]:
    flags: list[str] = []
    blob = text or ""

    if origin in TRANSCRIPT_LIKE_ORIGINS:
        flags.append(RISK_TRANSCRIPT_NOISE)
    if origin in OCR_LIKE_ORIGINS or extraction_method == ExtractionMethod.OCR.value:
        flags.append(RISK_OCR_NOISE)
    if origin in BOOK_LIKE_ORIGINS or _ACADEMIC_CUE.search(blob):
        flags.append(RISK_ACADEMIC)
    if _FOREIGN_MARKET_CUE.search(blob):
        flags.append(RISK_FOREIGN_MARKET)
    if _OUTDATED_CUE.search(blob):
        flags.append(RISK_OUTDATED)
        flags.append(RISK_TOOL_UI_OLD)
    if origin == SourceOrigin.TRANSLATED_MATERIAL.value or _TRANSLATED_CUE.search(blob[:1200]):
        flags.append(RISK_TRANSLATED)
    if len(_FILLER_CUE.findall(blob)) >= 4:
        flags.append(RISK_REPETITIVE)
    if len(blob) < 500 and blob.count(".") < 3:
        flags.append(RISK_SHALLOW)
    if _SUSPICIOUS_TOKEN_RE.search(blob) and (
        origin in OCR_LIKE_ORIGINS or extraction_method == ExtractionMethod.OCR.value
    ):
        flags.append(RISK_UNCERTAIN_TERMS)

    # Dedupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for f in flags:
        if f not in seen and f in ALL_RISK_FLAGS:
            seen.add(f)
            out.append(f)
    return out


def strip_ocr_page_artifacts(text: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    lines = (text or "").splitlines()
    kept: list[str] = []
    for line in lines:
        if _HEADER_FOOTER_LINE_RE.match(line.strip()):
            notes.append("removed OCR header/footer line")
            continue
        kept.append(line)
    cleaned = "\n".join(kept)
    if _OCR_ARTIFACT_RE.search(cleaned):
        cleaned2 = _OCR_ARTIFACT_RE.sub(" ", cleaned)
        if cleaned2 != cleaned:
            notes.append("removed OCR page artifacts")
            cleaned = cleaned2
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned.strip(), notes


def fix_obvious_ocr_tokens(text: str) -> tuple[str, list[str], list[str]]:
    """Fix only high-confidence OCR token substitutions; mark other suspicious tokens."""
    notes: list[str] = []
    uncertain: list[str] = []
    out = text or ""
    for pattern, replacement in _OCR_TOKEN_FIXES:
        if pattern.pattern == r"\brn\b":
            continue  # too aggressive; skip
        if pattern.search(out):
            notes.append(f"corrected obvious OCR token -> {replacement}")
            out = pattern.sub(replacement, out)
    for m in _SUSPICIOUS_TOKEN_RE.finditer(out):
        tok = m.group(0)
        if len(tok) >= 4 and tok.lower() not in {"meta", "roas", "ads"}:
            # Skip tokens we already fixed into known brands
            if any(x.lower() in tok.lower() for x in ("Facebook", "Instagram", "ROAS", "Meta")):
                continue
            if re.search(r"\d", tok) and tok not in uncertain:
                uncertain.append(tok)
    return out, notes, uncertain[:12]


def dedupe_repeated_lines(text: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    lines = [ln.rstrip() for ln in (text or "").splitlines()]
    out: list[str] = []
    for ln in lines:
        if out and ln.strip() and ln.strip().lower() == out[-1].strip().lower():
            notes.append("removed repeated OCR/line fragment")
            continue
        out.append(ln)
    return "\n".join(out), notes


def normalize_ocr_text(text: str) -> SourceNormalizationResult:
    """Conservative OCR cleanup — never invent meaning."""
    original = text or ""
    current = original
    corrections: list[str] = []
    uncertain: list[str] = []

    current, n = strip_ocr_page_artifacts(current)
    corrections.extend(n)
    current, n = dedupe_repeated_lines(current)
    corrections.extend(n)
    current, n, unc = fix_obvious_ocr_tokens(current)
    corrections.extend(n)
    uncertain.extend(unc)

    return SourceNormalizationResult(
        original_text=original,
        cleaned_text=current.strip(),
        corrections=corrections,
        uncertain_fragments=uncertain,
    )


def prompt_labels_for_source(
    *,
    origin: str,
    extraction_method: str,
    risk_flags: list[str],
) -> list[str]:
    labels = [SOURCE_MISTRUST_LABEL]
    if origin in TRANSCRIPT_LIKE_ORIGINS or RISK_TRANSCRIPT_NOISE in risk_flags:
        from app.generation.source_origin import (
            COURSE_TRANSCRIPT_RAW_LABEL,
            OLD_COURSE_TRANSCRIPT_LABEL,
            TRANSCRIPT_DERIVED_LABEL,
        )

        labels.append(TRANSCRIPT_DERIVED_LABEL)
        if origin in (
            SourceOrigin.COURSE_TRANSCRIPT.value,
            SourceOrigin.OLD_COURSE_TRANSCRIPT.value,
        ):
            labels.append(COURSE_TRANSCRIPT_RAW_LABEL)
        if origin == SourceOrigin.OLD_COURSE_TRANSCRIPT.value:
            labels.append(OLD_COURSE_TRANSCRIPT_LABEL)
    if origin in OCR_LIKE_ORIGINS or extraction_method == ExtractionMethod.OCR.value:
        labels.append(OCR_SOURCE_LABEL)
    if origin in BOOK_LIKE_ORIGINS or RISK_ACADEMIC in risk_flags:
        labels.append(ACADEMIC_BOOK_LABEL)
    return labels


def apply_source_imperfection(
    memory: dict[str, Any],
    *,
    raw_text: str,
    category: str,
    original_filename: str | None = None,
    mime_type: str | None = None,
    declared_origin: str | None = None,
    declared_extraction_method: str | None = None,
    title: str | None = None,
    course_promise: dict[str, Any] | None = None,
    pre_cleaned_text: str | None = None,
) -> tuple[str, SourceNormalizationResult | None]:
    """Apply general mistrust + conservative cleaning for any source."""
    infer_from = raw_text or ""
    method = infer_extraction_method(
        original_filename=original_filename,
        mime_type=mime_type,
        declared_method=declared_extraction_method,
        text=infer_from,
    )
    origin = infer_expanded_source_origin(
        infer_from,
        category=category,
        original_filename=original_filename,
        mime_type=mime_type,
        declared_origin=declared_origin,
        title=title,
        extraction_method=method,
    )

    working = pre_cleaned_text if pre_cleaned_text is not None else infer_from
    normalization: SourceNormalizationResult | None = None

    # OCR / scan cleaning (skip if caller already cleaned)
    if pre_cleaned_text is None and (
        origin in OCR_LIKE_ORIGINS or method == ExtractionMethod.OCR.value
    ):
        normalization = normalize_ocr_text(working)
        working = normalization.cleaned_text or working

    # Transcript cleaning (subset)
    if pre_cleaned_text is None and (
        origin in TRANSCRIPT_LIKE_ORIGINS or category == SourceCategory.TRANSCRIPT.value
    ):
        from app.generation.transcript_imperfection import normalize_transcript_text

        tnorm = normalize_transcript_text(working)
        working = tnorm.cleaned_text or working
        if normalization is None:
            normalization = SourceNormalizationResult(
                original_text=raw_text,
                cleaned_text=working,
                corrections=list(tnorm.corrections),
                uncertain_fragments=list(tnorm.uncertain_fragments),
            )
        else:
            normalization.cleaned_text = working
            normalization.corrections.extend(tnorm.corrections)
            normalization.uncertain_fragments.extend(tnorm.uncertain_fragments)
    elif pre_cleaned_text is not None:
        normalization = SourceNormalizationResult(
            original_text=raw_text,
            cleaned_text=working,
            corrections=[],
            uncertain_fragments=[],
        )

    risk_flags = detect_source_risk_flags(
        working, origin=origin, extraction_method=method
    )
    if normalization and normalization.uncertain_fragments:
        if RISK_UNCERTAIN_TERMS not in risk_flags:
            risk_flags.append(RISK_UNCERTAIN_TERMS)

    memory["source_origin"] = origin
    memory["source_origin_version"] = "2.0"
    memory["extraction_method"] = method
    memory["source_risk_flags"] = risk_flags
    memory["source_imperfection_version"] = SOURCE_IMPERFECTION_VERSION
    memory["source_intent"] = category
    if declared_origin and declared_origin in VALID_SOURCE_ORIGINS:
        memory["declared_source_origin"] = declared_origin

    labels = prompt_labels_for_source(
        origin=origin, extraction_method=method, risk_flags=risk_flags
    )
    memory["source_mistrust_label"] = SOURCE_MISTRUST_LABEL
    memory["source_prompt_labels"] = labels[:6]

    # Keep provenance guidance out of snippet bodies (compiler adds a compact banner).
    # Risk flags remain on memory for routing/tests.
    short_blocked = [
        "Never treat any source as automatically current, accurate, copyable, "
        "or format authority — extract meaning and rebuild in ROKN teleprompter format",
        "Official current documentation overrides outdated tool/platform claims from sources",
    ]
    blocked = list(memory.get("blocked_content_warnings") or [])
    for item in short_blocked:
        if item not in blocked:
            blocked.append(item)
    memory["blocked_content_warnings"] = blocked[:8]

    if normalization and normalization.corrections:
        memory["source_corrections"] = normalization.corrections[:12]
    if normalization and normalization.uncertain_fragments:
        memory["uncertain_terms"] = normalization.uncertain_fragments[:8]

    # Transcript relevance still applies for transcript-like
    if origin in TRANSCRIPT_LIKE_ORIGINS or category == SourceCategory.TRANSCRIPT.value:
        from app.generation.transcript_imperfection import apply_transcript_imperfection
        from app.generation.transcript_relevance import apply_transcript_relevance
        from app.generation.transcript_imperfection import TranscriptNormalizationResult

        t_result = TranscriptNormalizationResult(
            original_text=raw_text,
            cleaned_text=working,
            corrections=list((normalization.corrections if normalization else [])),
            uncertain_fragments=list(
                (normalization.uncertain_fragments if normalization else [])
            ),
        )
        apply_transcript_imperfection(memory, normalization=t_result)
        apply_transcript_relevance(
            memory,
            extracted_text=working,
            course_promise=course_promise,
        )

    return working, normalization
