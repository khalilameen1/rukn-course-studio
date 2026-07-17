"""Structured research needs from the course brief (not token-soup gaps).

Produces a small set of real information needs (definition / tool / practice /
market) before autonomous web fill. No LangChain / vector DB.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.generation.official_tool_docs import _TOOL_ALIASES

_STOP = frozenset(
    {
        "this",
        "that",
        "with",
        "from",
        "your",
        "their",
        "about",
        "course",
        "learn",
        "learning",
        "student",
        "students",
        "practical",
        "skill",
        "skills",
        "using",
        "how",
        "what",
        "when",
        "where",
        "which",
        "كورس",
        "تعلم",
        "الطلاب",
        "عملي",
    }
)

_SENSITIVE = re.compile(
    r"\b(religio|quran|hadith|sharia|فتوى|قانون|legal advice|medical|"
    r"تشخيص|علاج|دواء|invest|financial advice|ROI guaranteed|"
    r"diagnos|prescription|clinical trial)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class StructuredNeed:
    question: str
    why_needed: str
    kind: str  # definition | tool | practice | market
    sensitive: bool = False


def _detect_tools(blob: str) -> list[str]:
    low = (blob or "").lower()
    found: list[str] = []
    for alias, canonical in sorted(_TOOL_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in low and canonical not in found:
            found.append(canonical)
    return found[:3]


def _covered(question: str, upload_blob: str) -> bool:
    if not upload_blob or len(upload_blob) < 80:
        return False
    tokens = [
        t
        for t in re.findall(r"[\w\u0600-\u06FF]{4,}", question.lower())
        if t not in _STOP
    ]
    if not tokens:
        return False
    hits = sum(1 for t in tokens if t in upload_blob.lower())
    return hits >= max(2, (len(tokens) + 1) // 2)


def build_structured_research_needs(
    *,
    course_title: str,
    audience: str,
    outcome: str,
    special_notes: str | None,
    upload_summaries: list[str],
    max_needs: int = 5,
) -> list[StructuredNeed]:
    """Build 1–5 concrete research needs from the brief + upload thickness."""
    upload_blob = " ".join(s for s in upload_summaries if s)
    brief = f"{course_title} {audience} {outcome} {special_notes or ''}".strip()
    sensitive = bool(_SENSITIVE.search(f"{brief} {upload_blob}"))
    tools = _detect_tools(brief)
    thick_uploads = len(upload_blob) >= 2000
    thin_uploads = len(upload_blob) < 400

    candidates: list[StructuredNeed] = []
    core = (outcome or course_title or "course topic").strip()
    if core:
        candidates.append(
            StructuredNeed(
                question=f"Core concept and realistic limits: {core}",
                why_needed="definition",
                kind="definition",
                sensitive=sensitive,
            )
        )

    for tool in tools:
        candidates.append(
            StructuredNeed(
                question=f"{tool} current official workflow for beginners",
                why_needed="platform_current_tool_docs",
                kind="tool",
                sensitive=True,
            )
        )

    if audience.strip():
        candidates.append(
            StructuredNeed(
                question=(
                    f"Practical first steps for {audience.strip()} to achieve: {core}"
                ),
                why_needed="audience_practice",
                kind="practice",
                sensitive=sensitive,
            )
        )

    if re.search(
        r"\b(ads?|marketing|seo|pricing|algorithm|campaign|roi|roas)\b",
        brief,
        re.I,
    ) or any(t in {"Meta Ads", "Google Ads", "TikTok Ads"} for t in tools):
        candidates.append(
            StructuredNeed(
                question=f"Evergreen principles vs short-lived UI/pricing for: {core}",
                why_needed="market_evergreen",
                kind="market",
                sensitive=sensitive,
            )
        )

    ordered = sorted(
        candidates,
        key=lambda n: {"tool": 0, "definition": 1, "practice": 2, "market": 3}.get(
            n.kind, 9
        ),
    )

    out: list[StructuredNeed] = []
    seen: set[str] = set()
    for need in ordered:
        key = need.question.casefold()
        if key in seen:
            continue
        if thick_uploads and need.kind in {"practice", "market"} and _covered(
            need.question, upload_blob
        ):
            continue
        if not thin_uploads and _covered(need.question, upload_blob):
            continue
        seen.add(key)
        out.append(need)
        if len(out) >= max_needs:
            break

    if not out and thin_uploads:
        out.append(
            StructuredNeed(
                question=core or "course topic",
                why_needed="insufficient_uploaded_sources",
                kind="definition",
                sensitive=sensitive,
            )
        )
    return out
