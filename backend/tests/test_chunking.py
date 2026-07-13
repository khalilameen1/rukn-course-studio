"""Tests for app/services/chunking.py."""

from app.services.chunking import chunk_text


def test_empty_text_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n  ") == []


def test_splits_by_markdown_headings_when_present():
    text = (
        "# Introduction\n"
        "Some intro text.\n"
        "\n"
        "## Formulas\n"
        "Formula content here.\n"
        "More formula content.\n"
    )

    chunks = chunk_text(text)

    assert [c.heading for c in chunks] == ["Introduction", "Formulas"]
    assert "Some intro text." in chunks[0].text
    assert "Formula content here." in chunks[1].text
    assert "More formula content." in chunks[1].text


def test_content_before_first_heading_is_dropped_if_empty():
    text = "# Only Heading\nBody text."
    chunks = chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0].heading == "Only Heading"
    assert chunks[0].text == "Body text."


def test_falls_back_to_paragraphs_when_no_headings():
    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."

    chunks = chunk_text(text)

    assert all(c.heading is None for c in chunks)
    joined = " ".join(c.text for c in chunks)
    assert "First paragraph." in joined
    assert "Second paragraph." in joined
    assert "Third paragraph." in joined


def test_paragraph_chunks_are_capped_in_size():
    long_paragraph = "word " * 300  # ~1500 chars, over MAX_CHUNK_CHARS on its own
    text = f"{long_paragraph}\n\n{long_paragraph}\n\n{long_paragraph}"

    chunks = chunk_text(text)

    # Each long paragraph should force a new chunk rather than merging.
    assert len(chunks) >= 3


def test_chunk_indexes_are_sequential():
    text = "# A\ntext a\n\n# B\ntext b\n\n# C\ntext c"
    chunks = chunk_text(text)
    assert [c.index for c in chunks] == list(range(len(chunks)))
