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
