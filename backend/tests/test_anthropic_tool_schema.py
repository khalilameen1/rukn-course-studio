"""Anthropic tool JSON Schema must be flattened (no $ref/$defs)."""

from app.ai.anthropic_tool_schema import anthropic_tool_input_schema
from app.schemas.generation import CourseMap, GeneratedReel, ReviewResult


def test_course_map_tool_schema_keeps_title_fields():
    schema = anthropic_tool_input_schema(CourseMap)
    blob = str(schema)
    assert "$ref" not in blob
    assert "$defs" not in blob
    modules = schema["properties"]["modules"]
    module_props = modules["items"]["properties"]
    assert "title" in module_props
    reel_props = module_props["reels"]["items"]["properties"]
    assert "title" in reel_props
    assert "reel_id" in reel_props


def test_generated_reel_enum_inlined():
    schema = anthropic_tool_input_schema(GeneratedReel)
    status = schema["properties"]["self_check_status"]
    assert "$ref" not in status
    assert status.get("enum") == ["pass", "needs_revision"] or "enum" in str(status)


def test_review_result_flattened():
    schema = anthropic_tool_input_schema(ReviewResult)
    assert "$defs" not in schema
    assert "$ref" not in str(schema)
