"""Tests for app/services/source_analysis.py."""

from app.services.source_analysis import (
    SUMMARY_MAX_CHARS,
    analyze_source_text,
    select_relevant_chunks,
)


def test_analyze_short_text_summary_is_full_text():
    result = analyze_source_text("Short text about VLOOKUP.", "scientific_reference")
    assert result.source_summary == "Short text about VLOOKUP."


def test_analyze_long_text_summary_is_truncated():
    long_text = "This is a sentence about formulas. " * 30  # well over SUMMARY_MAX_CHARS
    result = analyze_source_text(long_text, "scientific_reference")

    assert len(result.source_summary) <= SUMMARY_MAX_CHARS + 3  # allow "..." fallback
    assert result.source_summary != long_text


def test_key_points_use_headings_when_present():
    text = "# Getting Started\nSome content.\n\n# Advanced Topics\nMore content."
    result = analyze_source_text(text, "scientific_reference")

    assert result.key_points == ["Getting Started", "Advanced Topics"]


def test_key_points_fall_back_to_first_sentence_without_headings():
    text = "VLOOKUP finds values in a table. It is one of the most common formulas."
    result = analyze_source_text(text, "scientific_reference")

    assert result.key_points == ["VLOOKUP finds values in a table."]


def test_avoid_points_are_category_driven():
    flow = analyze_source_text("some text", "flow_reference")
    old = analyze_source_text("some text", "old_course")
    raw = analyze_source_text("some text", "raw_material")
    scientific = analyze_source_text("some text", "scientific_reference")

    assert "factual source" in flow.avoid_points[0]
    assert "outdated" in old.avoid_points[0]
    assert "uncertain" in raw.avoid_points[0]
    assert scientific.avoid_points == []


def test_select_relevant_chunks_ranks_by_keyword_overlap():
    chunks = [
        {"heading": "VLOOKUP basics", "text": "How to use VLOOKUP to find values."},
        {"heading": "Formatting cells", "text": "How to change cell colors and borders."},
        {"heading": "Advanced VLOOKUP", "text": "VLOOKUP with approximate match and ranges."},
    ]

    selected = select_relevant_chunks(chunks, "Write a reel about VLOOKUP formulas", max_chunks=2)

    assert len(selected) == 2
    headings = [c["heading"] for c in selected]
    assert "VLOOKUP basics" in headings
    assert "Advanced VLOOKUP" in headings
    assert "Formatting cells" not in headings


def test_select_relevant_chunks_returns_empty_when_no_overlap():
    chunks = [{"heading": "Formatting cells", "text": "Colors and borders."}]
    selected = select_relevant_chunks(chunks, "xyz123 nonexistent topic", max_chunks=2)
    assert selected == []


def test_select_relevant_chunks_respects_max_chunks():
    chunks = [
        {"heading": f"Topic {i}", "text": "budget formulas excel"} for i in range(10)
    ]
    selected = select_relevant_chunks(chunks, "budget formulas excel", max_chunks=3)
    assert len(selected) == 3
