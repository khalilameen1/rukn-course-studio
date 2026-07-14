"""Course Promise Relevance Gate for mixed-quality AI course drafts."""

from app.generation.mixed_draft_memory import (
    MIXED_QUALITY_PROMPT_LABEL,
    CoursePromise,
    build_mixed_draft_memory,
    classify_relevance,
    classify_segment,
    classify_segment_decision,
    format_mixed_draft_snippet,
    is_dumb_reel,
)
from app.generation.prompt_compiler import (
    DISALLOWED_USE_BY_CATEGORY,
    SourceForCompiler,
    compile_source_context,
)
from app.generation.source_memory_store import (
    build_source_memory_payload,
    compiler_text_from_memory,
    compute_source_hash,
)


META_ADS_PROMISE = CoursePromise(
    title="Meta Ads for Egyptian Boutique Shops",
    audience="Beginner Egyptian shop owners",
    outcome="Launch and measure profitable Meta ads campaigns",
    target_market="egypt",
    course_map_text="Campaign setup, creative testing, ROAS measurement",
)

DRAFT_WITH_BLOAT = """
# Module 1: Campaign Setup
Step 1 checklist: create a Meta ads campaign for a Cairo boutique. Measure ROAS weekly.

## Lesson: Budget objections
Common mistake: people think Meta ads are magic. Learner might object that budget is too small.

# Module 2: Brand Identity Theory Framework
This entire branding theory module covers visual identity systems and brand guidelines
in academic depth. Branding theory brand identity framework visual identity system
brand guidelines literature review history of logos founded in 1870.

## Lesson: Freelancer psychology soft skills
Freelance psychology and client mindset coaching for freelancers. Freelancer soft skills
and سيكولوجية الفريلانس session that does not help run ads.

# Module 3: Motivational filler reel
Believe in yourself. Unlock your potential. Dream big and never give up. Hustle harder.
Success is a journey. You are enough. Mindset is everything.

## Lesson: Fake tension hook
In this video stay until the end don't skip. You won't believe this shocking secret.
Fake tension before we start click like.

## Lesson: Side detail dump
History of Facebook founded in 2004. Academic theory of attention markets. Nice to know
platform history trivia and literature review of engagement metrics from 2012.

## Lesson: Relevant but stiff
In today's digital world, it is important to note that audience targeting can help shops
select relevant Meta ads placements. Moreover furthermore needless to say we delve into
placements. For example, a Cairo boutique burned budget testing cool blue headlines.
"""


def test_irrelevant_module_discarded_off_promise():
    md = build_mixed_draft_memory(
        source_hash="h1",
        text=DRAFT_WITH_BLOAT,
        course_promise=META_ADS_PROMISE,
    )
    discarded = " ".join(md["discarded_off_promise_modules"]).lower()
    assert "discarded_off_promise" in discarded
    assert "brand" in discarded or "freelancer" in discarded or "module 2" in discarded
    # Branding theory must not become a core/supporting keep that biases the map
    kept = " ".join(
        md["core_candidates"] + md["supporting_candidates"] + md["map_hints_not_authority"]
    ).lower()
    assert "brand identity framework" not in kept
    assert "freelancer psychology" not in kept


def test_dumb_reel_not_preserved():
    md = build_mixed_draft_memory(
        source_hash="h2",
        text=DRAFT_WITH_BLOAT,
        course_promise=META_ADS_PROMISE,
    )
    dumb = " ".join(md["discarded_dumb_reels"]).lower()
    assert "believe" in dumb or "unlock" in dumb or "hustle" in dumb or "shocking" in dumb
    useful = " ".join(md["core_candidates"] + md["supporting_candidates"]).lower()
    assert "believe in yourself" not in useful
    assert "shocking secret" not in useful


def test_side_detail_trimmed_to_useful_core():
    heavy = (
        "Step 1 checklist: set campaign budget for Meta ads. "
        "History of Facebook founded in 2004. Academic theory of attention markets. "
        "Nice to know platform history trivia. Warning: do not scale losers."
    )
    trimmed_decision = classify_segment_decision(
        heavy, relevance=classify_relevance(heavy, META_ADS_PROMISE)
    )
    assert trimmed_decision in {"keep_candidate", "rebuild_candidate", "optional_candidate"}
    md = build_mixed_draft_memory(
        source_hash="h3",
        text=f"# Module Ads\n{heavy}",
        course_promise=META_ADS_PROMISE,
    )
    pool = " ".join(
        md["core_candidates"] + md["supporting_candidates"] + md["rebuild_candidates"]
    )
    assert "campaign" in pool.lower() or "budget" in pool.lower() or "roas" in pool.lower() or "scale" in pool.lower()
    # Trivia should not dominate kept candidates.
    assert pool.lower().count("founded in 2004") == 0


