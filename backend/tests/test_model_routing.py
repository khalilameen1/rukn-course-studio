"""Tests for app/generation/model_routing.py stage budgets and model ceilings."""

from app.generation.model_routing import (
    MODEL_OUTPUT_MAX_TOKENS,
    MODEL_ROUTING_OVERRIDES,
    model_output_max_tokens,
    resolve_stage_overrides,
)
from app.prompts.prompt_registry import PipelineStage


def test_resolve_stage_overrides_empty_unless_listed():
    for stage in PipelineStage:
        expected = dict(MODEL_ROUTING_OVERRIDES.get(stage, {}))
        assert resolve_stage_overrides(stage) == expected


def test_map_stage_uses_large_max_tokens_budget():
    route = resolve_stage_overrides(PipelineStage.BUILD_COURSE_MAP)
    assert route["max_output_tokens"] == MODEL_OUTPUT_MAX_TOKENS
    assert route["max_tokens"] == MODEL_OUTPUT_MAX_TOKENS
    assert route["reasoning_effort"] == "max"


def test_generation_stages_expose_openai_and_anthropic_token_keys():
    for stage in (
        PipelineStage.BUILD_COURSE_MAP,
        PipelineStage.WRITE_SINGLE_REEL,
        PipelineStage.REVIEW_SINGLE_REEL,
        PipelineStage.FINAL_REVIEW,
        PipelineStage.REBUILD_FINAL_COURSE,
    ):
        route = resolve_stage_overrides(stage)
        assert route["max_output_tokens"] == route["max_tokens"]
        assert route["max_output_tokens"] >= 24_000


def test_model_output_max_tokens_for_production_and_legacy_slugs():
    assert model_output_max_tokens("gpt-5.6-sol") == MODEL_OUTPUT_MAX_TOKENS
    assert model_output_max_tokens("gpt-5.6") == MODEL_OUTPUT_MAX_TOKENS
    assert model_output_max_tokens("claude-sonnet-5") == MODEL_OUTPUT_MAX_TOKENS
    assert model_output_max_tokens("claude-haiku-4-5") == 64_000
    assert model_output_max_tokens("unknown-model") == 8_192
