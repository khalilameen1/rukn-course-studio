"""Per-pipeline-stage AI provider routing overrides (§9).

Default behavior: every stage uses Settings.ai_model_name and the course
preset temperature unless listed below. Map/rebuild get higher max_tokens
so large CourseMap JSON is less likely to truncate mid-tool-call.
"""

from __future__ import annotations

from app.prompts.prompt_registry import PipelineStage

MODEL_ROUTING_OVERRIDES: dict[PipelineStage, dict] = {
    PipelineStage.BUILD_COURSE_MAP: {"max_tokens": 8192},
    PipelineStage.REBUILD_FINAL_COURSE: {"max_tokens": 8192},
    PipelineStage.WRITE_SINGLE_REEL: {"max_tokens": 6144},
    PipelineStage.FINAL_REVIEW: {"max_tokens": 4096},
}


def resolve_stage_overrides(stage: PipelineStage) -> dict:
    """Whatever override dict is configured for `stage`, or `{}` if none.

    Never raises - an unrecognized/missing stage just means "use the
    provider's own defaults", never an error.
    """
    return dict(MODEL_ROUTING_OVERRIDES.get(stage, {}))
