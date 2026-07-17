"""Generation hardening: preflight, boot safety, context trim, safe flush."""

from app.ai.factory import AIProviderConfigError, get_ai_provider
from app.config import Settings
from app.generation.boot_safety import CRITICAL_JOB_COLUMNS, verify_generation_job_columns
from app.generation.context_budget import trim_rules_context, trim_source_excerpts_for_map
from app.generation.errors import classify_provider_error
from app.generation.generation_preflight import (
    generation_preflight,
    validate_ai_model_name,
)
from app.generation.prompt_compiler import SourceExcerpt
from app.generation.safe_flush import OPTIONAL_JOB_FLUSH_KEYS, safe_job_flush
from app.generation.model_routing import MODEL_ROUTING_OVERRIDES, resolve_stage_overrides
from app.prompts.prompt_registry import PipelineStage
import pytest


def test_validate_rejects_bad_model_slug():
    assert validate_ai_model_name("") is not None
    assert validate_ai_model_name("changeme") is not None
    assert validate_ai_model_name("claude-sonnet-5") is None  # official Sonnet 5 ID
    assert validate_ai_model_name("claude-sonnet-4-5-20250929") is None


def test_get_ai_provider_rejects_bad_anthropic_model():
    cfg = Settings(
        ai_provider="anthropic",
        anthropic_api_key="sk-test",
        ai_model_name="changeme",
    )
    with pytest.raises(AIProviderConfigError):
        get_ai_provider(cfg)


def test_get_ai_provider_accepts_sonnet_5():
    cfg = Settings(
        ai_provider="anthropic",
        anthropic_api_key="sk-test",
        ai_model_name="claude-sonnet-5",
    )
    provider = get_ai_provider(cfg)
    assert provider._model_name == "claude-sonnet-5"


def test_generation_preflight_fake_ok():
    # Uses process settings — fake should be ok in tests.
    result = generation_preflight()
    assert "ok" in result
    assert "blockers" in result


def test_trim_source_excerpts_respects_budget():
    excerpts = [
        SourceExcerpt(
            source_id=i,
            category="user_notes",
            priority="high",
            text=("word " * 5000),
            allowed_use=["factual_knowledge"],
            disallowed_use=[],
        )
        for i in range(5)
    ]
    trimmed = trim_source_excerpts_for_map(excerpts, max_chars=3000, max_items=3)
    assert len(trimmed) <= 3
    assert sum(len(e.text or "") for e in trimmed) <= 3200


def test_trim_rules_context_caps_size():
    rules = {f"k{i}": ("x" * 5000) for i in range(20)}
    out = trim_rules_context(rules, max_total_chars=8000)
    total = sum(len(k) + len(v) for k, v in out.items())
    assert total <= 12_000  # stubs for remaining keys allowed
    assert len(out) == 20


def test_safe_flush_retries_without_optional_columns():
    calls: list[dict] = []

    def flush(**fields):
        calls.append(fields)
        if "provenance_summary" in fields:
            raise RuntimeError("no such column: provenance_summary")
        return {"ok": True}

    result = safe_job_flush(
        flush,
        status="running",
        provenance_summary="x",
        architecture_summary="y",
    )
    assert result == {"ok": True}
    assert len(calls) == 2
    assert "provenance_summary" not in calls[1]
    assert "architecture_summary" not in calls[1]
    assert calls[1]["status"] == "running"
    assert "provenance_summary" in OPTIONAL_JOB_FLUSH_KEYS


def test_map_stage_has_higher_max_tokens():
    from app.generation.model_routing import MODEL_OUTPUT_MAX_TOKENS

    ov = resolve_stage_overrides(PipelineStage.BUILD_COURSE_MAP)
    # No soft product cap: every map call uses the model output ceiling.
    assert ov.get("max_tokens", 0) == MODEL_OUTPUT_MAX_TOKENS
    assert PipelineStage.BUILD_COURSE_MAP in MODEL_ROUTING_OVERRIDES


def test_empty_map_classifies_malformed():
    assert (
        classify_provider_error(
            RuntimeError("Course map was empty or had no lessons after build")
        )
        == "malformed_response"
    )


def test_critical_job_columns_list_includes_genspark_fields():
    for name in (
        "architecture_summary",
        "grounding_confidence",
        "research_synthesis_summary",
        "improve_next_tip",
    ):
        assert name in CRITICAL_JOB_COLUMNS
