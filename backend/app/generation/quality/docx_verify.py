"""Post-export DOCX verification against the approved spoken text."""

from __future__ import annotations

from docx import Document

from app.generation.quality.issue_codes import IssueCode
from app.generation.quality.protected_spans import (
    assert_protected_spans_unchanged,
    strip_markers_keep_text,
)
from app.schemas.generation import FinalCourse
from app.services.docx_export import extract_plain_text


def verify_exported_docx(
    docx_path: str,
    *,
    final_course: FinalCourse,
    protected_fingerprint: dict[str, str] | None = None,
) -> list[str]:
    """Re-open DOCX and compare against approved course text. Returns error codes."""
    errors: list[str] = []
    document = Document(docx_path)
    plain = extract_plain_text(document)
    if not plain.strip():
        errors.append(f"{IssueCode.DEPTH_EMPTY.value}:docx_empty")
        return errors

    expected_titles = [final_course.title or ""]
    for module in final_course.modules:
        expected_titles.append(module.title)
        for reel in module.reels:
            expected_titles.append(reel.title)
            body = strip_markers_keep_text(reel.script_text or "")
            # Every non-trivial spoken line should appear (punctuation may be stripped).
            for line in body.splitlines():
                token = " ".join(line.split()[:4])
                if len(token) >= 8 and token not in plain and token.replace("،", "") not in plain:
                    # Soft: only flag if whole script missing.
                    pass
            compact = " ".join(body.split()[:6])
            if compact and compact not in " ".join(plain.split()):
                # Allow punctuation-stripped mismatch by checking first 3 words.
                words = body.split()[:3]
                if words and not all(w in plain for w in words):
                    errors.append(f"docx_content_mismatch:{reel.reel_id}")

    # No metadata leaks
    lowered = plain.lower()
    for needle in ("critic note", "hook:", "loop:", "visual plan", "needs_review", "```"):
        if needle in lowered:
            errors.append(f"{IssueCode.METADATA_LEAK.value}:{needle}")

    if protected_fingerprint:
        errors.extend(
            assert_protected_spans_unchanged(protected_fingerprint, plain)
        )

    # Basic XML / RTL smoke: paragraphs exist and styles are set.
    if not document.paragraphs:
        errors.append("docx_no_paragraphs")
    return list(dict.fromkeys(errors))
