"""Tests for app/ai/anthropic_provider.py.

Never calls the real Anthropic API: `messages.create` is replaced with a
fake that returns pre-scripted responses, so these tests run with no
ANTHROPIC_API_KEY and no network access.
"""

import pytest

from app.ai.anthropic_provider import AnthropicProvider, AnthropicProviderError
from app.prompts.prompt_registry import PipelineStage, PROMPT_SPECS, load_prompt
from app.ai.provider import (
    BuildCourseMapInput,
    CourseBrief,
    FinalReviewInput,
    ModuleWithReels,
    RebuildFinalCourseInput,
    ReviewFiveReelsInput,
    ReviewModuleInput,
    ReviewSingleReelInput,
    ReviewTwoModulesInput,
    WriteSingleReelInput,
)
from app.models.enums import ExplanationLevel, StructureMode
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


class FakeResponse:
    def __init__(self, content: list):
        self.content = content


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

    assert "Task: Review a Single Reel" in prompt
    assert '"reel_id": "r1"' in prompt
    assert "rukn-core" in prompt


def test_call_structured_succeeds_on_first_attempt():
    responses = [FakeResponse([FakeToolUseBlock("review_result", VALID_REVIEW_RESULT)])]
    provider = _provider_with_responses(responses)

    result = provider._call_structured("prompt", ReviewResult, "review_result")

    assert isinstance(result, ReviewResult)
    assert result.status == "pass"
    assert len(provider._client.messages.calls) == 1


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
    provider = _provider_with_responses([invalid1, invalid2])

    with pytest.raises(AnthropicProviderError):
        provider._call_structured("prompt", ReviewResult, "review_result")

    assert len(provider._client.messages.calls) == 2


def test_call_structured_treats_missing_tool_call_as_failure_and_retries():
    no_tool_call = FakeResponse([FakeTextBlock("I refuse to use the tool.")])
    valid = FakeResponse([FakeToolUseBlock("review_result", VALID_REVIEW_RESULT)])
    provider = _provider_with_responses([no_tool_call, valid])

    result = provider._call_structured("prompt", ReviewResult, "review_result")

    assert result.status == "pass"
    assert len(provider._client.messages.calls) == 2


def test_call_structured_uses_forced_tool_choice_and_configured_model():
    responses = [FakeResponse([FakeToolUseBlock("review_result", VALID_REVIEW_RESULT)])]
    provider = _provider_with_responses(responses)

    provider._call_structured("prompt", ReviewResult, "review_result")

    call = provider._client.messages.calls[0]
    assert call["tool_choice"] == {"type": "tool", "name": "review_result"}
    assert call["model"] == provider._model_name
    assert call["tools"][0]["name"] == "review_result"


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
            "Build Course Map",
        ),
        (
            "write_single_reel",
            lambda: WriteSingleReelInput(
                course_title="Course", main_thread="thread", module=_module_plan(), reel=_reel_plan()
            ),
            "generated_reel",
            VALID_GENERATED_REEL,
            GeneratedReel,
            "Write a Single Reel Script",
        ),
        (
            "review_single_reel",
            lambda: ReviewSingleReelInput(reel_plan=_reel_plan(), generated_reel=_generated_reel()),
            "review_result",
            VALID_REVIEW_RESULT,
            ReviewResult,
            "Review a Single Reel",
        ),
        (
            "review_five_reels",
            lambda: ReviewFiveReelsInput(reels=[_generated_reel()]),
            "review_result",
            {"scope": "five_reels", "status": "pass", "actions": []},
            ReviewResult,
            "Review a Window of Five Reels",
        ),
        (
            "review_module",
            lambda: ReviewModuleInput(module=_module_plan(), reels=[_generated_reel()]),
            "review_result",
            {"scope": "module", "status": "pass", "actions": []},
            ReviewResult,
            "Review One Completed Module",
        ),
        (
            "review_two_modules",
            lambda: ReviewTwoModulesInput(
                first=ModuleWithReels(module=_module_plan(), reels=[_generated_reel()]),
                second=ModuleWithReels(module=_module_plan(), reels=[_generated_reel()]),
            ),
            "review_result",
            {"scope": "two_modules", "status": "pass", "actions": []},
            ReviewResult,
            "Review a Pair of Modules",
        ),
        (
            "final_review",
            lambda: FinalReviewInput(course_map=_course_map(), all_reels=[_generated_reel()]),
            "review_result",
            {"scope": "final", "status": "pass", "actions": []},
            ReviewResult,
            "Final Full-Course Review",
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
            "Rebuild the Final Course",
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
    assert prompt_file_marker in call["messages"][0]["content"]
