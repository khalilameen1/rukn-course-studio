"""Immutable, unified generation-context snapshot (RUKN standard v1.3).

The snapshot is frozen once, after the approved course map exists and before
lesson writing begins.  Later stages may maintain their own working ledgers,
but they must never rewrite this record.  Resume/finalize/export boundaries
validate both the snapshot's internal fingerprint and any supplied current
configuration.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.data.course_standard import STANDARD_VERSION, standard_manifest
from app.generation.prompt_compiler import PROMPT_COMPILER_VERSION
from app.generation.presets import GenerationPreset, resolve_generation_settings
from app.generation.quality.contract import CourseQualityContract
from app.prompts.prompt_registry import PROMPT_SPECS, load_prompt
from app.schemas.generation import CourseMap, CourseThesis
from app.version import get_app_commit

SNAPSHOT_VERSION = "2.0"
REQUIRED_STATE_KEYS: tuple[str, ...] = (
    "COURSE_THESIS",
    "AUDIENCE_MODEL",
    "INSTRUCTOR_PROFILE",
    "CAPABILITY_GRAPH",
    "COVERAGE_MATRIX",
    "BENCHMARK_MATRIX",
    "MARKET_PACK",
    "SOURCE_LEDGER",
    "TERM_LEDGER",
    "CLAIM_LEDGER",
    "LESSON_LEDGER",
    "PHRASE_LEDGER",
    "PROJECT_LEDGER",
    "DEMONSTRATION_LEDGER",
    "ASSET_LEDGER",
    "QUALITY_FINDINGS",
    "CONFIG_FINGERPRINT",
    "ACTIVE_RULE_PACK",
    "STAGE_CONTRACT_STATE",
    "PEDAGOGY_ADAPTER",
    "EPISODIC_PROGRESSION_MAP",
    "LANGUAGE_REWRITE_RECORD",
)


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "value"):
        return value.value
    return value


def canonical_json(data: Any) -> str:
    return json.dumps(
        _jsonable(data),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )


def fingerprint_value(data: Any) -> str:
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def fingerprint_dict(data: dict) -> str:
    """Backward-compatible name; now returns a full SHA-256 digest."""
    return fingerprint_value(data)


def active_prompt_versions() -> dict[str, str]:
    """Content hashes for every registered prompt that can affect output."""
    return {
        stage.value: hashlib.sha256(load_prompt(stage).encode("utf-8")).hexdigest()
        for stage in PROMPT_SPECS
    }


def build_active_rule_pack(admin_rules: dict[str, str] | None = None) -> dict[str, Any]:
    """Return compact, content-addressed rule metadata without raw Markdown."""
    if admin_rules is None:
        return standard_manifest()
    hashes = [
        {
            "order": index,
            "key": key,
            "content_sha256": hashlib.sha256((text or "").encode("utf-8")).hexdigest(),
        }
        for index, (key, text) in enumerate(admin_rules.items(), start=1)
    ]
    canonical = standard_manifest()
    if [item["key"] for item in hashes] == [item["key"] for item in canonical["files"]]:
        if all(
            item["content_sha256"] == expected["content_sha256"]
            for item, expected in zip(hashes, canonical["files"], strict=True)
        ):
            return canonical
    return {
        "standard_version": STANDARD_VERSION,
        "fingerprint": fingerprint_value(hashes),
        "file_count": len(hashes),
        "files": hashes,
    }


def source_ledger_from_fingerprints(
    source_ids: list[int] | None,
    source_fingerprints: dict[str, str] | None,
    source_metadata: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    ids = list(source_ids or [])
    fingerprints = dict(source_fingerprints or {})
    metadata = dict(source_metadata or {})
    rows: list[dict[str, Any]] = []
    for source_id in ids:
        row = {
            "source_id": source_id,
            "content_sha256": fingerprints.get(str(source_id), ""),
        }
        row.update(_jsonable(metadata.get(str(source_id)) or {}))
        rows.append(row)
    return rows


def build_config_inputs(
    *,
    active_rule_pack: dict[str, Any],
    brief: dict[str, Any],
    thesis: dict[str, Any],
    source_ledger: list[dict[str, Any]],
    research_result: Any,
    market: str,
    course_type: str,
    language_profile: dict[str, Any],
    address_form: str,
    quality_mode: str,
    provider_name: str,
    model_name: str,
    generation_settings: dict[str, Any],
    approved_map: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build only the compact identity inputs used by CONFIG_FINGERPRINT."""
    return {
        "STANDARD_PACKAGE": _jsonable(active_rule_pack),
        "BRIEF": _jsonable(brief),
        "COURSE_THESIS": _jsonable(thesis),
        "SELECTED_SOURCES": _jsonable(source_ledger),
        "RESEARCH_RESULT_SHA256": fingerprint_value(research_result),
        "MARKET": market,
        "COURSE_TYPE": course_type,
        "LANGUAGE_PROFILE": _jsonable(language_profile),
        "ADDRESS_FORM": address_form,
        "QUALITY_MODE": quality_mode,
        "PROVIDER": provider_name,
        "MODEL": model_name,
        "GENERATION_SETTINGS": _jsonable(generation_settings),
        "APPROVED_MAP": _jsonable(approved_map),
    }


