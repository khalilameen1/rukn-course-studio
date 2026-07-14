"""Mixed-quality previous AI course draft handling.

Previous AI-generated course drafts are neither worthless nor quality
references. Every segment is evaluated against the *current* course promise
(Course Promise Relevance Gate) before it can become a candidate. Off-promise
modules, dumb reels, and tangents are discarded. Survivors are candidate_only
and must be rebuilt in ROKN quality — never copied.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from app.services.chunking import chunk_text

MIXED_QUALITY_AI_COURSE_DRAFT = "mixed_quality_ai_course_draft"
LEGACY_OLD_COURSE = "old_course"

MIXED_QUALITY_DRAFT_CATEGORIES = frozenset(
    {MIXED_QUALITY_AI_COURSE_DRAFT, LEGACY_OLD_COURSE}
)

MIXED_QUALITY_PROMPT_LABEL = (
    "This is a mixed-quality previous AI-generated course draft. It may "
    "contain useful candidates, irrelevant modules, dumb reels, side details, "
    "and defects. Evaluate every segment against the current course promise "
    "before using it. Discard off-promise modules and irrelevant reels even "
    "if they are well-written. Extract only useful candidate ideas, then "
    "rebuild from scratch in ROKN quality."
)

# Quality / delivery defect markers.
_WEAK_HOOK_RE = re.compile(
    r"(?i)("
    r"in this video|before we start|stay until the end|don't skip|"
    r"في الفيديو ده|قبل ما نبدأ|شوف لحد الآخر|لو وصلت للنهاية|"
    r"click like|subscribe now|اضغط لايك"
    r")"
)
_ARTIFICIAL_LOOP_RE = re.compile(
    r"(?i)("
    r"as we said|as mentioned earlier|let'?s go back|coming back to|"
    r"زي ما قولنا|تعالى نرجع|نرجع تاني|مرة تانية هنقول|"
    r"remember what we covered|recap of what we just|"
    r"fake tension|you won'?t believe|shocking secret"
    r")"
)
_FILLER_RE = re.compile(
    r"(?i)("
    r"in today'?s digital world|let'?s dive in|without further ado|"
    r"it'?s important to note|as we all know|in conclusion|"
    r"moreover|furthermore|needless to say|"
    r"في الحقيقة|يعني باختصار|خلينا نقول|بصراحة بقى"
    r")"
)
_GENERIC_AI_RE = re.compile(
    r"(?i)("
    r"unlock your potential|game[- ]changer|leverage synergies|"
    r"holistic approach|cutting[- ]edge|delve into|believe in yourself|"
    r"manifest success|mindset is everything|"
    r"في عالمنا اليوم|حلول متكاملة|بأسلوب مبسط وفعال|"
    r"كل واحد فينا يقدر|ابدأ رحلتك"
    r")"
)
_MOTIVATIONAL_FILLER_RE = re.compile(
    r"(?i)("
    r"you(?:'re| are) enough|dream big|never give up|hustle harder|"
    r"success is a journey|inspiration|motivational|"
    r"التحفيز|ؤمن بنفسك|لا تستسلم|النجاح مشوار"
    r")"
)
_CLAIMISH_RE = re.compile(
    r"(?i)("
    r"\d+\s*%|always works|guaranteed|never fails|officially|"
    r"button|click here|ui\b|dashboard|meta ads|facebook ads|"
    r"دائماً|دائما|مضمون|اضغط على|زر ال"
    r")"
)
_OBJECTION_RE = re.compile(
    r"(?i)("
    r"but what if|learner might|students often|common mistake|"
    r"people think|objection|myth|"
    r"طبعا هتقول|هتقولي|ناس كتير بتفتكر|غلط شائع|اعتراض"
    r")"
)
_PRACTICAL_RE = re.compile(
    r"(?i)("
    r"step\s*\d|workflow|checklist|do this|warning:|actionable|"
    r"خطوة|اعمل كده|تحذير|مسار العمل"
    r")"
)
_EXAMPLE_RE = re.compile(
    r"(?i)("
    r"for example|e\.g\.|imagine|suppose|case study|"
    r"مثلاً|مثلا|تخيّل|تخيل لو|حالة"
    r")"
)
_SIDE_DETAIL_RE = re.compile(
    r"(?i)("
    r"history of|founded in|etymology|academic theory|literature review|"
    r"nice to know|fun fact|background trivia|platform history|"
    r"تاريخ|نظرية أكاديمية|معلومة جانبية|للمعرفة فقط"
    r")"
)
_MODULE_HEADING_RE = re.compile(
    r"(?i)^\s*(?:#{1,3}\s*)?(?:module|الوحدة|باب)\s*[\d\-.:]*\s*(.+)?$"
)
_LESSON_HEADING_RE = re.compile(
    r"(?i)^\s*(?:#{1,3}\s*)?(?:lesson|reel|الدرس|حصة)\s*[\d\-.:]*\s*(.+)?$"
)

# Domain detours: count as off-promise when promise tokens do not include them.
_DETOUR_TOPICS: dict[str, re.Pattern[str]] = {
    "branding_theory": re.compile(
        r"(?i)\b(brand(?:ing)? theory|brand identity framework|"
        r"visual identity system|brand guidelines|"
        r"نظرية البراند|هوية بصرية عامة)\b"
    ),
    "freelancing_psychology": re.compile(
        r"(?i)\b(freelance(?:r)? psychology|client mindset coaching|"
        r"freelancer soft skills|"
        r"سيكولوجية الفريلانس|علم نفس الفريلانسر)\b"
    ),
    "productivity_tools": re.compile(
        r"(?i)\b(productivity tools?|notion second brain|time[- ]blocking apps|"
        r"أدوات الإنتاجية|نوتشن)\b"
    ),
    "general_motivation": re.compile(
        r"(?i)\b(general motivation module|life coaching basics|"
        r"وحدة التحفيز العام)\b"
    ),
    "unrelated_sales_theory": re.compile(
        r"(?i)\b(spin selling theory|challenger sale framework|"
        r"نظرية المبيعات العامة)\b"
    ),
}

_WORD_RE = re.compile(r"[\w\u0600-\u06FF]{3,}", re.UNICODE)
_STOP = {
    "the", "and", "for", "with", "this", "that", "from", "your", "you",
    "are", "was", "will", "have", "has", "not", "but", "about", "into",
    "على", "من", "في", "الى", "إلى", "هذا", "هذه", "التي", "الذي",
}


@dataclass
class CoursePromise:
    """Current course brief used by the Relevance Gate."""

    title: str = ""
    audience: str = ""
    outcome: str = ""
    target_market: str = ""
    course_map_text: str = ""
    special_notes: str = ""

    def as_dict(self) -> dict[str, str]:
        return {k: str(v or "") for k, v in asdict(self).items()}

    def blob(self) -> str:
        return " ".join(
            [
                self.title,
                self.audience,
                self.outcome,
                self.target_market,
                self.course_map_text,
                self.special_notes,
            ]
        )


def is_mixed_quality_draft_category(category: str | None) -> bool:
    return (category or "").strip() in MIXED_QUALITY_DRAFT_CATEGORIES


def course_promise_from_course(course: Any | None) -> CoursePromise:
    if course is None:
        return CoursePromise()
    market = getattr(course, "target_market", None)
    market_val = market.value if hasattr(market, "value") else str(market or "")
    return CoursePromise(
        title=str(getattr(course, "title", "") or ""),
        audience=str(getattr(course, "audience", "") or ""),
        outcome=str(getattr(course, "outcome", "") or ""),
        target_market=market_val,
        course_map_text=str(getattr(course, "manual_map_text", "") or ""),
        special_notes=str(getattr(course, "special_notes", "") or ""),
    )


def _tokens(text: str) -> set[str]:
    return {
        t.lower()
        for t in _WORD_RE.findall(text or "")
        if t.lower() not in _STOP and len(t) >= 3
    }


def _short_idea(text: str, limit: int = 180) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _uniq(items: list[str], limit: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def _split_segments(text: str) -> list[dict[str, str]]:
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    chunks = chunk_text(cleaned)
    segments: list[dict[str, str]] = []
    current_module = ""
    for ch in chunks:
        body = (ch.text or "").strip()
        if not body:
            continue
        heading = (ch.heading or f"segment_{ch.index + 1}").strip()
        mod_m = _MODULE_HEADING_RE.match(heading) or _MODULE_HEADING_RE.match(body.split("\n", 1)[0])
        if mod_m or re.search(r"(?i)\bmodule\s+\d", heading):
            current_module = heading.split("::", 1)[0][:160]
        paras = [p.strip() for p in re.split(r"\n\s*\n+", body) if p.strip()]
        if not paras:
            paras = [body]
        for i, para in enumerate(paras):
            h = heading
            if len(paras) > 1:
                h = f"{heading}::{i + 1}"
            segments.append(
                {
                    "heading": h[:160],
                    "text": para[:1200],
                    "module": current_module,
                }
            )
    if not segments:
        lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
        buf: list[str] = []
        for ln in lines:
            buf.append(ln)
            if len(" ".join(buf)) >= 280:
                segments.append(
                    {
                        "heading": f"block_{len(segments) + 1}",
                        "text": " ".join(buf)[:1200],
                        "module": "",
                    }
                )
                buf = []
        if buf:
            segments.append(
                {
                    "heading": f"block_{len(segments) + 1}",
                    "text": " ".join(buf)[:1200],
                    "module": "",
                }
            )
    return segments[:100]


def classify_relevance(text: str, promise: CoursePromise) -> str:
    """core_to_promise | useful_supporting | adjacent_but_optional |
    tangent | off_promise | harmful_distraction
    """
    t = text or ""
    if not t.strip():
        return "tangent"

    promise_tokens = _tokens(promise.blob())
    seg_tokens = _tokens(t)
    overlap = len(promise_tokens & seg_tokens) if promise_tokens else 0
    overlap_ratio = (overlap / max(len(seg_tokens), 1)) if seg_tokens else 0.0

    # Explicit domain detours not present in the current promise.
    for name, pat in _DETOUR_TOPICS.items():
        if pat.search(t):
            # If promise itself is about that topic, allow it.
            if pat.search(promise.blob()):
                break
            if overlap_ratio < 0.18:
                return "off_promise"

    if _MOTIVATIONAL_FILLER_RE.search(t) and not _PRACTICAL_RE.search(t):
        if overlap_ratio < 0.12:
            return "harmful_distraction"

    if not promise_tokens:
        # No brief yet — be conservative: supporting at best, never assume core.
        if _PRACTICAL_RE.search(t) or _OBJECTION_RE.search(t):
            return "useful_supporting"
        return "adjacent_but_optional"

    if overlap >= 3 or overlap_ratio >= 0.22:
        if _PRACTICAL_RE.search(t) or _OBJECTION_RE.search(t) or overlap >= 5:
            return "core_to_promise"
        return "useful_supporting"

    if overlap >= 1 or overlap_ratio >= 0.08:
        if _SIDE_DETAIL_RE.search(t) and not (
            _PRACTICAL_RE.search(t) or _OBJECTION_RE.search(t)
        ):
            return "adjacent_but_optional"
        return "useful_supporting"

    # Low overlap: side trivia / filler are tangents or distractions.
    if _SIDE_DETAIL_RE.search(t) and not _PRACTICAL_RE.search(t):
        return "tangent"
    if _GENERIC_AI_RE.search(t) or _FILLER_RE.search(t):
        return "harmful_distraction"
    return "off_promise" if len(seg_tokens) > 25 else "tangent"


def is_dumb_reel(text: str, *, relevance: str) -> bool:
    """Obvious / filler / fake-tension / shallow / off-promise reels."""
    t = text or ""
    words = len(_WORD_RE.findall(t))
    if relevance in {"off_promise", "harmful_distraction", "tangent"}:
        return True
    if words < 28 and not (_PRACTICAL_RE.search(t) or _OBJECTION_RE.search(t)):
        return True
    defect = sum(
        [
            bool(_WEAK_HOOK_RE.search(t)),
            bool(_ARTIFICIAL_LOOP_RE.search(t)),
            bool(_FILLER_RE.search(t)),
            bool(_GENERIC_AI_RE.search(t)),
            bool(_MOTIVATIONAL_FILLER_RE.search(t)),
        ]
    )
    if defect >= 2:
        return True
    if defect >= 1 and words < 55 and not _PRACTICAL_RE.search(t):
        return True
    if _MOTIVATIONAL_FILLER_RE.search(t) and not _PRACTICAL_RE.search(t):
        return True
    return False


def classify_segment_decision(
    text: str,
    *,
    relevance: str,
) -> str:
    """Segment decision after relevance gate.

    keep_candidate | rebuild_candidate | optional_candidate |
    discard_irrelevant | discard_low_quality | discard_repetitive |
    discard_outdated | discard_harmful_distraction
    """
    t = text or ""
    if relevance == "harmful_distraction":
        return "discard_harmful_distraction"
    if relevance in {"off_promise", "tangent"}:
        return "discard_irrelevant"
    # Relevant but dumb/filler writing → rebuild (do not keep as a lesson as-is).
    if is_dumb_reel(t, relevance=relevance):
        if relevance in {"core_to_promise", "useful_supporting"}:
            return "rebuild_candidate"
        return "discard_low_quality"

    weak = bool(_WEAK_HOOK_RE.search(t))
    loop = bool(_ARTIFICIAL_LOOP_RE.search(t))
    filler = bool(_FILLER_RE.search(t))
    generic = bool(_GENERIC_AI_RE.search(t))
    claimish = bool(_CLAIMISH_RE.search(t))
    objection = bool(_OBJECTION_RE.search(t))
    practical = bool(_PRACTICAL_RE.search(t))
    example = bool(_EXAMPLE_RE.search(t))
    word_count = len(_WORD_RE.findall(t))
    defect_hits = sum([weak, loop, filler, generic])

    if _ARTIFICIAL_LOOP_RE.search(t) and "as we said" in t.lower():
        # Repeated rehash without new action.
        if not practical:
            return "discard_repetitive"

    if claimish and re.search(r"(?i)button|click|زر|dashboard|ui\b", t):
        # Relevant but tool UI may be outdated — still can rebuild after verify.
        if relevance in {"core_to_promise", "useful_supporting"}:
            return "rebuild_candidate"
        return "discard_outdated"

    if relevance == "adjacent_but_optional":
        if practical or objection:
            # Trim side-detail heavy text to optional idea only.
            return "optional_candidate"
        return "discard_irrelevant"

    # Relevant path
    if defect_hits >= 1 or weak or loop or generic:
        return "rebuild_candidate"
    if objection or (practical and not weak):
        return "keep_candidate"
    if example or word_count >= 25:
        return "rebuild_candidate"
    return "discard_low_quality"


# Back-compat alias used by earlier tests / callers.
def classify_segment(text: str, promise: CoursePromise | None = None) -> str:
    """Quality-oriented label; when promise given, returns decision enum."""
    if promise is None:
        # Legacy quality-only labels for unit tests that do not pass a promise.
        t = text or ""
        if not t.strip():
            return "discard"
        weak = bool(_WEAK_HOOK_RE.search(t))
        loop = bool(_ARTIFICIAL_LOOP_RE.search(t))
        filler = bool(_FILLER_RE.search(t))
        generic = bool(_GENERIC_AI_RE.search(t))
        claimish = bool(_CLAIMISH_RE.search(t))
        objection = bool(_OBJECTION_RE.search(t))
        practical = bool(_PRACTICAL_RE.search(t))
        example = bool(_EXAMPLE_RE.search(t))
        word_count = len(_WORD_RE.findall(t))
        defect_hits = sum([weak, loop, filler, generic])
        if defect_hits >= 2 and word_count < 60:
            return "discard"
        if weak and word_count < 40:
            return "discard"
        if loop and not (objection or practical or example):
            return "discard"
        if filler and word_count < 35 and not (objection or practical):
            return "discard"
        if claimish and not (objection and practical):
            return "verify_before_use"
        if objection or (practical and not weak):
            return "keep_candidate"
        if example or (word_count >= 40 and defect_hits >= 1):
            return "rebuild_candidate"
        if word_count >= 25:
            return "rebuild_candidate"
        return "discard"
    relevance = classify_relevance(text, promise)
    return classify_segment_decision(text, relevance=relevance)


def _trim_side_details(text: str) -> str:
    """Keep supporting idea; drop long academic / trivia detours."""
    parts = [p.strip() for p in re.split(r"(?<=[.!?۔؟])\s+", text or "") if p.strip()]
    kept: list[str] = []
    for sent in parts:
        if _SIDE_DETAIL_RE.search(sent) and not (
            _PRACTICAL_RE.search(sent) or _OBJECTION_RE.search(sent)
        ):
            continue
        if _MOTIVATIONAL_FILLER_RE.search(sent) and not _PRACTICAL_RE.search(sent):
            continue
        kept.append(sent)
    if not kept:
        return _short_idea(text, 140)
    return _short_idea(" ".join(kept), 200)


def build_mixed_draft_memory(
    *,
    source_hash: str,
    text: str,
    title: str = "Mixed-quality AI course draft",
    course_promise: CoursePromise | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Process once: relevance gate → decisions → candidate bags."""
    if isinstance(course_promise, dict):
        promise = CoursePromise(**{
            k: course_promise.get(k, "")
            for k in (
                "title",
                "audience",
                "outcome",
                "target_market",
                "course_map_text",
                "special_notes",
            )
        })
    elif isinstance(course_promise, CoursePromise):
        promise = course_promise
    else:
        promise = CoursePromise()

    segments = _split_segments(text)
    classified: list[dict[str, str]] = []
    core_candidates: list[str] = []
    supporting_candidates: list[str] = []
    optional_candidates: list[str] = []
    rebuild_candidates: list[str] = []
    discarded_off_promise_modules: list[str] = []
    discarded_tangents: list[str] = []
    discarded_dumb_reels: list[str] = []
    repeated_bad_patterns: list[str] = []
    useful_ideas_to_verify: list[str] = []
    examples_to_rebuild: list[str] = []
    map_hints_not_authority: list[str] = []
    discard_patterns: list[str] = []
    good_objections: list[str] = []
    useful_candidates: list[str] = []  # back-compat alias bag

    module_relevance: dict[str, list[str]] = {}
    discard_pattern_counts: dict[str, int] = {}

    for seg in segments:
        body = seg["text"]
        heading = seg["heading"]
        module = seg.get("module") or ""
        relevance = classify_relevance(body, promise)
        decision = classify_segment_decision(body, relevance=relevance)
        classified.append(
            {
                "heading": heading,
                "module": module,
                "relevance": relevance,
                "decision": decision,
                "preview": _short_idea(body, 100),
            }
        )
        if module:
            module_relevance.setdefault(module, []).append(relevance)

        idea = _short_idea(body)

        if decision == "discard_harmful_distraction":
            discarded_dumb_reels.append(f"harmful: {idea[:100]}")
            discard_pattern_counts["harmful_distraction"] = (
                discard_pattern_counts.get("harmful_distraction", 0) + 1
            )
            continue
        if decision == "discard_irrelevant":
            if relevance == "off_promise":
                discarded_tangents.append(f"off_promise: {idea[:100]}")
            else:
                discarded_tangents.append(f"tangent: {idea[:100]}")
            continue
        if decision == "discard_low_quality":
            discarded_dumb_reels.append(idea[:120])
            discard_pattern_counts["dumb_reel"] = discard_pattern_counts.get("dumb_reel", 0) + 1
            continue
        if decision == "discard_repetitive":
            discard_patterns.append(f"repetitive: {idea[:100]}")
            discard_pattern_counts["repetitive"] = discard_pattern_counts.get("repetitive", 0) + 1
            continue
        if decision == "discard_outdated":
            discard_patterns.append(f"outdated_ui: {idea[:100]}")
            useful_ideas_to_verify.append(idea)
            continue

        trimmed = _trim_side_details(body)

        if decision == "optional_candidate":
            optional_candidates.append(trimmed)
            continue

        if decision == "rebuild_candidate":
            rebuild_candidates.append(trimmed)
            if _EXAMPLE_RE.search(body):
                examples_to_rebuild.append("Rebuild (do not copy): " + _short_idea(trimmed, 140))
            if relevance == "core_to_promise" and heading:
                map_hints_not_authority.append(heading.split("::", 1)[0][:120])
            if _CLAIMISH_RE.search(body):
                useful_ideas_to_verify.append(trimmed)
            useful_candidates.append(trimmed)
            continue

        # keep_candidate
        if relevance == "core_to_promise":
            core_candidates.append(trimmed)
        else:
            supporting_candidates.append(trimmed)
        useful_candidates.append(trimmed)
        if _OBJECTION_RE.search(body):
            good_objections.append(trimmed)
        if _EXAMPLE_RE.search(body):
            examples_to_rebuild.append("Rebuild (do not copy): " + _short_idea(trimmed, 140))
        if heading and relevance in {"core_to_promise", "useful_supporting"}:
            map_hints_not_authority.append(heading.split("::", 1)[0][:120])
        if _CLAIMISH_RE.search(body):
            useful_ideas_to_verify.append(trimmed)

    # Module-level pruning: entire modules that are mostly off_promise.
    for mod, rels in module_relevance.items():
        if not mod:
            continue
        off = sum(1 for r in rels if r in {"off_promise", "harmful_distraction", "tangent"})
        if rels and off / len(rels) >= 0.6:
            discarded_off_promise_modules.append(
                f"discarded_off_promise: {mod}"
            )
            # Strip any map hints that came from that module.
            map_hints_not_authority = [
                h for h in map_hints_not_authority if mod not in h and h != mod
            ]

    for pattern, count in sorted(discard_pattern_counts.items(), key=lambda x: -x[1]):
        if count >= 1:
            repeated_bad_patterns.append(f"{pattern} (x{count})")

    creator_warnings = [
        "Course Promise Relevance Gate applied — off-promise modules/reels discarded.",
        "All extractions are candidate_only — not final authority.",
        "Do not copy wording, hooks, loops, structure, or examples.",
        "Old draft must not dictate module/lesson count, order, depth, hooks, or ending.",
        "Rebuild final course map from current promise + grounded sources + ROKN rules.",
        "Important claims require grounding outside this draft.",
    ]

    return {
        "source_hash": source_hash,
        "title": title,
        "kind": "mixed_draft_memory",
        "candidate_only": True,
        "not_quality_reference": True,
        "not_worthless": True,
        "prompt_label": MIXED_QUALITY_PROMPT_LABEL,
        "current_course_promise": promise.as_dict(),
        "segment_count": len(segments),
        "segment_classifications": classified[:50],
        "core_candidates": _uniq(core_candidates, 20),
        "supporting_candidates": _uniq(supporting_candidates, 16),
        "optional_candidates": _uniq(optional_candidates, 10),
        "rebuild_candidates": _uniq(rebuild_candidates, 20),
        # Back-compat bags for earlier snippet/tests
        "useful_candidates": _uniq(useful_candidates, 24),
        "good_objections": _uniq(good_objections, 12),
        "discarded_off_promise_modules": _uniq(discarded_off_promise_modules, 12),
        "discarded_tangents": _uniq(discarded_tangents, 16),
        "discarded_dumb_reels": _uniq(discarded_dumb_reels, 16),
        "repeated_bad_patterns": _uniq(repeated_bad_patterns, 12),
        "useful_ideas_to_verify": _uniq(useful_ideas_to_verify, 16),
        "unsupported_claim_candidates": _uniq(useful_ideas_to_verify, 16),
        "examples_to_rebuild": _uniq(examples_to_rebuild, 12),
        "map_hints_not_authority": _uniq(map_hints_not_authority, 16),
        "discard_patterns": _uniq(discard_patterns + discarded_tangents[:4], 16),
        # Back-compat alias for earlier tests / snippet consumers
        "possible_topic_inventory": _uniq(map_hints_not_authority, 20),
        "creator_warnings": creator_warnings,
        "processed_once": True,
    }


