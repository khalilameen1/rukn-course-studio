"""Domain Terminology Map — natural spoken meaning first, then pro term if needed."""

from __future__ import annotations

from dataclasses import dataclass, field


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
            pro = f" (ثم يمكن ذكر {e.pro_term})" if e.pro_term else ""
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
