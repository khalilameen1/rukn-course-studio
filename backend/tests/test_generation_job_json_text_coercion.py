"""GenerationJobRead must accept JSON columns returned as TEXT strings."""

from datetime import datetime, timezone

from app.models.enums import GenerationQualityMode, JobStatus
from app.schemas.generation_job import GenerationJobRead


def _base(**extra):
    now = datetime.now(timezone.utc)
    data = {
        "id": 1,
        "course_id": 1,
        "status": "running",
        "cancel_requested": False,
        "current_stage": "generating",
        "progress_percent": 10,
        "output_docx_path": None,
        "error_message": None,
        "last_completed_step": None,
        "error_category": None,
        "partial_docx_path": None,
        "generation_quality_mode": "premium",
        "web_research_mode": "autonomous_gap_fill",
        "created_at": now,
        "updated_at": now,
    }
    data.update(extra)
    return data


def test_waste_warnings_json_string_array_coerces():
    read = GenerationJobRead.model_validate(_base(waste_warnings_json="[]"))
    assert read.waste_warnings_json == []
    read2 = GenerationJobRead.model_validate(_base(waste_warnings_json='["dup"]'))
    assert read2.waste_warnings_json == ["dup"]


def test_optional_json_object_strings_coerce():
    read = GenerationJobRead.model_validate(
        _base(
            usage_by_stage_json='{"map": 1}',
            run_snapshot_json="{}",
            output_score_json='{"score": 1}',
        )
    )
    assert read.usage_by_stage_json == {"map": 1}
    assert read.run_snapshot_json == {}
    assert read.output_score_json == {"score": 1}


def test_legacy_enum_names_still_ok():
    read = GenerationJobRead.model_validate(
        _base(status="RUNNING", generation_quality_mode="PREMIUM")
    )
    assert read.status == JobStatus.RUNNING
    assert read.generation_quality_mode == GenerationQualityMode.PREMIUM
