"""Persistent Source Memory — process uploads once; inject snippets only.



No LangChain / vector DB. Uses SourceAnalysis chunks + heuristics.

Never send full PDF/extracted_text into generation prompts when memory exists.

Skip re-extraction when source_hash is unchanged.

"""



from __future__ import annotations



import hashlib

import re

from dataclasses import dataclass

from datetime import datetime, timezone

from typing import Any



from app.services.source_analysis import (

    MAX_KEY_POINTS,

    MAX_RELEVANT_CHUNKS,

    SHORT_SOURCE_MAX_CHARS,

    analyze_source_text,

    select_relevant_chunks,

)



# Soft cap per source in a generation prompt (facts/examples/terms/snippets).

MEMORY_SNIPPET_MAX_CHARS = 1400

# Rough token estimate (chars/4) for telemetry only.

CHARS_PER_TOKEN = 4

EXTRACTION_VERSION = "1.2"



_TERM_RE = re.compile(

    r"\b([A-Z]{2,}(?:/[A-Z]+)?|[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b"

)

_EXAMPLE_CUE = re.compile(

    r"(?:for example|e\.g\.|مثلاً|مثال|مثل)[^.。!؟\n]{8,160}",

    re.IGNORECASE,

)

_CONCEPT_CUE = re.compile(

    r"(?:concept of|principle of|تعريف|مفهوم|مفهوم ال)[^.。!؟\n]{6,120}",

    re.IGNORECASE,

)





@dataclass

class SourceMemoryTelemetry:

    source_tokens_used: int = 0

    web_searches_count: int = 0

    reused_source_memory_count: int = 0

    repeated_source_extraction_warnings: int = 0

    source_chars_injected: int = 0

    research_memory_reuses: int = 0



    def model_dump(self) -> dict[str, int]:

        return {

            "source_tokens_used": self.source_tokens_used,

            "web_searches_count": self.web_searches_count,

            "reused_source_memory_count": self.reused_source_memory_count,

            "repeated_source_extraction_warnings": self.repeated_source_extraction_warnings,

            "source_chars_injected": self.source_chars_injected,

            "research_memory_reuses": self.research_memory_reuses,

        }



    def note_chars(self, n: int) -> None:

        self.source_chars_injected += max(0, n)

        self.source_tokens_used += max(0, n) // CHARS_PER_TOKEN





def estimate_tokens(text: str) -> int:

    return max(0, len(text or "")) // CHARS_PER_TOKEN





def compute_source_hash(extracted_text: str) -> str:

    """Stable content hash — unchanged hash ⇒ do not re-extract."""

    payload = (extracted_text or "").encode("utf-8")

    return hashlib.sha256(payload).hexdigest()





def memory_matches_hash(memory: dict[str, Any] | None, extracted_text: str) -> bool:

    """True when the raw uploaded/pasted source text is unchanged."""

    if not memory:

        return False

    stored = (memory.get("raw_source_hash") or memory.get("source_hash") or "").strip()

    if not stored:

        return False

    return stored == compute_source_hash(extracted_text)





def extract_terminology(text: str, *, limit: int = 20) -> list[str]:

    found: list[str] = []

    seen: set[str] = set()

    for m in _TERM_RE.finditer(text or ""):

        term = m.group(1).strip()

        if len(term) < 2 or term.lower() in seen:

            continue

        if term.lower() in {"the", "this", "that", "when", "what", "with"}:

            continue

        seen.add(term.lower())

        found.append(term)

        if len(found) >= limit:

            break

    return found





def extract_example_snippets(text: str, *, limit: int = 6) -> list[str]:

    out: list[str] = []

    for m in _EXAMPLE_CUE.finditer(text or ""):

        snippet = " ".join(m.group(0).split())

        if snippet and snippet not in out:

            out.append(snippet)

        if len(out) >= limit:

            break

    return out





def extract_concepts(text: str, *, key_points: list[str] | None = None, limit: int = 10) -> list[str]:

    out: list[str] = []

    for m in _CONCEPT_CUE.finditer(text or ""):

        snippet = " ".join(m.group(0).split())

        if snippet and snippet not in out:

            out.append(snippet)

        if len(out) >= limit:

            break

    if len(out) < 3 and key_points:

        for kp in key_points:

            if kp not in out:

                out.append(kp)

            if len(out) >= limit:

                break

    return out[:limit]





