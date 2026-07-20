"""Focused Phase 7 source-authority, provenance, market, and tool tests.

Pure/unit-level only: no full course generation and no external provider calls.
"""

from app.generation.market_evergreen import build_market_pack, compile_market_guidance
from app.generation.official_tool_docs import compile_official_tool_guidance
from app.generation.originality_rights import (
    compile_originality_guidance,
    rewrite_script_originality,
)
from app.generation.prompt_compiler import (
    ALLOWED_USE_BY_CATEGORY,
    DISALLOWED_USE_BY_CATEGORY,
    SourceForCompiler,
    compile_source_context,
)
from app.generation.quality.context_snapshot import source_ledger_from_fingerprints
from app.generation.source_memory_store import format_memory_snippet
from app.generation.source_origin import prompt_labels_for_origin
from app.models.enums import SourceOrigin, TargetMarket


def test_flow_reference_is_language_calibration_only():
    allowed = ALLOWED_USE_BY_CATEGORY["flow_reference"]
    blocked = DISALLOWED_USE_BY_CATEGORY["flow_reference"]
    guidance = compile_originality_guidance().lower()
    assert "calibrate_natural_spoken_egyptian_arabic" in allowed
    assert "learn_pacing_model" in blocked
    assert "use_domain_terminology_from_transcript" in blocked
    assert "language naturalness only" in guidance
    assert "teach pacing" not in guidance


def test_old_course_is_candidate_knowledge_never_structure_or_workflow():
    allowed = ALLOWED_USE_BY_CATEGORY["old_course"]
    blocked = DISALLOWED_USE_BY_CATEGORY["old_course"]
    assert not any("structure" in item or "workflow" in item for item in allowed)
    assert "reuse_old_course_structure_or_workflow" in blocked

    snippet = format_memory_snippet(
        {
            "source_type": "old_course",
            "old_course_lessons": ["COPY THIS OLD MODULE ORDER"],
        }
    )
    assert "COPY THIS OLD MODULE ORDER" not in snippet
    assert "old_map_not_authority=true" in snippet


def test_source_ledger_keeps_internal_policy_but_drops_raw_metadata():
    ledger = source_ledger_from_fingerprints(
        [7],
        {"7": "a" * 64},
        {
            "7": {
                "category": "scientific_reference",
                "priority": "high",
                "source_origin": "written_document",
                "file_format": "pdf",
                "raw_text": "SECRET SOURCE BODY",
                "url": "https://private.invalid/source",
                "filename": "owner-name.pdf",
            }
        },
    )
    row = ledger[0]
    assert row["authority_type"] == "factual_domain"
    assert row["source_origin"] == "written_document"
    assert "extract_factual_knowledge" in row["allowed_use"]
    assert row["provenance_policy"] == "internal_trace_only_never_lecturer_text"
    assert "SECRET SOURCE BODY" not in str(row)
    assert "private.invalid" not in str(row)
    assert "owner-name.pdf" not in str(row)


def test_category_authority_beats_length_and_priority():
    excerpts = compile_source_context(
        [
            SourceForCompiler(
                source_id=1,
                category="old_course",
                priority="high",
                text="polished old material " * 300,
            ),
            SourceForCompiler(
                source_id=2,
                category="scientific_reference",
                priority="low",
                text="verified concept with evidence",
            ),
        ],
        query_text="verified concept",
    )
    assert excerpts[0].source_id == 2


def test_ai_transcript_provenance_warns_about_asr_and_literal_copying():
    label = " ".join(
        prompt_labels_for_origin(SourceOrigin.AI_GENERATED_TRANSCRIPT.value)
    ).lower()
    assert "asr" in label
    assert "wrong terms" in label
    assert "do not copy wording" in label


def test_originality_rewrite_never_mentions_source_or_internal_rokn_process():
    source = "one two three four five six seven eight nine ten"
    out = rewrite_script_originality(source, source_texts=[source])
    assert "المصدر" not in out
    assert "رُكن" not in out
    assert "source" not in out.lower()


def test_market_pack_is_selected_brief_reality_not_model_assumption():
    egypt = build_market_pack(
        TargetMarket.EGYPT,
        realistic_student_budget="up to EGP 800 monthly",
        available_tools=["DaVinci Resolve"],
    )
    assert egypt["selected_market"] == "egypt"
    assert egypt["realistic_student_budget"] == "up to EGP 800 monthly"
    assert egypt["available_tools"] == ["DaVinci Resolve"]
    assert "stereotypes" in str(egypt)

    global_pack = build_market_pack(TargetMarket.GLOBAL)
    custom = build_market_pack(
        TargetMarket.CUSTOM,
        special_notes="Brazilian independent designers",
    )
    assert "Egyptian realities" not in str(global_pack)
    assert "WhatsApp" not in str(global_pack)
    assert custom["custom_context"] == "Brazilian independent designers"
    assert "Egyptian realities" not in str(custom)


def test_market_guidance_allows_paid_value_without_enterprise_assumption():
    guidance = compile_market_guidance(TargetMarket.GLOBAL).lower()
    assert "do not assume enterprise subscriptions" in guidance
    assert "reject a tool merely because it is paid" in guidance
    assert "professional value" in guidance


def test_official_tool_guidance_is_current_principle_first_and_evergreen():
    guidance = compile_official_tool_guidance(None).lower()
    assert "current official behavior beats old courses" in guidance
    assert "principle and decision before" in guidance
    assert "temporary prices/stats" in guidance
    assert "research notes" in guidance
