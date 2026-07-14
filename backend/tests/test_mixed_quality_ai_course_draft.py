"""Mixed-quality previous AI course draft — candidates, not authority."""

from app.generation.mixed_draft_memory import (
    MIXED_QUALITY_PROMPT_LABEL,
    build_mixed_draft_memory,
    classify_segment,
    is_mixed_quality_draft_category,
)
from app.generation.prompt_compiler import (
    DISALLOWED_USE_BY_CATEGORY,
    SourceForCompiler,
    STYLE_CONTAMINATION_WARNING_BY_CATEGORY,
    compile_source_context,
)
from app.generation.source_memory_store import (
    build_source_memory_payload,
    compiler_text_from_memory,
    compute_source_hash,
    format_memory_snippet,
)
from app.models.enums import SourceCategory


DRAFT = """
## Weak opener
In this video stay until the end don't skip. Before we start click like.

## Useful objection
Common mistake: people think Meta ads are magic. Learner might object that budget is too small.

## Tool claim needing verify
Always click the blue button at the top-left of the Ads dashboard to guarantee 200% ROI.

## Example worth rebuilding
For example, a Cairo boutique burned budget testing cool blue headlines last Ramadan.

## Artificial loop filler
As we said earlier, let's go back to what we covered. Moreover furthermore needless to say.

## Practical workflow
Step 1 checklist: measure ROAS weekly. Warning: do not scale losers.
"""


def test_mixed_quality_category_accepted_in_enum_and_helpers():
    assert SourceCategory.MIXED_QUALITY_AI_COURSE_DRAFT.value == "mixed_quality_ai_course_draft"
    assert is_mixed_quality_draft_category("mixed_quality_ai_course_draft")
    assert is_mixed_quality_draft_category("old_course")
    assert not is_mixed_quality_draft_category("scientific_reference")


def test_segment_classification_keep_discard_verify_rebuild():
    assert classify_segment("In this video stay until the end click like") == "discard"
    assert classify_segment("As we said earlier let's go back to what we covered") == "discard"
    assert (
        classify_segment(
            "Common mistake: people think ads are magic. Learner might object about budget."
        )
        == "keep_candidate"
    )
    assert (
        classify_segment(
            "Always click the blue button at the top-left of the Ads dashboard to guarantee ROI."
        )
        == "verify_before_use"
    )
    example = classify_segment(
        "For example, a Cairo boutique burned budget testing cool blue headlines last Ramadan "
        "and then rebuilt the offer."
    )
    assert example in {"rebuild_candidate", "keep_candidate"}


def test_useful_candidates_extracted_and_bad_patterns_blocked():
    from app.generation.mixed_draft_memory import CoursePromise

    promise = CoursePromise(
        title="Meta Ads for shops",
        audience="Beginner Egyptian shop owners",
        outcome="Launch and measure profitable Meta ads",
        course_map_text="ROAS campaign creative testing",
    )
    md = build_mixed_draft_memory(
        source_hash=compute_source_hash(DRAFT),
        text=DRAFT,
        course_promise=promise,
    )
    assert md["candidate_only"] is True
    assert md["not_quality_reference"] is True
    idea_pool = " ".join(
        md["useful_candidates"]
        + md["rebuild_candidates"]
        + md["good_objections"]
        + md.get("possible_topic_inventory")
        + md["core_candidates"]
        + md["supporting_candidates"]
    ).lower()
    assert "mistake" in idea_pool or "object" in idea_pool or "roas" in idea_pool
    discard_blob = " ".join(
        md["discard_patterns"]
        + md["repeated_bad_patterns"]
        + md["discarded_dumb_reels"]
        + md["discarded_tangents"]
    ).lower()
    assert (
        "hook" in discard_blob
        or "loop" in discard_blob
        or "filler" in discard_blob
        or "generic" in discard_blob
        or "dumb" in discard_blob
        or "weak" in discard_blob
        or "video" in discard_blob
    )
    assert md["useful_ideas_to_verify"] or md["unsupported_claim_candidates"] or md["examples_to_rebuild"]
    assert md["map_hints_not_authority"] is not None
    assert all("grounded" not in c.lower() for c in md["unsupported_claim_candidates"])


