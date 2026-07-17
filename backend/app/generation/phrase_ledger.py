"""Course-level phrase ledger — prevent template openers/closers across lessons."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from app.schemas.generation import GeneratedReel

# Soft templates — fail diversity when overused, not absolute bans on colloquial words.
_TEMPLATE_OPENERS = (
    "قبل ما تفتح",
    "أول حاجة",
    "خليني أوضح",
    "وده اللي",
    "الفرق بين",
    "القاعدة اللي تاخدها معاك",
    "في الفيديو ده",
    "النهارده هنتكلم",
    "هل تعلم",
)

_MAX_TEMPLATE_HITS_PER_COURSE = 2


@dataclass
class PhraseLedger:
    openings: list[str] = field(default_factory=list)
    closings: list[str] = field(default_factory=list)
    repeated_phrases: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    metaphors: list[str] = field(default_factory=list)
    terms: list[str] = field(default_factory=list)
    taught_ideas: list[str] = field(default_factory=list)
    template_counts: Counter = field(default_factory=Counter)

    def record_reel(self, reel: GeneratedReel) -> None:
        lines = [ln.strip() for ln in (reel.script_text or "").splitlines() if ln.strip()]
        if lines:
            self.openings.append(lines[0][:120])
            self.closings.append(lines[-1][:120])
        self.examples.extend(reel.used_examples or [])
        self.taught_ideas.extend(reel.used_ideas or [])
        blob = (reel.script_text or "").lower()
        for tmpl in _TEMPLATE_OPENERS:
            if tmpl in blob:
                self.template_counts[tmpl] += 1

    def compact_summary_for_writer(self, *, max_chars: int = 1200) -> str:
        """Compressed prior-course memory for Creator — not full scripts."""
        parts = [
            "# Phrase ledger (avoid repeating these patterns)",
            "Recent openings:",
            *[f"- {o}" for o in self.openings[-8:]],
            "Recent closings:",
            *[f"- {c}" for c in self.closings[-8:]],
            "Examples already used:",
            *[f"- {e}" for e in self.examples[-12:]],
            "Ideas already taught:",
            *[f"- {i}" for i in self.taught_ideas[-16:]],
        ]
        overused = [t for t, n in self.template_counts.items() if n >= _MAX_TEMPLATE_HITS_PER_COURSE]
        if overused:
            parts.append("Overused templates — do NOT reuse:")
            parts.extend(f"- {t}" for t in overused)
        text = "\n".join(parts)
        return text[:max_chars]

    def diversity_failures(self) -> list[str]:
        fails: list[str] = []
        for tmpl, n in self.template_counts.items():
            if n > _MAX_TEMPLATE_HITS_PER_COURSE:
                fails.append(
                    f"Template «{tmpl}» used {n} times across the course "
                    f"(max {_MAX_TEMPLATE_HITS_PER_COURSE})"
                )
        # Near-duplicate openings.
        for i, a in enumerate(self.openings):
            for b in self.openings[i + 1 :]:
                if _near_dup(a, b):
                    fails.append(f"Near-duplicate openings: «{a[:40]}» / «{b[:40]}»")
                    break
        return fails

    def model_dump(self) -> dict:
        return {
            "openings": list(self.openings),
            "closings": list(self.closings),
            "examples": list(self.examples),
            "taught_ideas": list(self.taught_ideas),
            "template_counts": dict(self.template_counts),
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "PhraseLedger":
        if not data:
            return cls()
        ledger = cls(
            openings=list(data.get("openings") or []),
            closings=list(data.get("closings") or []),
            examples=list(data.get("examples") or []),
            taught_ideas=list(data.get("taught_ideas") or []),
        )
        ledger.template_counts = Counter(data.get("template_counts") or {})
        return ledger


def _near_dup(a: str, b: str) -> bool:
    ta = set(re.findall(r"[\w\u0600-\u06FF]{3,}", (a or "").lower()))
    tb = set(re.findall(r"[\w\u0600-\u06FF]{3,}", (b or "").lower()))
    if not ta or not tb:
        return False
    return len(ta & tb) / max(1, min(len(ta), len(tb))) >= 0.85
