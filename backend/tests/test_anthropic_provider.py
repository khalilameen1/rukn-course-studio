"""Tests for app/ai/anthropic_provider.py.

Never calls the real Anthropic API: `messages.create` is replaced with a
fake that returns pre-scripted responses, so these tests run with no
ANTHROPIC_API_KEY and no network access.
"""

import pytest

from app.ai.anthropic_provider import (
    AnthropicProvider,
    AnthropicProviderError,
    _bump_max_tokens,
    _create_anthropic_client,
    _create_message_kwargs,
    _model_rejects_custom_sampling,
    _normalize_tool_input,
)
from app.prompts.prompt_registry import PipelineStage, PROMPT_SPECS, load_prompt
from app.ai.provider import (
    BuildCourseMapInput,
    CourseBrief,
    FinalReviewInput,
    RebuildFinalCourseInput,
    ReviewSingleReelInput,
    WriteSingleReelInput,
)
from app.generation.presets import PRESET_TEMPERATURES
from app.generation.model_routing import model_output_max_tokens
from app.models.enums import ExplanationLevel, GenerationPreset, StructureMode
from app.schemas.generation import (
    CourseMap,
    FinalCourse,
    GeneratedReel,
    ModulePlan,
    ReelPlan,
    ReviewResult,
)


class FakeToolUseBlock:
    def __init__(self, name: str, input_data: dict):
        self.type = "tool_use"
        self.name = name
        self.input = input_data


class FakeTextBlock:
    def __init__(self, text: str):
        self.type = "text"
        self.text = text


class FakeUsage:
    def __init__(
        self,
        input_tokens=None,
        output_tokens=None,
        cache_creation_input_tokens=None,
        cache_read_input_tokens=None,
    ):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_creation_input_tokens = cache_creation_input_tokens
        self.cache_read_input_tokens = cache_read_input_tokens


class FakeResponse:
    def __init__(self, content: list, usage=None, stop_reason=None):
        self.content = content
        self.usage = usage
        self.stop_reason = stop_reason


class FakeMessagesAPI:
    def __init__(self, responses: list[FakeResponse]):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class FakeAnthropicClient:
    def __init__(self, responses: list[FakeResponse]):
        self.messages = FakeMessagesAPI(responses)


def _provider_with_responses(responses: list[FakeResponse]) -> AnthropicProvider:
    provider = AnthropicProvider(api_key="test-key")
    provider._client = FakeAnthropicClient(responses)
    return provider


VALID_REVIEW_RESULT = {"scope": "reel", "status": "pass", "actions": []}


def test_sonnet_5_omits_temperature_and_disables_thinking():
    assert _model_rejects_custom_sampling("claude-sonnet-5")
    kwargs = _create_message_kwargs(
        model_name="claude-sonnet-5",
        max_tokens=1024,
        temperature=0.45,
        tools=[{"name": "x", "input_schema": {"type": "object", "properties": {}}}],
        tool_name="x",
        content="hi",
    )
    assert "temperature" not in kwargs
    assert kwargs.get("thinking") == {"type": "disabled"}


def test_older_models_still_pass_temperature():
    kwargs = _create_message_kwargs(
        model_name="claude-sonnet-4-5-20250929",
        max_tokens=1024,
        temperature=0.45,
        tools=[{"name": "x", "input_schema": {"type": "object", "properties": {}}}],
        tool_name="x",
        content="hi",
    )
    assert kwargs.get("temperature") == 0.45
    assert "thinking" not in kwargs


def test_model_name_defaults_to_settings_single_source_of_truth(monkeypatch):
    import app.ai.anthropic_provider as module

    monkeypatch.setattr(module.settings, "ai_model_name", "claude-example-model")
    provider = AnthropicProvider(api_key="test-key")

    assert provider._model_name == "claude-example-model"


def test_model_name_can_be_overridden_explicitly():
    provider = AnthropicProvider(api_key="test-key", model_name="custom-model")

    assert provider._model_name == "custom-model"


