"""Source origin handling — transcript-derived sources across any category/intent."""

from app.generation.prompt_compiler import (
    PROMPT_COMPILER_VERSION,
    SourceForCompiler,
    compile_source_context,
)
from app.generation.source_distillation import DISTILLED_LABEL
from app.generation.source_memory_store import build_source_memory_payload, memory_matches_hash
from app.generation.source_origin import (
    TRANSCRIPT_DERIVED_LABEL,
    infer_source_origin,
    is_transcript_derived_memory,
    is_transcript_like_origin,
)
from app.generation.teleprompter_checks import find_forbidden_substrings
from app.models.enums import SourceOrigin
from app.schemas.generation import FinalCourse, FinalModule, FinalReel
from app.services.docx_export import extract_plain_text, render_final_course_docx

META_ADS_PROMISE = {
    "title": "Meta Ads for Egyptian Boutique Shops",
    "audience": "Beginner Egyptian shop owners",
    "outcome": "Launch and measure profitable Meta ads campaigns",
    "target_market": "egypt",
    "course_map_text": "Campaign setup, creative testing, ROAS measurement",
}

SAME_TOPIC_TRANSCRIPT = """
[00:00:12] Speaker 1: Meta ads campaign setup for Egyptian boutique shops in Cairo.
Measure ROAS weekly. Common mistake: people think Meta ads are magic before creative testing.
Learner objection: budget is too small for profitable campaigns.
Practical point: test one creative variable at a time before scaling spend.
"""

OFF_TOPIC_TRANSCRIPT = (
    "[00:00:01] Speaker 1: How to bake sourdough bread at home. Fermentation starter kitchen recipe flour yeast. "
    "Knead the dough and preheat the oven. Sourdough crust scoring technique. "
) * 12

OLD_COURSE_OUTDATED = """
[00:01:00] Module one lesson two: Meta ads for Egyptian boutique shops.
Use Facebook boost post from power editor in 2019 before the legacy interface changed.
This deprecated workflow still works before iOS 14 ATT changes. Measure ROAS weekly.
"""

GOOD_SPOKEN_SCRIPT = """\
خليني أوضح لك الحتة دي بسرعة.

الغلط هنا إن ناس كتير بتفهم الموضوع بالعكس لما الميزانية صغيرة.

اللي يفرق معاك عمليًا هو إنك تختبر متغير واحد في كل مرة قبل ما ترفع الإنفاق.
"""


def test_txt_raw_material_inferred_as_transcript_derived():
    memory = build_source_memory_payload(
        title="lesson.txt",
        category="raw_material",
        extracted_text=SAME_TOPIC_TRANSCRIPT,
        original_filename="lesson.txt",
        mime_type="text/plain",
        course_promise=META_ADS_PROMISE,
    )
    assert memory.get("file_format") == "txt"
    assert is_transcript_like_origin(memory.get("source_origin"))
    assert is_transcript_derived_memory(memory)
    assert memory.get("transcript_normalized") is True
    assert memory.get("raw_source_hash") != memory.get("normalized_text_hash")