def build_source_memory_payload(

    *,

    title: str,

    category: str,

    extracted_text: str,

    summary: str | None = None,

    chunks: list[dict[str, Any]] | None = None,

    key_points: list[str] | None = None,

    avoid_points: list[str] | None = None,

    priority: str = "medium",

    include_in_generation: bool = True,

    flow_profile: dict[str, Any] | None = None,

    old_course_lessons: list[str] | None = None,

    course_promise: dict[str, Any] | None = None,

    original_filename: str | None = None,

    mime_type: str | None = None,

    source_origin: str | None = None,

) -> dict[str, Any]:

    """One-time persistent memory dict stored on SourceAnalysis.source_memory_json."""

    raw_text = extracted_text or ""

    from app.generation.source_imperfection import (
        OCR_LIKE_ORIGINS,
        TRANSCRIPT_LIKE_ORIGINS,
        infer_expanded_source_origin,
        infer_extraction_method,
        normalize_ocr_text,
    )
    from app.generation.source_origin import (
        apply_source_origin,
        is_transcript_derived_memory,
    )
    from app.generation.transcript_imperfection import normalize_transcript_text

    pre_origin = None
    pre_method = None
    if raw_text.strip():
        pre_method = infer_extraction_method(
            original_filename=original_filename,
            mime_type=mime_type,
            text=raw_text,
        )
        pre_origin = infer_expanded_source_origin(
            raw_text,
            category=category,
            original_filename=original_filename,
            mime_type=mime_type,
            declared_origin=source_origin,
            title=title,
            extraction_method=pre_method,
        )

    text = raw_text
    transcript_normalization = None
    if raw_text.strip() and (
        (pre_origin or "") in OCR_LIKE_ORIGINS or pre_method == "ocr"
    ):
        ocr_norm = normalize_ocr_text(raw_text)
        text = ocr_norm.cleaned_text or text
    if raw_text.strip() and (
        category == "transcript"
        or (pre_origin or "") in TRANSCRIPT_LIKE_ORIGINS
    ):
        transcript_normalization = normalize_transcript_text(text)
        text = transcript_normalization.cleaned_text or text

    raw_source_hash = compute_source_hash(raw_text)
    normalized_text_hash = compute_source_hash(text)
    source_hash = raw_source_hash

    tokens_used = estimate_tokens(text)



    if summary is None or chunks is None or key_points is None:

        analysis = analyze_source_text(text, category)

        summary = summary or analysis.source_summary

        chunks = chunks or [

            {"index": c.index, "heading": c.heading, "text": c.text} for c in analysis.chunks

        ]

        key_points = key_points or analysis.key_points

        avoid_points = avoid_points if avoid_points is not None else analysis.avoid_points



    facts = list(key_points or [])[:MAX_KEY_POINTS]

    if len(facts) < 4 and chunks:

        for ch in chunks[:6]:

            lead = (ch.get("text") or "").strip().split("\n")[0][:200]

            if lead and lead not in facts:

                facts.append(lead)

            if len(facts) >= MAX_KEY_POINTS:

                break



    examples = extract_example_snippets(text)

    terms = extract_terminology(text)

    concepts = extract_concepts(text, key_points=key_points)



    memory: dict[str, Any] = {

        "source_hash": source_hash,

        "raw_source_hash": raw_source_hash,

        "normalized_text_hash": normalized_text_hash,

        "source_type": category,

        "source_priority": priority,

        "include_in_generation": include_in_generation,

        "title": title or "Source",

        "category": category,

        "summary": (summary or "")[:800],

        # Spec names + back-compat aliases

        "extracted_facts": facts,

        "facts": facts,

        "concepts": concepts,

        "terminology": terms,

        "useful_examples": examples,

        "examples": examples,

        "warnings_or_uncertainties": list(avoid_points or [])[:12],

        "chunk_count": len(chunks or []),

        "original_chars": len(raw_text),

        "processed_once": True,

        "extraction_version": EXTRACTION_VERSION,

        "extracted_at": datetime.now(timezone.utc).isoformat(),

        "tokens_used": tokens_used,

    }



    if category == "flow_reference":

        if flow_profile is None and text:

            try:

                from app.generation.prompt_compiler import build_flow_profile



                flow_profile = build_flow_profile(text)

            except Exception:

                flow_profile = None

        if flow_profile:

            memory["flow_profile"] = flow_profile



    text, transcript_normalization = apply_source_origin(
        memory,
        text=raw_text,
        category=category,
        original_filename=original_filename,
        mime_type=mime_type,
        declared_origin=source_origin,
        title=title,
        course_promise=course_promise,
        cleaned_text=text,
        transcript_normalization=transcript_normalization,
    )

    from app.generation.mixed_draft_memory import (
        build_mixed_draft_memory,
        is_mixed_quality_draft_category,
    )

    if is_mixed_quality_draft_category(category):

        md = build_mixed_draft_memory(

            source_hash=source_hash,

            text=text,

            title=title or "Mixed-quality AI course draft",

            course_promise=course_promise,

        )

        memory["mixed_draft_memory"] = md

        memory["candidate_only"] = True

        memory["not_quality_reference"] = True

        # Topic hints only — never the final course map.

        memory["map_hints_not_authority"] = list(md.get("map_hints_not_authority") or [])

        memory["useful_candidates"] = list(md.get("useful_candidates") or [])

        # Prefer candidate bags over raw fact dumps for this category.

        cand_facts = list(

            (md.get("core_candidates") or [])

            + (md.get("supporting_candidates") or [])

            + (md.get("useful_candidates") or [])

        )[:MAX_KEY_POINTS]

        if cand_facts:

            memory["extracted_facts"] = cand_facts

            memory["facts"] = cand_facts

        warn = list(memory.get("warnings_or_uncertainties") or [])

        for w in md.get("creator_warnings") or []:

            if w not in warn:

                warn.append(w)

        memory["warnings_or_uncertainties"] = warn[:16]

        if category == "old_course":

            lessons = list(old_course_lessons or [])

            if not lessons and chunks:

                lessons = [

                    (c.get("heading") or f"Lesson {i+1}")

                    for i, c in enumerate(chunks[:20])

                ]

            memory["old_course_lessons"] = lessons



    from app.generation.source_distillation import apply_source_distillation

    target_market = "egypt"
    if course_promise and isinstance(course_promise, dict):
        target_market = str(course_promise.get("target_market") or target_market)

    if not memory.get("transcript_colloquial_only"):
        apply_source_distillation(memory, extracted_text=text, target_market=target_market)
        if is_transcript_derived_memory(memory):
            from app.generation.transcript_relevance import scrub_transcript_delivery_artifacts

            scrub_transcript_delivery_artifacts(memory)

    from app.generation.source_usefulness import apply_source_usefulness

    apply_source_usefulness(memory)

    return memory





