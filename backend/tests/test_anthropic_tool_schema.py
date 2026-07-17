"""Anthropic tool JSON Schema must be flattened (no $ref/$defs)."""

from app.ai.anthropic_tool_schema import anthropic_tool_input_schema
from app.schemas.generation import CourseMap, GeneratedReel, ReviewResult


def test_course_map_tool_schema_has_no_defs_or_refs():
    schema = anthropic_tool_input_schema(CourseMap)
    blob = str(schema)
    assert "$ref" not in blob
    assert "$defs" not in blob
    assert schema.get("type") == "object"
    assert "modules" in schema.get("properties", {})
    # Nested reel plan inlined
    modules = schema["properties"]["modules"]
    assert modules["type"] == "array"
    reel_props = modules["items"]["properties"]["reels"]["items"]["properties"]
    assert "reel_id" in reel_props
    assert "estimated_length" in reel_props


def test_generated_reel_enum_inlined():
    schema = anthropic_tool_input_schema(GeneratedReel)
    status = schema["properties"]["self_check_status"]
    assert "$ref" not in status
    assert status.get("enum") == ["pass", "needs_revision"] or "enum" in str(status)


def test_review_result_flattened():
    schema = anthropic_tool_input_schema(ReviewResult)
    assert "$defs" not in schema
    assert "$ref" not in str(schema)
