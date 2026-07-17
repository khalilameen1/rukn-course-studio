"""Regression: AI/legacy clients often send enum NAMES or renamed aliases."""

from datetime import datetime, timezone

from app.models.enums import (
    GenerationQualityMode,
    JobStatus,
    Priority,
    SourceCategory,
    StructureMode,
)
from app.schemas.course import CourseCreate, CourseRead
from app.schemas.course_source import CourseSourceNotesCreate, CourseSourceRead
from app.schemas.generation_job import GenerateCourseRequest, GenerationJobRead
from app.services.enum_coerce import coerce_source_category, coerce_str_enum


def test_coerce_source_category_legacy_aliases():
    assert coerce_source_category("NOTES") is SourceCategory.USER_NOTES
    assert coerce_source_category("main_content") is SourceCategory.SCIENTIFIC_REFERENCE
    assert coerce_source_category("SPOKEN_STYLE") is SourceCategory.FLOW_REFERENCE
    assert coerce_source_category("user_notes") is SourceCategory.USER_NOTES


def test_coerce_job_status_name_and_value():
    assert coerce_str_enum(JobStatus, "RUNNING") is JobStatus.RUNNING
    assert coerce_str_enum(JobStatus, "running") is JobStatus.RUNNING
    assert coerce_str_enum(JobStatus, "Failed") is JobStatus.FAILED


def test_notes_create_accepts_legacy_category_name():
    body = CourseSourceNotesCreate(text="hello", source_category="NOTES")
    assert body.source_category is SourceCategory.USER_NOTES


def test_course_create_accepts_enum_member_names():
    body = CourseCreate(
        title="t",
        audience="a",
        outcome="o",
        structure_mode="CONNECTED_NO_MODULES",
        generation_quality_mode="PREMIUM",
    )
    assert body.structure_mode is StructureMode.CONNECTED_NO_MODULES
    assert body.generation_quality_mode is GenerationQualityMode.PREMIUM


def test_generate_request_accepts_names():
    body = GenerateCourseRequest(
        generation_quality_mode="PREVIEW",
        web_research_mode="AUTONOMOUS_GAP_FILL",
    )
    assert body.generation_quality_mode is GenerationQualityMode.PREVIEW


def test_course_source_read_null_include_defaults_true():
    now = datetime.now(timezone.utc)
    read = CourseSourceRead.model_validate(
        {
            "id": 1,
            "course_id": 1,
            "source_category": "NOTES",
            "original_filename": "a.txt",
            "file_path": None,
            "mime_type": None,
            "extracted_text": "x",
            "priority": "MEDIUM",
            "status": "ready",
            "include_in_generation": None,
            "created_at": now,
        }
    )
    assert read.source_category is SourceCategory.USER_NOTES
    assert read.priority is Priority.MEDIUM
    assert read.include_in_generation is True


def test_course_read_accepts_legacy_enum_names():
    now = datetime.now(timezone.utc)
    read = CourseRead.model_validate(
        {
            "id": 1,
            "title": "t",
            "audience": "a",
            "outcome": "o",
            "special_notes": None,
            "course_type": "practical_skill",
            "structure_mode": "CONNECTED_NO_MODULES",
            "manual_map_text": None,
            "explanation_level": "FINAL_ONLY",
            "generation_preset": "BALANCED",
            "generation_quality_mode": "PREMIUM",
            "web_research_mode": "AUTONOMOUS_GAP_FILL",
            "target_market": "EGYPT",
            "status": "draft",
            "created_at": now,
            "updated_at": now,
        }
    )
    assert read.structure_mode is StructureMode.CONNECTED_NO_MODULES
    assert read.generation_quality_mode is GenerationQualityMode.PREMIUM


def test_generation_job_read_still_coerces_string_json_and_enums():
    now = datetime.now(timezone.utc)
    read = GenerationJobRead.model_validate(
        {
            "id": 1,
            "course_id": 1,
            "status": "RUNNING",
            "cancel_requested": None,
            "current_stage": "map",
            "progress_percent": None,
            "output_docx_path": None,
            "error_message": None,
            "last_completed_step": None,
            "error_category": None,
            "partial_docx_path": None,
            "generation_quality_mode": "PREMIUM",
            "web_research_mode": "AUTONOMOUS_GAP_FILL",
            "waste_warnings_json": "[]",
            "created_at": now,
            "updated_at": now,
        }
    )
    assert read.status is JobStatus.RUNNING
    assert read.cancel_requested is False
    assert read.progress_percent == 0
    assert read.waste_warnings_json == []
