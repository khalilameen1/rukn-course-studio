"""Central registry: which prompt file each pipeline stage uses.

Every AI provider stage should resolve its template through this module
instead of hardcoding `.md` filenames in provider code. Prompt bodies stay
in sibling `*.md` files; this file owns the stage → file mapping only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent


class PipelineStage(str, Enum):
    """One entry per `AIProvider` method / orchestrator AI call."""

    BUILD_COURSE_MAP = "build_course_map"
    WRITE_SINGLE_REEL = "write_single_reel"
    REVIEW_SINGLE_REEL = "review_single_reel"
    FINAL_REVIEW = "final_review"
    REBUILD_FINAL_COURSE = "rebuild_final_course"


@dataclass(frozen=True)
class PromptSpec:
    """Metadata for one pipeline prompt template."""

    stage: PipelineStage
    filename: str
    tool_name: str
    provider_method: str


# Single source of truth: stage → prompt file + structured-output tool name.
PROMPT_SPECS: dict[PipelineStage, PromptSpec] = {
    PipelineStage.BUILD_COURSE_MAP: PromptSpec(
        stage=PipelineStage.BUILD_COURSE_MAP,
        filename="build_course_map.md",
        tool_name="course_map",
        provider_method="build_course_map",
    ),
    PipelineStage.WRITE_SINGLE_REEL: PromptSpec(
        stage=PipelineStage.WRITE_SINGLE_REEL,
        filename="write_single_reel.md",
        tool_name="generated_reel",
        provider_method="write_single_reel",
    ),
    PipelineStage.REVIEW_SINGLE_REEL: PromptSpec(
        stage=PipelineStage.REVIEW_SINGLE_REEL,
        filename="review_single_reel.md",
        tool_name="review_result",
        provider_method="review_single_reel",
    ),
    PipelineStage.FINAL_REVIEW: PromptSpec(
        stage=PipelineStage.FINAL_REVIEW,
        filename="final_review.md",
        tool_name="review_result",
        provider_method="final_review",
    ),
    PipelineStage.REBUILD_FINAL_COURSE: PromptSpec(
        stage=PipelineStage.REBUILD_FINAL_COURSE,
        filename="rebuild_final_course.md",
        tool_name="final_course",
        provider_method="rebuild_final_course",
    ),
}

_PROVIDER_METHOD_TO_STAGE: dict[str, PipelineStage] = {
    spec.provider_method: stage for stage, spec in PROMPT_SPECS.items()
}


def get_prompt_spec(stage: PipelineStage) -> PromptSpec:
    try:
        return PROMPT_SPECS[stage]
    except KeyError as exc:
        raise KeyError(f"No prompt registered for stage {stage!r}") from exc


def stage_for_provider_method(method_name: str) -> PipelineStage:
    try:
        return _PROVIDER_METHOD_TO_STAGE[method_name]
    except KeyError as exc:
        raise KeyError(f"No pipeline stage registered for provider method {method_name!r}") from exc


def prompt_path(stage: PipelineStage) -> Path:
    return PROMPTS_DIR / get_prompt_spec(stage).filename


def load_prompt(stage: PipelineStage) -> str:
    path = prompt_path(stage)
    if not path.is_file():
        raise FileNotFoundError(f"Prompt file missing for {stage.value}: {path}")
    return path.read_text(encoding="utf-8")
