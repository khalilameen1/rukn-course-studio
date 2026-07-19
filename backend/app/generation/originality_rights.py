"""Originality + Rights Gate (no new personas).

Sources (uploads + web) are knowledge inputs only — never writing templates.
Silent remediations only; never emit originality/copyright/source notes into
script_text or DOCX.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models.enums import TargetMarket
from app.schemas.generation import FinalCourse
from app.validators.similarity import text_similarity

# Forbidden if leaked into DOCX / spoken transcript.
ORIGINALITY_DOCX_LEAKS: tuple[str, ...] = (
    "originality note",
    "originality gate",
    "copyright note",
    "source note",
    "according to the source",
    "as the article says",
    "paraphrased from",
    "adapted from",
)

_NAMED_CREATOR_IMITATION = re.compile(
    r"("
    r"as\s+\w+\s+(?:always\s+)?says|"
    r"in\s+the\s+style\s+of\s+\w+|"
    r"like\s+(?:gary\s+vee|alex\s+hormozi|russell\s+brunson|grant\s+cardone)\b|"
    r"hormozi\s+offer|"
    r"\$100m\s+offers?|"
    r"signature\s+catchphrase|"
    r"imitate\s+(?:this\s+)?creator|"
    r"copy\s+\w+'s\s+style|"
    r"زي\s+ما\s+بيقول\s+\w+|"
    r"بأسلوب\s+\w+"
    r")",
    re.IGNORECASE,
)

_ARTICLE_PARAPHRASE = re.compile(
    r"("
    r"\bin\s+this\s+article\b|\bas\s+mentioned\s+above\b|"
    r"\bit\s+is\s+worth\s+noting\b|\bfurthermore\b|\bmoreover\b|"
    r"\baccording\s+to\s+(?:the\s+)?(?:source|article|study)\b|"
    r"من\s+الجدير\s+بالذكر|تجدر\s+الإشارة|بناءً\s+على\s+ما\s+سبق|"
    r"كما\s+ورد\s+في\s+(?:المقال|المصدر)"
    r")",
    re.IGNORECASE,
)

_IMPORTED_EXAMPLE = re.compile(
    r"("
    r"silicon\s+valley|fortune\s+500|series\s+[abc]\b|"
    r"nyc\s+startup|manhattan\s+agency|"
    r"\$10,?000\s+(?:ad\s+)?budget|"
    r"american\s+client|US\s+enterprise\s+client"
    r")",
    re.IGNORECASE,
)

_LOCAL_EXAMPLE_SWAP = (
    "مثلاً محل أو عيادة أو فريلانسر بيشتغل مع عملاء على واتساب وفيسبوك "
    "بميزانية واقعية."
)

_ORIGINAL_REWRITE_BEAT = (
    "خلّينا نشرح الفكرة دي بكلامنا وإيقاع رُكن، مش بنفس صياغة المصدر."
)

# Minimum consecutive words shared with a source to flag copying.
_COPY_NGRAM = 6
_WINDOW_SIM_THRESHOLD = 0.88
_WINDOW_WORDS = 24


@dataclass
class OriginalityFinding:
    code: str
    detail: str  # internal only


@dataclass
class OriginalityReport:
    findings: list[OriginalityFinding] = field(default_factory=list)
    remediations: list[str] = field(default_factory=list)

    @property
    def codes(self) -> set[str]:
        return {f.code for f in self.findings}


def compile_originality_guidance() -> str:
    """Runtime guidance injected beside the canonical standard (never DOCX)."""
    return (
        "ORIGINALITY_RIGHTS: Sources (upload + web) are for facts, concepts, "
        "terminology, field logic, common mistakes, and verified knowledge only. "
        "Never copy wording, distinctive examples, story/hook structure, creator "
        "style, catchphrases, or produce a translated/paraphrased rewrite of a "
        "source. Free/public sources are still not free to copy. Flow references "
        "teach pacing/tension/transitions/rhythm only — never verbal style or "
        "signature lines. Web research fills facts only — not article structure, "
        "hooks, examples, or tone. Rewrite from the underlying idea; keep the "
        "fact/concept, not the source's expression."
    )


def _words(text: str) -> list[str]:
    return re.findall(r"[\w\u0600-\u06FF]+", (text or "").lower())


def _ngrams(words: list[str], n: int) -> set[str]:
    if len(words) < n:
        return set()
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


def _source_copy_spans(script: str, sources: list[str]) -> list[str]:
    """Return shared n-grams / near-duplicate windows (evidence, internal)."""
    script_words = _words(script)
    if len(script_words) < _COPY_NGRAM:
        return []
    hits: list[str] = []
    script_grams = _ngrams(script_words, _COPY_NGRAM)
    for src in sources:
        src_words = _words(src)
        if len(src_words) < _COPY_NGRAM:
            continue
        overlap = script_grams & _ngrams(src_words, _COPY_NGRAM)
        for gram in sorted(overlap)[:5]:
            hits.append(gram)
        # Sliding-window similarity for paraphrase-ish blocks.
        if len(script_words) >= _WINDOW_WORDS and len(src_words) >= _WINDOW_WORDS:
            for i in range(0, len(script_words) - _WINDOW_WORDS + 1, _WINDOW_WORDS // 2):
                win = " ".join(script_words[i : i + _WINDOW_WORDS])
                for j in range(0, len(src_words) - _WINDOW_WORDS + 1, _WINDOW_WORDS // 2):
                    src_win = " ".join(src_words[j : j + _WINDOW_WORDS])
                    if text_similarity(win, src_win) >= _WINDOW_SIM_THRESHOLD:
                        hits.append(win[:80])
                        break
    seen: set[str] = set()
    out: list[str] = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def scan_script_originality(
    script: str,
    *,
    source_texts: list[str] | None = None,
    target_market: TargetMarket = TargetMarket.EGYPT,
) -> list[OriginalityFinding]:
    findings: list[OriginalityFinding] = []
    text = script or ""
    if not text:
        return findings

    sources = [s for s in (source_texts or []) if (s or "").strip()]
    spans = _source_copy_spans(text, sources) if sources else []
    if spans:
        findings.append(
            OriginalityFinding(
                "source_wording_overlap",
                f"Script shares phrasing/windows with a source ({len(spans)} hit(s)).",
            )
        )

    if _NAMED_CREATOR_IMITATION.search(text):
        findings.append(
            OriginalityFinding(
                "named_creator_imitation",
                "Named creator / catchphrase imitation detected.",
            )
        )

    if _ARTICLE_PARAPHRASE.search(text):
        findings.append(
            OriginalityFinding(
                "article_paraphrase_tone",
                "Sounds like a paraphrased/translated article, not original spoken teaching.",
            )
        )

    if sources:
        for src in sources:
            for m in re.finditer(
                r"(?:for example|مثلاً|مثال)[^.。]{20,120}", src, flags=re.I
            ):
                chunk = m.group(0).strip()
                if len(_words(chunk)) >= 5:
                    mid = " ".join(_words(chunk)[2:8])
                    if mid and mid in " ".join(_words(text)):
                        findings.append(
                            OriginalityFinding(
                                "distinctive_source_example",
                                "Distinctive example from a source appears in the script.",
                            )
                        )
                        break

    if target_market in (TargetMarket.EGYPT, TargetMarket.ARAB_MARKET):
        if _IMPORTED_EXAMPLE.search(text):
            findings.append(
                OriginalityFinding(
                    "imported_example_swap",
                    "Imported foreign example should be replaced with local realistic one.",
                )
            )

    for leak in ORIGINALITY_DOCX_LEAKS:
        if leak in text.lower():
            findings.append(
                OriginalityFinding(
                    "originality_label_leak",
                    f"Internal label '{leak}' must not appear in spoken script.",
                )
            )
            break

    return findings


def rewrite_script_originality(
    script: str,
    *,
    source_texts: list[str] | None = None,
    target_market: TargetMarket = TargetMarket.EGYPT,
    report: OriginalityReport | None = None,
) -> str:
    """Silent rewrite: keep facts/ideas, drop source expression."""
    report = report or OriginalityReport()
    text = script or ""
    findings = scan_script_originality(
        text, source_texts=source_texts, target_market=target_market
    )
    report.findings.extend(findings)
    if not findings:
        return text

    out = text
    sources = [s for s in (source_texts or []) if (s or "").strip()]

    for span in _source_copy_spans(out, sources):
        pattern = re.escape(span)
        if len(span) >= 12 and re.search(pattern, out, flags=re.IGNORECASE):
            out = re.sub(pattern, "", out, count=1, flags=re.IGNORECASE)
            report.remediations.append("strip_source_overlap")

    if any(f.code == "named_creator_imitation" for f in findings):
        out = _NAMED_CREATOR_IMITATION.sub("", out)
        report.remediations.append("strip_creator_imitation")

    if any(f.code == "article_paraphrase_tone" for f in findings):
        out = _ARTICLE_PARAPHRASE.sub("", out)
        report.remediations.append("strip_article_tone")

    if any(f.code == "imported_example_swap" for f in findings):
        out = _IMPORTED_EXAMPLE.sub(_LOCAL_EXAMPLE_SWAP, out)
        report.remediations.append("localize_imported_example")

    if any(
        f.code
        in {
            "source_wording_overlap",
            "distinctive_source_example",
            "article_paraphrase_tone",
        }
        for f in findings
    ):
        if _ORIGINAL_REWRITE_BEAT not in out:
            out = f"{out.rstrip()}\n{_ORIGINAL_REWRITE_BEAT}"
        report.remediations.append("original_rewrite_beat")

    for leak in ORIGINALITY_DOCX_LEAKS:
        out = re.sub(re.escape(leak), "", out, flags=re.IGNORECASE)

    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def apply_originality_to_final_course(
    course: FinalCourse,
    *,
    source_texts: list[str] | None = None,
    target_market: TargetMarket = TargetMarket.EGYPT,
) -> tuple[FinalCourse, OriginalityReport]:
    report = OriginalityReport()
    modules = []
    changed = False
    for module in course.modules:
        reels = []
        for reel in module.reels:
            original = reel.script_text or ""
            rewritten = rewrite_script_originality(
                original,
                source_texts=source_texts,
                target_market=target_market,
                report=report,
            )
            if rewritten != original:
                changed = True
                reels.append(reel.model_copy(update={"script_text": rewritten}))
            else:
                reels.append(reel)
        modules.append(module.model_copy(update={"reels": reels}))
    if not changed:
        return course, report
    return course.model_copy(update={"modules": modules}), report


def lesson_originality_instructions(
    script: str,
    *,
    source_texts: list[str] | None = None,
    target_market: TargetMarket = TargetMarket.EGYPT,
) -> list[str]:
    """Compact rewrite instructions for local lesson review (not DOCX)."""
    out: list[str] = []
    for f in scan_script_originality(
        script, source_texts=source_texts, target_market=target_market
    ):
        if f.code == "source_wording_overlap":
            out.append(
                "Rewrite from the underlying idea only — do not copy or closely "
                "paraphrase source wording/structure."
            )
        elif f.code == "distinctive_source_example":
            out.append(
                "Replace distinctive source examples with original, locally realistic ones."
            )
        elif f.code == "named_creator_imitation":
            out.append(
                "Remove named-creator imitation and catchphrases; teach in Rukn voice."
            )
        elif f.code == "article_paraphrase_tone":
            out.append(
                "Rewrite as original spoken teaching, not a paraphrased/translated article."
            )
        elif f.code == "imported_example_swap":
            out.append(
                "Swap imported US/EU examples for Egyptian/Arab market-realistic ones."
            )
        elif f.code == "originality_label_leak":
            out.append(
                "Remove internal originality/source/copyright labels from the script."
            )
    return out


def shared_ngrams_with_source(
    profile_or_script: str, source_text: str, *, min_ngram: int = 5
) -> list[str]:
    """Shared n-grams — used in tests to prove flow profiles don't leak wording."""
    return sorted(
        _ngrams(_words(source_text), min_ngram)
        & _ngrams(_words(profile_or_script), min_ngram)
    )
