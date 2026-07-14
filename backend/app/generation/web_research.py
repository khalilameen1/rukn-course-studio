"""Autonomous web research for factual/practical gap fill (internal only).

Default mode: `autonomous_gap_fill` — research missing facts without asking
the user. Never emit citations, evidence notes, or "needs confirmation" into
`script_text` / DOCX. Evidence Ledger + Web Source Memory are internal.

Short-lived facts (exact prices, UI positions, temporary stats) must not
become the spoken course spine — phrase evergreen / teach how to verify
(see app/generation/market_evergreen.py).

No LangChain / vector DB / RAG frameworks. Stdlib HTTP + optional fake backend.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from app.models.enums import WebResearchMode

PROGRESS_READING_UPLOADS = "Building course map"
PROGRESS_FILLING_FACTS = "Building course map"
PROGRESS_BUILDING_MEMORY = "Building course map"

# Forbidden in spoken transcript / DOCX (research & confirmation leaks).
RESEARCH_LEAK_SUBSTRINGS: tuple[str, ...] = (
    "needs confirmation",
    "needs_confirmation",
    "needs review",
    "needs_review",
    "evidence ledger",
    "evidence_ledger",
    "web source memory",
    "source memory",
    "according to source",
    "according to wikipedia",
    "http://",
    "https://",
    "www.",
    "[citation",
    "citation needed",
    "research note",
    "ask the user",
    "confirm with the user",
)

SENSITIVE_DOMAIN_CUES = re.compile(
    r"\b(religio|quran|hadith|sharia|فتوى|قانون|legal advice|medical|"
    r"تشخيص|علاج|دواء|invest|financial advice|ROI guaranteed|"
    r"diagnos|prescription|clinical trial)\b",
    re.IGNORECASE,
)

# Treat as low-trust / skip for sensitive or unsupported synthetic claims.
WEAK_CLAIM_CUES = re.compile(
    r"(always works|guaranteed|100%|proven forever|never fails|"
    r"secret that doctors|miracle|instant wealth)",
    re.IGNORECASE,
)


class EvidenceEntry(BaseModel):
    """One internal evidence row — never user-facing / never DOCX."""

    claim_or_gap: str
    support_status: str = "unsupported"  # supported | weak | unsupported | omitted
    source_kind: str = ""  # upload | web | none
    source_title: str = ""
    source_url: str = ""
    note: str = ""
    risk_flag: str = ""  # e.g. sensitive_domain, weak_evidence
    used_in_script: bool = False


class EvidenceLedger(BaseModel):
    entries: list[EvidenceEntry] = Field(default_factory=list)
    research_mode: str = WebResearchMode.AUTONOMOUS_GAP_FILL.value
    research_failed: bool = False
    research_error: str = ""


class SourceMemoryItem(BaseModel):
    title: str
    kind: str  # upload | web
    summary: str
    url: str = ""
    authority: str = "standard"  # standard | high | sensitive_restricted


class SourceMemory(BaseModel):
    """Uploaded Source Memory (compact) — internal."""

    items: list[SourceMemoryItem] = Field(default_factory=list)


class WebSourceMemory(BaseModel):
    """Web Source Memory — internal only.

    Holds compact web items plus Research Memory entries (one answer per
    distinct information need). Never dumped into DOCX / script_text.
    """

    items: list[SourceMemoryItem] = Field(default_factory=list)
    gaps_researched: list[str] = Field(default_factory=list)
    research_entries: list[dict] = Field(default_factory=list)
    needs_logged: list[dict] = Field(default_factory=list)


@dataclass
class ResearchGap:
    topic: str
    reason: str
    sensitive: bool = False


@dataclass
class WebFact:
    title: str
    summary: str
    url: str = ""
    authority: str = "standard"
    query: str = ""


def is_sensitive_domain(text: str) -> bool:
    return bool(SENSITIVE_DOMAIN_CUES.search(text or ""))


def find_research_leaks(text: str) -> list[str]:
    lowered = (text or "").lower()
    return [s for s in RESEARCH_LEAK_SUBSTRINGS if s in lowered]


def strip_research_leaks_from_script(script_text: str) -> str:
    """Remove accidental research/confirmation lines from spoken script."""
    if not script_text:
        return script_text
    text = script_text
    for leak in RESEARCH_LEAK_SUBSTRINGS:
        text = re.sub(re.escape(leak), "", text, flags=re.IGNORECASE)
    lines = []
    for line in text.splitlines():
        low = line.lower()
        if any(leak in low for leak in RESEARCH_LEAK_SUBSTRINGS):
            continue
        if re.search(r"https?://\S+|www\.\S+", line):
            line = re.sub(r"https?://\S+|www\.\S+", "", line).strip()
            if not line:
                continue
        line = re.sub(r"\s{2,}", " ", line).strip(" ,،")
        if line:
            lines.append(line)
    return "\n".join(lines).strip()


def build_upload_source_memory(
    *,
    course_title: str,
    audience: str,
    outcome: str,
    uploaded_texts: list[tuple[str, str]] | None = None,
    memory_items: list[SourceMemoryItem] | None = None,
) -> SourceMemory:
    """Prefer compact Source Memory items; do not slice full PDFs into prompts."""
    items: list[SourceMemoryItem] = list(memory_items or [])
    if not items:
        for title, text in uploaded_texts or []:
            snippet = (text or "").strip()
            if not snippet:
                continue
            # Cap hard — this path is legacy fallback only.
            summary = snippet[:500] + ("…" if len(snippet) > 500 else "")
            items.append(
                SourceMemoryItem(
                    title=title or "Uploaded source",
                    kind="upload",
                    summary=summary,
                    authority="high" if is_sensitive_domain(snippet) else "standard",
                )
            )
    if not items:
        items.append(
            SourceMemoryItem(
                title=f"Brief: {course_title}",
                kind="upload",
                summary=f"Audience: {audience}. Outcome: {outcome}.",
                authority="standard",
            )
        )
    return SourceMemory(items=items)


def identify_factual_gaps(
    *,
    course_title: str,
    audience: str,
    outcome: str,
    special_notes: str | None,
    upload_memory: SourceMemory,
    max_gaps: int = 5,
) -> list[ResearchGap]:
    """Heuristic gaps when uploads are thin relative to the brief."""
    blob = " ".join(item.summary for item in upload_memory.items)
    brief_bits = [
        w
        for w in re.findall(
            r"[\w\u0600-\u06FF]{4,}",
            f"{course_title} {audience} {outcome} {special_notes or ''}",
        )
        if len(w) >= 4
    ]
    gaps: list[ResearchGap] = []
    sensitive = is_sensitive_domain(
        f"{course_title} {outcome} {special_notes or ''} {blob}"
    )

    # If uploads are very short, treat core outcome terms as gaps.
    thin = len(blob) < 400
    seen: set[str] = set()
    for term in brief_bits:
        key = term.lower()
        if key in seen:
            continue
        if not thin and key in blob.lower():
            continue
        seen.add(key)
        gaps.append(
            ResearchGap(
                topic=term,
                reason="missing_practical_or_factual_coverage",
                sensitive=sensitive or is_sensitive_domain(term),
            )
        )
        if len(gaps) >= max_gaps:
            break

    if not gaps and thin:
        gaps.append(
            ResearchGap(
                topic=course_title or outcome or "course topic",
                reason="insufficient_uploaded_sources",
                sensitive=sensitive,
            )
        )
    return gaps


class ResearchBackend:
    def fetch_facts(self, query: str, *, sensitive: bool) -> list[WebFact]:
        raise NotImplementedError


class FakeResearchBackend(ResearchBackend):
    """Deterministic trusted snippets for tests / offline / fake AI runs."""

    def fetch_facts(self, query: str, *, sensitive: bool) -> list[WebFact]:
        if WEAK_CLAIM_CUES.search(query):
            return []
        authority = "high" if sensitive else "standard"
        return [
            WebFact(
                title=f"Trusted overview: {query}",
                summary=(
                    f"Practical, widely accepted facts about {query} for serious learners. "
                    "Prefer conditions and realistic limits over absolute promises."
                ),
                url="",
                authority=authority,
                query=query,
            )
        ]


class WikipediaResearchBackend(ResearchBackend):
    """Stdlib Wikipedia search + extract. No API key. Best-effort."""

    USER_AGENT = "RuknCourseStudio/1.0 (autonomous_gap_fill; educational)"

    def fetch_facts(self, query: str, *, sensitive: bool) -> list[WebFact]:
        try:
            search_url = (
                "https://en.wikipedia.org/w/api.php?"
                + urllib.parse.urlencode(
                    {
                        "action": "query",
                        "list": "search",
                        "srsearch": query,
                        "srlimit": 2,
                        "format": "json",
                    }
                )
            )
            raw = self._get(search_url)
            data = json.loads(raw)
            hits = (data.get("query") or {}).get("search") or []
            if not hits:
                return []
            title = hits[0].get("title") or query
            extract_url = (
                "https://en.wikipedia.org/w/api.php?"
                + urllib.parse.urlencode(
                    {
                        "action": "query",
                        "prop": "extracts",
                        "exintro": 1,
                        "explaintext": 1,
                        "titles": title,
                        "format": "json",
                    }
                )
            )
            raw2 = self._get(extract_url)
            data2 = json.loads(raw2)
            pages = (data2.get("query") or {}).get("pages") or {}
            extract = ""
            for page in pages.values():
                extract = (page.get("extract") or "").strip()
                if extract:
                    break
            if not extract:
                return []
            if sensitive and WEAK_CLAIM_CUES.search(extract):
                return []
            summary = extract[:900] + ("…" if len(extract) > 900 else "")
            page_url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
            return [
                WebFact(
                    title=title,
                    summary=summary,
                    url=page_url,
                    authority="high" if sensitive else "standard",
                    query=query,
                )
            ]
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, OSError):
            return []

    # Hard allowlist — Wikipedia API only (no arbitrary user-supplied hosts).
    _ALLOWED_HOSTS = frozenset({"en.wikipedia.org"})

    def _get(self, url: str) -> str:
        from app.security.url_safety import UnsafeURLError, assert_safe_public_https_url

        try:
            safe_url = assert_safe_public_https_url(
                url, allowed_hostnames=self._ALLOWED_HOSTS
            )
        except UnsafeURLError as exc:
            raise urllib.error.URLError(str(exc)) from exc

        req = urllib.request.Request(safe_url, headers={"User-Agent": self.USER_AGENT})

        class _SafeRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
                try:
                    assert_safe_public_https_url(
                        newurl, allowed_hostnames=WikipediaResearchBackend._ALLOWED_HOSTS
                    )
                except UnsafeURLError as exc:
                    raise urllib.error.HTTPError(
                        newurl, 403, f"Blocked redirect: {exc}", headers, fp
                    ) from exc
                return super().redirect_request(req, fp, code, msg, headers, newurl)

        opener = urllib.request.build_opener(_SafeRedirect)
        with opener.open(req, timeout=8) as resp:
            return resp.read().decode("utf-8", errors="replace")


def get_research_backend(prefer_fake: bool = False) -> ResearchBackend:
    if prefer_fake:
        return FakeResearchBackend()
    return WikipediaResearchBackend()


@dataclass
class AutonomousResearchResult:
    upload_memory: SourceMemory
    web_memory: WebSourceMemory
    ledger: EvidenceLedger
    web_excerpts_text: list[tuple[str, str]] = field(default_factory=list)
    # (title, summary) usable as scientific_reference-style prompt material
    web_searches_count: int = 0
    web_cache_hits: int = 0


def run_autonomous_gap_fill(
    *,
    course_title: str,
    audience: str,
    outcome: str,
    special_notes: str | None,
    uploaded_texts: list[tuple[str, str]] | None = None,
    memory_items: list[SourceMemoryItem] | None = None,
    mode: WebResearchMode,
    backend: ResearchBackend | None = None,
    prefer_fake: bool = False,
    cached_web_memory: WebSourceMemory | dict | None = None,
    course_id: int | None = None,
) -> AutonomousResearchResult:
    """Inspect uploads, research gaps if enabled, build internal memories/ledger.

    Never asks the user. Reuses Research Memory for the same distinct
    information need. Refreshes only when stale / low-confidence / platform-
    current freshness requires it. On research failure, continues with uploads.
    """
    from app.generation.research_memory import (
        ResearchMemoryStore,
        build_research_need,
        entry_from_web_facts,
        should_reuse_research,
        upsert_research_entry,
    )
    from app.generation.source_memory_store import normalize_gap_key
    from app.generation.trusted_sources import ScoredWebHit, filter_factual_hits

    upload_memory = build_upload_source_memory(
        course_title=course_title,
        audience=audience,
        outcome=outcome,
        uploaded_texts=uploaded_texts,
        memory_items=memory_items,
    )
    if isinstance(cached_web_memory, WebSourceMemory):
        web_memory = cached_web_memory.model_copy(deep=True)
    elif isinstance(cached_web_memory, dict) and cached_web_memory:
        web_memory = WebSourceMemory.model_validate(cached_web_memory)
    else:
        web_memory = WebSourceMemory()

    research_store = ResearchMemoryStore()
    # Load persisted research entries from web memory blob.
    if web_memory.research_entries:
        research_store = ResearchMemoryStore.model_validate(
            {
                "entries": web_memory.research_entries,
                "needs_logged": web_memory.needs_logged or [],
            }
        )

    ledger = EvidenceLedger(research_mode=mode.value)
    searches = 0
    cache_hits = 0
    cached_keys = {normalize_gap_key(g) for g in web_memory.gaps_researched}
    for item in web_memory.items:
        cached_keys.add(normalize_gap_key(item.title))

    if mode == WebResearchMode.DISABLED:
        return AutonomousResearchResult(
            upload_memory=upload_memory,
            web_memory=web_memory,
            ledger=ledger,
            web_searches_count=0,
            web_cache_hits=0,
        )

    gaps = identify_factual_gaps(
        course_title=course_title,
        audience=audience,
        outcome=outcome,
        special_notes=special_notes,
        upload_memory=upload_memory,
    )
    backend = backend or get_research_backend(prefer_fake=prefer_fake)
    excerpts: list[tuple[str, str]] = [(i.title, i.summary) for i in web_memory.items]
    # Seed excerpts from research memory answers already cached.
    for entry in research_store.entries:
        if entry.extracted_answer:
            excerpts.append(
                (
                    entry.source_titles[0] if entry.source_titles else entry.normalized_question,
                    entry.extracted_answer,
                )
            )

    for gap in gaps:
        need = build_research_need(
            question=gap.topic,
            why_needed=gap.reason,
            course_id=course_id,
            existing_memory_checked=True,
            required_source_quality="highest" if gap.sensitive else "strong",
        )
        web_memory.needs_logged.append(need.model_dump(mode="json"))

        reuse, cached_entry, reuse_reason = should_reuse_research(
            research_store,
            gap.topic,
            require_stronger=gap.sensitive,
        )
        if reuse and cached_entry is not None:
            cache_hits += 1
            if cached_entry.extracted_answer:
                excerpts.append(
                    (
                        cached_entry.source_titles[0]
                        if cached_entry.source_titles
                        else gap.topic,
                        cached_entry.extracted_answer,
                    )
                )
            ledger.entries.append(
                EvidenceEntry(
                    claim_or_gap=gap.topic,
                    support_status="supported",
                    source_kind="web",
                    source_title=(
                        cached_entry.source_titles[0] if cached_entry.source_titles else ""
                    ),
                    note=f"Research Memory reuse ({reuse_reason}) — internal only.",
                    risk_flag="sensitive_domain" if gap.sensitive else "",
                    used_in_script=False,
                )
            )
            continue

        key = normalize_gap_key(gap.topic)
        # Legacy gaps_researched list — still skip identical topics unless stale refresh.
        if (
            reuse_reason not in {"stale_or_low_confidence"}
            and (key in cached_keys
            or any(
                key in normalize_gap_key(g) or normalize_gap_key(g) in key
                for g in web_memory.gaps_researched
            ))
        ):
            cache_hits += 1
            continue

        facts = backend.fetch_facts(gap.topic, sensitive=gap.sensitive)
        searches += 1

        # Filter to trusted factual sources only.
        scored = [
            ScoredWebHit(
                title=f.title,
                summary=f.summary,
                url=f.url,
                publisher="",
            )
            for f in facts
        ]
        accepted = filter_factual_hits(scored)
        if gap.sensitive:
            accepted = [h for h in accepted if h.tier.value in {"highest", "strong"}]

        accepted_facts = [
            WebFact(
                title=h.title,
                summary=h.summary,
                url=h.url,
                authority="high" if h.tier.value == "highest" else "standard",
                query=gap.topic,
            )
            for h in accepted
        ]

        if not accepted_facts:
            ledger.entries.append(
                EvidenceEntry(
                    claim_or_gap=gap.topic,
                    support_status="omitted",
                    source_kind="none",
                    note="No sufficiently trusted web fact found; omit or narrow.",
                    risk_flag="sensitive_domain" if gap.sensitive else "unsupported",
                )
            )
            web_memory.gaps_researched.append(gap.topic)
            cached_keys.add(key)
            continue

        entry = entry_from_web_facts(need=need, facts=accepted_facts, tokens_used=0)
        research_store = upsert_research_entry(research_store, entry)

        for fact in accepted_facts:
            web_memory.items.append(
                SourceMemoryItem(
                    title=fact.title,
                    kind="web",
                    summary=fact.summary,
                    url=fact.url,
                    authority=fact.authority,
                )
            )
            excerpts.append((fact.title, fact.summary))
            ledger.entries.append(
                EvidenceEntry(
                    claim_or_gap=gap.topic,
                    support_status="supported",
                    source_kind="web",
                    source_title=fact.title,
                    source_url=fact.url,
                    note="Autonomous gap fill — trusted sources only; internal.",
                    risk_flag="sensitive_domain" if gap.sensitive else "",
                    used_in_script=False,
                )
            )
        web_memory.gaps_researched.append(gap.topic)
        cached_keys.add(key)

    web_memory.research_entries = [
        e.model_dump(mode="json") for e in research_store.entries
    ]
    # Cap needs log growth (cost hygiene / storage).
    logged = list(research_store.needs_logged) + list(web_memory.needs_logged)
    web_memory.needs_logged = logged[-50:]

    return AutonomousResearchResult(
        upload_memory=upload_memory,
        web_memory=web_memory,
        ledger=ledger,
        web_excerpts_text=excerpts,
        web_searches_count=searches,
        web_cache_hits=cache_hits,
    )


def mark_research_failure(ledger: EvidenceLedger, error: str) -> EvidenceLedger:
    ledger.research_failed = True
    ledger.research_error = (error or "")[:500]
    return ledger
