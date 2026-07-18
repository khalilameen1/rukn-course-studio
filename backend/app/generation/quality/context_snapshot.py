"""GenerationContextSnapshot — shared by map-preview, full gen, writer-test, finalize."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.generation.quality.contract import CourseQualityContract
from app.schemas.generation import CourseMap, CourseThesis


def _short_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def fingerprint_dict(data: dict) -> str:
    payload = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return _short_hash(payload)


class GenerationContextSnapshot(BaseModel):
    version: str = "1.0"
    created_at: str = ""
    course_id: int | None = None
    brief: dict = Field(default_factory=dict)
    quality_contract: dict = Field(default_factory=dict)
    thesis: dict = Field(default_factory=dict)
    approved_course_map: dict | None = None
    source_ids: list[int] = Field(default_factory=list)
    source_fingerprints: dict[str, str] = Field(default_factory=dict)
    research_fingerprint: str = ""
    admin_knowledge_fingerprint: str = ""
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    provider_name: str = "fake"
    model_name: str = "fake"
    quality_mode: str = "premium"
    web_research_mode: str = "disabled"
    terminology_fingerprint: str = ""
    claim_ledger_fingerprint: str = ""
    map_preview_confirmed: bool = False
    human_override_hard_limits: bool = False
    fingerprint: str = ""
    invalidated: bool = False
    invalidation_reasons: list[str] = Field(default_factory=list)

    def recompute_fingerprint(self) -> str:
        payload = self.model_dump(mode="json")
        payload.pop("fingerprint", None)
        payload.pop("invalidated", None)
        payload.pop("invalidation_reasons", None)
        payload.pop("created_at", None)
        self.fingerprint = fingerprint_dict(payload)
        return self.fingerprint


def build_generation_context_snapshot(
    *,
    course_id: int | None,
    brief,
    contract: CourseQualityContract,
    thesis: CourseThesis | None,
    course_map: CourseMap | None = None,
    source_ids: list[int] | None = None,
    source_fingerprints: dict[str, str] | None = None,
    research_blob: str = "",
    admin_rules: dict[str, str] | None = None,
    prompt_versions: dict[str, str] | None = None,
    provider_name: str = "fake",
    model_name: str = "fake",
    quality_mode: str = "premium",
    web_research_mode: str = "disabled",
    map_preview_confirmed: bool = False,
    human_override_hard_limits: bool = False,
) -> GenerationContextSnapshot:
    rules = admin_rules or {}
    snap = GenerationContextSnapshot(
        created_at=datetime.now(timezone.utc).isoformat(),
        course_id=course_id,
        brief=brief.model_dump(mode="json") if hasattr(brief, "model_dump") else dict(brief or {}),
        quality_contract=contract.model_dump(mode="json"),
        thesis=thesis.model_dump(mode="json") if thesis else {},
        approved_course_map=course_map.model_dump(mode="json") if course_map else None,
        source_ids=list(source_ids or []),
        source_fingerprints=dict(source_fingerprints or {}),
        research_fingerprint=_short_hash(research_blob),
        admin_knowledge_fingerprint=fingerprint_dict(
            {k: _short_hash(v) for k, v in rules.items()}
        ),
        prompt_versions=dict(prompt_versions or {}),
        provider_name=provider_name,
        model_name=model_name,
        quality_mode=quality_mode,
        web_research_mode=web_research_mode,
        map_preview_confirmed=map_preview_confirmed,
        human_override_hard_limits=human_override_hard_limits,
    )
    snap.recompute_fingerprint()
    return snap


def compare_snapshots(
    approved: GenerationContextSnapshot | dict,
    current: GenerationContextSnapshot | dict,
) -> list[str]:
    """Return human-readable drift reasons if fingerprints diverge on material fields."""
    a = (
        approved
        if isinstance(approved, GenerationContextSnapshot)
        else GenerationContextSnapshot.model_validate(approved)
    )
    b = (
        current
        if isinstance(current, GenerationContextSnapshot)
        else GenerationContextSnapshot.model_validate(current)
    )
    reasons: list[str] = []
    checks = [
        ("quality_contract", "CourseQualityContract changed"),
        ("thesis", "Course Thesis changed"),
        ("source_ids", "Source selection changed"),
        ("source_fingerprints", "Source content fingerprints changed"),
        ("admin_knowledge_fingerprint", "Admin Knowledge version changed"),
        ("prompt_versions", "Prompt versions changed"),
        ("provider_name", "Provider changed"),
        ("model_name", "Model changed"),
        ("quality_mode", "Quality mode changed"),
        ("web_research_mode", "Web research mode changed"),
        ("research_fingerprint", "Research results changed"),
    ]
    for field, label in checks:
        if getattr(a, field) != getattr(b, field):
            reasons.append(label)
    if a.fingerprint != b.fingerprint and not reasons:
        reasons.append("Generation snapshot fingerprint drift")
    return reasons
