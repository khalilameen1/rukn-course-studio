"""Tests for app/generation/output_scoring.py (§4)."""

import json

from app.generation.output_scoring import score_final_course
from app.validators.forbidden_phrase_checker import FORBIDDEN_PHRASES_KEY

CLEAN_DOCUMENT = (
    "Intro to Household Budgeting\n"
    "Module 1 — Getting Started\n"
    "Lesson 1 — Opening\n"
    "يلا نبدأ بسيط وسريع. بس خلينا نركز في نقطة واحدة.\n"
    "لكن لازم نفهم الأساس الأول عشان نكمل.\n"
    "Module 2 — Budgets\n"
    "Lesson 1 — Totals\n"
    "طيب خلينا نحسب الإجمالي بسرعة.\n"
)

DIRTY_DOCUMENT = (
    "Intro to Household Budgeting\n"
    "Module 1 — Getting Started\n"
    "Lesson 1 — Opening\n"
    "[internal_review] please double check this line before recording.\n"
    "Note to instructor: say this line slowly and explain that budgeting matters.\n"
)


def test_clean_document_passes_all_teleprompter_checks():
    report = score_final_course(CLEAN_DOCUMENT, rules_context={})

    assert report.teleprompter_clean is True
    assert report.internal_notes_absent is True
    assert report.forbidden_substrings_found == []
    assert report.module_lesson_structure_present is True


def test_document_with_planted_internal_notes_fails_teleprompter_checks():
    report = score_final_course(DIRTY_DOCUMENT, rules_context={})

    assert report.teleprompter_clean is False
    assert report.internal_notes_absent is False
    assert "internal_review" in report.forbidden_substrings_found
    assert "note to instructor" in report.forbidden_substrings_found
    assert "say this" in report.forbidden_substrings_found
    assert "explain that" in report.forbidden_substrings_found


def test_forbidden_phrases_are_flagged_using_the_real_validator():
    rules_context = {
        FORBIDDEN_PHRASES_KEY: json.dumps(
            {"phrases": [{"phrase": "غير قابل للتفاوض", "severity": "high"}]}
        )
    }
    text = "هذا الأمر غير قابل للتفاوض في منهج ركن."

    report = score_final_course(text, rules_context)

    assert report.forbidden_phrases_absent is False
    assert "غير قابل للتفاوض" in report.forbidden_phrases_found


def test_forbidden_phrases_absent_when_none_configured_or_present():
    report = score_final_course(CLEAN_DOCUMENT, rules_context={})

    assert report.forbidden_phrases_absent is True
    assert report.forbidden_phrases_found == []


def test_module_lesson_structure_detection():
    no_structure = score_final_course("Just some plain lines.\nAnother line.\n", rules_context={})
    assert no_structure.module_lesson_structure_present is False

    with_structure = score_final_course(CLEAN_DOCUMENT, rules_context={})
    assert with_structure.module_lesson_structure_present is True


def test_spoken_style_score_reflects_connector_density():
    conversational = score_final_course(
        "بس كده. لكن خد بالك. طيب وبعدين نكمل. لكن برضو فيه حاجة.", rules_context={}
    )
    formal = score_final_course(
        "The market experienced growth. Analysts reported results. Data confirmed trends.",
        rules_context={},
    )

    assert conversational.spoken_style_score.reads_conversationally is True
    assert formal.spoken_style_score.reads_conversationally is False


def test_paragraph_readability_is_computed_from_actual_text():
    report = score_final_course(CLEAN_DOCUMENT, rules_context={})

    assert report.paragraph_readability.avg_words_per_sentence > 0
    assert report.paragraph_readability.avg_words_per_paragraph > 0


def test_source_grounding_warning_absent_when_no_sources_were_available():
    report = score_final_course(CLEAN_DOCUMENT, rules_context={}, source_texts=None)
    assert report.source_grounding_warning is None

    report_empty_list = score_final_course(CLEAN_DOCUMENT, rules_context={}, source_texts=[])
    assert report_empty_list.source_grounding_warning is None


def test_source_grounding_warning_present_when_sources_available_but_unused():
    source_texts = ["thisisaveryuniquesignalword appears nowhere in the final text"]

    report = score_final_course(CLEAN_DOCUMENT, rules_context={}, source_texts=source_texts)

    assert report.source_grounding_warning is not None
    assert "crude keyword-overlap heuristic" in report.source_grounding_warning


def test_source_grounding_warning_absent_when_a_signal_word_is_present():
    document = CLEAN_DOCUMENT + "\nWe discussed budgeting extensively in this reel.\n"
    source_texts = ["A long article about budgeting strategies and habits."]

    report = score_final_course(document, rules_context={}, source_texts=source_texts)

    assert report.source_grounding_warning is None


def test_repetition_warning_flags_near_duplicate_paragraphs():
    duplicated = (
        "This is a fairly long paragraph that talks about budgeting basics in detail.\n"
        "This is a fairly long paragraph that talks about budgeting basics indeed.\n"
    )

    report = score_final_course(duplicated, rules_context={})

    assert report.repetition_warning is not None


def test_repetition_warning_absent_for_distinct_paragraphs():
    report = score_final_course(CLEAN_DOCUMENT, rules_context={})

    assert report.repetition_warning is None


def test_never_blocks_or_raises_on_empty_document():
    report = score_final_course("", rules_context={})

    assert report.teleprompter_clean is True
    assert report.module_lesson_structure_present is False
    assert report.paragraph_readability.avg_words_per_sentence == 0.0
