"""Voice Profile — spoken style calibration distilled from FLOW_REFERENCE sources.

Never copies catchphrases, famous closers, or distinctive templates.
Requires ~20k words of calibration material before marking depth as deep.
Compact profile is retrieved per lesson — never the full 20k corpus.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MIN_CALIBRATION_WORDS_FOR_DEEP = 20_000


@dataclass
class VoiceProfile:
    version: str = "1"
    rhythm_notes: str = ""
    sentence_shape: str = ""
    colloquial_level: str = "egyptian_spoken"
    transitions: list[str] = field(default_factory=list)
    explanation_style: str = ""
    terminology_habits: list[str] = field(default_factory=list)
    forbidden_copy: list[str] = field(default_factory=list)
    short_samples: list[str] = field(default_factory=list)
    calibration_word_count: int = 0
    is_deep: bool = False

    def compact_for_prompt(self, *, max_chars: int = 900) -> str:
        parts = [
            f"# Voice profile v{self.version}",
            f"Colloquial level: {self.colloquial_level}",
            f"Deep calibration: {'yes' if self.is_deep else 'no'}",
        ]
        if self.rhythm_notes:
            parts.append(f"Rhythm: {self.rhythm_notes}")
        if self.sentence_shape:
            parts.append(f"Sentence shape: {self.sentence_shape}")
        if self.explanation_style:
            parts.append(f"Explanation: {self.explanation_style}")
        if self.transitions:
            parts.append("Transitions: " + "; ".join(self.transitions[:6]))
        if self.terminology_habits:
            parts.append("Terms: " + "; ".join(self.terminology_habits[:8]))
        if self.forbidden_copy:
            parts.append(
                "Never copy these distinctive phrases: "
                + "; ".join(self.forbidden_copy[:8])
            )
        if self.short_samples:
            parts.append("Short rhythm samples (do not copy wording):")
            for s in self.short_samples[:3]:
                parts.append(f"- {s[:120]}")
        text = "\n".join(parts)
        return text[:max_chars]

    def model_dump(self) -> dict:
        return {
            "version": self.version,
            "rhythm_notes": self.rhythm_notes,
            "sentence_shape": self.sentence_shape,
            "colloquial_level": self.colloquial_level,
            "transitions": list(self.transitions),
            "explanation_style": self.explanation_style,
            "terminology_habits": list(self.terminology_habits),
            "forbidden_copy": list(self.forbidden_copy),
            "short_samples": list(self.short_samples),
            "calibration_word_count": self.calibration_word_count,
            "is_deep": self.is_deep,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "VoiceProfile":
        if not data:
            return cls()
        return cls(
            version=str(data.get("version") or "1"),
            rhythm_notes=str(data.get("rhythm_notes") or ""),
            sentence_shape=str(data.get("sentence_shape") or ""),
            colloquial_level=str(data.get("colloquial_level") or "egyptian_spoken"),
            transitions=list(data.get("transitions") or []),
            explanation_style=str(data.get("explanation_style") or ""),
            terminology_habits=list(data.get("terminology_habits") or []),
            forbidden_copy=list(data.get("forbidden_copy") or []),
            short_samples=list(data.get("short_samples") or []),
            calibration_word_count=int(data.get("calibration_word_count") or 0),
            is_deep=bool(data.get("is_deep")),
        )


def build_voice_profile_from_calibration_texts(texts: list[str]) -> VoiceProfile:
    """Distill a compact profile from FLOW_REFERENCE / spoken calibration texts."""
    blob = "\n".join(t for t in texts if (t or "").strip())
    words = [w for w in re.findall(r"[\w\u0600-\u06FF]+", blob)]
    word_count = len(words)
    # Short samples: middle sentences, stripped of obvious catchphrases later.
    sentences = [s.strip() for s in re.split(r"[.!?؟\n]+", blob) if 8 <= len(s.split()) <= 22]
    samples = sentences[:: max(1, len(sentences) // 3)][:3] if sentences else []
    # Heuristic forbidden: highly repeated 4-grams (likely catchphrases).
    grams: dict[str, int] = {}
    for i in range(max(0, len(words) - 3)):
        g = " ".join(words[i : i + 4]).lower()
        grams[g] = grams.get(g, 0) + 1
    forbidden = [g for g, n in sorted(grams.items(), key=lambda x: -x[1]) if n >= 4][:8]

    avg_len = (sum(len(s.split()) for s in sentences) / len(sentences)) if sentences else 12
    profile = VoiceProfile(
        rhythm_notes=f"Typical spoken clause ~{avg_len:.0f} words; prefer short beats.",
        sentence_shape="Direct address, concrete verbs, one idea per beat.",
        colloquial_level="egyptian_spoken",
        transitions=["بعد كده", "هنا بقى", "خلّينا نشوف"],
        explanation_style="Show the decision/difference first, then name the concept if needed.",
        terminology_habits=[],
        forbidden_copy=forbidden,
        short_samples=samples,
        calibration_word_count=word_count,
        is_deep=word_count >= MIN_CALIBRATION_WORDS_FOR_DEEP,
    )
    return profile
