"""User-facing progress copy — never expose multi-agent internals."""

from __future__ import annotations

# Coarse stage keys the UI may show as steps.
PUBLIC_STAGE_LABELS: dict[str, str] = {
    "queued": "Preparing course",
    "reading_sources": "Reading sources",
    "filling_gaps": "Filling knowledge gaps",
    "synthesizing": "Synthesizing research",
    "building_map": "Building course map",
    "generating": "Writing lessons",
    "reviewing_repetition": "Reviewing lessons",
    "reviewing": "Finalizing course",
    "exporting": "Exporting Teleprompter DOCX",
    "done": "Done",
    "failed": "Failed",
    "partial": "Stopped early",
    "paused": "Paused",
    "canceled": "Canceled",
}

# Phrases that must never appear in last_progress_message / UI.
_AGENT_LEAK_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("Running specialist critic", "Reviewing lesson quality"),
    ("Checking student clarity", "Reviewing lesson clarity"),
    ("Consulting master mentor", "Finalizing lesson"),
    ("specialist critic", "lesson review"),
    ("master mentor", "final review"),
    ("student clarity", "lesson clarity"),
    ("Creator draft", "Lesson draft"),
    ("Creator →", "Draft →"),
)


def public_stage_label(stage: str | None) -> str | None:
    if not stage:
        return stage
    return PUBLIC_STAGE_LABELS.get(stage, stage)


def estimate_live_eta(
    *,
    progress_percent: int,
    quality_mode: str = "premium",
    total_lessons: int = 0,
) -> str:
    """Rough remaining-time band from progress — never exact clock promises."""
    pct = max(0, min(100, int(progress_percent or 0)))
    if pct >= 95:
        return "~1–2 min left"
    # Baseline minutes for a full run.
    preview = "preview" in (quality_mode or "").lower()
    base = 18 if preview else 45
    if total_lessons:
        base = max(base, int(total_lessons * (1.2 if preview else 2.5)))
    remaining_frac = max(0.05, (100 - pct) / 100.0)
    mins = max(1, int(base * remaining_frac))
    if mins <= 3:
        return f"~{mins} min left"
    if mins <= 12:
        return f"~{mins}–{mins + 3} min left"
    return f"~{mins}–{mins + 8} min left"


def sanitize_progress_message(message: str | None, *, stage: str | None = None) -> str | None:
    if not message:
        return public_stage_label(stage) if stage else message
    text = message
    for old, new in _AGENT_LEAK_REPLACEMENTS:
        text = text.replace(old, new)
    # If still empty of meaning, fall back to stage label.
    if text.strip() == message.strip() and stage:
        # Prefer known safe stage label when message looks internal.
        lower = text.lower()
        if any(
            token in lower
            for token in ("critic", "mentor", "student agent", "creator agent")
        ):
            return public_stage_label(stage)
    return text
