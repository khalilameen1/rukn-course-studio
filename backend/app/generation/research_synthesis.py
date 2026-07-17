"""Post-research synthesis + public run signals (GENSPARK-style, never DOCX)."""

from __future__ import annotations

from typing import Any

from app.generation.web_research import EvidenceLedger, SourceMemory


def synthesize_research_for_write(
    *,
    ledger: EvidenceLedger | dict | None,
    web_excerpts: list[tuple[str, str]],
    upload_memory: SourceMemory | None,
) -> dict[str, Any]:
    """Internal synthesis gate before map/lessons.

    Produces a short internal brief for prompts + a public one-liner.
    Never includes URLs or claim dumps for the UI.
    """
    model = (
        EvidenceLedger.model_validate(ledger)
        if isinstance(ledger, dict)
        else (ledger or EvidenceLedger())
    )
    supported = sum(1 for e in model.entries if e.support_status == "supported")
    omitted = sum(1 for e in model.entries if e.support_status == "omitted")
    weak = sum(1 for e in model.entries if e.support_status == "weak")
    uploads = len((upload_memory.items if upload_memory else []) or [])
    excerpt_n = len(web_excerpts or [])

    confirmed = []
    if uploads:
        confirmed.append(f"{uploads} upload memory item(s)")
    if supported:
        confirmed.append(f"{supported} supported gap(s)")
    if excerpt_n:
        confirmed.append(f"{excerpt_n} web excerpt(s) merged")

    dropped = []
    if omitted:
        dropped.append(f"{omitted} omitted")
    if weak:
        dropped.append(f"{weak} weak/conditional")

    public_note = "Research synthesized for writing"
    if confirmed:
        public_note += " · " + ", ".join(confirmed[:3])
    if dropped:
        public_note += " · skipped " + ", ".join(dropped)

    # Compact internal brief — prompt influence only (never DOCX).
    internal_lines = [
        "SYNTHESIS (internal): Prefer confirmed practical steps over weak claims.",
        f"Confirmed signals: {', '.join(confirmed) if confirmed else 'brief only'}.",
    ]
    if dropped:
        internal_lines.append(f"Do not lean on: {', '.join(dropped)}.")
    # Top excerpt titles only (no URLs).
    for title, summary in (web_excerpts or [])[:4]:
        snip = (summary or "").strip().replace("\n", " ")[:180]
        if snip:
            internal_lines.append(f"- {title}: {snip}")

    return {
        "public_note": public_note,
        "internal_brief": "\n".join(internal_lines),
        "supported": supported,
        "omitted": omitted,
        "weak": weak,
    }


def format_architecture_summary(*, module_count: int, lesson_count: int) -> str:
    """Silent map → one public architecture line."""
    mods = max(0, int(module_count))
    lessons = max(0, int(lesson_count))
    if mods == 0 and lessons == 0:
        return "Architecture pending"
    path = "practical path" if lessons >= 4 else "focused path"
    return f"{lessons} lesson(s) · {mods} module(s) · {path}"


def grounding_confidence_label(ledger: EvidenceLedger | dict | None) -> str:
    """Coarse confidence without citations: strong | mixed | weak."""
    if ledger is None:
        return "mixed"
    model = (
        EvidenceLedger.model_validate(ledger)
        if isinstance(ledger, dict)
        else ledger
    )
    if not model.entries:
        return "mixed"
    supported = sum(1 for e in model.entries if e.support_status == "supported")
    omitted = sum(1 for e in model.entries if e.support_status == "omitted")
    weak = sum(1 for e in model.entries if e.support_status == "weak")
    used = sum(1 for e in model.entries if e.used_in_script)
    if supported >= 2 and used >= 1 and omitted <= supported:
        return "strong"
    if supported == 0 and (omitted + weak) > 0:
        return "weak"
    if weak > supported or (supported > 0 and used == 0):
        return "mixed"
    return "strong" if supported else "mixed"


def improve_next_run_tip(
    *,
    grounding_confidence: str | None,
    clarity_score: int | None = None,
    web_searches: int = 0,
    cache_hits: int = 0,
) -> str:
    """One actionable tip for the next run (Sparkpage footer)."""
    conf = (grounding_confidence or "mixed").lower()
    if clarity_score is not None and clarity_score < 55:
        return "Sharpen audience + measurable outcome, then re-run Premium."
    if conf == "weak":
        return "Add one strong notes/transcript source, or include cleaner uploads."
    if conf == "mixed" and web_searches and not cache_hits:
        return "Add practical notes for fragile topics so the next run leans less on gap-fill."
    if cache_hits and conf == "strong":
        return "Brief and sources look solid — re-run only if the goal changed."
    return "Optional: add a short practice checklist as notes before the next Premium run."


def merge_specialist_excerpts(
    excerpts: list[tuple[str, str]],
    *,
    max_items: int = 12,
) -> list[tuple[str, str]]:
    """Prefer tool/practice excerpts when merging parallel specialist fills."""
    from app.generation.claim_dedup import dedupe_excerpt_pairs

    def _rank(title: str, summary: str) -> int:
        blob = f"{title} {summary}".lower()
        if any(k in blob for k in ("official", "ads manager", "workflow", "help center")):
            return 0
        if any(k in blob for k in ("step", "practice", "beginner", "checklist")):
            return 1
        if any(k in blob for k in ("market", "egypt", "local")):
            return 3
        return 2

    ranked = sorted(excerpts, key=lambda p: (_rank(p[0], p[1]), -len(p[1] or "")))
    return dedupe_excerpt_pairs(ranked, max_items=max_items)
