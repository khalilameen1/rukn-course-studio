"""Tests for app/generation/model_routing.py (§9) - the no-override default
path, and that a configured override is actually honored by
`AnthropicProvider`.
"""

from app.ai.anthropic_provider import AnthropicProvider
from app.generation.model_routing import MODEL_ROUTING_OVERRIDES, resolve_stage_overrides
from app.prompts.prompt_registry import PipelineStage
from app.schemas.generation import ReviewResult
from tests.test_anthropic_provider import FakeResponse, FakeToolUseBlock, _provider_with_responses

VALID_REVIEW_RESULT = {"scope": "reel", "status": "pass", "actions": []}


def test_resolve_stage_overrides_empty_unless_listed():
    for stage in PipelineStage:
        expected = dict(MODEL_ROUTING_OVERRIDES.get(stage, {}))
        assert resolve_stage_overrides(stage) == expected


def test_map_stage_uses_large_max_tokens_budget():
    assert resolve_stage_overrides(PipelineStage.BUILD_COURSE_MAP)["max_tokens"] >= 32768


def test_no_override_path_uses_the_providers_own_configured_model_and_temperature():
    responses = [FakeResponse([FakeToolUseBlock("review_result", VALID_REVIEW_RESULT)])]
    provider = _provider_with_responses(responses)
    provider._model_name = "configured-model"
    provider._temperature = 0.42

    provider._run(PipelineStage.REVIEW_SINGLE_REEL, _dummy_review_input(), ReviewResult)

    call = provider._client.messages.calls[0]
    assert call["model"] == "configured-model"
    assert call["temperature"] == 0.42


def test_a_configured_override_for_one_stage_is_actually_honored(monkeypatch):
    import app.generation.model_routing as model_routing_module

    monkeypatch.setitem(
        model_routing_module.MODEL_ROUTING_OVERRIDES,
        PipelineStage.REVIEW_SINGLE_REEL,
        {"model": "override-model", "temperature": 0.05, "max_tokens": 256},
    )

    responses = [FakeResponse([FakeToolUseBlock("review_result", VALID_REVIEW_RESULT)])]
    provider = _provider_with_responses(responses)
    provider._model_name = "configured-model"
    provider._temperature = 0.42
    provider._max_tokens = 4096

    provider._run(PipelineStage.REVIEW_SINGLE_REEL, _dummy_review_input(), ReviewResult)

    call = provider._client.messages.calls[0]
    assert call["model"] == "override-model"
    assert call["temperature"] == 0.05
    assert call["max_tokens"] == 256


def test_an_override_for_one_stage_does_not_affect_other_stages(monkeypatch):
    import app.generation.model_routing as model_routing_module

    monkeypatch.setitem(
        model_routing_module.MODEL_ROUTING_OVERRIDES,
        PipelineStage.REVIEW_SINGLE_REEL,
        {"model": "override-model"},
    )

    # Stages that are not REVIEW_SINGLE_REEL keep their own configured overrides.
    assert resolve_stage_overrides(PipelineStage.REVIEW_SINGLE_REEL) == {
        "model": "override-model"
    }
    assert "model" not in resolve_stage_overrides(PipelineStage.FINAL_REVIEW)
    assert "model" not in resolve_stage_overrides(PipelineStage.WRITE_SINGLE_REEL)


def test_a_partial_override_falls_back_to_configured_values_for_missing_fields(monkeypatch):
    """Only `temperature` overridden -> `model`/`max_tokens` still come
    from the provider's own configured values."""
    import app.generation.model_routing as model_routing_module

    monkeypatch.setitem(
        model_routing_module.MODEL_ROUTING_OVERRIDES,
        PipelineStage.REVIEW_SINGLE_REEL,
        {"temperature": 0.01},
    )

    responses = [FakeResponse([FakeToolUseBlock("review_result", VALID_REVIEW_RESULT)])]
    provider = _provider_with_responses(responses)
    provider._model_name = "configured-model"
    provider._temperature = 0.42
    provider._max_tokens = 4096

    provider._run(PipelineStage.REVIEW_SINGLE_REEL, _dummy_review_input(), ReviewResult)

    call = provider._client.messages.calls[0]
    assert call["model"] == "configured-model"
    assert call["temperature"] == 0.01
    assert call["max_tokens"] == 4096


def _dummy_review_input():
    from app.ai.provider import ReviewSingleReelInput
    from app.schemas.generation import GeneratedReel, ReelPlan

    return ReviewSingleReelInput(
        reel_plan=ReelPlan(reel_id="r1", title="Reel 1", purpose="test", estimated_length="30s"),
        generated_reel=GeneratedReel(
            reel_id="r1", module_id="m1", title="Reel 1", script_text="hi", self_check_status="pass"
        ),
    )