class SnapshotMismatchError(RuntimeError):
    """Raised when a frozen run identity is missing, altered, or stale."""


class GenerationContextSnapshot(BaseModel):
    version: str = SNAPSHOT_VERSION
    created_at: str = ""
    course_id: int | None = None

    COURSE_THESIS: dict[str, Any] = Field(default_factory=dict)
    AUDIENCE_MODEL: dict[str, Any] = Field(default_factory=dict)
    INSTRUCTOR_PROFILE: dict[str, Any] = Field(default_factory=dict)
    CAPABILITY_GRAPH: dict[str, Any] = Field(default_factory=dict)
    COVERAGE_MATRIX: dict[str, Any] = Field(default_factory=dict)
    BENCHMARK_MATRIX: dict[str, Any] = Field(default_factory=dict)
    MARKET_PACK: dict[str, Any] = Field(default_factory=dict)
    SOURCE_LEDGER: list[dict[str, Any]] = Field(default_factory=list)
    TERM_LEDGER: dict[str, Any] = Field(default_factory=dict)
    CLAIM_LEDGER: dict[str, Any] = Field(default_factory=dict)
    LESSON_LEDGER: list[dict[str, Any]] = Field(default_factory=list)
    PHRASE_LEDGER: dict[str, Any] = Field(default_factory=dict)
    PROJECT_LEDGER: list[dict[str, Any]] = Field(default_factory=list)
    DEMONSTRATION_LEDGER: list[dict[str, Any]] = Field(default_factory=list)
    ASSET_LEDGER: list[dict[str, Any]] = Field(default_factory=list)
    QUALITY_FINDINGS: list[dict[str, Any]] = Field(default_factory=list)
    CONFIG_FINGERPRINT: str = ""
    ACTIVE_RULE_PACK: dict[str, Any] = Field(default_factory=dict)
    STAGE_CONTRACT_STATE: dict[str, Any] = Field(default_factory=dict)
    PEDAGOGY_ADAPTER: dict[str, Any] = Field(default_factory=dict)
    EPISODIC_PROGRESSION_MAP: dict[str, Any] = Field(default_factory=dict)
    LANGUAGE_REWRITE_RECORD: list[dict[str, Any]] = Field(default_factory=list)

    # Stored so a boundary can recompute the fingerprint without rebuilding
    # the pedagogical snapshot from mutable in-memory pipeline objects.
    CONFIG_INPUTS: dict[str, Any] = Field(default_factory=dict)

    invalidated: bool = False
    invalidation_reasons: list[str] = Field(default_factory=list)

    @property
    def fingerprint(self) -> str:
        return self.CONFIG_FINGERPRINT

    # Compatibility accessors for callers migrating from v1. They all read
    # from the same v2 snapshot and do not create a parallel identity.
    @property
    def brief(self) -> dict[str, Any]:
        return dict(self.CONFIG_INPUTS.get("BRIEF") or {})

    @property
    def thesis(self) -> dict[str, Any]:
        return self.COURSE_THESIS

    @property
    def approved_course_map(self) -> dict[str, Any] | None:
        return self.CONFIG_INPUTS.get("APPROVED_MAP")

    @property
    def source_ids(self) -> list[int]:
        return [int(row["source_id"]) for row in self.SOURCE_LEDGER if "source_id" in row]

    @property
    def quality_mode(self) -> str:
        return str(self.CONFIG_INPUTS.get("QUALITY_MODE") or "")

    @property
    def model_name(self) -> str:
        return str(self.CONFIG_INPUTS.get("MODEL") or "")

    def recompute_fingerprint(self) -> str:
        self.CONFIG_FINGERPRINT = fingerprint_value(self.CONFIG_INPUTS)
        return self.CONFIG_FINGERPRINT


