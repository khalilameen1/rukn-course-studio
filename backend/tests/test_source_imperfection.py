"""General source imperfection — books, OCR, foreign market, transcripts as subset."""

from app.generation.prompt_compiler import (
    PROMPT_COMPILER_VERSION,
    SourceForCompiler,
    compile_source_context,
)
from app.generation.source_imperfection import (
    ACADEMIC_BOOK_LABEL,
    OCR_SOURCE_LABEL,
    SOURCE_MISTRUST_LABEL,
    detect_source_risk_flags,
    infer_expanded_source_origin,
    infer_extraction_method,
    normalize_ocr_text,
)
from app.generation.source_memory_store import build_source_memory_payload
from app.generation.teleprompter_checks import find_forbidden_substrings
from app.models.enums import ExtractionMethod, SourceOrigin
from app.schemas.generation import FinalCourse, FinalModule, FinalReel
from app.seed_admin_knowledge import REQUIRED_KEYS, SOURCE_IMPERFECTION_GATE
from app.services.docx_export import extract_plain_text, render_final_course_docx

META = {
    "title": "Meta Ads for Egyptian Boutique Shops",
    "audience": "Beginner Egyptian shop owners",
    "outcome": "Launch and measure profitable Meta ads campaigns",
    "target_market": "egypt",
    "course_map_text": "Campaign setup, creative testing, ROAS measurement",
}

ACADEMIC_BOOK = """
Chapter 3 — Theoretical Framework
ISBN 978-1-23456-789-0
Copyright 2012 Published by Academic Press
Furthermore, the literature review establishes a scholarly methodology.
Moreover, the hypothesis requires peer-reviewed examination of advertising constructs.
In conclusion, the theoretical framework remains foundational for marketers.
Meta ads campaign measurement and ROAS appear briefly as an illustration only.
"""

OLD_BOOK_TOOL = """
Chapter 2 — Facebook Advertising in 2016
Use Facebook Power Editor and boost post from the legacy interface before iOS 14 ATT.
This deprecated workflow still works for United States ZIP code targeting and IRS small business ads.
"""

OCR_SCAN = """
Page 1 of 12
Scanned with Adobe Scan
Meta Ads for boutiques — Measure R0AS weekly
Faceb00k campaign setup
Page 2 of 12
www.example.com
Confidential
test creative test creative before scale
X9qZ12b suspicious OCR token here
"""

FOREIGN_MARKET = """
For United States small businesses using SBA loans and 401(k) matching,
set up Meta ads with ZIP code targeting and IRS-compliant invoices.
Universal principle: test one creative variable before scaling spend.
"""

TRANSCRIPT = """
[00:00:12] Speaker 1: Meta ads campaign setup for Egyptian boutique shops.
Measure ROAS weekly. Learner objection: budget is too small.
"""

GOOD_SCRIPT = """\
خليني أوضح لك الحتة دي بسرعة.
الغلط هنا إن ناس كتير بتفهم الموضوع بالعكس لما الميزانية صغيرة.
"""


def test_gate_in_required_keys():
    assert "rukn_source_imperfection_gate" in REQUIRED_KEYS
    assert "raw material" in SOURCE_IMPERFECTION_GATE.lower()
    assert PROMPT_COMPILER_VERSION == "2.20"


def test_book_pdf_treated_as_raw_material_not_format_authority():
    memory = build_source_memory_payload(
        title="marketing-book.pdf",
        category="scientific_reference",
        extracted_text=ACADEMIC_BOOK,
        original_filename="marketing-book.pdf",
        mime_type="application/pdf",
        course_promise=META,
    )
    assert memory.get("source_origin") in (
        SourceOrigin.ACADEMIC_BOOK.value,
        SourceOrigin.PRACTICAL_BOOK.value,
        SourceOrigin.WRITTEN_DOCUMENT.value,
    )
    assert memory.get("source_imperfection_version")
    assert SOURCE_MISTRUST_LABEL in (memory.get("source_prompt_labels") or [])
    blocked = " ".join(memory.get("blocked_content_warnings") or []).lower()
    assert "raw material" in blocked or "never treat" in blocked
    assert memory.get("raw_source_hash")
    assert memory.get("normalized_text_hash")


def test_academic_source_gets_book_label_not_copied_structure():
    memory = build_source_memory_payload(
        title="theory-book.pdf",
        category="scientific_reference",
        extracted_text=ACADEMIC_BOOK,
        original_filename="theory-book.pdf",
        course_promise=META,
    )
    labels = " ".join(memory.get("source_prompt_labels") or [])
    assert "academic" in labels.lower() or ACADEMIC_BOOK_LABEL[:40] in labels
    flags = memory.get("source_risk_flags") or []
    assert "academic_theory_heavy" in flags or memory.get("academic_source_flag")


def test_old_book_tool_does_not_override_official_docs():
    memory = build_source_memory_payload(
        title="old-fb-book.pdf",
        category="scientific_reference",
        extracted_text=OLD_BOOK_TOOL,
        original_filename="old-fb-book.pdf",
        course_promise=META,
    )
    flags = memory.get("source_risk_flags") or []
    assert "outdated_possible" in flags or "tool_ui_may_be_old" in flags
    blocked = " ".join(memory.get("blocked_content_warnings") or []).lower()
    assert "official" in blocked
    assert memory.get("outdated_warnings") or "outdated" in flags[0] if flags else True


