"""Tests for app/prompts/prompt_registry.py."""

from pathlib import Path

import pytest

from app.prompts.prompt_registry import (
    PROMPT_SPECS,
    PipelineStage,
    get_prompt_spec,
    load_prompt,
    prompt_path,
    stage_for_provider_method,
)


def test_every_stage_has_a_prompt_file_on_disk():
    for stage in PipelineStage:
        path = prompt_path(stage)
        assert path.is_file(), f"Missing prompt file for {stage.value}: {path}"


def test_registry_covers_all_provider_methods():
    expected_methods = {
        "build_course_map",
        "write_single_reel",
        "review_single_reel",
        "final_review",
        "rebuild_final_course",
    }
    registered = {spec.provider_method for spec in PROMPT_SPECS.values()}
    assert registered == expected_methods


def test_retired_no_effect_review_surfaces_are_gone():
    retired = {"review_five_reels", "review_module", "review_two_modules"}
    assert retired.isdisjoint(stage.value for stage in PipelineStage)
    assert retired.isdisjoint(spec.provider_method for spec in PROMPT_SPECS.values())
    for name in retired:
        assert not (Path(__file__).parents[1] / "app" / "prompts" / f"{name}.md").exists()


@pytest.mark.parametrize(
    ("method_name", "expected_stage"),
    [
        ("build_course_map", PipelineStage.BUILD_COURSE_MAP),
        ("write_single_reel", PipelineStage.WRITE_SINGLE_REEL),
        ("review_single_reel", PipelineStage.REVIEW_SINGLE_REEL),
        ("final_review", PipelineStage.FINAL_REVIEW),
        ("rebuild_final_course", PipelineStage.REBUILD_FINAL_COURSE),
    ],
)
def test_stage_for_provider_method(method_name, expected_stage):
    assert stage_for_provider_method(method_name) is expected_stage


def test_load_prompt_returns_markdown_content():
    text = load_prompt(PipelineStage.BUILD_COURSE_MAP)
    assert text.startswith("# Task: Build Course Map")


def test_get_prompt_spec_filename_matches_stage_value():
    spec = get_prompt_spec(PipelineStage.WRITE_SINGLE_REEL)
    assert spec.filename == "write_single_reel.md"
    assert spec.tool_name == "generated_reel"
    assert Path(spec.filename).stem == spec.stage.value