def test_build_prompt_includes_template_and_context():
    provider = AnthropicProvider(api_key="test-key")
    input_model = ReviewSingleReelInput(
        reel_plan=ReelPlan(
            reel_id="r1", title="Reel 1", purpose="test", estimated_length="30s"
        ),
        generated_reel=GeneratedReel(
            reel_id="r1", module_id="m1", title="Reel 1", script_text="hi", self_check_status="pass"
        ),
        rules_context={"rukn-core": "Some rule"},
    )

    prompt = provider._build_prompt(PipelineStage.REVIEW_SINGLE_REEL, input_model)

    assert "Task: Review one ROKN reel internally" in prompt
    assert '"reel_id": "r1"' in prompt
    assert "rukn-core" in prompt


def test_message_content_marks_stable_rules_for_cache():
    from app.data.course_standard import load_standard_files

    provider = AnthropicProvider(api_key="test-key")
    input_model = ReviewSingleReelInput(
        reel_plan=ReelPlan(
            reel_id="r1", title="Reel 1", purpose="test", estimated_length="30s"
        ),
        generated_reel=GeneratedReel(
            reel_id="r1", module_id="m1", title="Reel 1", script_text="hi", self_check_status="pass"
        ),
        rules_context={**load_standard_files(), "runtime_hint": "dynamic only"},
    )

    blocks = provider._build_message_content(
        PipelineStage.REVIEW_SINGLE_REEL, input_model
    )
    stable_blocks = [b for b in blocks if b.get("cache_control")]
    assert len(stable_blocks) == 1
    assert stable_blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert "Stable rules" in stable_blocks[0]["text"]
    assert "00-runtime-contract.md" in stable_blocks[0]["text"]
    assert "runtime_hint" not in stable_blocks[0]["text"]
    assert '"reel_id": "r1"' not in stable_blocks[0]["text"]
    flat = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    assert "runtime_hint" in flat


def test_call_structured_strips_cache_control_by_default():
    responses = [FakeResponse([FakeToolUseBlock("review_result", VALID_REVIEW_RESULT)])]
    provider = _provider_with_responses(responses)
    blocks = [
        {"type": "text", "text": "stable", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "dynamic"},
    ]
    provider._call_structured(blocks, ReviewResult, "review_result")
    sent = provider._client.messages.calls[0]["messages"][0]["content"]
    assert isinstance(sent, list)
    assert all("cache_control" not in b for b in sent if isinstance(b, dict))


def test_cache_control_rejection_retries_once_without_cache(monkeypatch):
    import app.ai.anthropic_provider as module

    class RejectCacheOnceMessages:
        def __init__(self):
            self.calls: list[dict] = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            sent = kwargs["messages"][0]["content"]
            if any(block.get("cache_control") for block in sent):
                raise RuntimeError("invalid_request: cache_control is not supported")
            return FakeResponse(
                [FakeToolUseBlock("review_result", VALID_REVIEW_RESULT)]
            )

    provider = AnthropicProvider(api_key="test-key")
    provider._client = type("Client", (), {})()
    provider._client.messages = RejectCacheOnceMessages()
    monkeypatch.setattr(module.settings, "anthropic_prompt_cache_enabled", True)
    blocks = [
        {"type": "text", "text": "stable", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "dynamic"},
    ]

    result = provider._call_structured(blocks, ReviewResult, "review_result")

    assert result.status == "pass"
    assert len(provider._client.messages.calls) == 2
    fallback = provider._client.messages.calls[1]["messages"][0]["content"]
    assert all("cache_control" not in block for block in fallback)


def test_cache_enabled_does_not_duplicate_uncached_prompt(monkeypatch):
    import app.ai.anthropic_provider as module

    provider = _provider_with_responses(
        [FakeResponse([FakeToolUseBlock("review_result", VALID_REVIEW_RESULT)])]
    )
    monkeypatch.setattr(module.settings, "anthropic_prompt_cache_enabled", True)

    provider._call_structured("plain prompt", ReviewResult, "review_result")

    assert len(provider._client.messages.calls) == 1


