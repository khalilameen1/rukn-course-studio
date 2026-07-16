"""Transcript topic relevance — same-topic raw material vs off-topic colloquial only."""

from app.generation.mixed_draft_memory import CoursePromise
from app.generation.prompt_compiler import (
    PROMPT_COMPILER_VERSION,
    SourceForCompiler,
    compile_source_context,
    select_packed_rules_for_stage,
    select_rules_for_stage,
)
from app.generation.source_distillation import DISTILLED_LABEL
from app.generation.source_memory_store import (
    build_source_memory_payload,
    format_memory_snippet,
)
from app.generation.teleprompter_checks import find_forbidden_substrings
from app.generation.transcript_relevance import (
    OFF_TOPIC_TRANSCRIPT_LABEL,
    SAME_TOPIC_TRANSCRIPT_LABEL,
    UNCLEAR_TRANSCRIPT_LABEL,
    classify_transcript_topic_relevance,
)
from app.prompts.prompt_registry import PipelineStage
from app.schemas.generation import FinalCourse, FinalModule, FinalReel
from app.seed_admin_knowledge import (
    REQUIRED_KEYS,
    SEED_ITEMS,
    TRANSCRIPT_TOPIC_RELEVANCE_GATE,
)
from app.services.docx_export import extract_plain_text, render_final_course_docx

META_ADS_PROMISE = CoursePromise(
    title="Meta Ads for Egyptian Boutique Shops",
    audience="Beginner Egyptian shop owners",
    outcome="Launch and measure profitable Meta ads campaigns",
    target_market="egypt",
    course_map_text="Campaign setup, creative testing, ROAS measurement",
).as_dict()

SAME_TOPIC_TRANSCRIPT = """
Meta ads campaign setup for Egyptian boutique shops in Cairo. Measure ROAS weekly.
Common mistake: people think Meta ads are magic before creative testing.
Learner objection: budget is too small for profitable campaigns.
Practical point: test one creative variable at a time before scaling spend.
Warning: do not scale before proof of offer for boutique shops.
"""

SAME_TOPIC_OUTDATED_TRANSCRIPT = """
Meta ads for Egyptian boutique shops. ROAS measurement and campaign setup.
Use Facebook boost post from power editor in 2019 before the legacy interface changed.
This deprecated workflow still works before iOS 14 ATT changes.
"""

HOOKY_SAME_TOPIC_TRANSCRIPT = """
Shocking secret hook openers forever champions rise! Stay until the end cliffhanger.
Module one module two module three viral loop ending catchphrase signature line.
Meta ads ROAS for Egyptian boutique Cairo campaign creative testing budget objections.
For example a Cairo boutique burned budget testing cool blue headlines verbatim.
"""

OFF_TOPIC_TRANSCRIPT = (
    "How to bake sourdough bread at home. Fermentation starter kitchen recipe flour yeast. "
    "Knead the dough and preheat the oven. Sourdough crust scoring technique. "
) * 12

GOOD_SPOKEN_SCRIPT = """\
خليني أوضح لك الحتة دي بسرعة.

الغلط هنا إن ناس كتير بتفهم الموضوع بالعكس لما الميزانية صغيرة.

اللي يفرق معاك عمليًا هو إنك تختبر متغير واحد في كل مرة قبل ما ترفع الإنفاق.
"""


def test_gate_in_seed_and_required_keys():
    assert "rukn_transcript_topic_relevance_gate" in REQUIRED_KEYS
    keys = {item["key"] for item in SEED_ITEMS}
    assert "rukn_transcript_topic_relevance_gate" in keys
    item = next(i for i in SEED_ITEMS if i["key"] == "rukn_transcript_topic_relevance_gate")
    assert item["content_text"] == TRANSCRIPT_TOPIC_RELEVANCE_GATE


def test_prompt_compiler_includes_transcript_gate():
    rules = {"rukn_transcript_topic_relevance_gate": TRANSCRIPT_TOPIC_RELEVANCE_GATE}
    selected = select_rules_for_stage(rules, PipelineStage.WRITE_SINGLE_REEL)
    assert "rukn_transcript_topic_relevance_gate" in selected
    packed = select_packed_rules_for_stage(rules, PipelineStage.WRITE_SINGLE_REEL)
    body = " ".join(packed.values()).lower()
    assert "same_topic" in body
    assert TRANSCRIPT_TOPIC_RELEVANCE_GATE not in body
    assert PROMPT_COMPILER_VERSION == "2.20"


