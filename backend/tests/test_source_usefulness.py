"""Source usefulness / credit hygiene — cheap distillation, not rejection."""

from app.generation.prompt_compiler import (
    PROMPT_COMPILER_VERSION,
    SourceForCompiler,
    compile_source_context,
)
from app.generation.source_memory_store import (
    build_source_memory_payload,
    compute_source_hash,
    format_memory_snippet,
    memory_matches_hash,
)
from app.generation.source_usefulness import (
    LOW_SIGNAL_BRIEF_MAX_CHARS,
    assess_source_usefulness,
    format_low_signal_snippet,
)
from app.generation.teleprompter_checks import find_forbidden_substrings
from app.schemas.generation import FinalCourse, FinalModule, FinalReel
from app.seed_admin_knowledge import SOURCE_DISTILLATION_GATE
from app.services.docx_export import extract_plain_text, render_final_course_docx

META = {
    "title": "Meta Ads for Egyptian Boutique Shops",
    "audience": "Beginner Egyptian shop owners",
    "outcome": "Launch and measure profitable Meta ads campaigns",
    "target_market": "egypt",
    "course_map_text": "Campaign setup, creative testing, ROAS measurement",
}

RICH_SOURCE = """
Meta ads campaign setup for Egyptian boutique shops in Cairo. Measure ROAS weekly.
Common mistake: people think Meta ads are magic before creative testing.
Learner objection: budget is too small for profitable campaigns.
Practical point: test one creative variable at a time before scaling spend.
Warning: do not scale before proof of offer for boutique shops.
Terminology: ROAS, creative, campaign, pixel.
"""

SHALLOW_FILLER = (
    "Furthermore, it is important to note that marketing is good. "
    "Moreover, in conclusion, ads help businesses grow somehow. "
) * 3

OFF_TOPIC = (
    "[00:00:01] Speaker 1: How to bake sourdough bread at home. "
    "Fermentation starter kitchen recipe flour yeast. "
) * 10

GOOD_SCRIPT = """\
خليني أوضح لك الحتة دي بسرعة.
الغلط هنا إن ناس كتير بتفهم الموضوع بالعكس لما الميزانية صغيرة.
"""


def test_gate_documents_usefulness_credit_hygiene():
    assert "usefulness" in SOURCE_DISTILLATION_GATE.lower()
    assert "low_signal" in SOURCE_DISTILLATION_GATE.lower()
    assert "mistrust does not mean rejection" in SOURCE_DISTILLATION_GATE.lower()
    assert PROMPT_COMPILER_VERSION == "2.21"


def test_useful_source_stays_distilled_not_rejected():
    memory = build_source_memory_payload(
        title="good.pdf",
        category="scientific_reference",
        extracted_text=RICH_SOURCE,
        original_filename="good.pdf",
        course_promise=META,
    )
    assert memory.get("low_signal") is False
    assert memory.get("source_usefulness") in ("high", "medium")
    assert memory.get("include_mode") in ("full_distilled", "brief_candidates")
    assert memory.get("has_unique_useful_material") is True
    snippet = format_memory_snippet(memory)
    assert "ROAS" in snippet or "creative" in snippet.lower()
    assert "[LOW_SIGNAL" not in snippet


def test_low_value_source_marked_low_signal_brief_only():
    memory = build_source_memory_payload(
        title="filler.txt",
        category="raw_material",
        extracted_text=SHALLOW_FILLER,
        original_filename="filler.txt",
        course_promise=META,
    )
    assert memory.get("shallow_source_flag") is True or memory.get("low_signal") is True
    assert memory.get("low_signal") is True
    assert memory.get("include_mode") == "brief_candidates"
    snippet = format_memory_snippet(memory)
    assert "[LOW_SIGNAL" in snippet
    assert len(snippet) <= LOW_SIGNAL_BRIEF_MAX_CHARS + 80


def test_off_topic_transcript_is_colloquial_only_not_full_dump():
    memory = build_source_memory_payload(
        title="bread.txt",
        category="transcript",
        extracted_text=OFF_TOPIC,
        course_promise=META,
    )
    assert memory.get("transcript_colloquial_only") is True
    assert memory.get("low_signal") is True
    assert memory.get("include_mode") == "colloquial_only"
    assert memory.get("facts") == [] or memory.get("extracted_facts") == []


def test_unchanged_source_cached_by_raw_hash():
    memory = build_source_memory_payload(
        title="cache.pdf",
        category="scientific_reference",
        extracted_text=RICH_SOURCE,
        course_promise=META,
    )
    assert memory.get("raw_source_hash") == compute_source_hash(RICH_SOURCE)
    assert memory_matches_hash(memory, RICH_SOURCE)
    assert not memory_matches_hash(memory, RICH_SOURCE + " x")


def test_low_signal_excluded_from_expensive_full_context():
    rich = build_source_memory_payload(
        title="rich.pdf",
        category="scientific_reference",
        extracted_text=RICH_SOURCE,
        course_promise=META,
    )
    weak = build_source_memory_payload(
        title="weak.txt",
        category="raw_material",
        extracted_text=SHALLOW_FILLER,
        course_promise=META,
    )
    # Force low_signal on weak for deterministic compiler behavior.
    weak["low_signal"] = True
    weak["include_mode"] = "brief_candidates"
    weak["source_usefulness"] = "low"

    excerpts = compile_source_context(
        [
            SourceForCompiler(
                source_id=1,
                category="scientific_reference",
                priority="high",
                text="placeholder",
                memory=rich,
            ),
            SourceForCompiler(
                source_id=2,
                category="raw_material",
                priority="medium",
                text="placeholder",
                memory=weak,
            ),
        ],
        query_text="ROAS",
        max_total_chars=2500,
    )
    by_id = {e.source_id: e for e in excerpts}
    assert "[LOW_SIGNAL" in by_id[2].text or len(by_id[2].text) <= LOW_SIGNAL_BRIEF_MAX_CHARS + 250
    assert len(by_id[2].text) < len(by_id[1].text) or "[LOW_SIGNAL" in by_id[2].text


def test_full_book_not_resent_in_compiler():
    long_book = ("Chapter about Meta ads attribution and ROAS for boutique brands. " * 120)
    memory = build_source_memory_payload(
        title="book.pdf",
        category="scientific_reference",
        extracted_text=long_book,
        original_filename="book.pdf",
        course_promise=META,
    )
    excerpts = compile_source_context(
        [
            SourceForCompiler(
                source_id=1,
                category="scientific_reference",
                priority="high",
                text="placeholder",
                memory=memory,
            )
        ],
        query_text="ROAS",
    )
    assert len(excerpts[0].text) < len(long_book) // 5
    assert long_book[:400] not in excerpts[0].text


def test_docx_has_no_usefulness_metadata_leak():
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
    assert "low_signal" not in plain.lower()
    assert "source_usefulness" not in plain.lower()


def test_format_low_signal_snippet_is_compact():
    mem = {
        "title": "weak",
        "useful_concepts": ["test one creative", "measure ROAS"],
        "outdated_warnings": ["old UI path"],
        "source_risk_flags": ["shallow_or_generic", "repetitive_or_filler"],
    }
    text = format_low_signal_snippet(mem)
    assert "[LOW_SIGNAL" in text
    assert len(text) <= LOW_SIGNAL_BRIEF_MAX_CHARS