def test_classify_anthropic_provider_error_as_malformed():
    from app.generation.errors import classify_provider_error
    from app.ai.anthropic_provider import AnthropicProviderError

    assert (
        classify_provider_error(
            AnthropicProviderError(
                "CourseMap output failed validation after 2 attempt(s): missing modules"
            )
        )
        == "malformed_response"
    )


def test_call_structured_retries_once_then_succeeds():
    invalid = FakeResponse([FakeToolUseBlock("review_result", {"scope": "reel"})])  # missing status
    valid = FakeResponse([FakeToolUseBlock("review_result", VALID_REVIEW_RESULT)])
    provider = _provider_with_responses([invalid, valid])

    result = provider._call_structured("prompt", ReviewResult, "review_result")

    assert result.status == "pass"
    assert len(provider._client.messages.calls) == 2
    # The retry message should mention the schema failure to the model.
    assert "Retry" in provider._client.messages.calls[1]["messages"][0]["content"]


def test_call_structured_raises_after_exhausting_retries():
    invalid1 = FakeResponse([FakeToolUseBlock("review_result", {"scope": "reel"})])
    invalid2 = FakeResponse([FakeToolUseBlock("review_result", {"bad": "data"})])
    invalid3 = FakeResponse([FakeToolUseBlock("review_result", {"still": "bad"})])
    provider = _provider_with_responses([invalid1, invalid2, invalid3])

    with pytest.raises(AnthropicProviderError):
        provider._call_structured("prompt", ReviewResult, "review_result")


def test_call_structured_rejects_course_map_with_no_lessons():
    empty_lessons = {
        "course_title": "Course",
        "main_thread": "thread",
        "modules": [
            {
                "module_id": "m1",
                "title": "Module",
                "purpose": "p",
                "reels": [],
            }
        ],
    }
    responses = [
        FakeResponse([FakeToolUseBlock("course_map", empty_lessons)]) for _ in range(3)
    ]
    provider = _provider_with_responses(responses)

    with pytest.raises(AnthropicProviderError, match="no lessons"):
        provider._call_structured("prompt", CourseMap, "course_map")

    assert len(provider._client.messages.calls) == 3


def test_normalize_tool_input_maps_lessons_alias_and_defaults():
    raw = {
        "course_title": "Course",
        "main_thread": "thread",
        "modules": [
            {
                "module_id": "m1",
                "title": "Module",
                "purpose": "p",
                "lessons": [
                    {
                        "reel_id": "r1",
                        "title": "Lesson",
                        "purpose": "teach",
                        "must_cover": None,
                    }
                ],
            }
        ],
    }
    fixed = _normalize_tool_input(CourseMap, raw)
    assert "lessons" not in fixed["modules"][0]
    reel = fixed["modules"][0]["reels"][0]
    assert reel["estimated_length"] == "3 minutes"
    assert reel["must_cover"] == []
    assert CourseMap.model_validate(fixed).modules[0].reels[0].reel_id == "r1"


def test_call_structured_accepts_lessons_alias_for_course_map():
    payload = {
        "course_title": "Course",
        "main_thread": "thread",
        "modules": [
            {
                "module_id": "m1",
                "title": "Module",
                "purpose": "p",
                "lessons": [
                    {
                        "reel_id": "r1",
                        "title": "Lesson",
                        "purpose": "teach",
                        "estimated_length": "3 minutes",
                    }
                ],
            }
        ],
    }
    provider = _provider_with_responses(
        [FakeResponse([FakeToolUseBlock("course_map", payload)])]
    )
    result = provider._call_structured("prompt", CourseMap, "course_map")
    assert result.modules[0].reels[0].reel_id == "r1"


