"""OpenAI provider request-shape and CourseMap normalization tests."""

from unittest.mock import MagicMock

import pytest

from app.ai.course_map_normalize import normalize_course_map_payload
from app.ai.openai_provider import (
    OpenAIProvider,
    OpenAIProviderError,
    _public_api_hint,
)
from app.prompts.prompt_registry import PipelineStage
from app.schemas.generation import CourseMap


def test_parse_kwargs_omit_prompt_cache_retention_for_gpt_5_6(monkeypatch):
    """GPT-5.6 rejects deprecated prompt_cache_retention=24h — omit it."""
    provider = OpenAIProvider(api_key="sk-test", model_name="gpt-5.6-sol")
    captured: dict = {}

    class FakeParsed:
        output_parsed = CourseMap(
            course_title="C",
            main_thread="t",
            modules=[
                {
                    "module_id": "m1",
                    "title": "M",
                    "purpose": "p",
                    "reels": [
                        {
                            "reel_id": "r1",
                            "title": "L",
                            "purpose": "teach",
                            "estimated_length": "3 minutes",
                        }
                    ],
                }
            ],
        )
        usage = None
        status = "completed"
        incomplete_details = None

    def fake_parse(**kwargs):
        captured.update(kwargs)
        return FakeParsed()

    provider._client = MagicMock()
    provider._client.responses.parse = fake_parse

    result = provider._call_structured(
        messages=[{"role": "user", "content": "x"}],
        schema=CourseMap,
        schema_name="course_map",
        model_name="gpt-5.6-sol",
        reasoning_mode="pro",
        reasoning_effort="max",
        max_output_tokens=128_000,
        verbosity="high",
        stage=PipelineStage.BUILD_COURSE_MAP,
    )

    assert result.course_title == "C"
    assert "prompt_cache_options" not in captured
    assert "prompt_cache_retention" not in captured
    assert captured["prompt_cache_key"] == "rukn-v1.7:build_course_map"
    assert captured["verbosity"] == "high"
    assert captured["reasoning"]["mode"] == "pro"
    assert captured["reasoning"]["effort"] == "max"
    assert "context" not in captured["reasoning"]


def test_unexpected_kwargs_hint_mentions_redeploy():
    hint = _public_api_hint(
        TypeError("Responses.parse() got an unexpected keyword argument 'prompt_cache_options'")
    )
    assert "Redeploy" in hint


def test_cache_retention_hint_mentions_gpt56_fix():
    hint = _public_api_hint(
        RuntimeError("Invalid parameter: prompt_cache_retention is not supported for this model")
    )
    assert "cache" in hint.lower()
    assert "Redeploy" in hint


def test_probe_openai_omits_cache_retention(monkeypatch):
    from app.ai import openai_provider as mod

    captured: dict = {}

    class FakeParsed:
        output_parsed = mod._OpenAIPing(ok=True)

    def fake_parse(**kwargs):
        captured.update(kwargs)
        return FakeParsed()

    class FakeOpenAI:
        def __init__(self, **_kwargs):
            self.responses = MagicMock()
            self.responses.parse = fake_parse

    monkeypatch.setattr(mod, "OpenAI", FakeOpenAI)
    monkeypatch.setattr(mod, "_PROBE_OK_MONO", None)

    err = mod.probe_openai_responses_api(api_key="sk-test", model_name="gpt-5.6-sol", force=True)
    assert err is None
    assert "prompt_cache_retention" not in captured
    assert "prompt_cache_options" not in captured
    assert captured["max_output_tokens"] == 64
    assert captured["reasoning"] == {"effort": "low"}
    assert captured["text_format"] is mod._OpenAIPing


def test_normalize_repairs_partial_semantic_contract_and_aliases():
    raw = {
        "course_title": "Course",
        "main_thread": "thread",
        "modules": [
            {
                "module_id": "m1",
                "title": "Module",
                "purpose": "p",
                "module_project": {"name": "", "brief": ""},
                "lessons": [
                    {
                        "reel_id": "r1",
                        "title": "Lesson",
                        "purpose": "teach",
                        "must_cover": None,
                        "delivery_mode": "demo",
                        "lesson_semantic_contract": {
                            "learner_before": "a",
                            # missing the rest on purpose
                        },
                    }
                ],
            }
        ],
    }
    fixed = normalize_course_map_payload(raw)
    reel = fixed["modules"][0]["reels"][0]
    assert reel["delivery_mode"] == "screen_demo"
    assert reel["lesson_semantic_contract"] is None
    assert reel["must_cover"] == []
    assert fixed["modules"][0]["module_project"] is None
    assert CourseMap.model_validate(fixed).modules[0].reels[0].reel_id == "r1"


def test_call_structured_raises_openai_provider_error_on_api_failure():
    provider = OpenAIProvider(api_key="sk-test", model_name="gpt-5.6-sol")

    def boom(**_kwargs):
        raise RuntimeError("401 authentication failed")

    provider._client = MagicMock()
    provider._client.responses.parse = boom

    with pytest.raises(OpenAIProviderError) as exc_info:
        provider._call_structured(
            messages=[{"role": "user", "content": "x"}],
            schema=CourseMap,
            schema_name="course_map",
            model_name="gpt-5.6-sol",
            reasoning_mode="pro",
            reasoning_effort="max",
            max_output_tokens=1000,
            verbosity="medium",
            stage=PipelineStage.BUILD_COURSE_MAP,
        )
    assert "OPENAI_API_KEY" in (exc_info.value.public_hint or "")


def test_call_structured_retries_without_reasoning_mode_on_param_error():
    provider = OpenAIProvider(api_key="sk-test", model_name="gpt-5.6-sol")
    calls: list[dict] = []

    class FakeParsed:
        output_parsed = CourseMap(
            course_title="C",
            main_thread="t",
            modules=[
                {
                    "module_id": "m1",
                    "title": "M",
                    "purpose": "p",
                    "reels": [
                        {
                            "reel_id": "r1",
                            "title": "L",
                            "purpose": "teach",
                            "estimated_length": "3 minutes",
                        }
                    ],
                }
            ],
        )
        usage = None
        status = "completed"
        incomplete_details = None

    def fake_parse(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise RuntimeError("Invalid parameter: reasoning.mode is not supported")
        return FakeParsed()

    provider._client = MagicMock()
    provider._client.responses.parse = fake_parse

    result = provider._call_structured(
        messages=[{"role": "user", "content": "x"}],
        schema=CourseMap,
        schema_name="course_map",
        model_name="gpt-5.6-sol",
        reasoning_mode="pro",
        reasoning_effort="high",
        max_output_tokens=1000,
        verbosity="medium",
        stage=PipelineStage.BUILD_COURSE_MAP,
    )
    assert result.course_title == "C"
    assert calls[0]["reasoning"].get("mode") == "pro"
    assert "mode" not in calls[1]["reasoning"]