def _map_ledgers(course_map: CourseMap | None) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    if course_map is None:
        return [], [], [], []
    lessons: list[dict[str, Any]] = []
    projects: list[dict[str, Any]] = []
    demonstrations: list[dict[str, Any]] = []
    assets: list[dict[str, Any]] = []
    for module in course_map.modules:
        if module.module_project:
            projects.append(
                {"module_id": module.module_id, **module.module_project.model_dump(mode="json")}
            )
        elif module.bridge_project:
            projects.append({"module_id": module.module_id, "brief": module.bridge_project})
        for reel in module.reels:
            lessons.append(
                {
                    "reel_id": reel.reel_id,
                    "module_id": module.module_id,
                    "outcome": reel.distinct_teaching_outcome or reel.purpose,
                    "prerequisites": list(reel.prerequisite_lesson_ids),
                }
            )
            if reel.needs_screen_or_visual:
                demonstrations.append(
                    {"reel_id": reel.reel_id, "plan": reel.internal_visual_plan}
                )
            for asset in reel.required_assets:
                assets.append({"reel_id": reel.reel_id, "asset": asset})
    if course_map.graduation_project:
        projects.append(
            {"module_id": "graduation", **course_map.graduation_project.model_dump(mode="json")}
        )
    return lessons, projects, demonstrations, assets


def _capability_graph(course_map: CourseMap | None) -> dict[str, Any]:
    if course_map is None:
        return {"nodes": [], "edges": []}
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    for module in course_map.modules:
        for reel in module.reels:
            nodes.append(
                {
                    "id": reel.reel_id,
                    "module_id": module.module_id,
                    "capability": reel.new_skill_or_decision
                    or reel.distinct_teaching_outcome
                    or reel.purpose,
                }
            )
            edges.extend(
                {"from": prerequisite, "to": reel.reel_id}
                for prerequisite in reel.prerequisite_lesson_ids
            )
    return {"nodes": nodes, "edges": edges}


