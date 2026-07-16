"""General Source Distillation Gate — internal only.

All course sources are raw material, not final authority and not a format/style
model. Distillation runs once at memory build; prompts receive labeled snippets
only — never full sources as equal authority.
"""

from __future__ import annotations

import re
from typing import Any

DISTILLATION_VERSION = "1.0"
DISTILLED_LABEL = "DISTILLED RAW MATERIAL"
NOT_AUTHORITY_NOTE = (
    "not final authority; not a style/format model; extract and rebuild in ROKN"
)

_FILLER_PHRASES = (
    "it is important to note",
    "furthermore",
    "moreover",
    "in conclusion",
    "as mentioned above",
    "at the end of the day",
    "من المهم أن نلاحظ",
    "في الختام",
    "باختصار شديد",
    "لا شك أن",
)

_ACADEMIC_CUES = re.compile(
    r"(?i)\b("
    r"hypothesis|peer[- ]reviewed|literature review|methodology|"
    r"theoretical framework|etymology|according to the study|"
    r"research demonstrates|scholarly|dissertation|bibliography"
    r")\b"
)

_US_MARKET_CUES = re.compile(
    r"(?i)\b("
    r"silicon valley|us market|american (?:small )?business|"
    r"united states|usd\b|dollar budget|super bowl|"
    r"black friday (?:in )?the us|us-based|western market"
    r")\b"
)

_OUTDATED_CUES = re.compile(
    r"(?i)\b("
    r"boost post|power editor(?! v)|201[0-8]\b|2020\b|2021\b|"
    r"deprecated|no longer available|legacy interface|"
    r"before ios 14|pre-?att\b"
    r")\b"
)

_STRUCTURE_HEADING_RE = re.compile(
    r"(?m)^(?:#+\s+|(?:module|chapter|lesson|unit|week)\s+\d+)",
    re.IGNORECASE,
)

_OBJECTION_CUE = re.compile(
    r"(?i)(?:common mistake|misconception|learners (?:often|usually)|"
    r"people think|wrong belief|غلط شائع|فكرة خاطئة)[^.。\n]{8,120}"
)

_WARNING_CUE = re.compile(
    r"(?i)(?:warning|caution|avoid|do not|never|pitfall|"
    r"تحذير|احذر|لا تفعل)[^.。\n]{8,120}"
)


def _unique_lines(items: list[str], *, limit: int = 8) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in items:
        line = " ".join((raw or "").split()).strip()
        if not line:
            continue
        key = line.lower()[:120]
        if key in seen:
            continue
        seen.add(key)
        out.append(line)
        if len(out) >= limit:
            break
    return out


def _detect_filler(text: str) -> list[str]:
    lower = (text or "").lower()
    return [p for p in _FILLER_PHRASES if p in lower]


def _detect_structure_headings(text: str) -> list[str]:
    return [m.group(0).strip() for m in _STRUCTURE_HEADING_RE.finditer(text or "")][:6]


_BANNED_TERM_TOKENS = frozenset(
    {
        "furthermore",
        "moreover",
        "however",
        "therefore",
        "additionally",
        "conclusion",
        "important",
        "note",
        "one",
        "at",
        "the",
        "and",
    }
)


def _is_filler_line(line: str) -> bool:
    lower = (line or "").lower()
    if any(p in lower for p in _FILLER_PHRASES):
        return True
    if lower.startswith(("furthermore", "moreover", "in conclusion")):
        return True
    return False


def _clean_terminology(terms: list[str]) -> list[str]:
    out: list[str] = []
    for term in terms:
        t = (term or "").strip()
        if not t:
            continue
        bare = re.sub(r"[^\w\u0600-\u06FF]+", "", t).lower()
        if bare in _BANNED_TERM_TOKENS or len(bare) < 3:
            continue
        if _is_filler_line(t):
            continue
        out.append(t)
    return out[:12]


def _is_structure_line(line: str) -> bool:
    return bool(_STRUCTURE_HEADING_RE.match((line or "").strip()))


