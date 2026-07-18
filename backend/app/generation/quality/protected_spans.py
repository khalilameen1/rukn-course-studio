"""Protected spans — preserve literal examples, quotes, code, sacred text, etc."""

from __future__ import annotations

import re
from pydantic import BaseModel, Field


class ProtectedSpan(BaseModel):
    span_id: str
    kind: str  # language_example | sacred_quote | code | equation | legal_cite | ipa | other
    text: str
    lesson_id: str | None = None


class ProtectedSpanLedger(BaseModel):
    spans: list[ProtectedSpan] = Field(default_factory=list)

    def fingerprint(self) -> dict[str, str]:
        return {s.span_id: s.text for s in self.spans}


_MARK_RE = re.compile(r"⟦PS:([^|]+)∥(.*?)⟧", re.DOTALL)


def wrap_protected(span_id: str, text: str) -> str:
    return f"⟦PS:{span_id}∥{text}⟧"


def extract_protected_spans(text: str) -> list[ProtectedSpan]:
    spans: list[ProtectedSpan] = []
    for m in _MARK_RE.finditer(text or ""):
        spans.append(ProtectedSpan(span_id=m.group(1), kind="other", text=m.group(2)))
    return spans


def strip_markers_keep_text(text: str) -> str:
    return _MARK_RE.sub(lambda m: m.group(2), text or "")


def punctuation_strip_preserving_protected(
    text: str,
    *,
    punctuation_policy: str,
    strip_fn,
) -> str:
    """Strip punctuation outside protected spans; never alter span interiors."""
    if punctuation_policy == "natural":
        return text or ""
    parts: list[str] = []
    pos = 0
    for m in _MARK_RE.finditer(text or ""):
        before = (text or "")[pos : m.start()]
        parts.append(strip_fn(before) if punctuation_policy in {"none", "protected_examples"} else before)
        parts.append(m.group(0) if punctuation_policy == "protected_examples" else m.group(2))
        pos = m.end()
    tail = (text or "")[pos:]
    parts.append(strip_fn(tail) if punctuation_policy in {"none", "protected_examples"} else tail)
    return "".join(parts)


def assert_protected_spans_unchanged(
    before: ProtectedSpanLedger | dict[str, str],
    after_text: str,
) -> list[str]:
    expected = before.fingerprint() if isinstance(before, ProtectedSpanLedger) else dict(before)
    found = {s.span_id: s.text for s in extract_protected_spans(after_text)}
    # Also accept unmarked presence of exact text for exported DOCX.
    plain = strip_markers_keep_text(after_text)
    errors: list[str] = []
    for span_id, text in expected.items():
        if span_id in found and found[span_id] != text:
            errors.append(f"PROTECTED_SPAN_CHANGED:{span_id}")
        elif span_id not in found and text not in plain:
            errors.append(f"PROTECTED_SPAN_CHANGED:{span_id}:missing")
    return errors
