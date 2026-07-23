"""Quality-first OpenAI GPT-5.6 stage routing.

The UI remains one action / one DOCX. Internally, the hardest architecture and
whole-course decisions run in Pro+max; long-form lesson writing and local review
run in Pro+xhigh to preserve quality without spending max reasoning on routine
prose realization.

``max_output_tokens`` is the OpenAI Responses parameter. ``max_tokens`` is kept
as a parallel alias so the legacy Anthropic provider path (tests / optional
fallback) still receives a usable ceiling from the same routing table.
"""
from __future__ import annotations

from app.prompts.prompt_registry import PipelineStage

MODEL_OUTPUT_MAX_TOKENS = 128_000
MAP_MAX_TOKENS_CAP = MODEL_OUTPUT_MAX_TOKENS
UNKNOWN_MODEL_OUTPUT_MAX_TOKENS = 8_192

# Prefer exact production slug first; substring markers cover dated Anthropic IDs.
_MODEL_OUTPUT_LIMITS: tuple[tuple[str, int], ...] = (
    ("gpt-5.6-sol", MODEL_OUTPUT_MAX_TOKENS),
    ("gpt-5.6-pro", MODEL_OUTPUT_MAX_TOKENS),
    ("gpt-5.6", MODEL_OUTPUT_MAX_TOKENS),
    ("claude-sonnet-5", MODEL_OUTPUT_MAX_TOKENS),
    ("claude-fable-5", MODEL_OUTPUT_MAX_TOKENS),
    ("claude-mythos-5", MODEL_OUTPUT_MAX_TOKENS),
    ("claude-opus-4-8", MODEL_OUTPUT_MAX_TOKENS),
    ("claude-opus-4-7", MODEL_OUTPUT_MAX_TOKENS),
    ("claude-opus-4-6", MODEL_OUTPUT_MAX_TOKENS),
    ("claude-sonnet-4-6", 64_000),
    ("claude-sonnet-4-5", 64_000),
    ("claude-haiku-4-5", 64_000),
)


def model_output_max_tokens(model_name: str) -> int:
    """Return a safe output ceiling for the configured model slug."""
    normalized = (model_name or "").strip().lower()
    for marker, limit in _MODEL_OUTPUT_LIMITS:
        if marker in normalized:
            return limit
    return UNKNOWN_MODEL_OUTPUT_MAX_TOKENS


MODEL_ROUTING_OVERRIDES: dict[PipelineStage, dict] = {
    PipelineStage.BUILD_COURSE_MAP: {
        "reasoning_mode": "pro",
        "reasoning_effort": "max",
        "max_output_tokens": MODEL_OUTPUT_MAX_TOKENS,
        "max_tokens": MODEL_OUTPUT_MAX_TOKENS,
        "verbosity": "high",
    },
    PipelineStage.WRITE_SINGLE_REEL: {
        "reasoning_mode": "pro",
        "reasoning_effort": "xhigh",
        "max_output_tokens": 32_000,
        "max_tokens": 32_000,
        "verbosity": "high",
    },
    PipelineStage.REVIEW_SINGLE_REEL: {
        "reasoning_mode": "pro",
        "reasoning_effort": "xhigh",
        "max_output_tokens": 24_000,
        "max_tokens": 24_000,
        "verbosity": "medium",
    },
    PipelineStage.FINAL_REVIEW: {
        "reasoning_mode": "pro",
        "reasoning_effort": "max",
        "max_output_tokens": 64_000,
        "max_tokens": 64_000,
        "verbosity": "high",
    },
    PipelineStage.REBUILD_FINAL_COURSE: {
        "reasoning_mode": "pro",
        "reasoning_effort": "max",
        "max_output_tokens": MODEL_OUTPUT_MAX_TOKENS,
        "max_tokens": MODEL_OUTPUT_MAX_TOKENS,
        "verbosity": "high",
    },
}


def resolve_stage_overrides(stage: PipelineStage) -> dict:
    return dict(MODEL_ROUTING_OVERRIDES.get(stage, {}))
