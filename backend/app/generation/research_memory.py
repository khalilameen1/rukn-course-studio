"""Research Need + Research Memory — one stored answer per distinct information need.

Caches per normalized question with freshness policies. No LangChain / vector DB.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.generation.source_memory_store import normalize_gap_key
from app.generation.trusted_sources import SourceQualityTier, classify_source

# Freshness windows (days). platform_current refreshes more often.
FRESHNESS_DAYS = {
    "evergreen": 180,
    "platform_current": 14,
    "short_ttl": 7,
    "low_confidence": 3,
}


class ResearchNeed(BaseModel):
    """Compact need created before every web search."""

    question: str
    why_needed: str
    course_id: int | None = None
    module_id: str | None = None
    lesson_id: str | None = None
    required_source_quality: str = "strong"  # highest | strong | conditional
    acceptable_source_types: list[str] = Field(
        default_factory=lambda: [
            "official_docs",
            "university",
            "academic",
            "textbook",
            "course_materials",
            "industry_report",
        ]
    )
    existing_memory_checked: bool = True


class ResearchMemoryEntry(BaseModel):
    """One cached answer for a distinct information need."""

    normalized_question: str
    related_claim: str = ""
    source_urls: list[str] = Field(default_factory=list)
    source_titles: list[str] = Field(default_factory=list)
    publishers: list[str] = Field(default_factory=list)
    source_quality: str = SourceQualityTier.CONDITIONAL.value
    extracted_answer: str = ""
    extracted_facts: list[str] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)
    retrieved_at: str = ""
    freshness_policy: str = "evergreen"
    used_in_lessons: list[str] = Field(default_factory=list)
    tokens_used: int = 0
    low_confidence: bool = False
    research_need: dict[str, Any] | None = None


class ResearchMemoryStore(BaseModel):
    """Persisted on Course.web_source_memory_json.research_entries (internal)."""

    entries: list[ResearchMemoryEntry] = Field(default_factory=list)
    needs_logged: list[dict[str, Any]] = Field(default_factory=list)

    def find(self, question: str) -> ResearchMemoryEntry | None:
        key = normalize_research_question(question)
        for entry in self.entries:
            if entry.normalized_question == key:
                return entry
            # Soft equivalence: key contained in stored or vice versa.
            if key and (
                key in entry.normalized_question or entry.normalized_question in key
            ):
                return entry
        return None


def normalize_research_question(question: str) -> str:
    """Normalize for cache identity (distinct information need)."""
    text = (question or "").strip().lower()
    text = re.sub(r"[^\w\u0600-\u06FF\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def infer_freshness_policy(question: str, *, why_needed: str = "") -> str:
    blob = f"{question} {why_needed}".lower()
    if re.search(
        r"\b(meta ads|facebook ads|tiktok ads|instagram|algorithm|"
        r"platform|policy|pricing|ui|dashboard|api version|"
        r"current|202[4-9]|update[ds]?)\b",
        blob,
    ):
        return "platform_current"
    if re.search(r"\b(price|rate|fee|deadline|temporary)\b", blob):
        return "short_ttl"
    return "evergreen"


def _parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def is_stale(
    entry: ResearchMemoryEntry,
    *,
    now: datetime | None = None,
    require_stronger: bool = False,
) -> bool:
    """True when memory should be refreshed (not 'search once globally')."""
    if require_stronger and entry.low_confidence:
        return True
    policy = entry.freshness_policy or "evergreen"
    if entry.low_confidence:
        policy = "low_confidence"
    days = FRESHNESS_DAYS.get(policy, FRESHNESS_DAYS["evergreen"])
    retrieved = _parse_iso(entry.retrieved_at)
    if retrieved is None:
        return False
    now = now or datetime.now(timezone.utc)
    if retrieved.tzinfo is None:
        retrieved = retrieved.replace(tzinfo=timezone.utc)
    age = (now - retrieved).total_seconds() / 86400.0
    return age > days


def should_reuse_research(
    store: ResearchMemoryStore | dict | None,
    question: str,
    *,
    require_stronger: bool = False,
) -> tuple[bool, ResearchMemoryEntry | None, str]:
    """Return (reuse, entry, reason)."""
    if isinstance(store, dict):
        store = ResearchMemoryStore.model_validate(store) if store else ResearchMemoryStore()
    store = store or ResearchMemoryStore()
    entry = store.find(question)
    if entry is None:
        return False, None, "no_memory"
    if is_stale(entry, require_stronger=require_stronger):
        return False, entry, "stale_or_low_confidence"
    return True, entry, "reuse"


def build_research_need(
    *,
    question: str,
    why_needed: str,
    course_id: int | None = None,
    module_id: str | None = None,
    lesson_id: str | None = None,
    existing_memory_checked: bool = True,
    required_source_quality: str = "strong",
) -> ResearchNeed:
    return ResearchNeed(
        question=question.strip(),
        why_needed=why_needed,
        course_id=course_id,
        module_id=module_id,
        lesson_id=lesson_id,
        required_source_quality=required_source_quality,
        existing_memory_checked=existing_memory_checked,
    )


def entry_from_web_facts(
    *,
    need: ResearchNeed,
    facts: list[Any],
    tokens_used: int = 0,
) -> ResearchMemoryEntry:
    """Build a Research Memory entry from accepted WebFact-like objects."""
    titles: list[str] = []
    urls: list[str] = []
    pubs: list[str] = []
    answer_parts: list[str] = []
    extracted: list[str] = []
    best_quality = SourceQualityTier.CONDITIONAL.value
    uncertainty: list[str] = []

    for fact in facts:
        title = getattr(fact, "title", "") or ""
        summary = getattr(fact, "summary", "") or ""
        url = getattr(fact, "url", "") or ""
        verdict = classify_source(title=title, url=url, summary=summary)
        if not verdict.allowed_as_fact:
            uncertainty.append(f"rejected:{title[:80]}")
            continue
        titles.append(title)
        if url:
            urls.append(url)
        if verdict.publisher:
            pubs.append(verdict.publisher)
        answer_parts.append(summary)
        extracted.append(summary[:240])
        if verdict.tier.value in (
            SourceQualityTier.HIGHEST.value,
            SourceQualityTier.STRONG.value,
        ):
            best_quality = verdict.tier.value

    policy = infer_freshness_policy(need.question, why_needed=need.why_needed)
    low_conf = not extracted or best_quality == SourceQualityTier.CONDITIONAL.value
    return ResearchMemoryEntry(
        normalized_question=normalize_research_question(need.question),
        related_claim=need.why_needed,
        source_urls=urls,
        source_titles=titles,
        publishers=pubs,
        source_quality=best_quality,
        extracted_answer=" ".join(answer_parts)[:1200],
        extracted_facts=extracted[:8],
        uncertainty_notes=uncertainty[:6],
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        freshness_policy=policy,
        tokens_used=tokens_used,
        low_confidence=low_conf,
        research_need=need.model_dump(mode="json"),
    )


def upsert_research_entry(
    store: ResearchMemoryStore, entry: ResearchMemoryEntry
) -> ResearchMemoryStore:
    key = entry.normalized_question
    kept = [e for e in store.entries if e.normalized_question != key]
    kept.append(entry)
    store.entries = kept
    return store
