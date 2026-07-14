"""Tests for app/generation/prompt_compiler.py - pure, no DB/session."""

from app.generation.prompt_compiler import (
    ALLOWED_USE_BY_CATEGORY,
    DEFAULT_MAX_TOTAL_CHARS,
    DISALLOWED_USE_BY_CATEGORY,
    STYLE_CONTAMINATION_WARNING_BY_CATEGORY,
    SourceForCompiler,
    build_flow_profile,
    compile_source_context,
    select_rules_for_stage,
)
from app.prompts.prompt_registry import PipelineStage

ALL_RULES = {
    "rukn_core_rules": "core",
    "rukn_practical_course_rules": "practical",
    "rukn_writing_style": "style",
    "rukn_forbidden_phrases": "forbidden",
    "rukn_quality_rubric": "rubric",
    "rukn_teleprompter_docx_contract": "contract",
    "rukn_high_signal_reel_doctrine": "doctrine",
    "rukn_dynamic_teaching_curve": "curve",
    "rukn_creator_persona_engine": "persona",
    "rukn_creator_critic_loop": "critic",
    "rukn_student_confusion_layer": "student",
    "rukn_master_mentor_engine": "mentor",
    "rukn_generation_presets": "presets",
}


def test_review_single_reel_includes_forbidden_and_rubric_but_not_core_rules():
    selected = select_rules_for_stage(ALL_RULES, PipelineStage.REVIEW_SINGLE_REEL)
    assert "rukn_forbidden_phrases" in selected
    assert "rukn_quality_rubric" in selected
    assert "rukn_core_rules" not in selected


def test_write_single_reel_includes_teleprompter_contract():
    selected = select_rules_for_stage(ALL_RULES, PipelineStage.WRITE_SINGLE_REEL)
    assert "rukn_teleprompter_docx_contract" in selected


def test_write_and_review_stages_include_high_signal_doctrine():
    for stage in (
        PipelineStage.WRITE_SINGLE_REEL,
        PipelineStage.REVIEW_SINGLE_REEL,
        PipelineStage.REVIEW_MODULE,
        PipelineStage.FINAL_REVIEW,
    ):
        selected = select_rules_for_stage(ALL_RULES, stage)
        assert "rukn_high_signal_reel_doctrine" in selected


def test_write_stages_include_dynamic_teaching_curve():
    for stage in (
        PipelineStage.BUILD_COURSE_MAP,
        PipelineStage.WRITE_SINGLE_REEL,
        PipelineStage.REVIEW_MODULE,
    ):
        selected = select_rules_for_stage(ALL_RULES, stage)
        assert "rukn_dynamic_teaching_curve" in selected


def test_write_stages_include_creator_persona_engine():
    for stage in (
        PipelineStage.BUILD_COURSE_MAP,
        PipelineStage.WRITE_SINGLE_REEL,
        PipelineStage.REVIEW_SINGLE_REEL,
        PipelineStage.FINAL_REVIEW,
    ):
        selected = select_rules_for_stage(ALL_RULES, stage)
        assert "rukn_creator_persona_engine" in selected


def test_write_stages_include_creator_critic_loop():
    for stage in (
        PipelineStage.BUILD_COURSE_MAP,
        PipelineStage.WRITE_SINGLE_REEL,
        PipelineStage.REVIEW_MODULE,
        PipelineStage.FINAL_REVIEW,
    ):
        selected = select_rules_for_stage(ALL_RULES, stage)
        assert "rukn_creator_critic_loop" in selected


def test_write_stages_include_student_confusion_layer():
    for stage in (
        PipelineStage.BUILD_COURSE_MAP,
        PipelineStage.WRITE_SINGLE_REEL,
        PipelineStage.REVIEW_MODULE,
        PipelineStage.FINAL_REVIEW,
    ):
        selected = select_rules_for_stage(ALL_RULES, stage)
        assert "rukn_student_confusion_layer" in selected


def test_write_stages_include_master_mentor_engine():
    for stage in (
        PipelineStage.BUILD_COURSE_MAP,
        PipelineStage.WRITE_SINGLE_REEL,
        PipelineStage.REVIEW_MODULE,
        PipelineStage.FINAL_REVIEW,
    ):
        selected = select_rules_for_stage(ALL_RULES, stage)
        assert "rukn_master_mentor_engine" in selected
    selected = select_rules_for_stage(ALL_RULES, PipelineStage.REBUILD_FINAL_COURSE)
    assert "rukn_teleprompter_docx_contract" in selected


def test_final_review_includes_teleprompter_contract():
    selected = select_rules_for_stage(ALL_RULES, PipelineStage.FINAL_REVIEW)
    assert "rukn_teleprompter_docx_contract" in selected


def test_generation_presets_key_never_included_for_any_stage():
    for stage in PipelineStage:
        selected = select_rules_for_stage(ALL_RULES, stage)
        assert "rukn_generation_presets" not in selected


def test_missing_keys_are_just_omitted_not_an_error():
    partial_rules = {"rukn_core_rules": "core"}
    selected = select_rules_for_stage(partial_rules, PipelineStage.BUILD_COURSE_MAP)
    assert selected == {"rukn_core_rules": "core"}


