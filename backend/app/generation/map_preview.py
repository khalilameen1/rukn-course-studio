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
from app.generation.domain_adapters import build_course_quality_contract
from app.generation.duration_policy import DEFAULT_SPOKEN_WPM
from app.generation.orchestrator import (
    _build_and_review_course_map,
    _build_course_brief,
    _load_active_rules,
    _load_usable_sources,
    _map_source_excerpts,
)
from app.generation.quality.context_snapshot import (
    build_generation_context_snapshot,
    fingerprint_value,
)
from app.generation.quality.coverage_matrix import evaluate_coverage_matrix
from app.models.enums import AddressForm, GenerationQualityMode, LessonDeliveryMode, WebResearchMode
from app.schemas.generation import CourseMap, CourseThesis


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
    snapshot: dict = field(default_factory=dict)
    snapshot_fingerprint: str = ""
    adapter_id: str = "generic"

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
            "snapshot": self.snapshot,
            "snapshot_fingerprint": self.snapshot_fingerprint,
            "adapter_id": self.adapter_id,
        }


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
        course, "web_research_mode", WebResearchMode.DISABLED
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
    usable = _load_usable_sources(session, course_id)
    sources = _map_source_excerpts(usable)
    # Preview does not call live web research (credit-safe). Fingerprint mode only.
    research_blob = f"mode={(web_research_mode.value if hasattr(web_research_mode, 'value') else web_research_mode)}"

    course_map, meta = _build_and_review_course_map(
        provider=provider,
        brief=brief,
        sources=sources,
        rules_context=rules_context,
        course_creator_persona={},
        quality_mode=quality_mode,
        thesis=thesis,
    )
    coverage = evaluate_coverage_matrix(course_map, thesis=thesis, contract=contract)

    from app.generation.course_map_generate import format_course_map_text

    source_fps = {
        str(item.course_source.id): fingerprint_value(
            item.course_source.extracted_text or ""
        )
        for item in usable
    }
    snapshot = build_generation_context_snapshot(
        course_id=course_id,
        brief=brief,
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
        research_blob=research_blob,
        admin_rules=rules_context,
        provider_name=(settings.ai_provider or "fake"),
        model_name="fake" if (settings.ai_provider or "fake") == "fake" else (settings.ai_model_name or ""),
        quality_mode=quality_mode.value if hasattr(quality_mode, "value") else str(quality_mode),
        web_research_mode=web_research_mode.value
        if hasattr(web_research_mode, "value")
        else str(web_research_mode),
        map_preview_confirmed=False,
        human_override_hard_limits=human_override_hard_limits,
        coverage_matrix=coverage.model_dump(mode="json"),
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
        manual_map_text=format_course_map_text(course_map),
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
    stats.snapshot = snapshot.model_dump(mode="json")
    stats.snapshot_fingerprint = snapshot.fingerprint
    stats.adapter_id = contract.adapter_id
    stats.theory_ratio_estimate = coverage.theory_ratio
    stats.practice_ratio_estimate = coverage.practice_ratio
    return stats


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