def format_memory_snippet(

    memory: dict[str, Any],

    *,

    query_text: str = "",

    chunks: list[dict[str, Any]] | None = None,

    max_chars: int = MEMORY_SNIPPET_MAX_CHARS,

) -> str:

    """Compact prompt material: facts / examples / terms / relevant snippets only."""

    from app.generation.mixed_draft_memory import (

        format_mixed_draft_snippet,

        is_mixed_quality_draft_category,

    )

    from app.generation.transcript_relevance import (
        format_transcript_colloquial_snippet,
        is_transcript_colloquial_only,
    )
    from app.generation.source_usefulness import (
        format_low_signal_snippet,
        should_use_brief_candidates,
    )

    if is_transcript_colloquial_only(memory):
        return format_transcript_colloquial_snippet(memory, max_chars=max_chars)

    if should_use_brief_candidates(memory):
        from app.generation.source_usefulness import LOW_SIGNAL_BRIEF_MAX_CHARS

        brief_cap = min(max_chars, LOW_SIGNAL_BRIEF_MAX_CHARS)
        return format_low_signal_snippet(memory, max_chars=brief_cap)

    if is_mixed_quality_draft_category(str(memory.get("source_type") or memory.get("category") or "")):

        from app.generation.source_distillation import format_distilled_memory_snippet

        base = format_mixed_draft_snippet(memory, max_chars=max_chars)
        if memory.get("distillation_version"):
            distilled = format_distilled_memory_snippet(
                memory, query_text=query_text, chunks=chunks, max_chars=max_chars
            )
            combined = f"{distilled}\n\n{base}"
            return combined[:max_chars] if len(combined) > max_chars else combined
        return base

    if memory.get("distillation_version"):
        from app.generation.source_distillation import format_distilled_memory_snippet

        return format_distilled_memory_snippet(
            memory, query_text=query_text, chunks=chunks, max_chars=max_chars
        )



    parts: list[str] = []

    title = memory.get("title") or "Source"

    summary = (memory.get("summary") or "").strip()

    if summary:

        parts.append(f"[Source memory: {title}]\nSummary: {summary}")



    facts = list(memory.get("extracted_facts") or memory.get("facts") or [])

    examples = list(memory.get("useful_examples") or memory.get("examples") or [])

    terms = list(memory.get("terminology") or [])

    concepts = list(memory.get("concepts") or [])

    warnings = list(memory.get("warnings_or_uncertainties") or [])



    if query_text:

        q = set(re.findall(r"[\w\u0600-\u06FF]{3,}", query_text.lower()))

        if q:

            facts = sorted(

                facts,

                key=lambda f: -len(q & set(re.findall(r"[\w\u0600-\u06FF]{3,}", f.lower()))),

            )

            examples = sorted(

                examples,

                key=lambda e: -len(q & set(re.findall(r"[\w\u0600-\u06FF]{3,}", e.lower()))),

            )



    if facts:

        parts.append("Facts:\n- " + "\n- ".join(facts[:6]))

    if concepts:

        parts.append("Concepts:\n- " + "\n- ".join(concepts[:5]))

    if examples:

        parts.append("Examples:\n- " + "\n- ".join(examples[:4]))

    if terms:

        parts.append("Terminology: " + ", ".join(terms[:12]))

    if warnings:

        parts.append("Warnings:\n- " + "\n- ".join(warnings[:4]))



    if memory.get("flow_profile") and memory.get("source_type") == "flow_reference":

        parts.append(
            "Natural Colloquial Calibration (language naturalness only — not "
            "hooks/structure/facts/teaching):\n"
            + str(memory["flow_profile"])[:400]
        )

    if memory.get("old_course_lessons") and memory.get("source_type") == "old_course":

        parts.append(

            "Prior course lessons (structure only):\n- "

            + "\n- ".join(str(x) for x in memory["old_course_lessons"][:8])

        )



    if chunks and query_text:

        relevant = select_relevant_chunks(chunks, query_text, max_chunks=MAX_RELEVANT_CHUNKS)

        if relevant:

            body = "\n\n".join(

                f"{c.get('heading') or 'Chunk'}: {(c.get('text') or '')[:400]}"

                for c in relevant

            )

            parts.append("Relevant snippets:\n" + body)

    elif chunks and not query_text:

        leads = []

        for c in chunks[:2]:

            t = (c.get("text") or "")[:350]

            if t:

                leads.append(t)

        if leads:

            parts.append("Key snippets:\n" + "\n\n".join(leads))



    text = "\n\n".join(parts).strip()

    if len(text) > max_chars:

        return text[: max_chars - 1].rstrip() + "…"

    return text





