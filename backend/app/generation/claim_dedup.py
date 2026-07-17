"""Deduplicate near-duplicate claim excerpts before prompt compile."""

from __future__ import annotations

import re
from typing import Iterable


def _norm_key(text: str) -> str:
    t = (text or "").strip().lower()
    t = re.sub(r"[^\w\u0600-\u06FF\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    # Keep first ~6 tokens as identity for near-dup detection.
    parts = t.split()
    return " ".join(parts[:6])


def dedupe_excerpt_pairs(
    pairs: Iterable[tuple[str, str]],
    *,
    max_items: int = 24,
) -> list[tuple[str, str]]:
    """Keep first of near-duplicate (title, summary) pairs; prefer longer summary."""
    best: dict[str, tuple[str, str]] = {}
    order: list[str] = []
    for title, summary in pairs:
        key = _norm_key(summary) or _norm_key(title)
        if not key:
            continue
        if key not in best:
            best[key] = (title, summary)
            order.append(key)
            continue
        prev_t, prev_s = best[key]
        if len(summary or "") > len(prev_s or ""):
            best[key] = (title or prev_t, summary)
    out = [best[k] for k in order]
    return out[:max_items]