def _filter_practical_lines(lines: list[str], *, limit: int = 8) -> list[str]:
    return _unique_lines(
        [ln for ln in lines if ln and not _is_filler_line(ln) and not _is_structure_line(ln)],
        limit=limit,
    )


def apply_source_distillation(
    memory: dict[str, Any],
    *,
    extracted_text: str,
    target_market: str = "egypt",
) -> dict[str, Any]:
    """Enrich Source Memory with distillation metadata (internal only)."""
    text = extracted_text or ""
    facts = _filter_practical_lines(list(memory.get("extracted_facts") or memory.get("facts") or []))
    concepts = _filter_practical_lines(list(memory.get("concepts") or []))
    examples = _filter_practical_lines(list(memory.get("useful_examples") or memory.get("examples") or []))
    avoid = list(memory.get("warnings_or_uncertainties") or [])
    memory["extracted_facts"] = facts
    memory["facts"] = facts

    is_academic = bool(_ACADEMIC_CUES.search(text)) or (
        len(text) > 2500 and sum(1 for f in facts if len(f) > 180) >= 2
    )
    is_shallow = len(text) < 600 and len(facts) < 4 and not is_academic
    filler = _detect_filler(text)
    structure_heads = _detect_structure_headings(text)
    us_hits = _US_MARKET_CUES.findall(text)
    outdated_hits = _OUTDATED_CUES.findall(text)

    objections = _unique_lines([m.group(0) for m in _OBJECTION_CUE.finditer(text)])
    warnings = _unique_lines(
        [m.group(0) for m in _WARNING_CUE.finditer(text)] + avoid
    )

    rebuild_candidates = _unique_lines(
        [e for e in examples if len(e) > 20]
        + [
            f
            for f in facts
            if any(w in f.lower() for w in ("how", "step", "when", "if ", "distinction", "variable", "test"))
        ]
        + ([facts[-1]] if is_shallow and facts else []),
        limit=6,
    )

    discarded: list[str] = []
    if filler:
        discarded.append("filler phrases detected — do not preserve wording")
    if len(facts) > len(set(f.lower()[:80] for f in facts)):
        discarded.append("repetitive points — merge/dedupe before use")
    if structure_heads:
        discarded.append("source headings/modules — do not copy as course map")
    if is_academic:
        discarded.append("academic wording/book tone — convert to spoken practical script")
    if is_shallow:
        discarded.append("shallow surface advice — verify before elevating to final script")

    market_notes: list[str] = []
    market = (target_market or "egypt").lower()
    if us_hits and market in ("egypt", "arab_market", "custom"):
        market_notes.append(
            "Source assumes US/Western market — adapt examples and execution to "
            f"{target_market}; keep universal principles only"
        )

    outdated_warnings: list[str] = []
    if outdated_hits:
        outdated_warnings.append(
            "Possible outdated tool/UI references — official current docs override "
            "this source for platform behavior"
        )
    outdated_warnings.extend(
        w for w in avoid if "outdated" in w.lower() or "deprecated" in w.lower()
    )

    blocked: list[str] = list(memory.get("blocked_content_warnings") or [])
    for item in (
        "Never copy source format, tone, structure, filler, or market assumptions",
        "Never treat distilled snippets as equal authority to ROKN rules or Teleprompter DOCX contract",
    ):
        if item not in blocked:
            blocked.append(item)
    if structure_heads:
        extra = "Source structure must not dictate course map or lesson order"
        if extra not in blocked:
            blocked.append(extra)

    memory["distillation_version"] = DISTILLATION_VERSION
    memory["distilled_label"] = DISTILLED_LABEL
    memory["not_authority"] = True
    memory["useful_concepts"] = _filter_practical_lines(concepts + facts[:4], limit=8)
    memory["learner_objections"] = objections
    memory["practical_warnings"] = warnings[:8]
    memory["rebuild_candidates"] = rebuild_candidates
    memory["terminology_if_current"] = _clean_terminology(list(memory.get("terminology") or []))
    memory["gaps_to_cover"] = list(memory.get("gaps_to_cover") or [])[:6]
    memory["mistakes_to_avoid"] = _unique_lines(avoid + objections, limit=8)
    memory["discarded_signals"] = _unique_lines(discarded, limit=10)
    preserved_relevance = list(memory.get("relevance_notes") or [])
    memory["relevance_notes"] = _unique_lines(
        preserved_relevance
        + [
            "Extract only what serves the current course promise",
            "Shallow but useful points are candidates — verify and rebuild" if is_shallow else "",
            "Academic depth may inform accuracy — final script stays spoken/practical"
            if is_academic
            else "",
        ],
        limit=12,
    )
    memory["outdated_warnings"] = _unique_lines(outdated_warnings, limit=6)
    memory["market_adaptation_notes"] = _unique_lines(market_notes, limit=4)
    memory["blocked_content_warnings"] = blocked
    memory["academic_source_flag"] = is_academic
    memory["shallow_source_flag"] = is_shallow
    memory["map_structure_not_authority"] = bool(structure_heads)
    return memory


