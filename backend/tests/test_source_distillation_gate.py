"""General Source Distillation Gate — Admin Knowledge, memory, prompts, DOCX."""

from app.generation.knowledge_packs import (
    build_stage_rules_pack,
    stage_source_distillation_gate,
)
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
from app.prompts.prompt_registry import PipelineStage
from app.schemas.generation import FinalCourse, FinalModule, FinalReel
from app.seed_admin_knowledge import (
    REQUIRED_KEYS,
    SEED_ITEMS,
    SOURCE_DISTILLATION_GATE,
)
from app.services.docx_export import extract_plain_text, render_final_course_docx

ACADEMIC_SOURCE = (
    "Chapter 3: Theoretical Framework of Attribution Modeling. "
    "According to the study, the hypothesis posits that peer-reviewed "
    "literature demonstrates a scholarly methodology for multi-touch attribution. "
    "Furthermore, it is important to note that the etymology of ROAS reflects "
    "bibliography entries and dissertation-level discussion. "
    "For example, a boutique brand in the US market with a USD budget used "
    "Facebook boost post settings in 2019 before the legacy interface changed."
) * 3

SHALLOW_SOURCE = (
    "5 tips for ads. Post more. Be consistent. Try video. Use hashtags. "
    "Engagement is key. One useful point: test one variable at a time."
)

OUTDATED_SOURCE = (
    "Module 1: Setup\n"
    "Use Facebook boost post from power editor in 2019. "
    "This deprecated workflow still works before iOS 14 ATT changes. "
    "Click the legacy interface button."
)

US_MARKET_SOURCE = (
    "American small business owners in Silicon Valley should allocate USD "
    "budget for Super Bowl campaigns. US market best practices for Black Friday "
    "in the US assume western market buying behavior."
)

FILLER_SOURCE = (
    "Furthermore, it is important to note that marketing matters. "
    "Moreover, in conclusion, as mentioned above, engagement is important. "
    "At the end of the day you need strategy. " * 5
    + "One real distinction: match message to audience temperature."
)

STRUCTURED_SOURCE = (
    "# Chapter 1\nModule 1: Intro\nLesson 1: Hooks\n"
    "Module 2: Scaling\n"
    "Content about Meta ads for Egyptian shops with practical warnings: "
    "do not scale before proof of offer."
)

GOOD_SPOKEN_SCRIPT = """\
خليني أوضح لك الحتة دي بسرعة.

الغلط هنا إن ناس كتير بتفهم الموضوع بالعكس لما الميزانية صغيرة.

اللي يفرق معاك عمليًا هو إنك تختبر متغير واحد في كل مرة قبل ما ترفع الإنفاق.

مش كل الحالات ينفع معها نفس الحل — والسوق المصري محتاج أمثلة واقعية مش افتراضات مستوردة.
"""


def test_distillation_gate_in_seed_and_required_keys():
    assert "rukn_source_distillation_gate" in REQUIRED_KEYS
    keys = {item["key"] for item in SEED_ITEMS}
    assert "rukn_source_distillation_gate" in keys
    item = next(i for i in SEED_ITEMS if i["key"] == "rukn_source_distillation_gate")
    assert item["content_text"] == SOURCE_DISTILLATION_GATE


def test_gate_covers_distillation_scenarios():
    text = SOURCE_DISTILLATION_GATE.lower()
    assert "raw material" in text
    assert "academic" in text
    assert "shallow" in text
    assert "outdated" in text
    assert "foreign-market" in text or "western" in text
    assert "teleprompter docx" in text
    assert "distilled raw material" in text
    assert "never copy sources literally" in text or "never copy" in text


def test_prompt_compiler_includes_distillation_gate_in_relevant_stages():
    rules = {"rukn_source_distillation_gate": SOURCE_DISTILLATION_GATE}
    for stage in (
        PipelineStage.BUILD_COURSE_MAP,
        PipelineStage.WRITE_SINGLE_REEL,
        PipelineStage.REVIEW_SINGLE_REEL,
        PipelineStage.FINAL_REVIEW,
        PipelineStage.REBUILD_FINAL_COURSE,
    ):
        selected = select_rules_for_stage(rules, stage)
        assert "rukn_source_distillation_gate" in selected


def test_packed_distillation_gate_is_stage_slice_not_full_dump():
    full_len = len(SOURCE_DISTILLATION_GATE)
    assert full_len > 800
    write_slice = stage_source_distillation_gate(
        SOURCE_DISTILLATION_GATE, PipelineStage.WRITE_SINGLE_REEL
    )
    assert write_slice
    assert len(write_slice) < full_len // 2
    assert SOURCE_DISTILLATION_GATE not in write_slice
    packed = select_packed_rules_for_stage(
        {"rukn_source_distillation_gate": SOURCE_DISTILLATION_GATE},
        PipelineStage.WRITE_SINGLE_REEL,
    )
    body = " ".join(packed.values())
    assert SOURCE_DISTILLATION_GATE not in body
    assert "distillation" in body.lower()


