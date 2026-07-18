"""Spoken Egyptian Arabic Gate — deterministic teleprompter speech checks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models.enums import AddressForm

# Article / stiff MSA cues that clash with spoken Egyptian teleprompter.
_ARTICLE_MSA = re.compile(
    r"(من الجدير بالذكر|تجدر الإشارة|بناءً على ما سبق|في الختام|"
    r"علاوة على ذلك|من ناحية أخرى|يتضح مما سبق|وعليه فإن|"
    r"لا سيما أن|إذ إن|حيث إن)",
)
_AI_TONE = re.compile(
    r"(في الفيديو ده هنتعلم|هل تعلم|النهارده هنتكلم عن|تعالى أقولك|"
    r" thr أكبر غلطة| thr أكبر خطأ| thr أهم حاجة هتتعلمها|"
    r"في الريل الجاي|في الدرس الجاي|الدرس الجاي هنشوف)",
)
_LITERAL_TRANSLATION = re.compile(
    r"(الجمهور البارد|الدعوة لاتخاذ إجراء|نقطة الألم|القيمة المقترحة|"
    r"رحلة العميل|النداء للعمل)",
)
_RHETORICAL_PAD = re.compile(
    r"(خليني أوضح|وقبل ما نبدأ|مهم جدًا جدًا|القاعدة اللي تاخدها معاك)",
)

# Rough gender markers in Egyptian second person.
_MASC_MARKERS = re.compile(r"\b(انت|إنت|عندك|نفسك|شوف|اعمل|افتح|اختار)\b")
_FEM_MARKERS = re.compile(r"\b(انتي|إنتي|عندكِ|نفسكِ|شوفي|اعملي|افتحي|اختاري)\b")

_LONG_LINE_WORDS = 42


@dataclass
class ArabicGateIssue:
    code: str
    detail: str
    severity: str  # fatal | serious | minor


@dataclass
class ArabicGateReport:
    issues: list[ArabicGateIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.severity in ("fatal", "serious") for i in self.issues)


def run_egyptian_arabic_gate(
    script_text: str,
    *,
    address_form: AddressForm = AddressForm.MASCULINE,
) -> ArabicGateReport:
    text = script_text or ""
    report = ArabicGateReport()
    if not text.strip():
        report.issues.append(
            ArabicGateIssue("empty_script", "Spoken script is empty", "fatal")
        )
        return report

    if _ARTICLE_MSA.search(text):
        report.issues.append(
            ArabicGateIssue(
                "msa_article_tone",
                "Script contains stiff MSA/article phrasing unfit for spoken Egyptian",
                "serious",
            )
        )
    if _AI_TONE.search(text):
        report.issues.append(
            ArabicGateIssue(
                "ai_intro_template",
                "Banned AI intro/outro template detected",
                "serious",
            )
        )
    if _LITERAL_TRANSLATION.search(text):
        report.issues.append(
            ArabicGateIssue(
                "literal_translation",
                "Literal translated marketing jargon — use natural spoken phrasing",
                "serious",
            )
        )
    if _RHETORICAL_PAD.search(text):
        report.issues.append(
            ArabicGateIssue(
                "rhetorical_padding",
                "Template rhetorical padding detected",
                "minor",
            )
        )

    # Long unspeakable lines.
    for line in text.splitlines():
        words = [w for w in line.split() if w.strip()]
        if len(words) >= _LONG_LINE_WORDS:
            report.issues.append(
                ArabicGateIssue(
                    "unsayable_long_line",
                    f"Line has {len(words)} words — split into spoken beats",
                    "serious",
                )
            )
            break

    # Address form consistency.
    masc = bool(_MASC_MARKERS.search(text))
    fem = bool(_FEM_MARKERS.search(text))
    if address_form == AddressForm.MASCULINE and fem and not masc:
        report.issues.append(
            ArabicGateIssue(
                "address_form_mismatch",
                "Course address_form is masculine but script uses feminine forms",
                "serious",
            )
        )
    elif address_form == AddressForm.FEMININE and masc and not fem:
        report.issues.append(
            ArabicGateIssue(
                "address_form_mismatch",
                "Course address_form is feminine but script uses masculine forms",
                "serious",
            )
        )
    elif masc and fem:
        report.issues.append(
            ArabicGateIssue(
                "address_form_switch",
                "Script switches between masculine and feminine address",
                "serious",
            )
        )

    return report
