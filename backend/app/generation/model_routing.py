"""Per-pipeline-stage AI provider routing overrides (§9).

Default behavior (and today's *only* behavior, since
`MODEL_ROUTING_OVERRIDES` starts empty): every stage uses whatever
`Settings.ai_model_name` and the course's own `generation_preset`-resolved
temperature already apply (see app/ai/anthropic_provider.py) - this module
changes nothing unless a stage is explicitly listed below.

To override a specific stage, add a `PipelineStage` key with any subset of
`{"model", "temperature", "max_tokens"}` to `MODEL_ROUTING_OVERRIDES`. Any
field left out of an override dict still falls back to the provider's own
already-configured value for that call. Kept as a plain Python constant
(no config-file loader) per this codebase's "explicit, readable code over
a framework" style - see `.cursor/rules/v1-architecture-constraints.mdc`.

`FakeProvider` never consults this - it has no concept of model/
temperature at all.
"""

from __future__ import annotations

from app.prompts.prompt_registry import PipelineStage

# Empty by default - no override is required for MVP. Example of what a
# future override would look like (commented out intentionally):
#
#   MODEL_ROUTING_OVERRIDES: dict[PipelineStage, dict] = {
#       PipelineStage.FINAL_REVIEW: {"temperature": 0.1},
#   }
MODEL_ROUTING_OVERRIDES: dict[PipelineStage, dict] = {}


def resolve_stage_overrides(stage: PipelineStage) -> dict:
    """Whatever override dict is configured for `stage`, or `{}` if none.

    Never raises - an unrecognized/missing stage just means "use the
    provider's own defaults", never an error.
    """
    return dict(MODEL_ROUTING_OVERRIDES.get(stage, {}))