def format_distilled_memory_snippet(
    memory: dict[str, Any],
    *,
    query_text: str = "",
    chunks: list[dict[str, Any]] | None = None,
    max_chars: int = 1400,
) -> str:
    """Prompt-facing snippet — distilled raw material only."""
    title = memory.get("title") or "Source"
    parts: list[str] = [
        f"[{DISTILLED_LABEL} — {title} — {NOT_AUTHORITY_NOTE}]",
    ]
    if memory.get("academic_source_flag"):
        parts.append(
            "Academic source: convert theory to practical spoken explanation — "
            "no book chapter tone in final script."
        )
    if memory.get("shallow_source_flag"):
        parts.append(
            "Shallow source: candidate ideas only — verify and rebuild; "
            "do not inherit shallowness."
        )
    if memory.get("map_structure_not_authority"):
        parts.append("Source headings are NOT course map authority.")

    def add_section(label: str, items: list[str], *, cap: int = 5) -> None:
        if not items:
            return
        parts.append(f"{label}:\n- " + "\n- ".join(items[:cap]))

    add_section("Useful concepts", list(memory.get("useful_concepts") or []))
    add_section("Rebuild candidates (verify)", list(memory.get("rebuild_candidates") or []))
    add_section("Learner objections", list(memory.get("learner_objections") or []))
    add_section("Practical warnings", list(memory.get("practical_warnings") or []))
    add_section("Mistakes to avoid", list(memory.get("mistakes_to_avoid") or []))
    terms = list(memory.get("terminology_if_current") or [])
    if not terms:
        terms = _clean_terminology(list(memory.get("terminology") or []))
    if terms:
        parts.append("Terminology (if still current): " + ", ".join(terms[:10]))
    add_section("Relevance notes", list(memory.get("relevance_notes") or []), cap=3)
    add_section("Outdated warnings", list(memory.get("outdated_warnings") or []), cap=3)
    add_section("Market adaptation", list(memory.get("market_adaptation_notes") or []), cap=2)
    add_section("Blocked / discard", list(memory.get("discarded_signals") or []), cap=4)
    add_section("Do not inherit", list(memory.get("blocked_content_warnings") or []), cap=3)

    # Query-ranked chunk snippets stay internal and short.
    if chunks and query_text:
        from app.services.source_analysis import select_relevant_chunks, MAX_RELEVANT_CHUNKS

        relevant = select_relevant_chunks(chunks, query_text, max_chunks=MAX_RELEVANT_CHUNKS)
        if relevant:
            body = "\n\n".join(
                f"{c.get('heading') or 'Snippet'}: {(c.get('text') or '')[:280]}"
                for c in relevant
            )
            parts.append("Distilled snippets (verify, do not copy):\n" + body)

    text = "\n\n".join(p for p in parts if p).strip()
    if len(text) > max_chars:
        return text[: max_chars - 1].rstrip() + "…"
    return text
