"""Independent Spoken Variety Integrity Gate for Egyptian teleprompter speech."""

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

# Structural residue is inspected across syntax, morphology, connectors, word
# order, attached prefixes, and auditory flow — not as one generic word list.
_WRITTEN_CONNECTOR = re.compile(
    r"(بالإضافة إلى ذلك|ومن ثم(?:ّ)?|وعلى هذا الأساس|وبناءً عليه|"
    r"في ضوء ما سبق|بصفة عامة|على صعيد آخر)"
)
_FORMAL_CONSTRUCTION = re.compile(
    r"(أما\s+.{2,45}\s+فهو|إذا\s+.{2,45}\s+فإن|فإنه|حيث إن|إذ إن|"
    r"لا بد من الإشارة إلى|يجدر بنا|يتعين عليك|يتوجب عليك|ينبغي عليك)"
)
_FORMAL_COMMAND_OR_QUESTION = re.compile(
    r"(قم ب(?:ال|ـ)?|احرص على أن|يرجى|هل قمت ب|أليس من|يمكنك أن تقوم ب)"
)
_ATTACHED_PREFIX_RESIDUE = re.compile(
    r"(وبالتالي فإنه|فبمجرد أن|فلذلك|فإنك|فحينئذ)"
)
_COLLOQUIAL_SIGNAL = re.compile(
    r"\b(إنت|انت|عندك|عايز|عايزة|هتعمل|هتلاقي|خلّي|خلي|بعدين|كده|دلوقتي)\b"
)
_STANDALONE_THEN = re.compile(r"(?<![\u0600-\u06FF])ثم(?![\u0600-\u06FF])")
_STRANGE_OR_HOSTILE_TRANSLITERATION = re.compile(
    r"(مانيبوليشن|مانيبوليت|إكسبلويت|استغل العميل|هاك العميل|اخدع العميل)"
)
_CORPORATE_ETHICS = re.compile(
    r"(أصحاب المصلحة|الحوكمة المؤسسية|المسؤولية الاجتماعية للشركات|"
    r"إطار الممارسات الأخلاقية|ميثاق الأخلاقيات المؤسسية)"
)
_CORPORATE_ETHICS_DOMAIN = re.compile(
    r"(ethic|governance|compliance|legal|policy|sustainab|مسؤولية|حوكمة|أخلاق|امتثال)",
    re.IGNORECASE,
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


def compile_language_profile_guidance(language_profile: dict | None) -> str:
    """Prompt policy for direct composition in the selected spoken variety."""
    profile = dict(language_profile or {})
    language = str(profile.get("presenter_language") or "ar")
    variety = str(profile.get("presenter_dialect") or "egyptian")
    address = str(profile.get("address_form") or "masculine")
    bilingual = str(profile.get("bilingual_policy") or "presenter_primary")
    return "\n".join(
        [
            "LANGUAGE_PROFILE (frozen before writing; internal only):",
            f"- presenter_language={language}; spoken_variety={variety}; address_form={address}",
            f"- bilingual_policy={bilingual}",
            "- Compose the idea directly in the target spoken language. Never draft in English or MSA then translate.",
            "- Keep one justified spoken register and one address form across the course.",
            "- Code-switch only for conventional domain/tool/interface terms; explain meaning naturally on first use.",
            "- A common English word is not permission for a strange, hostile, or misleading Arabic calque.",
            "- For Egyptian speech, standalone ثم is a serious finding unless protected verbatim or justified by approved voice evidence.",
        ]
    )


def _mask_protected_spans(text: str, protected_spans: list[str] | None) -> str:
    masked = text
    for index, span in enumerate(protected_spans or []):
        value = str(span or "").strip()
        if value:
            masked = masked.replace(value, f" PROTECTEDSPAN{index} ")
    return masked


def run_spoken_variety_integrity_gate(
    script_text: str,
    *,
    address_form: AddressForm = AddressForm.MASCULINE,
    spoken_variety: str = "egyptian",
    course_domain: str = "",
    protected_spans: list[str] | None = None,
    approved_voice_evidence: list[str] | None = None,
) -> ArabicGateReport:
    """Audit the completed semantic rewrite without mutating its meaning."""
    text = script_text or ""
    report = ArabicGateReport()
    if not text.strip():
        report.issues.append(
            ArabicGateIssue("empty_script", "Spoken script is empty", "fatal")
        )
        return report

    variety = (spoken_variety or "").strip().lower()
    if variety not in {"egyptian", "egyptian_colloquial", "ar-eg", "arz"}:
        return report

    audit_text = _mask_protected_spans(text, protected_spans)

    if _ARTICLE_MSA.search(audit_text):
        report.issues.append(
            ArabicGateIssue(
                "msa_article_tone",
                "Script contains stiff MSA/article phrasing unfit for spoken Egyptian",
                "serious",
            )
        )
    if _WRITTEN_CONNECTOR.search(audit_text):
        report.issues.append(
            ArabicGateIssue(
                "written_connector_residue",
                "Written-register connector disrupts ordinary Egyptian auditory flow",
                "serious",
            )
        )
    if _FORMAL_CONSTRUCTION.search(audit_text):
        report.issues.append(
            ArabicGateIssue(
                "formal_syntax_morphology",
                "Formal syntax/morphology remains in the Egyptian spoken rewrite",
                "serious",
            )
        )
    if _FORMAL_COMMAND_OR_QUESTION.search(audit_text):
        report.issues.append(
            ArabicGateIssue(
                "formal_command_or_question",
                "Formal command/question word order should be rewritten as natural speech",
                "serious",
            )
        )
    if _ATTACHED_PREFIX_RESIDUE.search(audit_text):
        report.issues.append(
            ArabicGateIssue(
                "attached_prefix_residue",
                "Attached formal result/sequence prefix sounds written rather than spoken",
                "serious",
            )
        )

    then_approved = any(
        _STANDALONE_THEN.search(str(item or ""))
        for item in (approved_voice_evidence or [])
    )
    if _STANDALONE_THEN.search(audit_text) and not then_approved:
        report.issues.append(
            ArabicGateIssue(
                "standalone_thumma_connector",
                "Standalone ثم is serious written-register residue in ordinary Egyptian speech",
                "serious",
            )
        )

    formal_signal = bool(
        _ARTICLE_MSA.search(audit_text)
        or _WRITTEN_CONNECTOR.search(audit_text)
        or _FORMAL_CONSTRUCTION.search(audit_text)
        or _FORMAL_COMMAND_OR_QUESTION.search(audit_text)
    )
    if formal_signal and _COLLOQUIAL_SIGNAL.search(audit_text):
        report.issues.append(
            ArabicGateIssue(
                "unjustified_register_mixing",
                "MSA/written constructions are mixed with colloquial Egyptian without a protected reason",
                "serious",
            )
        )

    if _STRANGE_OR_HOSTILE_TRANSLITERATION.search(audit_text):
        report.issues.append(
            ArabicGateIssue(
                "hostile_or_strange_calque",
                "English-derived wording sounds hostile/strange or misleads the learner",
                "serious",
            )
        )

    if _CORPORATE_ETHICS.search(audit_text) and not _CORPORATE_ETHICS_DOMAIN.search(
        course_domain or ""
    ):
        report.issues.append(
            ArabicGateIssue(
                "irrelevant_corporate_ethics_register",
                "Corporate ethics/governance register is not justified by this skill domain",
                "serious",
            )
        )

    words = re.findall(r"[A-Za-z]+|[\u0600-\u06FF]+", audit_text)
    english_words = [word for word in words if re.fullmatch(r"[A-Za-z]+", word)]
    if len(english_words) >= 4 and len(english_words) / max(len(words), 1) > 0.35:
        report.issues.append(
            ArabicGateIssue(
                "uncontrolled_code_switching",
                "English dominates an Egyptian sentence beyond necessary professional terms",
                "serious",
            )
        )

    if _AI_TONE.search(audit_text):
        report.issues.append(
            ArabicGateIssue(
                "ai_intro_template",
                "Banned AI intro/outro template detected",
                "serious",
            )
        )
    if _LITERAL_TRANSLATION.search(audit_text):
        report.issues.append(
            ArabicGateIssue(
                "literal_translation",
                "Literal translated marketing jargon — use natural spoken phrasing",
                "serious",
            )
        )
    if _RHETORICAL_PAD.search(audit_text):
        report.issues.append(
            ArabicGateIssue(
                "rhetorical_padding",
                "Template rhetorical padding detected",
                "minor",
            )
        )

    for line in audit_text.splitlines():
        words_in_line = [word for word in line.split() if word.strip()]
        if len(words_in_line) >= _LONG_LINE_WORDS:
            report.issues.append(
                ArabicGateIssue(
                    "unsayable_long_line",
                    f"Line has {len(words_in_line)} words — split into spoken beats",
                    "serious",
                )
            )
            break

    masc = bool(_MASC_MARKERS.search(audit_text))
    fem = bool(_FEM_MARKERS.search(audit_text))
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


def run_egyptian_arabic_gate(
    script_text: str,
    *,
    address_form: AddressForm = AddressForm.MASCULINE,
) -> ArabicGateReport:
    return run_spoken_variety_integrity_gate(
        script_text,
        address_form=address_form,
        spoken_variety="egyptian",
    )