def compiler_text_from_memory(

    *,

    memory: dict[str, Any] | None,

    summary: str | None,

    chunks: list[dict[str, Any]] | None,

    fallback_text: str,

    query_text: str,

    category: str,

) -> str:

    """What SourceForCompiler.text should hold — never full long PDF."""

    if category == "user_notes":

        return fallback_text or ""



    from app.generation.mixed_draft_memory import (

        format_mixed_draft_snippet,

        is_mixed_quality_draft_category,

    )

    from app.generation.transcript_relevance import (
        format_transcript_colloquial_snippet,
        is_transcript_colloquial_only,
    )

    if category == "transcript" and memory and is_transcript_colloquial_only(memory):
        return format_transcript_colloquial_snippet(memory)

    if is_mixed_quality_draft_category(category):

        # Never resend the full mixed-quality draft into lesson prompts.

        if memory and (memory.get("mixed_draft_memory") or memory.get("kind") == "mixed_draft_memory"):

            return format_mixed_draft_snippet(memory)

        if memory:

            return format_memory_snippet(memory, query_text=query_text, chunks=None)

        return format_mixed_draft_snippet(

            {"prompt_label": "mixed quality draft", "useful_candidates": [], "creator_warnings": []}

        )



    if memory:

        original = int(memory.get("original_chars") or 0)

        if original and original <= SHORT_SOURCE_MAX_CHARS and (fallback_text or ""):

            return fallback_text

        if not original and len(fallback_text or "") <= SHORT_SOURCE_MAX_CHARS:

            return fallback_text or ""

        return format_memory_snippet(memory, query_text=query_text, chunks=chunks)



    text = fallback_text or ""

    if len(text) <= SHORT_SOURCE_MAX_CHARS:

        return text

    if chunks and query_text:

        relevant = select_relevant_chunks(chunks, query_text)

        if relevant:

            return "\n\n".join((c.get("text") or "")[:500] for c in relevant)[

                :MEMORY_SNIPPET_MAX_CHARS

            ]

    if summary:

        return summary

    return text[:SHORT_SOURCE_MAX_CHARS]





@dataclass

class WebCacheStats:

    searches_performed: int = 0

    cache_hits: int = 0

    gaps_skipped_cached: int = 0





def normalize_gap_key(topic: str) -> str:

    return re.sub(r"\s+", " ", (topic or "").strip().lower())


