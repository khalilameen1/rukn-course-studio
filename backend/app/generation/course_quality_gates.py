"""Final course-level quality gates (pre-DOCX export).

No new persona layers. Heuristic gates that may rewrite FinalCourse scripts
internally. Never emit reviews, citations, or "needs confirmation" into
script_text / DOCX.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.ai.provider import CourseBrief
from app.generation.course_map_quality import total_estimated_minutes
from app.generation.market_evergreen import (
    MARKET_EVERGREEN_DOCX_LEAKS,
    apply_market_evergreen_to_final_course,
)
from app.generation.originality_rights import (
    ORIGINALITY_DOCX_LEAKS,
    apply_originality_to_final_course,
)
from app.generation.teleprompter_checks import find_forbidden_substrings
from app.generation.web_research import RESEARCH_LEAK_SUBSTRINGS, strip_research_leaks_from_script
from app.models.enums import TargetMarket
from app.schemas.generation import CourseMap, FinalCourse, FinalReel
from app.validators.similarity import text_similarity

# V1: quality gates run silently — user progress stays on the locked vocabulary.
PROGRESS_GATES = "Rewriting final master version"
PROGRESS_GATE_PROMISE = "Rewriting final master version"
PROGRESS_GATE_LEVEL = "Rewriting final master version"
PROGRESS_GATE_RECORD = "Rewriting final master version"
PROGRESS_GATE_APPLY = "Rewriting final master version"
PROGRESS_GATE_REPEAT = "Rewriting final master version"
PROGRESS_GATE_ENDING = "Rewriting final master version"
PROGRESS_GATE_MARKET = "Rewriting final master version"
PROGRESS_GATE_EVERGREEN = "Rewriting final master version"
PROGRESS_GATE_ORIGINALITY = "Rewriting final master version"

# Written / article tone cues (Egyptian educational teleprompter context).
_WRITTEN_TONE = re.compile(
    r"(في الختام|من الجدير بالذكر|تجدر الإشارة|بناءً على ما سبق|"
    r"in conclusion|it is worth noting|furthermore|moreover|"
    r"this article|as mentioned above)",
    re.IGNORECASE,
)
_BREATHLESS_SENTENCE_WORDS = 42
_ADVANCED_TERM = re.compile(
    r"\b(ROAS|LTV|CAC|API|SDK|heuristic|stochastic|KPI|CTR|CPA)\b"
)
_PRACTICAL_CUE = re.compile(
    r"(جرّب|اطبق|طبّق|افتح|اختر|اكتب|قيس|اختبر|اعمل|try |open |measure |apply )",
    re.IGNORECASE,
)
_BEGINNER_OVEREXPLAIN = re.compile(
    r"(يعني إيه بالظبط كلمة|ببساطة شديدة جدًا|حتى الطفل يفهم)",
    re.IGNORECASE,
)


@dataclass
class GateIssue:
    gate: str
    code: str
    detail: str  # internal only — never DOCX


@dataclass
class CourseGateReport:
    issues: list[GateIssue] = field(default_factory=list)
    remediations: list[str] = field(default_factory=list)
    rebuilt_reel_ids: list[str] = field(default_factory=list)
    estimated_duration_minutes: float = 0.0
    risk_count: int = 0

    def model_dump(self) -> dict:
        return {
            "issues": [
                {"gate": i.gate, "code": i.code, "detail": i.detail} for i in self.issues
            ],
            "remediations": list(self.remediations),
            "rebuilt_reel_ids": list(self.rebuilt_reel_ids),
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "risk_count": self.risk_count,
        }


def _all_reels(course: FinalCourse) -> list[FinalReel]:
    return [r for m in course.modules for r in m.reels]


def _outcome_tokens(brief: CourseBrief) -> set[str]:
    blob = f"{brief.title} {brief.outcome} {brief.audience}"
    return {
        t.lower()
        for t in re.findall(r"[\w\u0600-\u06FF]{4,}", blob)
        if len(t) >= 4
    }


def gate_promise_fulfillment(
    course: FinalCourse, brief: CourseBrief, report: CourseGateReport
) -> FinalCourse:
    tokens = _outcome_tokens(brief)
    if not tokens:
        return course
    body = " ".join(r.script_text for r in _all_reels(course)).lower()
    hits = sum(1 for t in tokens if t in body)
    coverage = hits / max(len(tokens), 1)
    if coverage >= 0.25:
        return course
    report.issues.append(
        GateIssue(
            gate="promise",
            code="under_delivers_title_or_outcome",
            detail=(
                f"Outcome/title token coverage {coverage:.0%} — course may "
                "under-deliver the promised transformation."
            ),
        )
    )
    # Soft internal rebuild: close the promise on the last lesson (no DOCX notes).
    reels = _all_reels(course)
    if not reels:
        return course
    last = reels[-1]
    outcome = (brief.outcome or brief.title or "").strip()
    beat = (
        f"خلّينا نقف عند وعد الكورس ده بوضوح: "
        f"{outcome}. "
        f"اللي اتعلمناه لازم يوصل للنتيجة دي عمليًا، مش كعنوان بس."
    )
    if beat[:40] in (last.script_text or ""):
        return course
    new_text = f"{(last.script_text or '').rstrip()}\n{beat}"
    modules = []
    for mi, module in enumerate(course.modules):
        if mi < len(course.modules) - 1:
            modules.append(module)
            continue
        new_reels = list(module.reels)
        new_reels[-1] = last.model_copy(update={"script_text": new_text})
        modules.append(module.model_copy(update={"reels": new_reels}))
    report.remediations.append(f"promise_close:{last.reel_id}")
    report.rebuilt_reel_ids.append(last.reel_id)
    return course.model_copy(update={"modules": modules})


def gate_learner_level(
    course: FinalCourse, report: CourseGateReport
) -> None:
    reels = _all_reels(course)
    advanced_cold = 0
    overexplained = 0
    for reel in reels:
        text = reel.script_text or ""
        terms = _ADVANCED_TERM.findall(text)
        if terms and not re.search(r"(يعني|means|يعني إيه)", text):
            # acronym present with no quick gloss nearby
            advanced_cold += 1
        if _BEGINNER_OVEREXPLAIN.search(text):
            overexplained += 1
    if advanced_cold >= 2 and overexplained >= 1:
        report.issues.append(
            GateIssue(
                gate="learner_level",
                code="level_drift",
                detail=(
                    "Mix of unexplained advanced terms and over-explained "
                    "beginner padding — inconsistent learner level."
                ),
            )
        )
    elif advanced_cold >= 3:
        report.issues.append(
            GateIssue(
                gate="learner_level",
                code="missing_prerequisites",
                detail="Multiple advanced terms without quick orientation for 80% learners.",
            )
        )


def gate_recordability(course: FinalCourse, report: CourseGateReport) -> FinalCourse:
    """Rewrite scripts for teleprompter breath/spoken tone; strip leaks."""
    modules = []
    changed = False
    for module in course.modules:
        reels = []
        for reel in module.reels:
            original = reel.script_text or ""
            text = strip_research_leaks_from_script(original)
            if _WRITTEN_TONE.search(text):
                text = _WRITTEN_TONE.sub("", text)
                text = re.sub(r"\s{2,}", " ", text).strip()
                report.remediations.append(f"recordability_strip_written:{reel.reel_id}")
            # Split breathless sentences (after written-tone strip so phrases stay intact).
            sentences = re.split(r"(?<=[.!?؟۔])\s+", text)
            fixed: list[str] = []
            for sent in sentences:
                words = sent.split()
                if len(words) > _BREATHLESS_SENTENCE_WORDS:
                    mid = len(words) // 2
                    fixed.append(" ".join(words[:mid]).rstrip(",،") + ".")
                    fixed.append(" ".join(words[mid:]))
                    report.remediations.append(f"recordability_split:{reel.reel_id}")
                else:
                    fixed.append(sent)
            text = " ".join(s for s in fixed if s.strip())
            leaks = find_forbidden_substrings(text) + [
                s for s in RESEARCH_LEAK_SUBSTRINGS if s in text.lower()
            ]
            if leaks:
                text = strip_research_leaks_from_script(text)
                for leak in TELEPROMPTER_SOFT_STRIP:
                    text = re.sub(re.escape(leak), "", text, flags=re.IGNORECASE)
                report.remediations.append(f"recordability_strip_leaks:{reel.reel_id}")
            if text != original:
                changed = True
                report.rebuilt_reel_ids.append(reel.reel_id)
            reels.append(reel.model_copy(update={"script_text": text}))
        modules.append(module.model_copy(update={"reels": reels}))
    if changed:
        report.issues.append(
            GateIssue(
                gate="recordability",
                code="spoken_rewrite_applied",
                detail="Applied teleprompter spoken remediations internally.",
            )
        )
    return course.model_copy(update={"modules": modules}) if changed else course


TELEPROMPTER_SOFT_STRIP = (
    "needs confirmation",
    "needs_review",
    "critic said",
    "student asked",
    "mentor advised",
)


def gate_application(
    course: FinalCourse, brief: CourseBrief, report: CourseGateReport
) -> FinalCourse:
    """Practical courses need do-something cues; theoretical → understanding ok."""
    practical = not re.search(
        r"(theory|نظري|philosophy|تاريخ فقط)",
        f"{brief.title} {brief.outcome} {brief.special_notes or ''}",
        re.IGNORECASE,
    )
    if not practical:
        return course
    modules_out = []
    for module in course.modules:
        texts = " ".join(r.script_text for r in module.reels)
        if _PRACTICAL_CUE.search(texts):
            modules_out.append(module)
            continue
        report.issues.append(
            GateIssue(
                gate="application",
                code="module_missing_application",
                detail=f"Module '{module.title}' lacks clear apply/do steps.",
            )
        )
        if not module.reels:
            modules_out.append(module)
            continue
        # Soft internal fix: add one short practical beat to last reel only.
        last = module.reels[-1]
        addon = "جرّب الخطوة دي على وضعك الحقيقي قبل ما تعدّي."
        if addon not in (last.script_text or ""):
            new_text = f"{(last.script_text or '').rstrip()}\n{addon}"
            new_reels = list(module.reels[:-1]) + [
                last.model_copy(update={"script_text": new_text})
            ]
            modules_out.append(module.model_copy(update={"reels": new_reels}))
            report.remediations.append(f"application_add_step:{last.reel_id}")
            report.rebuilt_reel_ids.append(last.reel_id)
        else:
            modules_out.append(module)
    return course.model_copy(update={"modules": modules_out})


def gate_repetition(course: FinalCourse, report: CourseGateReport) -> FinalCourse:
    reels = _all_reels(course)
    modules_out = [
        m.model_copy(update={"reels": [r.model_copy() for r in m.reels]})
        for m in course.modules
    ]
    id_to_reel = {
        r.reel_id: (mi, ri)
        for mi, m in enumerate(modules_out)
        for ri, r in enumerate(m.reels)
    }

    for i, reel in enumerate(reels):
        opener = (reel.script_text or "").strip().split("\n")[0][:120]
        for j in range(i):
            prev = reels[j]
            prev_opener = (prev.script_text or "").strip().split("\n")[0][:120]
            if text_similarity(opener, prev_opener) >= 0.85 and len(opener) > 20:
                report.issues.append(
                    GateIssue(
                        gate="repetition",
                        code="repeated_opening",
                        detail=f"{reel.reel_id} opening echoes {prev.reel_id}.",
                    )
                )
                # Diversify later opener slightly without padding essays.
                mi, ri = id_to_reel[reel.reel_id]
                current = modules_out[mi].reels[ri]
                lines = (current.script_text or "").split("\n")
                if lines:
                    lines[0] = f"خلّينا نثبت فرق تاني: {lines[0]}"
                    new_script = "\n".join(lines)
                    modules_out[mi].reels[ri] = current.model_copy(
                        update={"script_text": new_script}
                    )
                    report.remediations.append(f"repetition_diversify:{reel.reel_id}")
                    report.rebuilt_reel_ids.append(reel.reel_id)
                break

        body = reel.script_text or ""
        for j in range(i):
            if text_similarity(body[:200], (reels[j].script_text or "")[:200]) >= 0.9:
                report.issues.append(
                    GateIssue(
                        gate="repetition",
                        code="near_duplicate_lesson",
                        detail=f"{reel.reel_id} ≈ {reels[j].reel_id}",
                    )
                )
                break

    return course.model_copy(update={"modules": modules_out})


def gate_course_ending(course: FinalCourse, report: CourseGateReport) -> FinalCourse:
    reels = _all_reels(course)
    if not reels:
        report.issues.append(
            GateIssue(gate="ending", code="empty_course", detail="No lessons to close.")
        )
        return course
    last = reels[-1]
    text = (last.script_text or "").strip()
    abrupt = len(text) < 40 or text.endswith(("...", "…", "هنكمل", "stay tuned"))
    salesy = bool(
        re.search(r"(اشترك|اشترِ|اشتري الآن|limited offer|subscribe now)", text, re.I)
    )
    fake_motiv = bool(
        re.search(r"(غيّر حياتك النهاردة|أنت البطل|believe in yourself)", text, re.I)
    )
    if abrupt or salesy or fake_motiv:
        report.issues.append(
            GateIssue(
                gate="ending",
                code="weak_ending",
                detail="Final lesson ends abruptly, salesy, or fake-motivational.",
            )
        )
        closer = (
            "كده قفلنا الرحلة دي على وعد الكورس، "
            "وجاهز تطبق اللي اتفقنا عليه في شغلك."
        )
        cleaned = re.sub(
            r"(اشترك|اشترِ|اشتري الآن|limited offer|subscribe now|"
            r"غيّر حياتك النهاردة|أنت البطل|believe in yourself).*$",
            "",
            text,
            flags=re.I | re.DOTALL,
        ).strip()
        cleaned = re.sub(
            r"اشترك(?:\s*الآن)?|اشتري الآن|subscribe now|limited offer",
            "",
            cleaned,
            flags=re.I,
        )
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" .،…")
        # Pure sales/short abrupt closers → replace with journey closer only.
        if salesy and len(cleaned) < 40:
            new_text = closer
        else:
            new_text = closer if len(cleaned) < 20 else f"{cleaned}\n{closer}"
        if new_text != text:
            modules = []
            for mi, module in enumerate(course.modules):
                if mi < len(course.modules) - 1:
                    modules.append(module)
                    continue
                new_reels = list(module.reels)
                new_reels[-1] = last.model_copy(update={"script_text": new_text})
                modules.append(module.model_copy(update={"reels": new_reels}))
            report.remediations.append(f"ending_close:{last.reel_id}")
            report.rebuilt_reel_ids.append(last.reel_id)
            return course.model_copy(update={"modules": modules})
    return course


def gate_market_and_evergreen(
    course: FinalCourse, brief: CourseBrief, report: CourseGateReport
) -> FinalCourse:
    """Egyptian/Arab market realism + evergreen/UI durability (silent rewrites)."""
    market = getattr(brief, "target_market", None) or TargetMarket.EGYPT
    updated, me_report = apply_market_evergreen_to_final_course(
        course, target_market=market
    )
    seen_codes: set[str] = set()
    for finding in me_report.findings:
        if finding.code in seen_codes:
            continue
        seen_codes.add(finding.code)
        gate = (
            "egyptian_market"
            if finding.code
            in {
                "foreign_market_assumption",
                "missing_local_context",
                "expensive_tool_assumption",
                "translated_tone",
            }
            else "evergreen"
        )
        report.issues.append(
            GateIssue(gate=gate, code=finding.code, detail=finding.detail)
        )
    for rem in sorted(set(me_report.remediations)):
        report.remediations.append(rem)

    modules = []
    for mi, module in enumerate(updated.modules):
        orig_module = course.modules[mi]
        reels = []
        for ri, reel in enumerate(module.reels):
            text = reel.script_text or ""
            for leak in MARKET_EVERGREEN_DOCX_LEAKS:
                text = re.sub(re.escape(leak), "", text, flags=re.IGNORECASE)
            text = text.strip()
            orig = orig_module.reels[ri].script_text or ""
            if text != orig:
                report.rebuilt_reel_ids.append(reel.reel_id)
                reels.append(reel.model_copy(update={"script_text": text}))
            else:
                reels.append(reel)
        modules.append(module.model_copy(update={"reels": reels}))
    return updated.model_copy(update={"modules": modules})


def gate_originality_rights(
    course: FinalCourse,
    brief: CourseBrief,
    report: CourseGateReport,
    *,
    source_texts: list[str] | None = None,
) -> FinalCourse:
    """Silent originality remediations against uploaded/web source material."""
    market = getattr(brief, "target_market", None) or TargetMarket.EGYPT
    updated, o_report = apply_originality_to_final_course(
        course, source_texts=source_texts, target_market=market
    )
    seen: set[str] = set()
    for finding in o_report.findings:
        if finding.code in seen:
            continue
        seen.add(finding.code)
        report.issues.append(
            GateIssue(
                gate="originality",
                code=finding.code,
                detail=finding.detail,
            )
        )
    for rem in sorted(set(o_report.remediations)):
        report.remediations.append(rem)

    modules = []
    for mi, module in enumerate(updated.modules):
        orig_module = course.modules[mi]
        reels = []
        for ri, reel in enumerate(module.reels):
            text = reel.script_text or ""
            for leak in ORIGINALITY_DOCX_LEAKS:
                text = re.sub(re.escape(leak), "", text, flags=re.IGNORECASE)
            text = text.strip()
            orig = orig_module.reels[ri].script_text or ""
            if text != orig:
                report.rebuilt_reel_ids.append(reel.reel_id)
                reels.append(reel.model_copy(update={"script_text": text}))
            else:
                reels.append(reel)
        modules.append(module.model_copy(update={"reels": reels}))
    return updated.model_copy(update={"modules": modules})


def _refresh_full_text(course: FinalCourse) -> FinalCourse:
    parts = [f"# {course.title}"]
    for module in course.modules:
        parts.append(f"# {module.title}")
        for reel in module.reels:
            parts.append(f"## {reel.title}")
            parts.append(reel.script_text)
    return course.model_copy(update={"full_text": "\n".join(parts)})


def run_course_quality_gates(
    *,
    final_course: FinalCourse,
    course_map: CourseMap,
    brief: CourseBrief,
    source_texts: list[str] | None = None,
) -> tuple[FinalCourse, CourseGateReport]:
    """Run all final gates; return possibly rewritten FinalCourse + report."""
    report = CourseGateReport(
        estimated_duration_minutes=round(total_estimated_minutes(course_map), 1)
    )
    course = final_course

    course = gate_promise_fulfillment(course, brief, report)
    gate_learner_level(course, report)
    course = gate_recordability(course, report)
    course = gate_application(course, brief, report)
    course = gate_repetition(course, report)
    course = gate_course_ending(course, report)
    course = gate_market_and_evergreen(course, brief, report)
    course = gate_originality_rights(
        course, brief, report, source_texts=source_texts
    )
    course = _refresh_full_text(course)

    # Risk count = distinct issue codes (excluding soft remediations-only noise).
    report.risk_count = len(
        {
            i.code
            for i in report.issues
            if i.code
            not in {"spoken_rewrite_applied"}  # remediation ack, not a blocker signal
        }
    )
    # Deduplicate rebuilt ids
    report.rebuilt_reel_ids = sorted(set(report.rebuilt_reel_ids))
    return course, report


def format_handoff_status(
    *,
    lessons: int,
    estimated_minutes: float,
    complete: bool,
    risk_count: int = 0,
) -> str:
    """Coarse user-facing handoff — V1: status only, no internal flag counts."""
    del risk_count  # retained for call-site compatibility; never shown to users
    state = "complete" if complete else "partial"
    mins = int(round(estimated_minutes)) if estimated_minutes else 0
    duration = f" · ~{mins} min" if mins else ""
    return f"Course generated · {lessons} lessons{duration} · {state}"
