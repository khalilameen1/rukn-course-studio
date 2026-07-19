"""Course Thesis + Map preview (no lesson scripts) before full generation.

Uses the same sources as full generation. Persists a GenerationContextSnapshot
so run_generation can reuse the approved map instead of silently rebuilding.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlmodel import Session

from app.ai.factory import get_ai_provider
from app.ai.provider import AIProvider
from app.config import settings
from app.crud import courses
from app.generation.contracts.course_thesis import build_course_thesis_from_brief
from app.generation.course_map_quality import total_estimated_minutes
from app.generation.creator_persona import (
    compact_course_persona,
    plan_course_creator_persona,
)
from app.generation.domain_adapters import build_course_quality_contract
from app.generation.knowledge_priority_ladder import (
    ConflictRecord,
    compile_knowledge_priority_guidance,
)
from app.generation.market_evergreen import compile_market_guidance
from app.generation.official_tool_docs import (
    annotate_dependencies_from_map,
    compile_official_tool_guidance,
    run_official_tool_docs_pass,
    tool_memory_excerpts,
)
from app.generation.orchestrator import (
    _build_and_review_course_map,
    _build_course_brief,
    _load_active_rules,
    _load_usable_sources_with_memory,
    _map_source_excerpts,
    _usable_memory,
    _web_facts_as_excerpts,
)
from app.generation.originality_rights import compile_originality_guidance
from app.generation.prompt_compiler import select_packed_rules_for_stage
from app.generation.quality.context_snapshot import (
    SnapshotMismatchError,
    assert_snapshot_compatible,
    build_generation_context_snapshot,
    fingerprint_value,
)
from app.generation.quality.coverage_matrix import evaluate_coverage_matrix
from app.generation.trusted_sources import compile_educational_transform_guidance
from app.generation.web_research import (
    SourceMemoryItem,
    build_upload_source_memory,
    mark_research_failure,
    research_identity_payload,
    run_autonomous_gap_fill,
)
from app.models.enums import (
    AddressForm,
    GenerationQualityMode,
    LessonDeliveryMode,
    WebResearchMode,
)
from app.prompts.prompt_registry import PipelineStage
from app.schemas.generation import CourseMap, CourseThesis
from app.services.json_coerce import coerce_json_dict


@dataclass
class MapPreviewStats:
    module_count: int
    lesson_count: int
    delivery_mode_counts: dict[str, int]
    estimated_minutes: float
    project_count: int
    theory_ratio_estimate: float
    practice_ratio_estimate: float
    approx_tokens: int
    approx_cost_usd: float
    warnings: list[str] = field(default_factory=list)
    can_start_full_generation: bool = True
    thesis: dict = field(default_factory=dict)
    course_map: dict = field(default_factory=dict)
    quality_contract: dict = field(default_factory=dict)
    snapshot_fingerprint: str = ""
    adapter_id: str = "generic"
    map_text: str = ""

    def model_dump(self) -> dict:
        return {
            "module_count": self.module_count,
            "lesson_count": self.lesson_count,
            "delivery_mode_counts": dict(self.delivery_mode_counts),
            "estimated_minutes": self.estimated_minutes,
            "project_count": self.project_count,
            "theory_ratio_estimate": self.theory_ratio_estimate,
            "practice_ratio_estimate": self.practice_ratio_estimate,
            "approx_tokens": self.approx_tokens,
            "approx_cost_usd": self.approx_cost_usd,
            "warnings": list(self.warnings),
            "can_start_full_generation": self.can_start_full_generation,
            "thesis": self.thesis,
            "course_map": self.course_map,
            "quality_contract": self.quality_contract,
            "snapshot_fingerprint": self.snapshot_fingerprint,
            "adapter_id": self.adapter_id,
            "map_text": self.map_text,
        }


def format_course_map_text(course_map: CourseMap) -> str:
    """Editable view of the exact approved internal map."""
    lines: list[str] = [
        f"# {course_map.course_title}",
        f"Main thread: {course_map.main_thread}",
        "",
    ]
    for module in course_map.modules:
        lines.append(f"## Module: {module.title}")
        if module.purpose:
            lines.append(f"Purpose: {module.purpose}")
        for reel in module.reels:
            lines.append(f"- Lesson: {reel.title}")
            if reel.purpose:
                lines.append(f"  Purpose: {reel.purpose}")
            if reel.estimated_length:
                lines.append(f"  Length: {reel.estimated_length}")
            if reel.must_cover:
                lines.append(f"  Cover: {', '.join(reel.must_cover)}")
        project = module.module_project
        if project:
            lines.append(f"Project: {project.name} — {project.brief}")
        elif module.bridge_project:
            lines.append(f"Project: {module.bridge_project}")
        lines.append("")
    if course_map.graduation_project:
        project = course_map.graduation_project
        lines.append(f"## Graduation Project: {project.name}")
        lines.append(project.brief)
    return "\n".join(lines).strip()


def build_map_preview(
    session: Session,
    course_id: int,
    *,
    provider: AIProvider | None = None,
    quality_mode: GenerationQualityMode | None = None,
    human_override_hard_limits: bool = False,
    address_form: AddressForm | None = None,
    presenter_language: str | None = None,
    presenter_dialect: str | None = None,
    delivery_pattern: str = "teleprompter_standard",
    web_research_mode: WebResearchMode | None = None,
) -> MapPreviewStats:
    course = courses.get(session, course_id)
    if course is None:
        raise ValueError(f"Course {course_id} not found")
    provider = provider or get_ai_provider()
    quality_mode = quality_mode or getattr(
        course, "generation_quality_mode", GenerationQualityMode.PREMIUM
    )
    web_research_mode = web_research_mode or getattr(
        course, "web_research_mode", WebResearchMode.AUTONOMOUS_GAP_FILL
    )
    brief = _build_course_brief(course)
    contract = build_course_quality_contract(
        brief,
        course_domain=getattr(course, "course_domain", None),
        course_type=getattr(course, "course_type", None) or "practical_skill",
        address_form=address_form or brief.address_form,
        presenter_language=presenter_language,
        presenter_dialect=presenter_dialect,
        delivery_pattern=delivery_pattern,
        human_override_hard_limits=human_override_hard_limits,
    )
    thesis = build_course_thesis_from_brief(
        brief,
        course_type=getattr(course, "course_type", None) or "practical_skill",
        address_form=address_form or brief.address_form,
        human_override_hard_limits=human_override_hard_limits,
        hard_max_lessons=contract.delivery.hard_max_lessons,
        hard_max_minutes=contract.delivery.hard_max_minutes,
        mix_type=contract.pedagogy.mix_type,
        target_theory_ratio=contract.pedagogy.target_theory_ratio,
        target_practice_ratio=contract.pedagogy.target_practice_ratio,
    )
    rules_context = _load_active_rules(session)
    usable, memory_telemetry = _load_usable_sources_with_memory(session, course_id)
    memory_items: list[SourceMemoryItem] = []
    for item in usable:
        memory = _usable_memory(item) or {}
        summary = memory.get("summary") or (
            item.analysis.source_summary if item.analysis else ""
        )
        if not summary:
            continue
        memory_items.append(
            SourceMemoryItem(
                title=memory.get("title")
                or item.course_source.title
                or item.course_source.original_filename
                or f"source-{item.course_source.id}",
                kind="upload",
                summary=summary,
                authority="standard",
            )
        )

    prefer_fake = (settings.ai_provider or "fake").strip().lower() == "fake"
    try:
        research_result = run_autonomous_gap_fill(
            course_title=course.title,
            audience=course.audience,
            outcome=course.outcome,
            special_notes=course.special_notes,
            memory_items=memory_items,
            mode=web_research_mode,
            prefer_fake=prefer_fake,
            cached_web_memory=coerce_json_dict(
                getattr(course, "web_source_memory_json", None)
            ),
            course_id=course.id,
        )
    except Exception as exc:  # noqa: BLE001 - same fail-soft research policy
        research_result = run_autonomous_gap_fill(
            course_title=course.title,
            audience=course.audience,
            outcome=course.outcome,
            special_notes=course.special_notes,
            memory_items=memory_items,
            mode=WebResearchMode.DISABLED,
            prefer_fake=True,
            cached_web_memory=coerce_json_dict(
                getattr(course, "web_source_memory_json", None)
            ),
            course_id=course.id,
        )
        research_result.ledger = mark_research_failure(
            research_result.ledger, str(exc)
        )

    source_snippets = [
        (item.course_source.extracted_text or "")[:1200]
        for item in usable
        if (item.course_source.extracted_text or "").strip()
    ]
    tool_store = run_official_tool_docs_pass(
        title=course.title,
        audience=course.audience,
        outcome=course.outcome,
        special_notes=course.special_notes,
        course_domain=getattr(course, "course_domain", None),
        map_text=course.manual_map_text or "",
        source_snippets=source_snippets,
        cached=coerce_json_dict(getattr(course, "official_tool_memory_json", None)),
        course_id=course.id,
        prefer_fake=prefer_fake,
        allow_fetch=web_research_mode != WebResearchMode.DISABLED,
    )

    sources = _map_source_excerpts(usable, memory_telemetry) + _web_facts_as_excerpts(
        research_result.web_excerpts_text + tool_memory_excerpts(tool_store)
    )
    from app.generation.context_budget import (
        trim_rules_context,
        trim_source_excerpts_for_map,
    )

    sources = trim_source_excerpts_for_map(sources)
    conflict_records: list[ConflictRecord] = []
    for raw in tool_store.authority_conflicts or []:
        try:
            conflict_records.append(ConflictRecord.model_validate(raw))
        except Exception:
            continue
    map_rules = select_packed_rules_for_stage(
        rules_context, PipelineStage.BUILD_COURSE_MAP
    )
    map_rules = trim_rules_context(
        {
            **map_rules,
            "rukn_target_market_runtime": compile_market_guidance(
                brief.target_market
            ),
            "rukn_originality_runtime": compile_originality_guidance(),
            "rukn_educational_transform_runtime": (
                compile_educational_transform_guidance()
            ),
            "rukn_official_tool_docs_runtime": compile_official_tool_guidance(
                tool_store
            ),
            "rukn_knowledge_priority_runtime": compile_knowledge_priority_guidance(
                conflict_records
            ),
        }
    )
    persona = plan_course_creator_persona(
        title=brief.title,
        audience=brief.audience,
        outcome=brief.outcome,
    )

    course_map, meta = _build_and_review_course_map(
        provider=provider,
        brief=brief,
        sources=sources,
        rules_context=map_rules,
        course_creator_persona=compact_course_persona(persona),
        quality_mode=quality_mode,
        thesis=thesis,
        official_tool_store=tool_store,
    )
    tool_store.tool_dependencies = annotate_dependencies_from_map(
        tool_store.tool_dependencies, course_map
    )
    coverage = evaluate_coverage_matrix(course_map, thesis=thesis, contract=contract)
    map_text = format_course_map_text(course_map)
    # The editable map is part of the frozen brief. Editing it after preview
    # therefore invalidates the approval instead of silently changing output.
    brief_for_snapshot = brief.model_copy(update={"manual_map_text": map_text})

    source_fps = {
        str(item.course_source.id): fingerprint_value(
            item.course_source.extracted_text or ""
        )
        for item in usable
    }
    provider_name = (settings.ai_provider or "fake").strip().lower()
    snapshot = build_generation_context_snapshot(
        course_id=course_id,
        brief=brief_for_snapshot,
        contract=contract,
        thesis=thesis,
        course_map=course_map,
        source_ids=[item.course_source.id for item in usable],
        source_fingerprints=source_fps,
        source_metadata={
            str(item.course_source.id): {
                "category": item.course_source.source_category.value,
                "priority": item.course_source.priority.value,
                "include_in_generation": item.course_source.include_in_generation,
            }
            for item in usable
        },
        research_blob=research_identity_payload(
            research_result.upload_memory,
            research_result.web_memory,
        ),
        admin_rules=rules_context,
        provider_name=provider_name,
        model_name=(
            "fake" if provider_name == "fake" else (settings.ai_model_name or "")
        ),
        quality_mode=quality_mode.value if hasattr(quality_mode, "value") else str(quality_mode),
        web_research_mode=web_research_mode.value
        if hasattr(web_research_mode, "value")
        else str(web_research_mode),
        map_preview_confirmed=False,
        human_override_hard_limits=human_override_hard_limits,
        instructor_profile=persona.model_dump(mode="json"),
        coverage_matrix=coverage.model_dump(mode="json"),
        benchmark_matrix={"map_review": meta},
        claim_ledger=research_result.ledger.model_dump(mode="json"),
        generation_settings={
            "generation_preset": brief.generation_preset.value,
            "structure_mode": brief.structure_mode.value,
            "explanation_level": brief.explanation_level.value,
            "delivery_pattern": delivery_pattern,
        },
    )

    # Persist approved preview map + snapshot on the course row (JSON text fields).
    courses.update(
        session,
        course.id,
        manual_map_text=map_text,
        web_source_memory_json=research_result.web_memory.model_dump(mode="json"),
        official_tool_memory_json=tool_store.model_dump(mode="json"),
        generation_context_snapshot_json=snapshot.model_dump(mode="json"),
    )

    stats = summarize_map_preview(
        course_map,
        thesis=thesis,
        map_meta=meta,
        contract=contract,
        coverage_ok=coverage.ok,
        coverage_issues=[i.detail for i in coverage.issues],
    )
    stats.quality_contract = contract.model_dump(mode="json")
    stats.snapshot_fingerprint = snapshot.fingerprint
    stats.adapter_id = contract.adapter_id
    stats.map_text = map_text
    stats.theory_ratio_estimate = coverage.theory_ratio
    stats.practice_ratio_estimate = coverage.practice_ratio
    return stats


def assert_approved_map_ready(
    session: Session,
    course_id: int,
    *,
    approved_snapshot_fingerprint: str | None,
    quality_mode: GenerationQualityMode,
    web_research_mode: WebResearchMode,
    human_override_hard_limits: bool,
) -> dict:
    """Fail before job claim if the approved preview is absent or stale."""
    course = courses.get(session, course_id)
    if course is None:
        raise SnapshotMismatchError(f"Course {course_id} not found")
    frozen = assert_snapshot_compatible(
        course.generation_context_snapshot_json,
        action="start full generation",
    )
    if not approved_snapshot_fingerprint:
        raise SnapshotMismatchError(
            "Cannot start full generation: approved snapshot fingerprint is required"
        )
    if approved_snapshot_fingerprint != frozen.CONFIG_FINGERPRINT:
        raise SnapshotMismatchError(
            "Cannot start full generation: approved map fingerprint mismatch"
        )
    if not bool(frozen.COVERAGE_MATRIX.get("ok")):
        raise SnapshotMismatchError(
            "Cannot start full generation: approved map has unresolved coverage blockers"
        )
    map_data = frozen.approved_course_map
    if not map_data:
        raise SnapshotMismatchError(
            "Cannot start full generation: approved snapshot has no course map"
        )
    course_map = CourseMap.model_validate(map_data)
    thesis = CourseThesis.model_validate(frozen.COURSE_THESIS)
    brief = _build_course_brief(course)
    frozen_settings = dict(
        frozen.CONFIG_INPUTS.get("GENERATION_SETTINGS") or {}
    )
    delivery_pattern = str(
        frozen_settings.get("delivery_pattern") or "teleprompter_standard"
    )
    contract = build_course_quality_contract(
        brief,
        course_domain=getattr(course, "course_domain", None),
        course_type=getattr(course, "course_type", None) or "practical_skill",
        address_form=brief.address_form,
        delivery_pattern=delivery_pattern,
        human_override_hard_limits=human_override_hard_limits,
    )
    usable, _telemetry = _load_usable_sources_with_memory(session, course_id)
    memory_items: list[SourceMemoryItem] = []
    for item in usable:
        memory = _usable_memory(item) or {}
        summary = memory.get("summary") or (
            item.analysis.source_summary if item.analysis else ""
        )
        if summary:
            memory_items.append(
                SourceMemoryItem(
                    title=memory.get("title")
                    or item.course_source.title
                    or item.course_source.original_filename
                    or f"source-{item.course_source.id}",
                    kind="upload",
                    summary=summary,
                    authority="standard",
                )
            )
    upload_memory = build_upload_source_memory(
        course_title=course.title,
        audience=course.audience,
        outcome=course.outcome,
        memory_items=memory_items,
    )
    source_fingerprints = {
        str(item.course_source.id): fingerprint_value(
            item.course_source.extracted_text or ""
        )
        for item in usable
    }
    provider_name = (settings.ai_provider or "fake").strip().lower()
    current = build_generation_context_snapshot(
        course_id=course_id,
        brief=brief,
        contract=contract,
        thesis=thesis,
        course_map=course_map,
        source_ids=[item.course_source.id for item in usable],
        source_fingerprints=source_fingerprints,
        source_metadata={
            str(item.course_source.id): {
                "category": item.course_source.source_category.value,
                "priority": item.course_source.priority.value,
                "include_in_generation": item.course_source.include_in_generation,
            }
            for item in usable
        },
        research_blob=research_identity_payload(
            upload_memory,
            coerce_json_dict(getattr(course, "web_source_memory_json", None)),
        ),
        admin_rules=_load_active_rules(session),
        provider_name=provider_name,
        model_name=(
            "fake" if provider_name == "fake" else (settings.ai_model_name or "")
        ),
        quality_mode=quality_mode.value,
        web_research_mode=web_research_mode.value,
        map_preview_confirmed=True,
        human_override_hard_limits=human_override_hard_limits,
        generation_settings={
            "generation_preset": brief.generation_preset.value,
            "structure_mode": brief.structure_mode.value,
            "explanation_level": brief.explanation_level.value,
            "delivery_pattern": delivery_pattern,
        },
    )
    assert_snapshot_compatible(
        frozen,
        current_config_inputs=current.CONFIG_INPUTS,
        action="start full generation",
    )
    return frozen.model_dump(mode="json")


def summarize_map_preview(
    course_map: CourseMap,
    *,
    thesis: CourseThesis | None = None,
    map_meta: dict | None = None,
    contract=None,
    coverage_ok: bool = True,
    coverage_issues: list[str] | None = None,
) -> MapPreviewStats:
    thesis = thesis or course_map.thesis
    lessons = [r for m in course_map.modules for r in m.reels]
    mode_counts: dict[str, int] = {}
    for r in lessons:
        mode = r.delivery_mode or LessonDeliveryMode.CAMERA_EXPLAINER
        key = mode.value if hasattr(mode, "value") else str(mode)
        mode_counts[key] = mode_counts.get(key, 0) + 1
    projects = sum(
        1
        for m in course_map.modules
        if m.module_project is not None or (m.bridge_project or "").strip()
    )
    if course_map.graduation_project or (thesis and thesis.final_project):
        projects += 1
    minutes = total_estimated_minutes(course_map)
    approx_tokens = 4000 + len(lessons) * 2200
    approx_cost = round(approx_tokens / 1_000_000 * 3.0, 2)
    warnings: list[str] = list(coverage_issues or [])
    can_start = coverage_ok
    hard_max_lessons = (
        contract.delivery.hard_max_lessons if contract is not None else (thesis.hard_max_lessons if thesis else 60)
    )
    hard_max_minutes = (
        contract.delivery.hard_max_minutes if contract is not None else (thesis.hard_max_minutes if thesis else 240)
    )
    override = bool(thesis and thesis.human_override_hard_limits)
    if thesis:
        if len(lessons) > hard_max_lessons and not override:
            warnings.append(
                f"Map has {len(lessons)} lessons over hard max {hard_max_lessons}"
            )
            can_start = False
        if minutes > hard_max_minutes and not override:
            warnings.append(
                f"Map estimates ~{minutes:.0f} min over hard max {hard_max_minutes}"
            )
            can_start = False
        require_projects = True
        if contract is not None:
            require_projects = contract.pedagogy.mix_type.value == "practical"
        if require_projects and projects < len(course_map.modules):
            warnings.append("Some modules are missing practical projects")
            can_start = False
    if map_meta and map_meta.get("merged"):
        warnings.append(f"Compression merged {map_meta['merged']} near-duplicate pair(s)")
    return MapPreviewStats(
        module_count=len(course_map.modules),
        lesson_count=len(lessons),
        delivery_mode_counts=mode_counts,
        estimated_minutes=round(minutes, 1),
        project_count=projects,
        theory_ratio_estimate=0.0,
        practice_ratio_estimate=0.0,
        approx_tokens=approx_tokens,
        approx_cost_usd=approx_cost,
        warnings=warnings,
        can_start_full_generation=can_start,
        thesis=thesis.model_dump(mode="json") if thesis else {},
        course_map=course_map.model_dump(mode="json"),
    )
