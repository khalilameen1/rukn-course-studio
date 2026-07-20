"""Per-pipeline-stage AI provider routing overrides (§9).

Default behavior: every stage uses Settings.ai_model_name and the course
preset temperature unless listed below.

``max_tokens`` is required by the Anthropic API — it cannot be omitted. We
set every generation stage to the model output ceiling (128k for Claude
Sonnet 5 / Opus 4.x) so structured calls are never cut off mid-tool-call.
Actual billed tokens are only what the model writes, not this ceiling.
"""

from __future__ import annotations

from app.prompts.prompt_registry import PipelineStage

# Claude Sonnet 5 / Opus 4.x documented max output. Anthropic requires
# ``max_tokens`` on every messages.create call — this is the effective
# "no soft product limit" ceiling.
MODEL_OUTPUT_MAX_TOKENS = 128_000

# Conservative, explicit synchronous Messages API limits. Unknown/future
# model IDs use 8k so we never knowingly submit an invalid oversized request.
_MODEL_OUTPUT_LIMITS: tuple[tuple[str, int], ...] = (
    ("claude-sonnet-5", 128_000),
    ("claude-fable-5", 128_000),
    ("claude-mythos-5", 128_000),
    ("claude-opus-4-8", 128_000),
    ("claude-opus-4-7", 128_000),
    ("claude-opus-4-6", 128_000),
    ("claude-sonnet-4-6", 64_000),
    ("claude-sonnet-4-5", 64_000),
    ("claude-haiku-4-5", 64_000),
)
UNKNOWN_MODEL_OUTPUT_MAX_TOKENS = 8_192


def model_output_max_tokens(model_name: str) -> int:
    """Return a safe synchronous Messages API output ceiling for a model."""
    normalized = (model_name or "").strip().lower()
    for marker, limit in _MODEL_OUTPUT_LIMITS:
        if marker in normalized:
            return limit
    return UNKNOWN_MODEL_OUTPUT_MAX_TOKENS

# Backward-compatible alias used by truncation retries.
MAP_MAX_TOKENS_CAP = MODEL_OUTPUT_MAX_TOKENS

MODEL_ROUTING_OVERRIDES: dict[PipelineStage, dict] = {
    PipelineStage.BUILD_COURSE_MAP: {"max_tokens": MODEL_OUTPUT_MAX_TOKENS},
    PipelineStage.REBUILD_FINAL_COURSE: {"max_tokens": MODEL_OUTPUT_MAX_TOKENS},
    PipelineStage.WRITE_SINGLE_REEL: {"max_tokens": MODEL_OUTPUT_MAX_TOKENS},
    PipelineStage.REVIEW_SINGLE_REEL: {"max_tokens": MODEL_OUTPUT_MAX_TOKENS},
    PipelineStage.FINAL_REVIEW: {"max_tokens": MODEL_OUTPUT_MAX_TOKENS},
}


def resolve_stage_overrides(stage: PipelineStage) -> dict:
    """Whatever override dict is configured for `stage`, or `{}` if none.

    Never raises - an unrecognized/missing stage just means "use the
    provider's own defaults", never an error.
    """
    return dict(MODEL_ROUTING_OVERRIDES.get(stage, {}))
