"""Transcript imperfection hygiene — conservative STT/OCR noise handling."""

from app.generation.source_memory_store import build_source_memory_payload
from app.generation.transcript_imperfection import (
    TRANSCRIPT_IMPERFECTION_NOTE,
    TRANSCRIPT_IMPERFECTION_VERSION,
    dedupe_transcript_fragments,
    fix_obvious_ocr_substitutions,
    normalize_transcript_text,
    strip_transcript_timestamps,
)
from app.seed_admin_knowledge import TRANSCRIPT_TOPIC_RELEVANCE_GATE

META_ADS_PROMISE = {
    "title": "Meta Ads for Egyptian Boutique Shops",
    "audience": "Beginner Egyptian shop owners",
    "outcome": "Launch and measure profitable Meta ads campaigns",
    "target_market": "egypt",
    "course_map_text": "Campaign setup, creative testing, ROAS measurement",
}


def test_gate_documents_transcript_imperfection_mistrust():
    assert "do not trust wording literally" in TRANSCRIPT_TOPIC_RELEVANCE_GATE.lower()
    assert "source origin" in TRANSCRIPT_TOPIC_RELEVANCE_GATE.lower()


def test_duplicated_transcript_fragments_collapsed():
    raw = (
        "Test one creative before scaling. "
        "Test one creative before scaling. "
        "test creative test creative before scale"
    )
    cleaned, notes = dedupe_transcript_fragments(raw)
    assert cleaned.lower().count("test one creative before scaling") == 1
    assert notes


def test_obvious_ocr_substitutions_only():
    raw = "Use Faceb00k and Metа Ads with R0AS budget"
    cleaned, notes = fix_obvious_ocr_substitutions(raw)
    assert "Facebook" in cleaned
    assert "Meta Ads" in cleaned
    assert "ROAS" in cleaned
    assert notes


def test_conservative_normalization_skips_semantic_guessing():
    raw = "Set teh camapign buget with رواس before scaling"
    result = normalize_transcript_text(raw)
    assert "teh" in result.cleaned_text
    assert "camapign" in result.cleaned_text
    assert "رواس" in result.cleaned_text
    assert not any("typo" in c.lower() for c in result.corrections)


def test_timestamps_and_speaker_tags_stripped():
    raw = "[00:00:05] Speaker 1: Meta ads setup\n00:01:00 --> 00:01:30 budget tips"
    cleaned, notes = strip_transcript_timestamps(raw)
    assert "00:00" not in cleaned
    assert "Speaker 1:" not in cleaned
    assert "Meta ads setup" in cleaned
    assert notes


def test_transcript_memory_applies_imperfection_metadata():
    raw = (
        "[00:01:00] Meta ads for Egyptian boutique shops. "
        "test creative test creative before scale"
    )
    memory = build_source_memory_payload(
        title="lesson.txt",
        category="transcript",
        extracted_text=raw,
        course_promise=META_ADS_PROMISE,
    )
    assert memory.get("transcript_imperfection_version") == TRANSCRIPT_IMPERFECTION_VERSION
    assert memory.get("raw_source_hash")
    assert memory.get("normalized_text_hash")
    assert memory.get("transcript_normalized") is True
    assert memory.get("source_origin")
    blocked = " ".join(memory.get("blocked_content_warnings") or [])
    assert "not trusted literally" in blocked.lower()