def test_call_structured_bumps_max_tokens_after_truncation():
    truncated = FakeResponse(
        [FakeTextBlock("partial")],
        stop_reason="max_tokens",
    )
    valid = FakeResponse([FakeToolUseBlock("review_result", VALID_REVIEW_RESULT)])
    provider = _provider_with_responses([truncated, valid])

    result = provider._call_structured(
        "prompt", ReviewResult, "review_result", overrides={"max_tokens": 1024}
    )

    assert result.status == "pass"
    assert provider._client.messages.calls[0]["max_tokens"] == 1024
    expected_limit = model_output_max_tokens(provider._model_name)
    assert provider._client.messages.calls[1]["max_tokens"] == expected_limit
    assert _bump_max_tokens(1024, provider._model_name) == expected_limit


def test_max_tokens_is_clamped_to_model_output_limit():
    provider = AnthropicProvider(
        api_key="test-key", model_name="claude-haiku-4-5", max_tokens=128_000
    )
    provider._client = FakeAnthropicClient(
        [FakeResponse([FakeToolUseBlock("review_result", VALID_REVIEW_RESULT)])]
    )

    provider._call_structured(
        "prompt", ReviewResult, "review_result", overrides={"max_tokens": 128_000}
    )

    assert provider._client.messages.calls[0]["max_tokens"] == 64_000


def test_truncation_public_hint_mentions_token_limit():
    responses = [
        FakeResponse([FakeTextBlock("cut off")], stop_reason="max_tokens")
        for _ in range(3)
    ]
    provider = _provider_with_responses(responses)

    with pytest.raises(AnthropicProviderError) as exc_info:
        provider._call_structured(
            "prompt", ReviewResult, "review_result", overrides={"max_tokens": 512}
        )

    assert "token limit" in (exc_info.value.public_hint or "").lower()


def test_call_structured_treats_missing_tool_call_as_failure_and_retries():
    no_tool_call = FakeResponse([FakeTextBlock("I refuse to use the tool.")])
    valid = FakeResponse([FakeToolUseBlock("review_result", VALID_REVIEW_RESULT)])
    provider = _provider_with_responses([no_tool_call, valid])

    result = provider._call_structured("prompt", ReviewResult, "review_result")

    assert result.status == "pass"
    assert len(provider._client.messages.calls) == 2


def test_last_usage_is_none_before_any_call():
    provider = AnthropicProvider(api_key="test-key")

    assert provider.last_usage is None


def test_last_usage_captures_real_response_usage_fields():
    usage = FakeUsage(
        input_tokens=120,
        output_tokens=45,
        cache_creation_input_tokens=10,
        cache_read_input_tokens=5,
    )
    responses = [FakeResponse([FakeToolUseBlock("review_result", VALID_REVIEW_RESULT)], usage=usage)]
    provider = _provider_with_responses(responses)

    provider._call_structured("prompt", ReviewResult, "review_result")

    assert provider.last_usage == {
        "model": provider._model_name,
        "input_tokens": 120,
        "output_tokens": 45,
        "cache_creation_input_tokens": 10,
        "cache_read_input_tokens": 5,
        "request_attempts": 1,
        "response_attempts": 1,
    }


def test_last_usage_is_safely_zero_valued_when_response_has_no_usage_attribute():
    responses = [FakeResponse([FakeToolUseBlock("review_result", VALID_REVIEW_RESULT)])]
    provider = _provider_with_responses(responses)

    provider._call_structured("prompt", ReviewResult, "review_result")

    assert provider.last_usage["input_tokens"] == 0
    assert provider.last_usage["output_tokens"] == 0


def test_last_usage_aggregates_every_billed_response_attempt():
    invalid_usage = FakeUsage(input_tokens=999, output_tokens=999)
    valid_usage = FakeUsage(input_tokens=10, output_tokens=20)
    invalid = FakeResponse([FakeToolUseBlock("review_result", {"scope": "reel"})], usage=invalid_usage)
    valid = FakeResponse(
        [FakeToolUseBlock("review_result", VALID_REVIEW_RESULT)], usage=valid_usage
    )
    provider = _provider_with_responses([invalid, valid])

    provider._call_structured("prompt", ReviewResult, "review_result")

    assert provider.last_usage["input_tokens"] == 1009
    assert provider.last_usage["output_tokens"] == 1019
    assert provider.last_usage["request_attempts"] == 2
    assert provider.last_usage["response_attempts"] == 2


