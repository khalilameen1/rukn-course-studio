"""Mark evidence ledger rows that likely informed Final Master (internal).

Never surfaces URLs/citations — only coarse counts for a public one-liner.
"""

from __future__ import annotations

import re
from typing import Any

from app.generation.web_research import EvidenceEntry, EvidenceLedger


def _tokens(text: str) -> set[str]:
    return {
        t
        for t in re.findall(r"[\w\u0600-\u06FF]{4,}", (text or "").lower())
        if len(t) >= 4
    }


def mark_evidence_used_in_scripts(
    ledger: EvidenceLedger | dict[str, Any] | None,
    script_texts: list[str],
) -> EvidenceLedger:
    """Flip `used_in_script` when claim/title tokens overlap Final Master text."""
    if ledger is None:
        return EvidenceLedger()
    if isinstance(ledger, dict):
        model = EvidenceLedger.model_validate(ledger)
    else:
        model = ledger.model_copy(deep=True)

    corpus = _tokens(" ".join(script_texts))
    if not corpus:
        return model

    for entry in model.entries:
        probe = _tokens(f"{entry.claim_or_gap} {entry.source_title} {entry.note}")
        if not probe:
            continue
        overlap = len(probe & corpus)
        if overlap >= max(2, min(4, len(probe) // 3)):
            entry.used_in_script = True
    return model


def format_provenance_summary(
    *,
    upload_count: int,
    web_gap_count: int,
    ledger: EvidenceLedger | None,
    web_searches: int = 0,
    cache_hits: int = 0,
) -> str:
    """Coarse public string — never URLs or claim text."""
    used = omitted = weak = 0
    if ledger:
        for e in ledger.entries:
            if e.used_in_script:
                used += 1
            if e.support_status == "omitted":
                omitted += 1
            elif e.support_status == "weak":
                weak += 1
    parts = [
        f"Grounded on {upload_count} upload(s)",
        f"{web_gap_count} web gap(s) filled",
    ]
    if used:
        parts.append(f"{used} evidence hit(s) in scripts")
    if omitted:
        parts.append(f"{omitted} omitted")
    if weak:
        parts.append(f"{weak} weak")
    if web_searches or cache_hits:
        parts.append(f"searches {web_searches} · cache {cache_hits}")
    return " · ".join(parts)


def ledger_support_rollup(ledger: EvidenceLedger | dict | None) -> str | None:
    """Internal QA warning from support mix — not keyword DOCX overlap."""
    if ledger is None:
        return None
    model = (
        EvidenceLedger.model_validate(ledger)
        if isinstance(ledger, dict)
        else ledger
    )
    if not model.entries:
        return None
    supported = sum(1 for e in model.entries if e.support_status == "supported")
    omitted = sum(1 for e in model.entries if e.support_status == "omitted")
    weak = sum(1 for e in model.entries if e.support_status == "weak")
    used = sum(1 for e in model.entries if e.used_in_script)
    if supported == 0 and omitted > 0:
        return (
            "Evidence ledger shows researched gaps were omitted — "
            "scripts may rely on the brief and canonical RUKN standard only."
        )
    if supported > 0 and used == 0:
        return (
            "Evidence was gathered but little of it appears reflected in Final Master "
            "(overlap heuristic) — double-check manually."
        )
    if weak > supported:
        return "Evidence mix is mostly weak/conditional — treat fragile claims carefully."
    return None