def test_flow_reference_produces_profile_not_verbatim_excerpt():
    source_text = (
        "هل جربت قبل كده تصميم إعلان في خمس دقايق؟ خد بالك من الخطوة الأولى "
        "كويس، بس المهم إنك تبدأ فعليا من غير تفكير كتير. لو الألوان مش واضحة "
        "هتضيع وقتك، وده اللي بيفرق فعليا. خلاصة الكلام، جرب دلوقتي."
    )
    source = SourceForCompiler(
        source_id=1,
        category="flow_reference",
        priority="medium",
        text=source_text,
    )

    excerpts = compile_source_context([source], query_text="")

    assert len(excerpts) == 1
    result_text = excerpts[0].text
    assert source_text not in result_text
    assert "هتضيع وقتك" not in result_text
    assert "heuristic profile" in result_text


def test_scientific_reference_uses_extract_summarize_chunk_selection_path():
    long_text = (
        "# Excel Basics\n"
        + ("Opening Excel and understanding the ribbon interface. " * 40)
        + "\n\n# Advanced Formulas\n"
        + ("VLOOKUP and SUMIF are powerful budgeting formulas. " * 40)
    )
    chunks = [
        {"heading": "Excel Basics", "text": "Opening Excel and understanding the ribbon interface."},
        {"heading": "Advanced Formulas", "text": "VLOOKUP and SUMIF are powerful budgeting formulas."},
    ]
    source = SourceForCompiler(
        source_id=2,
        category="scientific_reference",
        priority="high",
        text=long_text,
        summary="A short summary about Excel formulas.",
        chunks=chunks,
    )

    excerpts = compile_source_context([source], query_text="budget formulas excel")

    assert len(excerpts) == 1
    assert excerpts[0].text != long_text
    assert len(excerpts[0].text) < len(long_text)
    # Chunk selection found something relevant to the query - not just the
    # fallback summary.
    assert "VLOOKUP" in excerpts[0].text or "ribbon" in excerpts[0].text


def test_scientific_reference_short_source_passes_through_full_text():
    source = SourceForCompiler(
        source_id=3, category="scientific_reference", priority="medium", text="Short note."
    )
    excerpts = compile_source_context([source], query_text="")
    assert excerpts[0].text == "Short note."


def test_user_notes_always_pass_through_unmodified_when_within_budget():
    source = SourceForCompiler(
        source_id=4, category="user_notes", priority="low", text="Please keep this exact tone."
    )
    excerpts = compile_source_context([source], query_text="")
    assert excerpts[0].text == "Please keep this exact tone."


def test_raw_material_gets_unclassified_marker_prefix():
    source = SourceForCompiler(
        source_id=5, category="raw_material", priority="medium", text="Some mixed content here."
    )
    excerpts = compile_source_context([source], query_text="")
    assert "unclassified" in excerpts[0].text.lower() or "mixed" in excerpts[0].text.lower()


def test_budget_trims_many_huge_low_priority_sources_without_raising():
    sources = [
        SourceForCompiler(
            source_id=i,
            category="raw_material",
            priority="low",
            text="x" * 5000,
        )
        for i in range(10)
    ]

    excerpts = compile_source_context(sources, query_text="", max_total_chars=1000)

    total_chars = sum(len(e.text) for e in excerpts)
    assert total_chars <= 1000
    assert len(excerpts) == 10  # nothing dropped, just trimmed


def test_user_notes_survive_trimming_over_low_priority_raw_material():
    user_notes_text = "Important user instructions that must not be cut."
    raw_material_text = "y" * 5000

    sources = [
        SourceForCompiler(
            source_id=1, category="user_notes", priority="medium", text=user_notes_text
        ),
        SourceForCompiler(
            source_id=2, category="raw_material", priority="low", text=raw_material_text
        ),
    ]

    excerpts = compile_source_context(sources, query_text="", max_total_chars=200)

    by_category = {e.category: e for e in excerpts}
    assert by_category["user_notes"].text == user_notes_text
    assert len(by_category["raw_material"].text) < len(raw_material_text)


def test_default_max_total_chars_is_a_sane_positive_number():
    assert DEFAULT_MAX_TOTAL_CHARS > 0


# --- Source Authority Firewall ------------------------------------------


def test_scientific_reference_excerpt_carries_allowed_and_disallowed_use():
    long_academic_text = (
        "This treatise presents a formal exposition of budgetary allocation "
        "heuristics as established in the extant literature. " * 30
    )
    source = SourceForCompiler(
        source_id=10,
        category="scientific_reference",
        priority="high",
        text=long_academic_text,
        summary="Budget allocation heuristics, summarized.",
    )

    excerpts = compile_source_context([source], query_text="")
    excerpt = excerpts[0]

    assert "extract_factual_knowledge" in excerpt.allowed_use
    assert "rephrase_into_rukn_style" in excerpt.allowed_use
    assert "imitate_source_tone" in excerpt.disallowed_use
    assert "copy_source_structure" in excerpt.disallowed_use
    assert excerpt.style_contamination_warning is not None

    # Never the raw text verbatim for a long source - paraphrased/summarized instead.
    assert excerpt.text != long_academic_text
    assert len(excerpt.text) < len(long_academic_text)


