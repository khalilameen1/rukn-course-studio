"""Flatten Pydantic JSON Schema into an Anthropic-safe tool input_schema.

Anthropic tool schemas are a JSON Schema subset. Raw Pydantic v2 output often
includes ``$defs`` + ``$ref`` and ``anyOf`` nullables that some models reject
with ``invalid_request_error`` — which we surface as Unusable response.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def anthropic_tool_input_schema(schema: type) -> dict[str, Any]:
    """Build a dereferenced, Anthropic-friendly object schema."""
    raw = schema.model_json_schema()
    return _prepare_for_anthropic(raw)


def _prepare_for_anthropic(raw: dict[str, Any]) -> dict[str, Any]:
    defs = raw.get("$defs") or raw.get("definitions") or {}
    root = {k: v for k, v in raw.items() if k not in {"$defs", "definitions"}}
    resolved = _resolve_refs(root, defs)
    cleaned = _simplify_nullables(resolved)
    cleaned = _strip_heavy_metadata(cleaned)
    # Anthropic tools expect a top-level object schema.
    if cleaned.get("type") != "object":
        cleaned = {
            "type": "object",
            "properties": cleaned.get("properties") or {},
            "required": cleaned.get("required") or [],
        }
    cleaned.pop("title", None)
    cleaned.pop("description", None)
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
        # Merge sibling keys (e.g. description) over the def.
        merged = {**resolved, **{k: v for k, v in node.items() if k != "$ref"}}
        return _resolve_refs(merged, defs, stack)
    return {k: _resolve_refs(v, defs, stack) for k, v in node.items()}


def _simplify_nullables(node: Any) -> Any:
    """Convert anyOf[{type:T},{type:null}] → type:[T,\"null\"] (or just T)."""
    if isinstance(node, list):
        return [_simplify_nullables(item) for item in node]
    if not isinstance(node, dict):
        return node
    out = {k: _simplify_nullables(v) for k, v in node.items()}
    any_of = out.get("anyOf")
    if isinstance(any_of, list) and len(any_of) == 2:
        types = []
        for branch in any_of:
            if isinstance(branch, dict) and branch.get("type") == "null":
                types.append("null")
            elif isinstance(branch, dict) and "type" in branch and len(branch) == 1:
                types.append(branch["type"])
            elif isinstance(branch, dict) and branch.get("type"):
                # Keep richer branch as primary non-null type.
                primary = {k: v for k, v in branch.items()}
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


def _strip_heavy_metadata(node: Any) -> Any:
    if isinstance(node, list):
        return [_strip_heavy_metadata(item) for item in node]
    if not isinstance(node, dict):
        return node
    skip = {"title", "description", "examples", "default"}
    return {
        k: _strip_heavy_metadata(v)
        for k, v in node.items()
        if k not in skip
    }