def test_call_structured_uses_forced_tool_choice_and_configured_model():
    responses = [FakeResponse([FakeToolUseBlock("review_result", VALID_REVIEW_RESULT)])]
    provider = _provider_with_responses(responses)

    provider._call_structured("prompt", ReviewResult, "review_result")

    call = provider._client.messages.calls[0]
    assert call["tool_choice"] == {"type": "tool", "name": "review_result"}
    assert call["model"] == provider._model_name
    assert call["tools"][0]["name"] == "review_result"


def test_default_temperature_matches_balanced_preset_before_configure_for_run():
    """Before `configure_for_run` is ever called, a freshly-constructed
    provider already uses the Balanced preset's temperature (the default
    generation preset - see app/generation/presets.py)."""
    provider = AnthropicProvider(api_key="test-key")

    assert provider._temperature == PRESET_TEMPERATURES[GenerationPreset.BALANCED]


def test_configure_for_run_changes_temperature_sent_to_messages_create():
    responses = [FakeResponse([FakeToolUseBlock("review_result", VALID_REVIEW_RESULT)])]
    provider = _provider_with_responses(responses)
    assert provider._temperature == PRESET_TEMPERATURES[GenerationPreset.BALANCED]

    provider.configure_for_run(GenerationPreset.CREATIVE)
    provider._call_structured("prompt", ReviewResult, "review_result")

    call = provider._client.messages.calls[0]
    assert call["temperature"] == PRESET_TEMPERATURES[GenerationPreset.CREATIVE]
    assert call["temperature"] != PRESET_TEMPERATURES[GenerationPreset.BALANCED]


def test_request_timeout_defaults_from_settings(monkeypatch):
    import app.ai.anthropic_provider as module

    captured: dict = {}

    class FakeAnthropicClass:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(module.anthropic, "Anthropic", FakeAnthropicClass)

    AnthropicProvider(api_key="test-key")

    assert captured["timeout"] == module.settings.anthropic_request_timeout_seconds
    assert captured["max_retries"] == 0


def test_request_timeout_can_be_overridden_explicitly(monkeypatch):
    import app.ai.anthropic_provider as module

    captured: dict = {}

    class FakeAnthropicClass:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(module.anthropic, "Anthropic", FakeAnthropicClass)

    AnthropicProvider(api_key="test-key", request_timeout_seconds=5.0)

    assert captured["timeout"] == 5.0