def format_mixed_draft_snippet(memory: dict[str, Any], *, max_chars: int = 3200) -> str:
    """Compact Mixed Draft Memory for prompts — never the full source text."""
    md = memory.get("mixed_draft_memory") if "mixed_draft_memory" in memory else memory
    if not isinstance(md, dict):
        return MIXED_QUALITY_PROMPT_LABEL

    parts: list[str] = [MIXED_QUALITY_PROMPT_LABEL]
    parts.append(
        "Status: candidate_only=true; not_quality_reference=true; "
        "course_promise_relevance_gate=applied; old_map_not_authority=true."
    )
    promise = md.get("current_course_promise") or {}
    if isinstance(promise, dict) and any(promise.values()):
        parts.append(
            "Current course promise (authority for relevance):\n"
            f"- title: {promise.get('title') or ''}\n"
            f"- audience: {promise.get('audience') or ''}\n"
            f"- outcome: {promise.get('outcome') or ''}\n"
            f"- market: {promise.get('target_market') or ''}"
        )

    def _bag(label: str, items: list[Any], n: int = 6) -> None:
        cleaned = [str(x).strip() for x in (items or []) if str(x).strip()]
        if cleaned:
            parts.append(f"{label}:\n- " + "\n- ".join(cleaned[:n]))

    _bag("Core candidates (rebuild in ROKN; do not copy)", md.get("core_candidates") or [])
    _bag("Supporting candidates", md.get("supporting_candidates") or md.get("useful_candidates") or [])
    _bag("Optional candidates (use only if non-bloating)", md.get("optional_candidates") or [])
    _bag("Rebuild candidates (intent only)", md.get("rebuild_candidates") or [])
    _bag("Examples to rebuild (never verbatim)", md.get("examples_to_rebuild") or [])
    _bag("Map hints (NOT authority — do not copy module order/count)", md.get("map_hints_not_authority") or [])
    _bag("Verify before use", md.get("useful_ideas_to_verify") or md.get("unsupported_claim_candidates") or [])
    _bag("Discarded off-promise modules", md.get("discarded_off_promise_modules") or [], n=5)
    _bag("Discarded tangents", md.get("discarded_tangents") or [], n=4)
    _bag("Discarded dumb reels", md.get("discarded_dumb_reels") or [], n=4)
    _bag("Repeated bad patterns", md.get("repeated_bad_patterns") or [], n=4)
    warnings = md.get("creator_warnings") or []
    if warnings:
        parts.append("Creator warnings:\n- " + "\n- ".join(str(w) for w in warnings[:5]))

    text = "\n\n".join(parts).strip()
    if len(text) > max_chars:
        return text[: max_chars - 1].rstrip() + "…"
    return text