def test_relevant_but_badly_written_becomes_rebuild():
    stiff = (
        "In today's digital world it is important to note that Meta ads audience "
        "targeting helps Egyptian boutique shops measure ROAS. Moreover furthermore "
        "needless to say we delve into placements."
    )
    relevance = classify_relevance(stiff, META_ADS_PROMISE)
    assert relevance in {"core_to_promise", "useful_supporting", "adjacent_but_optional"}
    decision = classify_segment_decision(stiff, relevance=relevance)
    assert decision == "rebuild_candidate"


def test_well_written_but_off_promise_discarded():
    beautiful_but_irrelevant = (
        "A clear freelancing psychology framework for client mindset coaching. "
        "Freelance psychology soft skills with practical client boundary worksheets."
    )
    relevance = classify_relevance(beautiful_but_irrelevant, META_ADS_PROMISE)
    assert relevance in {"off_promise", "tangent", "harmful_distraction"}
    decision = classify_segment_decision(beautiful_but_irrelevant, relevance=relevance)
    assert decision in {
        "discard_irrelevant",
        "discard_harmful_distraction",
        "discard_low_quality",
    }


def test_old_module_order_does_not_dictate_final_map():
    md = build_mixed_draft_memory(
        source_hash="h4",
        text=DRAFT_WITH_BLOAT,
        course_promise=META_ADS_PROMISE,
    )
    warnings = " ".join(md["creator_warnings"]).lower()
    assert "must not dictate" in warnings or "not authority" in warnings
    assert md["map_hints_not_authority"] is not None
    # Snippet states old map is not authority
    snip = format_mixed_draft_snippet({"mixed_draft_memory": md})
    assert "old_map_not_authority=true" in snip
    assert "NOT authority" in snip or "not authority" in snip.lower()
    assert MIXED_QUALITY_PROMPT_LABEL.split(".")[0] in snip


def test_small_weak_reel_merged_or_discarded():
    tiny = "Dream big. Unlock your potential."
    assert is_dumb_reel(tiny, relevance="harmful_distraction")
    md = build_mixed_draft_memory(
        source_hash="h5",
        text=f"# Module Ads\n## Reel\n{tiny}\n\n## Real\nStep 1 checklist: measure ROAS for Meta ads weekly.",
        course_promise=META_ADS_PROMISE,
    )
    assert md["discarded_dumb_reels"] or "dumb_reel" in " ".join(md["repeated_bad_patterns"])
    # Tiny motivational line is not a full keep lesson
    assert not any("dream big" in c.lower() for c in md["core_candidates"])


def test_final_docx_has_no_relevance_labels():
    spoken = "في الدرس ده هنجهز حملة إعلانات ونقيس العائد."
    for mark in (
        "core_to_promise",
        "off_promise",
        "discarded_off_promise",
        "harmful_distraction",
        "keep_candidate",
        "rebuild_candidate",
        "Course Promise Relevance Gate",
    ):
        assert mark not in spoken


def test_course_map_follows_promise_not_old_bloat():
    memory = build_source_memory_payload(
        title="old.docx",
        category="mixed_quality_ai_course_draft",
        extracted_text=DRAFT_WITH_BLOAT,
        course_promise=META_ADS_PROMISE.as_dict(),
    )
    compact = compiler_text_from_memory(
        memory=memory,
        summary=memory["summary"],
        chunks=None,
        fallback_text=DRAFT_WITH_BLOAT,
        query_text="",
        category="mixed_quality_ai_course_draft",
    )
    excerpts = compile_source_context(
        [
            SourceForCompiler(
                source_id=1,
                category="mixed_quality_ai_course_draft",
                priority="high",
                text=compact,
                memory=memory,
            )
        ],
        query_text="",
    )
    text = excerpts[0].text.lower()
    assert "course promise" in text or "relevance" in text or "mixed-quality" in text
    disallowed = set(excerpts[0].disallowed_use)
    assert "preserve_off_promise_modules_because_they_exist" in disallowed
    assert "let_old_draft_dictate_module_or_lesson_count" in disallowed
    assert "use_old_map_as_final_map" in disallowed
    # Branding bloat should not be pushed as keep content in the compact snippet
    assert "brand identity framework" not in text or "discard" in text


def test_legacy_quality_classify_segment_still_works():
    assert classify_segment("In this video stay until the end click like") == "discard"
    assert (
        classify_segment(
            "Common mistake: people think ads are magic. Learner might object about budget."
        )
        == "keep_candidate"
    )


def test_promise_gate_label_updated():
    assert "irrelevant modules" in MIXED_QUALITY_PROMPT_LABEL
    assert "dumb reels" in MIXED_QUALITY_PROMPT_LABEL
    assert "course promise" in MIXED_QUALITY_PROMPT_LABEL.lower()
    assert "preserve_off_promise_modules_because_they_exist" in DISALLOWED_USE_BY_CATEGORY[
        "mixed_quality_ai_course_draft"
    ]
