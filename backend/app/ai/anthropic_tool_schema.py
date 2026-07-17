"""Flatten Pydantic JSON Schema into an Anthropic-safe tool input_schema.

Anthropic tool schemas are a JSON Schema subset. Raw Pydantic v2 output often
includes ``$defs`` + ``$ref`` and ``anyOf`` nullables that some models reject
with ``invalid_request_error`` — which we surface as Unusable response.

Also: never strip property names like ``title`` (field on ReelPlan) when
cleaning schema annotations.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_SCHEMA_META_KEYS = frozenset({"description", "examples", "default"})


def anthropic_tool_input_schema(schema: type) -> dict[str, Any]:
    """Build a dereferenced, Anthropic-friendly object schema."""
    raw = schema.model_json_schema()
    cleaned = _prepare_for_anthropic(raw)
    # Pydantic keeps ModulePlan.reels open (empty lists in unit tests), but
    # Anthropic must advertise minItems so title-only maps are rejected by
    # the tool schema instead of surviving as empty lesson lists.
    if getattr(schema, "__name__", None) == "CourseMap":
        cleaned = _enforce_course_map_lesson_floor(cleaned)
    return cleaned


def _enforce_course_map_lesson_floor(schema: dict[str, Any]) -> dict[str, Any]:
    """Ensure each module's ``reels`` array requires at least one lesson."""
    try:
        modules = schema["properties"]["modules"]
        reels = modules["items"]["properties"]["reels"]
        if isinstance(reels, dict):
            reels = dict(reels)
            reels["minItems"] = max(int(reels.get("minItems") or 0), 1)
            modules["items"]["properties"]["reels"] = reels
    except (KeyError, TypeError, ValueError):
        return schema
    return schema


def _prepare_for_anthropic(raw: dict[str, Any]) -> dict[str, Any]:
    defs = raw.get("$defs") or raw.get("definitions") or {}
    root = {k: v for k, v in raw.items() if k not in {"$defs", "definitions"}}
    resolved = _resolve_refs(root, defs)
    cleaned = _simplify_nullables(resolved)
    cleaned = _strip_schema_annotations(cleaned)
    # Anthropic tools expect a top-level object schema.
    if cleaned.get("type") != "object":
        cleaned = {
            "type": "object",
            "properties": cleaned.get("properties") or {},
            "required": cleaned.get("required") or [],
        }
    return cleaned


def _resolve_refs(node: Any, defs: dict[str, Any], stack: set[str] | None = None) -> Any:
    stack = stack or set()
    if isinstance(node, list):
        return [_resolve_refs(item, defs, stack) for item in node]
    if not isinstance(node, dict):
        return node
    if "$ref" in node:
        ref = str(node["$ref"])
        name = ref.rsplit("/", 1)[-1]
        if name in stack:
            return {"type": "object"}
        if name not in defs:
            return {"type": "object"}
        stack.add(name)
        resolved = _resolve_refs(deepcopy(defs[name]), defs, stack)
        stack.discard(name)
        merged = {**resolved, **{k: v for k, v in node.items() if k != "$ref"}}
        return _resolve_refs(merged, defs, stack)
    return {k: _resolve_refs(v, defs, stack) for k, v in node.items()}


def _simplify_nullables(node: Any) -> Any:
    """Convert anyOf[{type:T},{type:null}] → type:[T,\"null\"]."""
    if isinstance(node, list):
        return [_simplify_nullables(item) for item in node]
    if not isinstance(node, dict):
        return node
    out = {k: _simplify_nullables(v) for k, v in node.items()}
    any_of = out.get("anyOf")
    if isinstance(any_of, list) and len(any_of) == 2:
        types: list[Any] = []
        for branch in any_of:
            if isinstance(branch, dict) and branch.get("type") == "null":
                types.append("null")
            elif isinstance(branch, dict) and branch.get("type"):
                primary = dict(branch)
                types.append(primary.get("type"))
                for k, v in primary.items():
                    if k != "type" and k not in out:
                        out[k] = v
            else:
                types = []
                break
        if types and "null" in types:
            non_null = [t for t in types if t != "null" and isinstance(t, str)]
            if len(non_null) == 1:
                out.pop("anyOf", None)
                out["type"] = [non_null[0], "null"]
    return out


def _strip_schema_annotations(node: Any, *, in_properties_map: bool = False) -> Any:
    """Drop JSON-Schema fluff without deleting field names like ``title``."""
    if isinstance(node, list):
        return [_strip_schema_annotations(item, in_properties_map=False) for item in node]
    if not isinstance(node, dict):
        return node

    if in_properties_map:
        # Keys here are model field names (may be "title") — keep them all.
        return {
            k: _strip_schema_annotations(v, in_properties_map=False)
            for k, v in node.items()
        }

    out: dict[str, Any] = {}
    for k, v in node.items():
        if k in _SCHEMA_META_KEYS:
            continue
        # Schema-object annotation "title": "ReelPlan" — drop.
        if k == "title":
            continue
        if k == "properties":
            out[k] = _strip_schema_annotations(v, in_properties_map=True)
        else:
            out[k] = _strip_schema_annotations(v, in_properties_map=False)
    return out
