"""Trusted knowledge gate — factual authority tiers (no social/forum as facts).

No LangChain / vector DB. Heuristic URL + title/publisher scoring only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

from pydantic import BaseModel, Field


class SourceQualityTier(str, Enum):
    HIGHEST = "highest"
    STRONG = "strong"
    CONDITIONAL = "conditional"
    REJECTED = "rejected"
    LEARNER_SIGNAL_ONLY = "learner_signal_only"


# Official / institutional / academic / docs patterns.
_HIGHEST_HOST_RE = re.compile(
    r"(?:^|\.)("
    r"gov|gob|gouv|gov\.uk|europa\.eu|"
    r"edu|ac\.uk|ac\.eg|"
    r"wikipedia\.org|"
    r"docs\.[a-z0-9.-]+|"
    r"help\.[a-z0-9.-]+|"
    r"support\.[a-z0-9.-]+|"
    r"developers?\.[a-z0-9.-]+|"
    r"developer\.[a-z0-9.-]+|"
    r"learn\.[a-z0-9.-]+"
    r")$",
    re.IGNORECASE,
)

_HIGHEST_HINTS = re.compile(
    r"\b("
    r"official(?:\s+docs?|\s+documentation|\s+help)?|"
    r"documentation|help center|developer docs|"
    r"ministry|regulator|university|whitepaper|"
    r"ISO\s*\d+|WHO|UNESCO|FDA|EMA"
    r")\b",
    re.IGNORECASE,
)

_STRONG_HINTS = re.compile(
    r"\b("
    r"textbook|academic|peer[- ]reviewed|journal|"
    r"course materials?|syllabus|lecture notes|"
    r"industry report|training (?:manual|guide)|"
    r"O'Reilly|Packt|Wiley|Springer|MIT Press|"
    r"Harvard|Stanford|Cambridge|Oxford"
    r")\b",
    re.IGNORECASE,
)

_CONDITIONAL_HINTS = re.compile(
    r"\b("
    r"engineering blog|design blog|marketing blog|"
    r"expert (?:blog|newsletter)|case study"
    r")\b",
    re.IGNORECASE,
)

# Hard reject as factual authority.
_REJECTED_HOST_RE = re.compile(
    r"(?:^|\.)("
    r"facebook\.com|fb\.com|tiktok\.com|instagram\.com|"
    r"reddit\.com|quora\.com|pinterest\.com|"
    r"twitter\.com|x\.com|threads\.net|"
    r"medium\.com|buzzfeed\.com|clickbait"
    r")$",
    re.IGNORECASE,
)

_REJECTED_HINTS = re.compile(
    r"\b("
    r"top\s*10\s+tips|viral|influencer|"
    r"reddit comment|forum comment|facebook post|"
    r"tiktok|youtube shorts|unsourced|"
    r"content farm|SEO article|listicle"
    r")\b",
    re.IGNORECASE,
)

_SOCIAL_LEARNER_HINTS = re.compile(
    r"\b(students? ask|common question|people struggle|confusion)\b",
    re.IGNORECASE,
)


class TrustedSourceVerdict(BaseModel):
    tier: SourceQualityTier
    allowed_as_fact: bool
    reason: str = ""
    publisher: str = ""


@dataclass
class ScoredWebHit:
    title: str
    summary: str
    url: str = ""
    publisher: str = ""
    tier: SourceQualityTier = SourceQualityTier.CONDITIONAL


def _host(url: str) -> str:
    try:
        host = (urlparse(url or "").hostname or "").lower().rstrip(".")
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def classify_source(
    *,
    title: str = "",
    url: str = "",
    publisher: str = "",
    summary: str = "",
) -> TrustedSourceVerdict:
    """Classify a candidate as factual authority or reject."""
    blob = f"{title} {publisher} {summary} {url}"
    host = _host(url)
    pub = publisher or host or ""
    path = ""
    try:
        path = (urlparse(url or "").path or "").lower()
    except Exception:
        path = ""

    # Official help/docs paths on major platforms beat social host rejection.
    if host and (
        "/business/help" in path
        or path.startswith("/docs")
        or "/help/" in path
        or "developers.facebook.com" in (url or "").lower()
        or "developers.google.com" in (url or "").lower()
    ):
        return TrustedSourceVerdict(
            tier=SourceQualityTier.HIGHEST,
            allowed_as_fact=True,
            reason="official_platform_docs",
            publisher=pub,
        )

    if host and _REJECTED_HOST_RE.search(host):
        learner = bool(_SOCIAL_LEARNER_HINTS.search(blob))
        return TrustedSourceVerdict(
            tier=(
                SourceQualityTier.LEARNER_SIGNAL_ONLY
                if learner
                else SourceQualityTier.REJECTED
            ),
            allowed_as_fact=False,
            reason="social_or_forum_not_factual_authority",
            publisher=pub,
        )
    if _REJECTED_HINTS.search(blob):
        return TrustedSourceVerdict(
            tier=SourceQualityTier.REJECTED,
            allowed_as_fact=False,
            reason="low_quality_or_unsourced_content",
            publisher=pub,
        )

    if host and (
        host.endswith(".gov")
        or host.endswith(".edu")
        or host.endswith(".ac.uk")
        or "wikipedia.org" in host
        or host.startswith("docs.")
        or host.startswith("help.")
        or host.startswith("support.")
        or host.startswith("developer.")
        or host.startswith("developers.")
    ):
        return TrustedSourceVerdict(
            tier=SourceQualityTier.HIGHEST,
            allowed_as_fact=True,
            reason="official_or_institutional",
            publisher=pub,
        )
    if _HIGHEST_HINTS.search(blob) or (host and _HIGHEST_HOST_RE.search(host)):
        return TrustedSourceVerdict(
            tier=SourceQualityTier.HIGHEST,
            allowed_as_fact=True,
            reason="official_or_institutional",
            publisher=pub,
        )
    if _STRONG_HINTS.search(blob):
        return TrustedSourceVerdict(
            tier=SourceQualityTier.STRONG,
            allowed_as_fact=True,
            reason="educational_or_professional",
            publisher=pub,
        )
    if _CONDITIONAL_HINTS.search(blob):
        return TrustedSourceVerdict(
            tier=SourceQualityTier.CONDITIONAL,
            allowed_as_fact=True,
            reason="domain_expert_conditional",
            publisher=pub,
        )

    # Unknown URL with thin metadata → conditional at best (Fake backend OK).
    if not url and (title or summary):
        return TrustedSourceVerdict(
            tier=SourceQualityTier.CONDITIONAL,
            allowed_as_fact=True,
            reason="trusted_overview_no_url",
            publisher=pub or "internal_trusted_overview",
        )

    return TrustedSourceVerdict(
        tier=SourceQualityTier.CONDITIONAL,
        allowed_as_fact=True,
        reason="unknown_treat_as_conditional",
        publisher=pub,
    )


def filter_factual_hits(hits: list[ScoredWebHit]) -> list[ScoredWebHit]:
    """Keep only sources allowed as factual authority."""
    kept: list[ScoredWebHit] = []
    for hit in hits:
        verdict = classify_source(
            title=hit.title, url=hit.url, publisher=hit.publisher, summary=hit.summary
        )
        if not verdict.allowed_as_fact:
            continue
        hit.tier = verdict.tier
        hit.publisher = verdict.publisher or hit.publisher
        kept.append(hit)
    return kept


# Compact prompt guidance — transform educational sources into Rukn spoken form.
RUKN_EDUCATIONAL_TRANSFORM = """Educational / book / course / docs knowledge rules:
- Keep accurate concepts, correct terms, field logic, useful distinctions, adaptable examples, stable principles.
- Remove academic dryness, unnecessary theory, foreign-market assumptions, outdated examples, over-formal language, citations, textbook structure, and irrelevant depth.
- Rewrite into clean Egyptian Arabic spoken teleprompter script: practical, locally realistic, high-signal — never translated academic prose.
- Never paste URLs, citations, or "according to source" into script_text.
"""


def compile_educational_transform_guidance() -> str:
    return RUKN_EDUCATIONAL_TRANSFORM
