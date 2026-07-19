"""Egyptian Market Reality + Evergreen Course Design (no new personas).

Heuristics used by:
- prompt guidance (compile_market_guidance)
- course map local review feedback
- per-lesson local review / silent rewrite
- final course quality gates

Never emit market analysis notes, evergreen review notes, or gate labels into
script_text / DOCX. Silent influence only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models.enums import TargetMarket
from app.schemas.generation import CourseMap, FinalCourse

# Forbidden in DOCX (internal gate notes leaking).
MARKET_EVERGREEN_DOCX_LEAKS: tuple[str, ...] = (
    "market analysis",
    "evergreen review",
    "egyptian market gate",
    "evergreen gate",
    "target_market note",
    "ui teaching note",
)

# --- Fragile / short-expiry cues --------------------------------------------
_FRAGILE_UI = re.compile(
    r"("
    r"top\s*left|top\s*right|bottom\s*left|bottom\s*right|"
    r"blue\s+button|red\s+button|green\s+button|"
    r"click\s+the\s+\w+\s+button|"
    r"go\s+to\s+settings\s*,?\s*then|"
    r"settings\s*→\s*|settings\s*>\s*|settings\s*,\s*then|"
    r"الزر\s+(الأزرق|الأيسر|الأيمن)|أعلى\s+يسار|أعلى\s+يمين|"
    r"من\s+قائمة\s+settings\s+ثم|"
    r"then\s+advanced\s+then\s+this\s+exact"
    r")",
    re.IGNORECASE,
)

_FRAGILE_NUMBERS = re.compile(
    r"("
    r"in\s+20\d{2}\b|as\s+of\s+20\d{2}\b|"
    r"currently\s+the\s+price\s+is|"
    r"the\s+price\s+is\s+\$?\d|"
    r"costs?\s+\$\d{2,}|"
    r"average\s+salary\s+is|"
    r"salary\s+is\s+\$?\d|"
    r"meta\s+now\s+does|"
    r"you\s+will\s+find\s+the\s+button|"
    r"الراتب\s+(المتوسط\s+)?هو|"
    r"السعر\s+حالياً|"
    r"في\s+سنة\s+20\d{2}|"
    r"متوسط\s+المرتب"
    r")",
    re.IGNORECASE,
)

_BUTTON_CLICK_HEAVY = re.compile(
    r"("
    r"(click|press|tap)\s+(the\s+)?\w+\s+(button|tab|menu)|"
    r"اضغط\s+على\s+الزر|"
    r"ثم\s+اضغط|"
    r"go\s+to\s+[\w\s]+then\s+[\w\s]+then"
    r")",
    re.IGNORECASE,
)

# --- Foreign / translated US-EU market cues ---------------------------------
_FOREIGN_MARKET = re.compile(
    r"("
    r"silicon\s+valley|series\s+[abc]\b|venture\s+capital|\bVC\s+funding|"
    r"\b401\(k\)|\bIRS\b|ZIP\s*code|social\s+security\s+number|"
    r"fortune\s+500|YC\s+startup|yc\s+batch|"
    r"\$10,?000\s+ad\s+budget|ten\s+thousand\s+dollar\s+budget|"
    r"american\s+client|US\s+clients?\b|european\s+enterprise|"
    r"hubspot\s+enterprise|salesforce\s+enterprise|"
    r"linkedin\s+inmail\s+as\s+primary|"
    r"سوق\s+(أمريكا|الولايات)|عميل\s+أمريكي"
    r")",
    re.IGNORECASE,
)

_TRANSLATED_TONE = re.compile(
    r"("
    r"\bleverage\b|\bsynergies\b|\bcircle\s+back\b|"
    r"\bit\s+is\s+worth\s+noting\b|\bfurthermore\b|\bmoreover\b|"
    r"\bin\s+conclusion\b|\bthis\s+article\b|"
    r"game[\s-]?changer\s+in\s+the\s+marketplace|"
    r"disrupt\s+the\s+industry|"
    r"من\s+الجدير\s+بالذكر|تجدر\s+الإشارة|بناءً\s+على\s+ما\s+سبق"
    r")",
    re.IGNORECASE,
)

_EXPENSIVE_TOOL_ASSUME = re.compile(
    r"("
    r"you\s+(must|need\s+to)\s+buy\s+(hubspot|salesforce|marketo|adobe\s+experience)|"
    r"enterprise\s+only\s+tool|"
    r"اشترِ?\s+(hubspot|salesforce)\s+(enterprise|premium)"
    r")",
    re.IGNORECASE,
)

_LOCAL_CUE = re.compile(
    r"("
    r"whatsapp|فيسبوك|انستجرام|instagram|facebook|"
    r"عميل\s+مصري|محل|عيادة|مطعم|فريلانسر|كاش|فودافون\s*كاش|"
    r"إحالة|ثقة|تفاوض|ورشة|سنتر\s+تدريب|"
    r"egyptian|cairo|giza|arab\s+client"
    r")",
    re.IGNORECASE,
)

_PRINCIPLE_CUE = re.compile(
    r"("
    r"القاعدة|المهم\s+إنك|ابحث\s+عن|لو\s+الواجهة\s+اتغيرت|"
    r"look\s+for|search\s+for|the\s+idea\s+is|"
    r"principle|decision\s+rule|what\s+you.?re\s+trying|"
    r"راجع\s+السعر\s+الحالي|من\s+الموقع\s+الرسمي"
    r")",
    re.IGNORECASE,
)

_EVERGREEN_UI_REWRITE = (
    "دور على زر إنشاء الحملة أو اللي بيعمل نفس الفكرة. "
    "مكانه ممكن يتغير، المهم تبدأ حملة جديدة، تختار الهدف، "
    "وتدخل إعدادات مجموعة الإعلانات."
)

_EVERGREEN_PRICE_REWRITE = (
    "راجع السعر الحالي من الموقع الرسمي وقت ما تحتاج — "
    "متبنيش القرار على رقم ثابت في الكورس."
)

_LOCAL_EXAMPLE_BEAT = (
    "خلّي المثال من واقع قريب: محل أو عيادة أو فريلانسر بيشتغل "
    "بميزانية محدودة، وبيتواصل مع العميل على واتساب وفيسبوك."
)


@dataclass
class MarketEvergreenFinding:
    code: str
    detail: str  # internal only


@dataclass
class MarketEvergreenReport:
    findings: list[MarketEvergreenFinding] = field(default_factory=list)
    remediations: list[str] = field(default_factory=list)

    @property
    def codes(self) -> set[str]:
        return {f.code for f in self.findings}


def compile_market_guidance(target_market: TargetMarket | str) -> str:
    """Compact runtime guidance injected beside the canonical standard."""
    market = (
        target_market
        if isinstance(target_market, TargetMarket)
        else TargetMarket(str(target_market))
    )
    evergreen = (
        "EVERGREEN: Prefer principles, decision rules, and workflows that survive "
        "UI updates. Do not depend on exact salaries, prices, dates, temporary "
        "stats, or button positions. Teach what to look for and how to verify "
        "current official docs/pricing. Demos may use today's UI but must not "
        "be button-click-only tutorials. Keep wording natural — avoid disclaimer spam."
    )
    if market == TargetMarket.GLOBAL:
        return (
            "TARGET_MARKET=global. Avoid over-localizing to Egypt, but never sound "
            "like a literal US/EU translation. Clean spoken Egyptian Arabic still "
            "applies unless the user asked otherwise.\n" + evergreen
        )
    if market == TargetMarket.CUSTOM:
        return (
            "TARGET_MARKET=custom. Follow course special_notes / brief for market. "
            "Still avoid literal translation tone and fragile short-expiry facts.\n"
            + evergreen
        )
    region = "Egypt" if market == TargetMarket.EGYPT else "Arab markets"
    return (
        f"TARGET_MARKET={market.value}. Default practical reality: learner in "
        f"{region}; mostly local/Arab clients; lower budgets than US/EU; "
        "WhatsApp/Facebook/Instagram/referrals/trust/negotiation matter. "
        "Examples: shops, freelancers, clinics, restaurants, real estate, "
        "training centers, local service providers. Do not assume US startup "
        "tools/budgets/salaries unless the topic requires it. Clean Egyptian "
        "Arabic — market realism, not fake street slang.\n" + evergreen
    )


def scan_script_market_evergreen(
    text: str,
    *,
    target_market: TargetMarket = TargetMarket.EGYPT,
) -> list[MarketEvergreenFinding]:
    findings: list[MarketEvergreenFinding] = []
    if not text:
        return findings
    if _FRAGILE_UI.search(text):
        findings.append(
            MarketEvergreenFinding(
                "fragile_ui_location",
                "Fragile UI button/menu location — rephrase to principle + what to look for.",
            )
        )
    if _FRAGILE_NUMBERS.search(text):
        findings.append(
            MarketEvergreenFinding(
                "short_lived_fact",
                "Exact short-lived price/salary/date/stat — evergreen rewrite.",
            )
        )
    click_hits = len(_BUTTON_CLICK_HEAVY.findall(text))
    if click_hits >= 2 and not _PRINCIPLE_CUE.search(text):
        findings.append(
            MarketEvergreenFinding(
                "button_click_tutorial",
                "Lesson is mostly button-click steps without durable principles.",
            )
        )
    if _TRANSLATED_TONE.search(text):
        findings.append(
            MarketEvergreenFinding(
                "translated_tone",
                "Sounds like translated / article English — rewrite spoken and local.",
            )
        )
    localizing = target_market in (TargetMarket.EGYPT, TargetMarket.ARAB_MARKET)
    if localizing and _FOREIGN_MARKET.search(text):
        findings.append(
            MarketEvergreenFinding(
                "foreign_market_assumption",
                "Assumes US/EU market behavior or examples — localize.",
            )
        )
    if localizing and _EXPENSIVE_TOOL_ASSUME.search(text):
        findings.append(
            MarketEvergreenFinding(
                "expensive_tool_assumption",
                "Pushes expensive foreign tools without local justification.",
            )
        )
    if localizing and len(text) > 120 and not _LOCAL_CUE.search(text):
        if _FOREIGN_MARKET.search(text) or _TRANSLATED_TONE.search(text):
            findings.append(
                MarketEvergreenFinding(
                    "missing_local_context",
                    "Practical script lacks Egyptian/Arab client/tool context.",
                )
            )
    return findings


def rewrite_script_market_evergreen(
    text: str,
    *,
    target_market: TargetMarket = TargetMarket.EGYPT,
    report: MarketEvergreenReport | None = None,
) -> str:
    """Silent spoken remediations — keep natural; no disclaimer spam."""
    report = report or MarketEvergreenReport()
    if not text:
        return text
    findings = scan_script_market_evergreen(text, target_market=target_market)
    report.findings.extend(findings)
    out = text

    if any(f.code == "fragile_ui_location" for f in findings):
        out = _FRAGILE_UI.sub("المكان اللي بتبدأ منه الإجراء", out)
        if "دور على" not in out and "Look for" not in out:
            out = f"{out.rstrip()}\n{_EVERGREEN_UI_REWRITE}"
        report.remediations.append("evergreen_ui_rephrase")

    if any(f.code == "short_lived_fact" for f in findings):
        out = _FRAGILE_NUMBERS.sub("", out)
        out = re.sub(r"\s{2,}", " ", out).strip()
        if "راجع السعر" not in out and "official" not in out.lower():
            # One light beat only if we stripped a price/salary cue.
            if re.search(r"(price|salary|راتب|مرتب|سعر)", text, re.I):
                out = f"{out.rstrip()}\n{_EVERGREEN_PRICE_REWRITE}"
        report.remediations.append("evergreen_fact_soften")

    if any(f.code == "translated_tone" for f in findings):
        out = _TRANSLATED_TONE.sub("", out)
        out = re.sub(r"\s{2,}", " ", out).strip()
        report.remediations.append("strip_translated_tone")

    if any(
        f.code in {"foreign_market_assumption", "missing_local_context", "expensive_tool_assumption"}
        for f in findings
    ):
        out = _FOREIGN_MARKET.sub("سوق محلي بميزانية واقعية", out)
        out = _EXPENSIVE_TOOL_ASSUME.sub(
            "اختار أداة تناسب ميزانيتك وتغطي الحاجة فعلاً", out
        )
        if target_market in (TargetMarket.EGYPT, TargetMarket.ARAB_MARKET):
            if _LOCAL_EXAMPLE_BEAT not in out and not _LOCAL_CUE.search(out):
                out = f"{out.rstrip()}\n{_LOCAL_EXAMPLE_BEAT}"
        report.remediations.append("localize_market_example")

    if any(f.code == "button_click_tutorial" for f in findings):
        if "القاعدة هنا أهم من شكل الواجهة" not in out:
            out = (
                f"{out.rstrip()}\n"
                "القاعدة هنا أهم من شكل الواجهة: اعرف الهدف، دور على الميزة "
                "باسمها أو فكرتها، واتأكد من التوثيق الرسمي لو مكانها اتغيّر."
            )
        report.remediations.append("principle_over_clicks")

    # Never leave internal leak labels.
    for leak in MARKET_EVERGREEN_DOCX_LEAKS:
        out = re.sub(re.escape(leak), "", out, flags=re.IGNORECASE)
    return out.strip()


def map_market_evergreen_feedback(
    course_map: CourseMap,
    *,
    target_market: TargetMarket = TargetMarket.EGYPT,
) -> list[str]:
    """Feedback strings for map two-pass rebuild (never DOCX)."""
    feedback: list[str] = []
    blob_parts: list[str] = [course_map.course_title, course_map.main_thread]
    fragile_lessons = 0
    foreign_hits = 0
    for module in course_map.modules:
        blob_parts.append(module.title)
        blob_parts.append(module.purpose or "")
        for reel in module.reels:
            piece = " ".join(
                [reel.title, reel.purpose or "", " ".join(reel.must_cover or [])]
            )
            blob_parts.append(piece)
            if _FRAGILE_UI.search(piece) or _BUTTON_CLICK_HEAVY.search(piece):
                fragile_lessons += 1
            if _FOREIGN_MARKET.search(piece) or _FRAGILE_NUMBERS.search(piece):
                foreign_hits += 1

    blob = " ".join(blob_parts)
    localizing = target_market in (TargetMarket.EGYPT, TargetMarket.ARAB_MARKET)

    if fragile_lessons:
        feedback.append(
            f"Evergreen: {fragile_lessons} planned lesson(s) look like brittle "
            "UI click-paths — rebuild so each software lesson teaches purpose, "
            "decision rules, and what to search for when the interface changes."
        )
    if _FRAGILE_NUMBERS.search(blob):
        feedback.append(
            "Evergreen: map references soon-expiring prices/dates/salaries — "
            "prefer durable principles and 'how to verify current official info'."
        )
    if localizing and (_FOREIGN_MARKET.search(blob) or foreign_hits):
        feedback.append(
            "Market: plan assumes US/EU startup/client context — rebuild examples "
            "for Egyptian/Arab learners (local SMEs, WhatsApp/FB/IG, realistic budgets)."
        )
    if localizing and not _LOCAL_CUE.search(blob) and len(blob) > 80:
        feedback.append(
            "Market: map lacks local Egyptian/Arab practical cues — add realistic "
            "client/tool scenarios unless target_market is global."
        )
    return feedback


def apply_market_evergreen_to_final_course(
    course: FinalCourse,
    *,
    target_market: TargetMarket = TargetMarket.EGYPT,
) -> tuple[FinalCourse, MarketEvergreenReport]:
    report = MarketEvergreenReport()
    modules = []
    changed = False
    for module in course.modules:
        reels = []
        for reel in module.reels:
            original = reel.script_text or ""
            rewritten = rewrite_script_market_evergreen(
                original, target_market=target_market, report=report
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


def lesson_market_evergreen_instructions(
    script_text: str,
    *,
    target_market: TargetMarket = TargetMarket.EGYPT,
) -> list[str]:
    """Compact rewrite instructions for local lesson review (not DOCX)."""
    findings = scan_script_market_evergreen(script_text, target_market=target_market)
    out: list[str] = []
    for f in findings:
        if f.code == "fragile_ui_location":
            out.append(
                "Rewrite fragile UI positions: teach what to look for and the "
                "decision rule; do not rely on 'button top left'."
            )
        elif f.code == "short_lived_fact":
            out.append(
                "Remove exact short-lived prices/salaries/dates/stats; teach how "
                "to check the current official source when needed."
            )
        elif f.code == "button_click_tutorial":
            out.append(
                "Teach the purpose and principle behind the feature; demos support "
                "the lesson — they are not the whole lesson."
            )
        elif f.code in {
            "foreign_market_assumption",
            "missing_local_context",
            "expensive_tool_assumption",
            "translated_tone",
        }:
            out.append(
                "Rewrite for Egyptian/Arab market realism (or the selected target_market); "
                "no literal US/EU translation; clean spoken Egyptian."
            )
    return out