def build_generation_context_snapshot(
    *,
    course_id: int | None,
    brief: Any,
    contract: CourseQualityContract,
    thesis: CourseThesis | None,
    course_map: CourseMap | None = None,
    source_ids: list[int] | None = None,
    source_fingerprints: dict[str, str] | None = None,
    source_metadata: dict[str, dict[str, Any]] | None = None,
    research_blob: Any = "",
    admin_rules: dict[str, str] | None = None,
    prompt_versions: dict[str, str] | None = None,
    provider_name: str = "fake",
    model_name: str = "fake",
    quality_mode: str = "premium",
    web_research_mode: str = "disabled",
    map_preview_confirmed: bool = False,
    human_override_hard_limits: bool = False,
    instructor_profile: dict[str, Any] | None = None,
    coverage_matrix: dict[str, Any] | None = None,
    benchmark_matrix: dict[str, Any] | None = None,
    term_ledger: dict[str, Any] | None = None,
    claim_ledger: dict[str, Any] | None = None,
    phrase_ledger: dict[str, Any] | None = None,
    quality_findings: list[dict[str, Any]] | None = None,
    generation_settings: dict[str, Any] | None = None,
) -> GenerationContextSnapshot:
    brief_data = _jsonable(brief or {})
    thesis_data = _jsonable(thesis or {})
    map_data = _jsonable(course_map) if course_map else None
    active_rule_pack = build_active_rule_pack(admin_rules)
    source_ledger = source_ledger_from_fingerprints(
        source_ids,
        source_fingerprints,
        source_metadata,
    )
    settings_payload = {
        "prompt_compiler_version": PROMPT_COMPILER_VERSION,
        "prompt_versions": dict(prompt_versions or active_prompt_versions()),
        "app_commit": get_app_commit(),
        "web_research_mode": web_research_mode,
        "map_preview_confirmed": map_preview_confirmed,
        "human_override_hard_limits": human_override_hard_limits,
        **dict(generation_settings or {}),
    }
    preset_value = settings_payload.get("generation_preset")
    if preset_value:
        try:
            settings_payload["resolved_generation_settings"] = resolve_generation_settings(
                GenerationPreset(str(preset_value))
            )
        except ValueError:
            settings_payload["resolved_generation_settings"] = {
                "preset": str(preset_value),
                "invalid": True,
            }
    address_form = contract.language.address_form.value
    config_inputs = build_config_inputs(
        active_rule_pack=active_rule_pack,
        brief=brief_data,
        thesis=thesis_data,
        source_ledger=source_ledger,
        research_result=research_blob,
        market=str(brief_data.get("target_market") or ""),
        course_type=str(contract.pedagogy.course_type or ""),
        language_profile=contract.language.model_dump(mode="json"),
        address_form=address_form,
        quality_mode=quality_mode,
        provider_name=provider_name,
        model_name=model_name,
        generation_settings=settings_payload,
        approved_map=map_data,
    )
    lessons, projects, demonstrations, assets = _map_ledgers(course_map)
    coverage = dict(coverage_matrix or {})
    findings = list(quality_findings or [])
    if not findings:
        findings = [
            dict(issue) if isinstance(issue, dict) else _jsonable(issue)
            for issue in coverage.get("issues", [])
        ]
    stage_state = {
        "snapshot": "frozen",
        "thesis": "complete" if thesis else "pending",
        "approved_map": "complete" if course_map else "pending",
        "lesson_writing": "pending",
        "quality_review": "pending",
        "export": "blocked_until_fingerprint_match",
    }
    sequence = [row["reel_id"] for row in lessons]
    snap = GenerationContextSnapshot(
        created_at=datetime.now(timezone.utc).isoformat(),
        course_id=course_id,
        COURSE_THESIS=thesis_data,
        AUDIENCE_MODEL={
            "audience": brief_data.get("audience", ""),
            "starting_level": thesis_data.get("audience_and_starting_level", ""),
            "desired_outcome": brief_data.get("outcome", ""),
        },
        INSTRUCTOR_PROFILE=dict(instructor_profile or {}),
        CAPABILITY_GRAPH=_capability_graph(course_map),
        COVERAGE_MATRIX=coverage,
        BENCHMARK_MATRIX=dict(benchmark_matrix or {}),
        MARKET_PACK={
            "target_market": brief_data.get("target_market", ""),
            "market_guidance_sha256": fingerprint_value(brief_data.get("target_market", "")),
        },
        SOURCE_LEDGER=source_ledger,
        TERM_LEDGER=dict(term_ledger or {}),
        CLAIM_LEDGER=dict(claim_ledger or {}),
        LESSON_LEDGER=lessons,
        PHRASE_LEDGER=dict(phrase_ledger or {}),
        PROJECT_LEDGER=projects,
        DEMONSTRATION_LEDGER=demonstrations,
        ASSET_LEDGER=assets,
        QUALITY_FINDINGS=findings,
        ACTIVE_RULE_PACK=active_rule_pack,
        STAGE_CONTRACT_STATE=stage_state,
        PEDAGOGY_ADAPTER={
            "adapter_id": contract.adapter_id,
            "contract_version": contract.version,
            "profile": contract.pedagogy.model_dump(mode="json"),
        },
        EPISODIC_PROGRESSION_MAP={"sequence": sequence, "lesson_count": len(sequence)},
        LANGUAGE_REWRITE_RECORD=[],
        CONFIG_INPUTS=config_inputs,
    )
    snap.recompute_fingerprint()
    return snap