def test_flow_reference_produces_all_twelve_profile_fields_non_empty():
    source_text = (
        "هل جربت قبل كده تصميم إعلان في خمس دقايق؟ خد بالك من الخطوة الأولى "
        "كويس، بس المهم إنك تبدأ فعليا من غير تفكير كتير. لو الألوان مش واضحة "
        "هتضيع وقتك، وده اللي بيفرق فعليا. جرب الخطوة دي دلوقتي واشوف الفرق. "
        "خلاصة الكلام، جرب دلوقتي."
    )

    profile = build_flow_profile(source_text)

    expected_fields = {
        "opening_energy",
        "hook_mechanism",
        "pacing",
        "transition_style",
        "idea_progression",
        "escalation_pattern",
        "tension_curve",
        "climax_or_turning_point",
        "example_integration",
        "ending_motion",
        "natural_speech_notes",
        "things_not_to_copy",
    }
    assert set(profile.keys()) == expected_fields

    for field in expected_fields - {"things_not_to_copy"}:
        assert isinstance(profile[field], str)
        assert profile[field].strip()

    assert isinstance(profile["things_not_to_copy"], list)
    assert len(profile["things_not_to_copy"]) > 0
    assert all(item.strip() for item in profile["things_not_to_copy"])


def test_flow_reference_never_copies_a_planted_catchphrase_verbatim():
    catchphrase = "يلا يا نجم يلا"
    source_text = (
        f"{catchphrase} خد بالك من الخطوة الأولى كويس وابدأ فعليا من غير "
        f"تفكير كتير. لو الألوان مش واضحة هتضيع وقتك. {catchphrase} وده "
        f"اللي بيفرق فعليا. جرب دلوقتي. {catchphrase}"
    )
    source = SourceForCompiler(
        source_id=11, category="flow_reference", priority="medium", text=source_text
    )

    excerpts = compile_source_context([source], query_text="")

    assert catchphrase not in excerpts[0].text
    profile = build_flow_profile(source_text)
    for value in profile.values():
        serialized = value if isinstance(value, str) else " ".join(value)
        assert catchphrase not in serialized


def test_flow_reference_profile_stays_compact_for_long_structured_input():
    heavily_structured_text = "\n\n".join(
        f"# Section {i}\n"
        + f"هذا الجزء رقم {i} يشرح فكرة جديدة بالتفصيل. " * 20
        + "\n## Sub-section\nمزيد من الشرح والتفاصيل هنا لهذا الجزء بالكامل. " * 15
        for i in range(1, 30)
    )
    assert len(heavily_structured_text) > 20000

    source = SourceForCompiler(
        source_id=12, category="flow_reference", priority="medium", text=heavily_structured_text
    )

    excerpts = compile_source_context([source], query_text="")

    # Compact regardless of the (very long, heavily-headed) input - a
    # profile, never a reproduction/template of the source.
    assert len(excerpts[0].text) < 2000
    assert len(excerpts[0].text) < len(heavily_structured_text) / 10


def test_select_rules_for_stage_always_includes_teleprompter_contract_regardless_of_sources():
    """Regression guard: no source category (flow_reference or otherwise)
    can ever override Rukn's own format authority - the teleprompter
    contract is selected purely from `all_rules`/`stage`, never touched by
    what sources are present in a given run."""
    for stage in (
        PipelineStage.WRITE_SINGLE_REEL,
        PipelineStage.REBUILD_FINAL_COURSE,
        PipelineStage.FINAL_REVIEW,
    ):
        selected = select_rules_for_stage(ALL_RULES, stage)
        assert "rukn_teleprompter_docx_contract" in selected


def test_compile_source_context_orders_by_authority_hierarchy():
    sources = [
        SourceForCompiler(source_id=1, category="raw_material", priority="low", text="raw"),
        SourceForCompiler(source_id=2, category="old_course", priority="low", text="old"),
        SourceForCompiler(
            source_id=3, category="flow_reference", priority="low", text="بس خد بالك."
        ),
        SourceForCompiler(
            source_id=4, category="scientific_reference", priority="low", text="science"
        ),
        SourceForCompiler(source_id=5, category="user_notes", priority="low", text="notes"),
    ]

    excerpts = compile_source_context(sources, query_text="")

    assert [e.category for e in excerpts] == [
        "user_notes",
        "scientific_reference",
        "flow_reference",
        "old_course",
        "raw_material",
    ]


def test_allowed_disallowed_use_dicts_cover_every_source_category():
    from app.models.enums import SourceCategory

    for category in SourceCategory:
        assert category.value in ALLOWED_USE_BY_CATEGORY
        assert category.value in DISALLOWED_USE_BY_CATEGORY
        assert category.value in STYLE_CONTAMINATION_WARNING_BY_CATEGORY

    assert STYLE_CONTAMINATION_WARNING_BY_CATEGORY["user_notes"] is None
    assert DISALLOWED_USE_BY_CATEGORY["user_notes"] == []