def test_prompt_compiler_version_bumped_for_distillation_gate():
    assert PROMPT_COMPILER_VERSION == "2.21"


def test_academic_source_distilled_to_practical_memory_not_literal_dump():
    memory = build_source_memory_payload(
        title="academic.pdf",
        category="scientific_reference",
        extracted_text=ACADEMIC_SOURCE,
    )
    assert memory.get("academic_source_flag") is True
    assert memory.get("distillation_version")
    snippet = format_memory_snippet(memory)
    assert DISTILLED_LABEL in snippet
    assert "academic" in snippet.lower()
    assert "spoken" in snippet.lower() or "practical" in snippet.lower()
    assert len(snippet) <= 1400
    assert len(snippet) < len(ACADEMIC_SOURCE)
    assert "Furthermore, it is important to note" not in snippet
    assert "Chapter 3:" not in snippet


def test_shallow_source_yields_candidate_without_weakening_flags():
    memory = build_source_memory_payload(
        title="shallow.txt",
        category="raw_material",
        extracted_text=SHALLOW_SOURCE,
    )
    assert memory.get("shallow_source_flag") is True
    assert memory.get("rebuild_candidates") or memory.get("useful_concepts")
    snippet = format_memory_snippet(memory)
    assert "Shallow source" in snippet
    assert "candidate" in snippet.lower()
    assert "test one variable" in snippet.lower() or "variable" in snippet.lower()


def test_outdated_source_warns_official_docs_override():
    memory = build_source_memory_payload(
        title="old.pdf",
        category="scientific_reference",
        extracted_text=OUTDATED_SOURCE,
    )
    assert memory.get("outdated_warnings")
    snippet = format_memory_snippet(memory)
    assert "official" in snippet.lower()
    assert "Outdated warnings" in snippet or "outdated" in snippet.lower()
    rules = select_rules_for_stage(
        {
            "rukn_official_tool_docs_gate": "Official docs override old sources.",
            "rukn_source_distillation_gate": SOURCE_DISTILLATION_GATE,
        },
        PipelineStage.WRITE_SINGLE_REEL,
    )
    assert "rukn_official_tool_docs_gate" in rules
    assert "rukn_source_distillation_gate" in rules


def test_us_market_source_gets_egypt_adaptation_note():
    memory = build_source_memory_payload(
        title="us.pdf",
        category="scientific_reference",
        extracted_text=US_MARKET_SOURCE,
        course_promise={"target_market": "egypt"},
    )
    assert memory.get("market_adaptation_notes")
    snippet = format_memory_snippet(memory)
    assert "Market adaptation" in snippet or "Western" in snippet or "US" in snippet
    notes_blob = " ".join(str(x) for x in (memory.get("market_adaptation_notes") or [])).lower()
    assert "egypt" in snippet.lower() or "egypt" in notes_blob


def test_filler_and_repetition_marked_discarded_not_preserved_in_snippet():
    memory = build_source_memory_payload(
        title="filler.txt",
        category="raw_material",
        extracted_text=FILLER_SOURCE,
    )
    assert any("filler" in s.lower() for s in memory.get("discarded_signals") or [])
    snippet = format_memory_snippet(memory)
    assert "Furthermore" not in snippet
    assert "Moreover, in conclusion" not in snippet
    assert "Blocked / discard" in snippet or "filler" in snippet.lower()


def test_source_structure_does_not_dictate_map_authority():
    memory = build_source_memory_payload(
        title="structured.docx",
        category="old_course",
        extracted_text=STRUCTURED_SOURCE,
    )
    assert memory.get("map_structure_not_authority") or memory.get("map_hints_not_authority") is not None
    snippet = format_memory_snippet(memory)
    assert "NOT course map" in snippet or "map" in snippet.lower()
    assert "Module 1: Intro" not in snippet or "structure" in snippet.lower()


def test_compile_context_labels_distilled_raw_material():
    memory = build_source_memory_payload(
        title="ref.pdf",
        category="scientific_reference",
        extracted_text=ACADEMIC_SOURCE,
    )
    compact = format_memory_snippet(memory, query_text="ROAS")
    excerpts = compile_source_context(
        [
            SourceForCompiler(
                source_id=1,
                category="scientific_reference",
                priority="high",
                text=compact,
                summary=memory["summary"],
                memory=memory,
            )
        ],
        query_text="ROAS",
    )
    assert excerpts
    assert DISTILLED_LABEL in excerpts[0].text
    assert "UNTRUSTED_REFERENCE_MATERIAL" in excerpts[0].text


def test_final_docx_keeps_teleprompter_format_without_source_leaks():
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
    assert "Module 1" in plain
    assert "Lesson 1" in plain
    assert "خليني أوضح" in plain
    assert not find_forbidden_substrings(plain)
    for banned in (
        "DISTILLED RAW MATERIAL",
        "Source memory",
        "citation",
        "according to the study",
        "UNTRUSTED_REFERENCE",
        "admin knowledge",
        "distilled raw material",
    ):
        assert banned.lower() not in plain.lower()
