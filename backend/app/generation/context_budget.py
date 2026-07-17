"""Trim map/lesson context so Anthropic requests stay under context limits."""

from __future__ import annotations

from app.generation.prompt_compiler import SourceExcerpt

# Soft budget for course-map source excerpts (chars of text fields).
DEFAULT_MAP_SOURCE_CHAR_BUDGET = 24_000
DEFAULT_MAP_MAX_EXCERPTS = 12


def trim_source_excerpts_for_map(
    excerpts: list[SourceExcerpt],
    *,
    max_chars: int = DEFAULT_MAP_SOURCE_CHAR_BUDGET,
    max_items: int = DEFAULT_MAP_MAX_EXCERPTS,
) -> list[SourceExcerpt]:
    """Keep highest-priority excerpts within a hard character budget."""
    if not excerpts:
        return []
    # Prefer user_notes / scientific_reference first (authority order already
    # applied by compile_source_context — preserve order, just cap).
    kept: list[SourceExcerpt] = []
    used = 0
    for ex in excerpts[: max_items * 2]:
        text = (ex.text or "").strip()
        if not text:
            continue
        room = max_chars - used
        if room <= 200:
            break
        if len(text) > room:
            text = text[: room - 1] + "…"
        kept.append(ex.model_copy(update={"text": text}))
        used += len(text)
        if len(kept) >= max_items:
            break
    return kept


def trim_rules_context(
    rules: dict[str, str],
    *,
    max_total_chars: int = 40_000,
) -> dict[str, str]:
    """Cap admin-knowledge payload size without dropping keys entirely."""
    if not rules:
        return {}
    items = list(rules.items())
    out: dict[str, str] = {}
    used = 0
    per_key_floor = 80
    for key, value in items:
        body = value or ""
        remaining_keys = max(1, len(items) - len(out))
        room = max(per_key_floor, (max_total_chars - used) // remaining_keys)
        room = min(room, max_total_chars - used)
        if room <= 0:
            out[key] = (body[:40] + "…") if len(body) > 40 else body
            continue
        if len(body) > room:
            body = body[: max(1, room - 1)] + "…"
        out[key] = body
        used += len(key) + len(body)
        if used >= max_total_chars:
            # Fill remaining keys with tiny stubs so callers keep key presence.
            for rest_key, rest_val in items[len(out) :]:
                stub = (rest_val or "")[:40]
                out[rest_key] = stub + ("…" if len(rest_val or "") > 40 else "")
            break
    return out
