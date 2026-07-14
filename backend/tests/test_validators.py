"""Tests for app/validators/."""

import json

from app.schemas.generation import GeneratedReel, ReviewStatus
from app.validators.forbidden_phrase_checker import check_forbidden_phrases
from app.validators.length_checker import check_length
from app.validators.opening_checker import check_opening
from app.validators.repetition_checker import check_repetition


def _reel(reel_id, title, script_text, used_ideas=None, used_examples=None) -> GeneratedReel:
    return GeneratedReel(
        reel_id=reel_id,
        module_id="m1",
        title=title,
        script_text=script_text,
        used_ideas=used_ideas or [],
        used_examples=used_examples or [],
        self_check_status=ReviewStatus.PASS,
    )


# --- forbidden_phrase_checker ------------------------------------------------

FORBIDDEN_RULES_CONTEXT = {
    "rukn_forbidden_phrases": json.dumps(
        {
            "phrases": [
                {
                    "phrase": "في الريل ده",
                    "severity": "high",
                    "replacement_hint": "Start directly with the content.",
                },
                {"phrase": "خلينا نتكلم عن", "severity": "high"},
            ]
        }
    )
}


def test_forbidden_phrase_checker_finds_match():
    text = "أهلاً بيكم. في الريل ده هنشرح VLOOKUP."
    matches = check_forbidden_phrases(text, FORBIDDEN_RULES_CONTEXT)
    assert len(matches) == 1
    assert matches[0].phrase == "في الريل ده"
    assert matches[0].severity == "high"
    assert matches[0].replacement_hint == "Start directly with the content."


def test_forbidden_phrase_checker_no_match_returns_empty():
    text = "This script has no forbidden phrases at all."
    assert check_forbidden_phrases(text, FORBIDDEN_RULES_CONTEXT) == []


def test_forbidden_phrase_checker_handles_missing_rule():
    assert check_forbidden_phrases("any text", {}) == []


def test_forbidden_phrase_checker_handles_malformed_json():
    assert check_forbidden_phrases("any text", {"rukn_forbidden_phrases": "{not json"}) == []


def test_forbidden_phrase_checker_finds_multiple_matches():
    text = "في الريل ده, خلينا نتكلم عن VLOOKUP."
    matches = check_forbidden_phrases(text, FORBIDDEN_RULES_CONTEXT)
    assert len(matches) == 2


# --- length_checker -----------------------------------------------------

def test_length_checker_flags_too_short():
    reel = _reel("r1", "Title", "Too short.")
    issues = check_length(reel)
    assert len(issues) == 1
    assert issues[0].reason == "too_short"


def test_length_checker_flags_too_long():
    reel = _reel("r1", "Title", "word " * 600)
    issues = check_length(reel)
    assert len(issues) == 1
    assert issues[0].reason == "too_long"


def test_length_checker_passes_reasonable_length():
    reel = _reel("r1", "Title", "word " * 100)
    assert check_length(reel) == []


# --- repetition_checker ---------------------------------------------------

def test_repetition_checker_flags_similar_title():
    prior = _reel("r1", "How to use VLOOKUP in Excel", "Some script.")
    candidate = _reel("r2", "How to use VLOOKUP in Excel!", "Different script text here.")

    matches = check_repetition(candidate, [prior])

    assert any(m.field == "title" for m in matches)


def test_repetition_checker_flags_similar_used_ideas():
    prior = _reel("r1", "Title A", "Script A.", used_ideas=["sum function basics"])
    candidate = _reel("r2", "Title B", "Script B, totally different text.", used_ideas=["sum function basics"])

    matches = check_repetition(candidate, [prior])

    assert any(m.field == "used_idea" for m in matches)


def test_repetition_checker_ignores_self():
    reel = _reel("r1", "Title", "Script.", used_ideas=["idea"])
    assert check_repetition(reel, [reel]) == []


def test_repetition_checker_passes_distinct_reels():
    prior = _reel("r1", "Understanding pivot tables", "Pivot table script.", used_ideas=["pivot basics"])
    candidate = _reel("r2", "Writing your first macro", "Macro script content.", used_ideas=["macro recording"])

    assert check_repetition(candidate, [prior]) == []


# --- opening_checker -----------------------------------------------------

def test_opening_checker_flags_repeated_opening():
    prior = _reel("r1", "Title A", "Welcome back everyone, today we are going to look at formulas.")
    candidate = _reel(
        "r2", "Title B", "Welcome back everyone, today we are going to look at charts."
    )

    issues = check_opening(candidate, [prior])

    assert len(issues) == 1
    assert issues[0].repeats_reel_id == "r1"


def test_opening_checker_passes_distinct_openings():
    prior = _reel("r1", "Title A", "Formulas can save you a lot of manual work.")
    candidate = _reel("r2", "Title B", "Charts turn raw numbers into something readable.")

    assert check_opening(candidate, [prior]) == []


def test_opening_checker_ignores_self():
    reel = _reel("r1", "Title", "Some opening text here for the reel.")
    assert check_opening(reel, [reel]) == []