def test_same_topic_transcript_provides_distilled_raw_material():
    relevance = classify_transcript_topic_relevance(
        SAME_TOPIC_TRANSCRIPT,
        course_title=META_ADS_PROMISE["title"],
        audience=META_ADS_PROMISE["audience"],
        outcome=META_ADS_PROMISE["outcome"],
        course_map_text=META_ADS_PROMISE["course_map_text"],
    )
    assert relevance == "same_topic"

    memory = build_source_memory_payload(
        title="lesson.txt",
        category="transcript",
        extracted_text=SAME_TOPIC_TRANSCRIPT,
        course_promise=META_ADS_PROMISE,
    )
    assert memory["topic_relevance"] == "same_topic"
    assert memory.get("transcript_colloquial_only") is False
    assert (
        memory.get("useful_concepts")
        or memory.get("facts")
        or memory.get("rebuild_candidates")
        or memory.get("extracted_facts")
    )
    snippet = format_memory_snippet(memory)
    assert DISTILLED_LABEL in snippet
    assert "raw material" in snippet.lower() or "objection" in snippet.lower()


def test_same_topic_outdated_claims_flagged_for_verification():
    memory = build_source_memory_payload(
        title="old-lesson.txt",
        category="transcript",
        extracted_text=SAME_TOPIC_OUTDATED_TRANSCRIPT,
        course_promise=META_ADS_PROMISE,
    )
    assert memory["topic_relevance"] == "same_topic"
    assert memory.get("outdated_warnings")
    snippet = format_memory_snippet(memory)
    assert "official" in snippet.lower() or "Outdated" in snippet
    blocked = " ".join(memory.get("blocked_content_warnings") or []).lower()
    assert "official" in blocked or memory.get("outdated_warnings")


def test_official_docs_gate_overrides_same_topic_transcript_in_stage_rules():
    rules = select_rules_for_stage(
        {
            "rukn_official_tool_docs_gate": "Official current documentation overrides old sources.",
            "rukn_transcript_topic_relevance_gate": TRANSCRIPT_TOPIC_RELEVANCE_GATE,
        },
        PipelineStage.WRITE_SINGLE_REEL,
    )
    assert "rukn_official_tool_docs_gate" in rules
    assert "rukn_transcript_topic_relevance_gate" in rules
    assert "official" in TRANSCRIPT_TOPIC_RELEVANCE_GATE.lower()
    assert "official" in rules["rukn_transcript_topic_relevance_gate"].lower()


def test_same_topic_transcript_does_not_override_rokn_format():
    memory = build_source_memory_payload(
        title="structured.txt",
        category="transcript",
        extracted_text=(
            "# Module 1: Hooks\n## Lesson 1\n"
            + SAME_TOPIC_TRANSCRIPT
            + "\nFurthermore, it is important to note scholarly methodology."
        ),
        course_promise=META_ADS_PROMISE,
    )
    snippet = format_memory_snippet(memory)
    assert "Module 1: Hooks" not in snippet
    assert "Furthermore, it is important to note" not in snippet
    compact = format_memory_snippet(memory, query_text="ROAS")
    excerpts = compile_source_context(
        [
            SourceForCompiler(
                source_id=1,
                category="transcript",
                priority="high",
                text=compact,
                summary=memory.get("summary"),
                memory=memory,
            )
        ],
        query_text="ROAS",
    )
    assert excerpts
    assert SAME_TOPIC_TRANSCRIPT_LABEL in excerpts[0].text
    assert "use_as_course_format_template" in excerpts[0].disallowed_use
    assert "copy_source_structure" in excerpts[0].disallowed_use


