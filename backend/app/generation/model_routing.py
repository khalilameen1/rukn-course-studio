"""Quality-first OpenAI GPT-5.6 stage routing.

The UI remains one action / one DOCX. Internally, the hardest architecture and
whole-course decisions run in Pro+max; long-form lesson writing and local review
run in Pro+xhigh to preserve quality without spending max reasoning on routine
prose realization.
"""
from __future__ import annotations

from app.prompts.prompt_registry import PipelineStage

MODEL_OUTPUT_MAX_TOKENS = 128_000
MAP_MAX_TOKENS_CAP = MODEL_OUTPUT_MAX_TOKENS

MODEL_ROUTING_OVERRIDES: dict[PipelineStage, dict] = {
    PipelineStage.BUILD_COURSE_MAP: {
        "reasoning_mode": "pro", "reasoning_effort": "max",
        "max_output_tokens": 128_000, "verbosity": "high",
    },
    PipelineStage.WRITE_SINGLE_REEL: {
        "reasoning_mode": "pro", "reasoning_effort": "xhigh",
        "max_output_tokens": 32_000, "verbosity": "high",
    },
    PipelineStage.REVIEW_SINGLE_REEL: {
        "reasoning_mode": "pro", "reasoning_effort": "xhigh",
        "max_output_tokens": 24_000, "verbosity": "medium",
    },
    PipelineStage.FINAL_REVIEW: {
        "reasoning_mode": "pro", "reasoning_effort": "max",
        "max_output_tokens": 64_000, "verbosity": "high",
    },
    PipelineStage.REBUILD_FINAL_COURSE: {
        "reasoning_mode": "pro", "reasoning_effort": "max",
        "max_output_tokens": 128_000, "verbosity": "high",
    },
}


def model_output_max_tokens(model_name: str) -> int:
    normalized = (model_name or "").strip().lower()
    return MODEL_OUTPUT_MAX_TOKENS if normalized in {"gpt-5.6", "gpt-5.6-sol"} else 8_192


def resolve_stage_overrides(stage: PipelineStage) -> dict:
    return dict(MODEL_ROUTING_OVERRIDES.get(stage, {}))
