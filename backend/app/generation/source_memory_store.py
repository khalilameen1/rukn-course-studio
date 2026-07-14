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
EXTRACTION_VERSION = "1.1"

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
    if not memory:
        return False
    stored = (memory.get("source_hash") or "").strip()
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
) -> dict[str, Any]:
    """One-time persistent memory dict stored on SourceAnalysis.source_memory_json."""
    text = extracted_text or ""
    source_hash = compute_source_hash(text)
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
        "original_chars": len(text),
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

    if category == "old_course":
        lessons = list(old_course_lessons or [])
        if not lessons and chunks:
            lessons = [
                (c.get("heading") or f"Lesson {i+1}")
                for i, c in enumerate(chunks[:20])
            ]
        memory["old_course_lessons"] = lessons

    return memory


def format_memory_snippet(
    memory: dict[str, Any],
    *,
    query_text: str = "",
    chunks: list[dict[str, Any]] | None = None,
    max_chars: int = MEMORY_SNIPPET_MAX_CHARS,
) -> str:
    """Compact prompt material: facts / examples / terms / relevant snippets only."""
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
        parts.append("Flow profile (style only — do not copy wording):\n" + str(memory["flow_profile"])[:400])
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
