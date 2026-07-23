"""Shared CourseMap repair helpers used before Pydantic validation.

Only harmless aliases/default omissions are fixed here. Invalid nested
objects that cannot be repaired are dropped to optional defaults so a
near-complete map can still save instead of failing the whole run.
"""

from __future__ import annotations

from typing import Any

from app.models.enums import LessonDeliveryMode


_DELIVERY_MODE_VALUES = {item.value for item in LessonDeliveryMode}

_SEMANTIC_REQUIRED = (
    "learner_before",
    "learner_after",
    "exact_capability_change",
    "strongest_non_obvious_meaning",
    "misconception_or_failure",
    "causal_explanation",
    "proof_example_or_demonstration",
    "learner_test_or_action",
    "boundary_or_exception",
    "real_tension",
    "complete_payoff",
    "earned_next_need",
    "escalation_role",
    "sequence_dependency",
)


def normalize_course_map_payload(data: object) -> object:
    """Repair common CourseMap shape mistakes before validation."""
    if not isinstance(data, dict):
        return data
    out = dict(data)
    modules = out.get("modules")
    if not isinstance(modules, list):
        return out

    fixed_modules: list[object] = []
    for module in modules:
        if not isinstance(module, dict):
            fixed_modules.append(module)
            continue
        mod = dict(module)
        if "reels" not in mod and isinstance(mod.get("lessons"), list):
            mod["reels"] = mod.pop("lessons")
        reels = mod.get("reels")
        if isinstance(reels, list):
            fixed_reels: list[object] = []
            for reel in reels:
                if not isinstance(reel, dict):
                    fixed_reels.append(reel)
                    continue
                item = dict(reel)
                if not str(item.get("estimated_length") or "").strip():
                    item["estimated_length"] = "3 minutes"
                for field in ("must_cover", "must_avoid", "source_hints"):
                    if item.get(field) is None:
                        item[field] = []
                for field in (
                    "required_assets",
                    "source_references",
                    "prerequisite_lesson_ids",
                    "already_taught_forbid_repeat",
                ):
                    if item.get(field) is None:
                        item[field] = []
                item["delivery_mode"] = _coerce_delivery_mode(item.get("delivery_mode"))
                item["lesson_semantic_contract"] = _coerce_semantic_contract(
                    item.get("lesson_semantic_contract")
                )
                fixed_reels.append(item)
            mod["reels"] = fixed_reels
        mod["module_project"] = _coerce_module_project(mod.get("module_project"))
        fixed_modules.append(mod)
    out["modules"] = fixed_modules
    return out


def _coerce_delivery_mode(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, LessonDeliveryMode):
        return value.value
    text = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    if text in _DELIVERY_MODE_VALUES:
        return text
    aliases = {
        "explainer": "camera_explainer",
        "camera": "camera_explainer",
        "demo": "screen_demo",
        "screen": "screen_demo",
        "critique_design": "design_critique",
        "before_and_after": "before_after",
        "fix": "error_fix",
        "case": "case_study",
        "project": "project_build",
        "micro": "micro_concept",
    }
    return aliases.get(text)


def _coerce_semantic_contract(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        return None
    contract = dict(value)
    for key in _SEMANTIC_REQUIRED:
        raw = contract.get(key)
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            # Partial contracts fail hard validation; drop so the lesson can save.
            return None
        contract[key] = str(raw).strip()
    return contract


def _coerce_module_project(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        return None
    project = dict(value)
    name = str(project.get("name") or "").strip()
    brief = str(project.get("brief") or "").strip()
    if not name and not brief:
        return None
    if not name:
        project["name"] = "مشروع الموديول"
    if not brief:
        project["brief"] = name or project["name"]
    for field in ("inputs_or_files", "pass_criteria", "skills_tested"):
        if project.get(field) is None:
            project[field] = []
    if project.get("deliverable_shape") is None:
        project["deliverable_shape"] = ""
    if project.get("closure") is None:
        project["closure"] = ""
    return project
