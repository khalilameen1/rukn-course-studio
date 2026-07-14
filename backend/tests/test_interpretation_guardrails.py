"""Final Interpretation Guardrails — Admin Knowledge anti-misread clarifications."""

from app.generation.knowledge_packs import (
    build_stage_rules_pack,
    stage_interpretation_guardrails,
)
from app.generation.prompt_compiler import select_packed_rules_for_stage, select_rules_for_stage
from app.prompts.prompt_registry import PipelineStage
from app.seed_admin_knowledge import (
    INTERPRETATION_GUARDRAILS,
    REQUIRED_KEYS,
    SEED_ITEMS,
)


def test_interpretation_guardrails_in_seed_and_required_keys():
    assert "rukn_interpretation_guardrails" in REQUIRED_KEYS
    keys = {item["key"] for item in SEED_ITEMS}
    assert "rukn_interpretation_guardrails" in keys
    item = next(i for i in SEED_ITEMS if i["key"] == "rukn_interpretation_guardrails")
    assert item["content_text"] == INTERPRETATION_GUARDRAILS


def test_guardrails_cover_critical_anti_misreads():
    text = INTERPRETATION_GUARDRAILS.lower()
    assert "street slang" in text or "صاحبي" in INTERPRETATION_GUARDRAILS
    assert "tiktok" in text or "one word per line" in text
    assert "hype" in text
    assert "cliffhanger" in text or "في الريل الجاي" in INTERPRETATION_GUARDRAILS
    assert "padding" in text
    assert "fragile" in text or "click here" in text
    assert "citation" in text
    assert "mixed-quality" in text or "old ai drafts" in text
    assert "colloquial calibration" in text or "natural colloquial" in text
    assert "student agent" in text
    assert "specialist critic" in text
    assert "master mentor" in text
    assert "admin knowledge" in text and "dumping" in text
    assert "cost hygiene" in text
    assert "ROKN quality beats source loyalty" in INTERPRETATION_GUARDRAILS
    assert "DOCX" in INTERPRETATION_GUARDRAILS
    assert "Teleprompter DOCX only" in INTERPRETATION_GUARDRAILS


def test_guardrails_selected_for_map_write_and_final_stages():
    rules = {"rukn_interpretation_guardrails": INTERPRETATION_GUARDRAILS}
    for stage in (
        PipelineStage.BUILD_COURSE_MAP,
        PipelineStage.WRITE_SINGLE_REEL,
        PipelineStage.REVIEW_SINGLE_REEL,
        PipelineStage.FINAL_REVIEW,
        PipelineStage.REBUILD_FINAL_COURSE,
    ):
        selected = select_rules_for_stage(rules, stage)
        assert "rukn_interpretation_guardrails" in selected


def test_guardrails_never_claim_new_output_types():
    assert "teleprompter docx only" in INTERPRETATION_GUARDRAILS.lower()
    # Must not invent new deliverables
    for banned in ("pdf workbook", "student handout export", "quiz bank product"):
        assert banned not in INTERPRETATION_GUARDRAILS.lower()


def test_packed_guardrails_are_stage_relevant_not_full_dump():
    """LLM packs must not resend the full ~5.9k article every stage."""
    full_len = len(INTERPRETATION_GUARDRAILS)
    assert full_len > 4000

    map_slice = stage_interpretation_guardrails(
        INTERPRETATION_GUARDRAILS, PipelineStage.BUILD_COURSE_MAP
    )
    write_slice = stage_interpretation_guardrails(
        INTERPRETATION_GUARDRAILS, PipelineStage.WRITE_SINGLE_REEL
    )
    review_slice = stage_interpretation_guardrails(
        INTERPRETATION_GUARDRAILS, PipelineStage.REVIEW_SINGLE_REEL
    )
    final_slice = stage_interpretation_guardrails(
        INTERPRETATION_GUARDRAILS, PipelineStage.FINAL_REVIEW
    )

    for slice_text in (map_slice, write_slice, review_slice, final_slice):
        assert slice_text
        assert len(slice_text) < full_len // 2
        assert len(slice_text) <= 900

    # Map: source/authority/map — not student/critic persona focus
    assert "Course Map" in map_slice or "Admin Knowledge" in map_slice or "mixed-quality" in map_slice.lower()
    assert "Student Agent" not in map_slice

    # Write: spoken/hook — not mentor imitation essay
    assert "Egyptian Arabic" in write_slice or "Hook" in write_slice or "Teleprompter" in write_slice
    assert "Master Mentor" not in write_slice

    # Review: student / critic / mentor interpretation
    assert "Student Agent" in review_slice or "Specialist Critic" in review_slice
    assert "Master Mentor" in review_slice

    # Final: DOCX / teleprompter / no-leak
    assert "DOCX" in final_slice or "Teleprompter" in final_slice
    assert "expose the machine" in final_slice.lower() or "title" in final_slice.lower()


def test_select_packed_rules_does_not_embed_full_guardrails_article():
    rules = {
        "rukn_interpretation_guardrails": INTERPRETATION_GUARDRAILS,
        "rukn_core_rules": "Be clear.",
    }
    packed = select_packed_rules_for_stage(rules, PipelineStage.BUILD_COURSE_MAP)
    body = " ".join(packed.values())
    assert INTERPRETATION_GUARDRAILS not in body
    assert len(body) < len(INTERPRETATION_GUARDRAILS)
    # Stage slice present (compact pack still includes the key heading)
    assert "interpretation_guardrails" in body
    assert "stage-relevant" in body.lower() or "Course Map" in body or "Admin Knowledge" in body


def test_build_stage_rules_pack_uses_stage_slice_helper():
    selected = {"rukn_interpretation_guardrails": INTERPRETATION_GUARDRAILS}
    packed = build_stage_rules_pack(selected, PipelineStage.FINAL_REVIEW)
    body = packed.get("final_export_rules_pack", "")
    assert "Student Agent" not in body
    assert "DOCX" in body or "Teleprompter" in body or "expose the machine" in body.lower()
