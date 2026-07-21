from pathlib import Path

from app.data.course_standard import STANDARD_FILE_NAMES, STANDARD_VERSION, load_standard_files
from app.generation.model_routing import resolve_stage_overrides
from app.prompts.prompt_registry import PipelineStage


def test_v17_standard_is_exact_and_old_project_filename_is_gone():
    assert STANDARD_VERSION.startswith("1.7")
    assert "04-inter-module-projects-and-practice.md" in STANDARD_FILE_NAMES
    assert "04-projects-practice-and-assessment.md" not in STANDARD_FILE_NAMES
    files = load_standard_files()
    assert len(files) == 14
    assert "RUKN" in files["README.md"]


def test_quality_first_openai_routing():
    for stage in PipelineStage:
        route = resolve_stage_overrides(stage)
        assert route["reasoning_mode"] == "pro"
        assert route["reasoning_effort"] in {"xhigh", "max"}
    assert resolve_stage_overrides(PipelineStage.BUILD_COURSE_MAP)["reasoning_effort"] == "max"
    assert resolve_stage_overrides(PipelineStage.FINAL_REVIEW)["reasoning_effort"] == "max"


def test_prompts_do_not_reintroduce_old_caps_or_final_project():
    prompt_dir = Path(__file__).resolve().parents[1] / "app" / "prompts"
    map_prompt = (prompt_dir / "build_course_map.md").read_text(encoding="utf-8")
    rebuild = (prompt_dir / "rebuild_final_course.md").read_text(encoding="utf-8")
    assert "hard max 60" not in map_prompt.lower()
    assert "graduation_project=null" in map_prompt
    assert "graduation_project" in rebuild and "must be null" in rebuild