def test_docx_transcript_not_treated_as_clean_written_document():
    origin = infer_source_origin(
        SAME_TOPIC_TRANSCRIPT,
        category="scientific_reference",
        original_filename="notes.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert origin != SourceOrigin.WRITTEN_DOCUMENT.value
    memory = build_source_memory_payload(
        title="notes.docx",
        category="scientific_reference",
        extracted_text=SAME_TOPIC_TRANSCRIPT,
        original_filename="notes.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        course_promise=META_ADS_PROMISE,
    )
    assert memory.get("source_origin") != SourceOrigin.WRITTEN_DOCUMENT.value
    assert memory.get("transcript_imperfection_version")


def test_dual_hash_raw_identity_preserved():
    raw_a = "[00:00:01] Meta ads ROAS test creative test creative"
    raw_b = "[00:00:99] Meta ads ROAS test creative test creative"
    mem_a = build_source_memory_payload(
        title="a.txt",
        category="transcript",
        extracted_text=raw_a,
        course_promise=META_ADS_PROMISE,
    )
    mem_b = build_source_memory_payload(
        title="b.txt",
        category="transcript",
        extracted_text=raw_b,
        course_promise=META_ADS_PROMISE,
    )
    assert mem_a["raw_source_hash"] != mem_b["raw_source_hash"]
    assert memory_matches_hash(mem_a, raw_a)
    assert not memory_matches_hash(mem_a, raw_b)


def test_conservative_normalization_does_not_guess_ambiguous_terms():
    ambiguous = "Set teh camapign buget with رواس and فيسبوك ادز before scaling"
    memory = build_source_memory_payload(
        title="ambiguous.txt",
        category="transcript",
        extracted_text=ambiguous,
        course_promise=META_ADS_PROMISE,
    )
    assert "teh" in ambiguous or "camapign" in ambiguous
    corrections = " ".join(memory.get("transcript_corrections") or [])
    assert "typo" not in corrections.lower()
    assert "restored technical term" not in corrections.lower()


def test_course_transcript_same_topic_becomes_raw_material_only():
    memory = build_source_memory_payload(
        title="ambiguous.txt",
        category="transcript",
        extracted_text=SAME_TOPIC_TRANSCRIPT,
        course_promise=META_ADS_PROMISE,
    )
    assert memory.get("topic_relevance") == "same_topic"
    assert memory.get("transcript_colloquial_only") is False
    snippet = memory.get("summary") or ""
    assert memory.get("facts") or memory.get("extracted_facts")
    excerpts = compile_source_context(
        [
            SourceForCompiler(
                source_id=1,
                category="transcript",
                priority="high",
                text=snippet,
                memory=memory,
            )
        ],
        query_text="ROAS",
    )
    assert excerpts
    excerpt_text = excerpts[0].text.lower()
    assert (
        "untrusted raw material" in excerpt_text
        or "transcript-derived" in excerpt_text
        or "course transcript raw material" in excerpt_text
        or "same-topic" in excerpt_text
        or "raw material" in excerpt_text
    )


def test_old_course_transcript_flags_outdated_and_official_docs():
    memory = build_source_memory_payload(
        title="old-course.txt",
        category="old_course",
        extracted_text=OLD_COURSE_OUTDATED,
        course_promise=META_ADS_PROMISE,
    )
    assert memory.get("source_origin") == SourceOrigin.OLD_COURSE_TRANSCRIPT.value
    assert memory.get("outdated_warnings") or any(
        "official" in w.lower()
        for w in (memory.get("blocked_content_warnings") or [])
    )


def test_off_topic_transcript_cannot_support_factual_claims():
    memory = build_source_memory_payload(
        title="off-topic.txt",
        category="raw_material",
        extracted_text=OFF_TOPIC_TRANSCRIPT,
        original_filename="chat.txt",
        course_promise=META_ADS_PROMISE,
    )
    assert memory.get("transcript_colloquial_only") is True
    assert memory.get("facts") == []
    assert memory.get("extracted_facts") == []


def test_course_transcript_wording_not_copied_in_compiler_excerpt():
    hooky = (
        "Shocking secret hook openers forever champions rise! Stay until the end cliffhanger.\n"
        + SAME_TOPIC_TRANSCRIPT
    )
    memory = build_source_memory_payload(
        title="ambiguous.txt",
        category="transcript",
        extracted_text=hooky,
        course_promise=META_ADS_PROMISE,
    )
    excerpts = compile_source_context(
        [
            SourceForCompiler(
                source_id=1,
                category="transcript",
                priority="high",
                text="distilled snippet",
                memory=memory,
            )
        ],
        query_text="ROAS",
    )
    body = excerpts[0].text.lower()
    assert "shocking secret" not in body
    assert "forever champions" not in body


def test_transcript_noise_does_not_leak_into_final_script():
    course = FinalCourse(
        title="Meta Ads Course",
        full_text="ignored",
        modules=[
            FinalModule(
                module_id="m1",
                title="Campaign Basics",
                reels=[
                    FinalReel(
                        reel_id="m1-r1",
                        title="ROAS Setup",
                        script_text=GOOD_SPOKEN_SCRIPT,
                    ),
                ],
            )
        ],
    )
    plain = extract_plain_text(render_final_course_docx(course)).lower()
    for leak in (
        "transcript-derived",
        "asr",
        "transcript_corrections",
        "source_origin",
        "transcript imperfection",
        TRANSCRIPT_DERIVED_LABEL.split(".")[0].lower()[:40],
    ):
        assert leak not in plain


def test_final_docx_has_no_source_origin_or_internal_transcript_labels():
    course = FinalCourse(
        title="Meta Ads Course",
        full_text="ignored",
        modules=[
            FinalModule(
                module_id="m1",
                title="Campaign Basics",
                reels=[
                    FinalReel(
                        reel_id="m1-r1",
                        title="ROAS Setup",
                        script_text=GOOD_SPOKEN_SCRIPT,
                    ),
                ],
            )
        ],
    )
    docx_bytes = render_final_course_docx(course)
    plain = extract_plain_text(docx_bytes)
    forbidden = find_forbidden_substrings(
        plain
        + " source_origin transcript_corrections ASR transcript-derived uncertain_terms"
    )
    assert "source_origin" in forbidden
    assert "transcript_corrections" in forbidden
    assert "asr" in forbidden
    assert "source_origin" not in plain.lower()
    assert "transcript_corrections" not in plain.lower()
    assert PROMPT_COMPILER_VERSION == "2.21"