def snapshot_with_config_overrides(
    snapshot: GenerationContextSnapshot | dict[str, Any],
    **overrides: Any,
) -> dict[str, Any]:
    """Copy embedded inputs and replace named identity fields for a boundary check."""
    snap = (
        snapshot
        if isinstance(snapshot, GenerationContextSnapshot)
        else GenerationContextSnapshot.model_validate(snapshot)
    )
    current = deepcopy(snap.CONFIG_INPUTS)
    current.update({key: _jsonable(value) for key, value in overrides.items()})
    return current


def assert_snapshot_compatible(
    snapshot: GenerationContextSnapshot | dict[str, Any] | None,
    *,
    current_config_inputs: dict[str, Any] | None = None,
    action: str = "continue",
) -> GenerationContextSnapshot:
    if not snapshot:
        raise SnapshotMismatchError(f"Cannot {action}: immutable run snapshot is missing")
    try:
        snap = (
            snapshot
            if isinstance(snapshot, GenerationContextSnapshot)
            else GenerationContextSnapshot.model_validate(snapshot)
        )
    except Exception as exc:  # noqa: BLE001
        raise SnapshotMismatchError(f"Cannot {action}: run snapshot is invalid") from exc
    dumped = snap.model_dump(mode="json")
    missing = [key for key in REQUIRED_STATE_KEYS if key not in dumped]
    if snap.version != SNAPSHOT_VERSION or missing:
        raise SnapshotMismatchError(
            f"Cannot {action}: run snapshot contract mismatch; missing={missing}"
        )
    embedded_fingerprint = fingerprint_value(snap.CONFIG_INPUTS)
    if not snap.CONFIG_FINGERPRINT or embedded_fingerprint != snap.CONFIG_FINGERPRINT:
        raise SnapshotMismatchError(
            f"Cannot {action}: frozen CONFIG_FINGERPRINT does not match embedded inputs"
        )
    if current_config_inputs is not None:
        current_fingerprint = fingerprint_value(current_config_inputs)
        if current_fingerprint != snap.CONFIG_FINGERPRINT:
            raise SnapshotMismatchError(
                f"Cannot {action}: output-affecting configuration changed "
                f"({snap.CONFIG_FINGERPRINT} != {current_fingerprint})"
            )
    return snap


def compare_snapshots(
    approved: GenerationContextSnapshot | dict[str, Any],
    current: GenerationContextSnapshot | dict[str, Any],
) -> list[str]:
    a = approved if isinstance(approved, GenerationContextSnapshot) else GenerationContextSnapshot.model_validate(approved)
    b = current if isinstance(current, GenerationContextSnapshot) else GenerationContextSnapshot.model_validate(current)
    if a.CONFIG_FINGERPRINT == b.CONFIG_FINGERPRINT:
        return []
    reasons: list[str] = []
    labels = {
        "STANDARD_PACKAGE": "Course standard package changed",
        "BRIEF": "Course brief changed",
        "COURSE_THESIS": "Course Thesis changed",
        "SELECTED_SOURCES": "Source selection or content changed",
        "RESEARCH_RESULT_SHA256": "Research results changed",
        "MARKET": "Target market changed",
        "COURSE_TYPE": "Course type changed",
        "LANGUAGE_PROFILE": "Language profile changed",
        "ADDRESS_FORM": "Address form changed",
        "QUALITY_MODE": "Quality mode changed",
        "PROVIDER": "Provider changed",
        "MODEL": "Model changed",
        "GENERATION_SETTINGS": "Generation settings changed",
        "APPROVED_MAP": "Approved map changed",
    }
    for key, label in labels.items():
        if a.CONFIG_INPUTS.get(key) != b.CONFIG_INPUTS.get(key):
            reasons.append(label)
    return reasons or ["Generation snapshot fingerprint drift"]