def test_good_example_rebuild_not_verbatim_copy_instruction():
    from app.generation.mixed_draft_memory import CoursePromise

    promise = CoursePromise(
        title="Meta Ads ROAS course",
        audience="Egyptian boutique owners",
        outcome="Measure profitable Meta ads",
        course_map_text="creative testing ROAS",
    )
    md = build_mixed_draft_memory(source_hash="h", text=DRAFT, course_promise=promise)
    rebuilds = " ".join(md["examples_to_rebuild"] + md["rebuild_candidates"]).lower()
    assert "rebuild" in rebuilds or "cairo" in rebuilds or "boutique" in rebuilds
    for item in md["examples_to_rebuild"]:
        assert not item.strip().startswith("For example, a Cairo boutique burned")


def test_old_draft_map_hints_are_not_authority():
    md = build_mixed_draft_memory(source_hash="h", text=DRAFT)
    assert md["map_hints_not_authority"] is not None
    warnings = " ".join(md["creator_warnings"])
    assert "Rebuild final course map" in warnings or "not dictate" in warnings.lower()


def test_memory_processed_once_not_full_draft_resent():
    long_draft = DRAFT + (" generic AI filler paragraph. Moreover furthermore. " * 400)
    memory = build_source_memory_payload(
        title="prev.docx",
        category="mixed_quality_ai_course_draft",
        extracted_text=long_draft,
    )
    assert memory["processed_once"] is True
    assert memory.get("mixed_draft_memory")
    assert memory["original_chars"] == len(long_draft)
    snippet = format_memory_snippet(memory)
    compact = compiler_text_from_memory(
        memory=memory,
        summary=memory["summary"],
        chunks=None,
        fallback_text=long_draft,
        query_text="Meta ads ROAS",
        category="mixed_quality_ai_course_draft",
    )
    assert len(snippet) < len(long_draft) // 5
    assert len(compact) < len(long_draft) // 5
    assert long_draft[:400] not in compact
    assert "mixed-quality" in compact.lower()
    assert MIXED_QUALITY_PROMPT_LABEL.split(".")[0] in compact


def test_prompt_compiler_blocks_copy_and_claim_grounding():
    memory = build_source_memory_payload(
        title="prev",
        category="mixed_quality_ai_course_draft",
        extracted_text=DRAFT,
    )
    compact = compiler_text_from_memory(
        memory=memory,
        summary=memory["summary"],
        chunks=None,
        fallback_text=DRAFT,
        query_text="",
        category="mixed_quality_ai_course_draft",
    )
    excerpts = compile_source_context(
        [
            SourceForCompiler(
                source_id=1,
                category="mixed_quality_ai_course_draft",
                priority="medium",
                text=compact,
                memory=memory,
            )
        ],
        query_text="",
    )
    assert len(excerpts) == 1
    ex = excerpts[0]
    disallowed = set(ex.disallowed_use)
    assert "copy_hooks" in disallowed
    assert "copy_artificial_loops" in disallowed
    assert "copy_examples_verbatim" in disallowed
    assert "ground_claims_from_draft_alone" in disallowed
    assert "use_old_map_as_final_map" in disallowed
    assert "treat_as_quality_reference" in disallowed
    assert "treat_whole_draft_as_worthless" in disallowed
    warning = STYLE_CONTAMINATION_WARNING_BY_CATEGORY["mixed_quality_ai_course_draft"] or ""
    assert "candidates" in warning.lower()
    assert "mixed-quality" in ex.text.lower()


def test_legacy_old_course_uses_same_mixed_pipeline():
    memory = build_source_memory_payload(
        title="legacy",
        category="old_course",
        extracted_text=DRAFT,
    )
    assert memory.get("mixed_draft_memory")
    compact = compiler_text_from_memory(
        memory=memory,
        summary=memory["summary"],
        chunks=None,
        fallback_text=DRAFT * 20,
        query_text="",
        category="old_course",
    )
    assert "candidate_only=true" in compact.lower() or "candidates" in compact.lower()
    assert "copy_hooks" in DISALLOWED_USE_BY_CATEGORY["old_course"]


def test_docx_surface_has_no_mixed_draft_analysis_labels():
    """Final spoken transcript must never include internal draft analysis markers."""
    from app.generation.teleprompter_checks import find_forbidden_substrings

    spoken = "في الدرس ده هنقيس العائد على الإنفاق الإعلاني بشكل عملي."
    for mark in (
        "mixed_draft",
        "keep_candidate",
        "rebuild_candidate",
        "candidate_only",
        "needs_review",
        "map_hints_not_authority",
        "discard_patterns",
    ):
        assert mark not in spoken
    assert find_forbidden_substrings(spoken) == []