def test_client_falls_back_from_deprecated_proxies_constructor_error(monkeypatch):
    import app.ai.anthropic_provider as module

    calls: list[dict] = []
    sentinel_http_client = object()

    class FakeAnthropicClass:
        def __init__(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise TypeError("Client.__init__() got an unexpected keyword argument 'proxies'")

    monkeypatch.setattr(module.anthropic, "Anthropic", FakeAnthropicClass)
    monkeypatch.setattr(module.httpx, "Client", lambda **_kwargs: sentinel_http_client)

    _create_anthropic_client(api_key="test-key", timeout=12.0)

    assert len(calls) == 2
    assert calls[0]["max_retries"] == 0
    assert "http_client" not in calls[0]
    assert calls[1]["http_client"] is sentinel_http_client


def _brief() -> CourseBrief:
    return CourseBrief(
        title="Intro to Excel Formulas",
        audience="new hires",
        outcome="build a budget sheet",
        structure_mode=StructureMode.CONNECTED_NO_MODULES,
        explanation_level=ExplanationLevel.FINAL_ONLY,
    )


def _reel_plan() -> ReelPlan:
    return ReelPlan(reel_id="m1-r1", title="Reel", purpose="p", estimated_length="30s")


def _module_plan() -> ModulePlan:
    return ModulePlan(module_id="m1", title="Module 1", purpose="p", reels=[_reel_plan()])


def _generated_reel() -> GeneratedReel:
    return GeneratedReel(
        reel_id="m1-r1", module_id="m1", title="Reel", script_text="script", self_check_status="pass"
    )


def _course_map() -> CourseMap:
    return CourseMap(course_title="Course", main_thread="thread", modules=[_module_plan()])


VALID_COURSE_MAP = {
    "course_title": "Course",
    "main_thread": "thread",
    "modules": [
        {
            "module_id": "m1",
            "title": "Module 1",
            "purpose": "p",
            "bridge_project": None,
            "reels": [
                {
                    "reel_id": "m1-r1",
                    "title": "Reel",
                    "purpose": "p",
                    "must_cover": [],
                    "must_avoid": [],
                    "source_hints": [],
                    "estimated_length": "30s",
                }
            ],
        }
    ],
}

VALID_GENERATED_REEL = {
    "reel_id": "m1-r1",
    "module_id": "m1",
    "title": "Reel",
    "script_text": "script",
    "used_ideas": [],
    "used_examples": [],
    "self_check_status": "pass",
}

VALID_FINAL_COURSE = {
    "title": "Course",
    "modules": [
        {
            "module_id": "m1",
            "title": "Module 1",
            "bridge_project": None,
            "reels": [{"reel_id": "m1-r1", "title": "Reel", "script_text": "script"}],
        }
    ],
    "full_text": "# Module 1\n\n## Reel\nscript",
}


@pytest.mark.parametrize(
    ("method_name", "make_input", "tool_name", "valid_output", "expected_type", "prompt_file_marker"),
    [
        (
            "build_course_map",
            lambda: BuildCourseMapInput(brief=_brief()),
            "course_map",
            VALID_COURSE_MAP,
            CourseMap,
            "Build the complete ROKN course map",
        ),
        (
            "write_single_reel",
            lambda: WriteSingleReelInput(
                course_title="Course", main_thread="thread", module=_module_plan(), reel=_reel_plan()
            ),
            "generated_reel",
            VALID_GENERATED_REEL,
            GeneratedReel,
            "Write one final-master-capable ROKN reel draft",
        ),
        (
            "review_single_reel",
            lambda: ReviewSingleReelInput(reel_plan=_reel_plan(), generated_reel=_generated_reel()),
            "review_result",
            VALID_REVIEW_RESULT,
            ReviewResult,
            "Review one ROKN reel internally",
        ),
        (
            "final_review",
            lambda: FinalReviewInput(course_map=_course_map(), all_reels=[_generated_reel()]),
            "review_result",
            {"scope": "final", "status": "pass", "actions": []},
            ReviewResult,
            "Final whole-course review",
        ),
        (
            "rebuild_final_course",
            lambda: RebuildFinalCourseInput(
                course_map=_course_map(),
                all_reels=[_generated_reel()],
                final_review=ReviewResult(scope="final", status="needs_revision", actions=[]),
            ),
            "final_course",
            VALID_FINAL_COURSE,
            FinalCourse,
            "Rebuild the final export-ready ROKN course",
        ),
    ],
)
def test_each_provider_method_calls_correct_tool_and_prompt(
    method_name, make_input, tool_name, valid_output, expected_type, prompt_file_marker
):
    responses = [FakeResponse([FakeToolUseBlock(tool_name, valid_output)])]
    provider = _provider_with_responses(responses)

    method = getattr(provider, method_name)
    result = method(make_input())

    assert isinstance(result, expected_type)
    call = provider._client.messages.calls[0]
    assert call["tool_choice"] == {"type": "tool", "name": tool_name}
    content = call["messages"][0]["content"]
    if isinstance(content, list):
        flat = "".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict)
        )
    else:
        flat = str(content)
    assert prompt_file_marker in flat