def test_ocr_errors_cleaned_conservatively():
    result = normalize_ocr_text(OCR_SCAN)
    assert "Page 1 of 12" not in result.cleaned_text or "removed" in " ".join(result.corrections)
    assert "Facebook" in result.cleaned_text or "Faceb00k" not in result.cleaned_text
    assert "ROAS" in result.cleaned_text or "R0AS" not in result.cleaned_text
    # Ambiguous/suspicious not invented into confident claims blindly
    assert result.uncertain_fragments or "X9qZ12b" in result.cleaned_text


def test_ocr_suspicious_terms_not_blindly_used():
    memory = build_source_memory_payload(
        title="scanned-ocr.pdf",
        category="raw_material",
        extracted_text=OCR_SCAN,
        original_filename="scanned-ocr.pdf",
        source_origin=SourceOrigin.OCR_TEXT.value,
        course_promise=META,
    )
    assert memory.get("extraction_method") in (
        ExtractionMethod.OCR.value,
        ExtractionMethod.PDF_TEXT.value,
    ) or memory.get("source_origin") in (
        SourceOrigin.OCR_TEXT.value,
        SourceOrigin.SCANNED_PDF.value,
    )
    labels = " ".join(memory.get("source_prompt_labels") or [])
    assert OCR_SOURCE_LABEL.split(".")[0] in labels or "OCR" in labels
    # Corrections are metadata only
    if memory.get("source_corrections") or memory.get("uncertain_terms"):
        assert memory.get("source_corrections") is not None or memory.get("uncertain_terms")


def test_foreign_market_source_flagged():
    memory = build_source_memory_payload(
        title="us-guide.docx",
        category="scientific_reference",
        extracted_text=FOREIGN_MARKET,
        original_filename="us-guide.docx",
        course_promise=META,
    )
    flags = memory.get("source_risk_flags") or []
    assert "foreign_market_context" in flags
    notes = " ".join(memory.get("market_adaptation_notes") or memory.get("relevance_notes") or []).lower()
    assert "market" in notes or "foreign" in " ".join(flags)


def test_transcript_specific_handling_still_works():
    memory = build_source_memory_payload(
        title="lesson.txt",
        category="transcript",
        extracted_text=TRANSCRIPT,
        original_filename="lesson.txt",
        course_promise=META,
    )
    assert memory.get("source_origin") == SourceOrigin.COURSE_TRANSCRIPT.value
    assert "transcript_noise_possible" in (memory.get("source_risk_flags") or [])
    assert memory.get("topic_relevance") == "same_topic"
    assert memory.get("transcript_imperfection_version") or memory.get("transcript_normalized")


def test_extension_does_not_determine_authority():
    txt_origin = infer_expanded_source_origin(
        TRANSCRIPT,
        category="raw_material",
        original_filename="notes.txt",
    )
    pdf_origin = infer_expanded_source_origin(
        ACADEMIC_BOOK,
        category="raw_material",
        original_filename="notes.pdf",
    )
    assert txt_origin != "txt"
    assert pdf_origin != "pdf"
    assert infer_extraction_method(original_filename="a.pdf") == ExtractionMethod.PDF_TEXT.value
    # Same extension can be different origins
    assert txt_origin != pdf_origin


def test_dual_hashes_exist_for_all_sources():
    memory = build_source_memory_payload(
        title="any.docx",
        category="scientific_reference",
        extracted_text=ACADEMIC_BOOK,
        original_filename="any.docx",
        course_promise=META,
    )
    assert memory.get("raw_source_hash")
    assert memory.get("normalized_text_hash")
    assert memory.get("source_hash") == memory.get("raw_source_hash")


def test_final_docx_has_no_provenance_or_risk_labels():
    course = FinalCourse(
        title="Ads",
        full_text="ignored",
        modules=[
            FinalModule(
                module_id="m1",
                title="Module 1",
                reels=[
                    FinalReel(
                        reel_id="m1-r1",
                        title="Lesson 1",
                        script_text=GOOD_SCRIPT,
                    )
                ],
            )
        ],
    )
    plain = extract_plain_text(render_final_course_docx(course))
    assert not find_forbidden_substrings(plain)
    for banned in (
        "source_origin",
        "extraction_method",
        "source_risk_flags",
        "transcript_corrections",
        SOURCE_MISTRUST_LABEL[:30],
    ):
        assert banned.lower() not in plain.lower()


def test_compiler_prefixes_book_with_mistrust_label():
    memory = build_source_memory_payload(
        title="book.pdf",
        category="scientific_reference",
        extracted_text=ACADEMIC_BOOK,
        original_filename="book.pdf",
        course_promise=META,
    )
    excerpts = compile_source_context(
        [
            SourceForCompiler(
                source_id=1,
                category="scientific_reference",
                priority="medium",
                text="snippet",
                memory=memory,
            )
        ],
        query_text="ROAS",
    )
    assert excerpts
    assert "untrusted raw material" in excerpts[0].text.lower()
