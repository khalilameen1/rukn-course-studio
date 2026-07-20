"""Term Ledger — natural spoken meaning first, then a real professional term."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

TERM_LEDGER_VERSION = "1.0"


@dataclass
class TermEntry:
    awkward_literal: str
    natural_spoken: str
    pro_term: str | None = None
    note: str = ""


# Shared defaults; courses may extend through canonical rules / source memory.
DEFAULT_TERMINOLOGY: list[TermEntry] = [
    TermEntry(
        awkward_literal="الجمهور البارد",
        natural_spoken="ناس لسه ما تعرفناش",
        pro_term="Cold Audience",
        note="قدم المعنى الطبيعي أولًا",
    ),
    TermEntry(
        awkward_literal="الدعوة لاتخاذ إجراء",
        natural_spoken="الخطوة اللي عايز الشخص يعملها",
        pro_term="CTA",
    ),
    TermEntry(
        awkward_literal="نقطة الألم",
        natural_spoken="المشكلة اللي بتوجع العميل",
        pro_term="Pain Point",
    ),
    TermEntry(
        awkward_literal="القيمة المقترحة",
        natural_spoken="ليه يختاروك انت مش غيرك",
        pro_term="Value Proposition",
    ),
    TermEntry(
        awkward_literal="رحلة العميل",
        natural_spoken="الطريق اللي العميل بيمشي فيه من أول ما يشوفك لحد ما يشتري",
        pro_term="Customer Journey",
    ),
]


@dataclass
class TerminologyMap:
    entries: list[TermEntry] = field(default_factory=lambda: list(DEFAULT_TERMINOLOGY))

    def rewrite_hints_for_prompt(self) -> str:
        lines = [
            "Terminology (spoken Egyptian first; keep English pro terms when natural):"
        ]
        for e in self.entries:
            pro = f" (وممكن تذكر {e.pro_term} لو ده المتعارف عليه)" if e.pro_term else ""
            lines.append(f"- لا تقل «{e.awkward_literal}» تلقائيًا → قل «{e.natural_spoken}»{pro}")
        return "\n".join(lines)

    def find_awkward_literals(self, text: str) -> list[str]:
        found: list[str] = []
        blob = text or ""
        for e in self.entries:
            if e.awkward_literal in blob:
                found.append(e.awkward_literal)
        return found


def default_terminology_map() -> TerminologyMap:
    return TerminologyMap()


def build_term_ledger(
    *,
    language_profile: dict[str, Any] | None = None,
    course_domain: str = "",
    target_market: str = "egypt",
    available_tools: list[str] | None = None,
) -> dict[str, Any]:
    """Freeze deterministic terminology policy before the first lesson write."""
    profile = dict(language_profile or {})
    terms = default_terminology_map()
    return {
        "version": TERM_LEDGER_VERSION,
        "built_before_writing": True,
        "presenter_language": str(profile.get("presenter_language") or "ar"),
        "spoken_variety": str(profile.get("presenter_dialect") or "egyptian"),
        "address_form": str(profile.get("address_form") or "masculine"),
        "course_domain": str(course_domain or "generic"),
        "target_market": str(target_market or "egypt"),
        "available_tools": [
            str(tool).strip()
            for tool in (available_tools or [])
            if str(tool).strip()
        ],
        "entries": [
            {
                "awkward_literal": entry.awkward_literal,
                "natural_spoken": entry.natural_spoken,
                "professional_term": entry.pro_term or "",
                "policy": "meaning_first_professional_term_only_when_conventional",
            }
            for entry in terms.entries
        ],
        "code_switching_policy": (
            "Use only a conventional field/tool/interface term that the learner needs; "
            "give its natural meaning on first use and keep Arabic sentence grammar."
        ),
        "literal_translation_policy": (
            "Reject misleading literal translation, strange transliteration, or wording "
            "that sounds insulting merely because the English source term is common."
        ),
        "register_policy": (
            "Do not mix MSA and colloquial registers without a protected quotation, "
            "language example, or explicit domain need."
        ),
        "corporate_ethics_policy": (
            "Do not insert corporate ethics/governance language into skill teaching "
            "unless the course domain genuinely requires it."
        ),
    }


def compile_term_ledger_guidance(ledger: dict[str, Any]) -> str:
    """Compact provider guidance; ledger stays internal and never enters DOCX."""
    lines = [
        "TERM_LEDGER (frozen before writing; internal only):",
        "- Write the idea directly in the target spoken language; never draft in English/MSA and translate.",
        f"- {ledger.get('code_switching_policy') or ''}",
        f"- {ledger.get('literal_translation_policy') or ''}",
        f"- {ledger.get('register_policy') or ''}",
        f"- {ledger.get('corporate_ethics_policy') or ''}",
    ]
    tools = list(ledger.get("available_tools") or [])
    if tools:
        lines.append("- Brief-declared tools whose exact names may remain: " + ", ".join(tools))
    for entry in list(ledger.get("entries") or []):
        awkward = str(entry.get("awkward_literal") or "")
        natural = str(entry.get("natural_spoken") or "")
        professional = str(entry.get("professional_term") or "")
        suffix = f"; conventional term={professional}" if professional else ""
        lines.append(f"- Avoid literal «{awkward}»; explain as «{natural}»{suffix}")
    return "\n".join(lines)