def test_same_topic_transcript_wording_hooks_loops_not_copied_in_compiler():
    memory = build_source_memory_payload(
        title="hooky.txt",
        category="transcript",
        extracted_text=HOOKY_SAME_TOPIC_TRANSCRIPT,
        course_promise=META_ADS_PROMISE,
    )
    compact = format_memory_snippet(memory)
    assert "Shocking secret hook openers" not in compact
    assert "champions rise" not in compact
    assert "Module one module two" not in compact

    excerpts = compile_source_context(
        [
            SourceForCompiler(
                source_id=2,
                category="transcript",
                priority="medium",
                text=compact,
                memory=memory,
            )
        ],
        query_text="Meta ads",
    )
    text = excerpts[0].text
    assert "Shocking secret" not in text
    assert "champions rise" not in text
    assert "learn_hooks_from_transcript" in excerpts[0].disallowed_use
    assert "copy_exact_hook_structure" in excerpts[0].disallowed_use
    assert SAME_TOPIC_TRANSCRIPT_LABEL in text


def test_off_topic_transcript_is_natural_colloquial_calibration_only():
    relevance = classify_transcript_topic_relevance(
        OFF_TOPIC_TRANSCRIPT,
        course_title=META_ADS_PROMISE["title"],
        audience=META_ADS_PROMISE["audience"],
        outcome=META_ADS_PROMISE["outcome"],
        course_map_text=META_ADS_PROMISE["course_map_text"],
    )
    assert relevance == "off_topic"

    memory = build_source_memory_payload(
        title="baking.txt",
        category="transcript",
        extracted_text=OFF_TOPIC_TRANSCRIPT,
        course_promise=META_ADS_PROMISE,
    )
    assert memory["transcript_colloquial_only"] is True
    assert memory.get("facts") == []
    assert memory.get("useful_concepts") == []

    snippet = format_memory_snippet(memory)
    assert OFF_TOPIC_TRANSCRIPT_LABEL in snippet
    assert "sourdough" not in snippet.lower()
    assert "fermentation" not in snippet.lower()

    excerpts = compile_source_context(
        [
            SourceForCompiler(
                source_id=3,
                category="transcript",
                priority="low",
                text=snippet,
                memory=memory,
            )
        ],
        query_text="",
    )
    assert excerpts[0].authority_type == "natural_colloquial_calibration"
    assert "learn_hooks_from_transcript" in excerpts[0].disallowed_use
    assert "support_factual_claims" in excerpts[0].disallowed_use
    assert OFF_TOPIC_TRANSCRIPT_LABEL in excerpts[0].style_contamination_warning


def test_unclear_transcript_used_conservatively():
    padded_promise = {
        **META_ADS_PROMISE,
        "special_notes": " ".join(f"scopeword{i}" for i in range(60)),
    }
    transcript = "Shop owners inventory organization focus routines habits systems."
    relevance = classify_transcript_topic_relevance(
        transcript,
        course_title=padded_promise["title"],
        audience=padded_promise["audience"],
        outcome=padded_promise["outcome"],
        course_map_text=padded_promise["course_map_text"],
        special_notes=padded_promise["special_notes"],
    )
    assert relevance == "unclear"

    memory = build_source_memory_payload(
        title="vague.txt",
        category="transcript",
        extracted_text=transcript,
        course_promise=padded_promise,
    )
    assert memory["topic_relevance"] == "unclear"
    assert len(memory.get("facts") or []) <= 3
    assert len(memory.get("useful_concepts") or []) <= 3
    assert memory.get("transcript_prompt_label") == UNCLEAR_TRANSCRIPT_LABEL


def test_final_docx_contains_no_internal_transcript_labels():
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
                        script_text=GOOD_SPOKEN_SCRIPT,
                    )
                ],
            )
        ],
    )
    docx_bytes = render_final_course_docx(course)
    plain = extract_plain_text(docx_bytes)
    assert not find_forbidden_substrings(plain)
    for banned in (
        SAME_TOPIC_TRANSCRIPT_LABEL,
        OFF_TOPIC_TRANSCRIPT_LABEL,
        UNCLEAR_TRANSCRIPT_LABEL,
        "DISTILLED RAW MATERIAL",
        "transcript_colloquial_only",
        "topic_relevance",
        "UNTRUSTED_REFERENCE_MATERIAL",
    ):
        assert banned not in plain
