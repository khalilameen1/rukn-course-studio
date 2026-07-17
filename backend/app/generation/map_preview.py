"""Course Thesis + Map preview (no lesson scripts) before full generation."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlmodel import Session

from app.ai.factory import get_ai_provider
from app.ai.provider import AIProvider
from app.crud import admin_knowledge_items, courses
from app.generation.contracts.course_thesis import build_course_thesis_from_brief
from app.generation.course_map_quality import total_estimated_minutes
from app.generation.duration_policy import DEFAULT_SPOKEN_WPM
from app.generation.orchestrator import _build_and_review_course_map, _build_course_brief
from app.models.enums import AddressForm, GenerationQualityMode, LessonDeliveryMode
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
        }


def build_map_preview(
    session: Session,
    course_id: int,
    *,
    provider: AIProvider | None = None,
    quality_mode: GenerationQualityMode | None = None,
    human_override_hard_limits: bool = False,
    address_form: AddressForm = AddressForm.MASCULINE,
) -> MapPreviewStats:
    course = courses.get(session, course_id)
    if course is None:
        raise ValueError(f"Course {course_id} not found")
    provider = provider or get_ai_provider()
    quality_mode = quality_mode or getattr(
        course, "generation_quality_mode", GenerationQualityMode.PREMIUM
    )
    brief = _build_course_brief(course)
    thesis = build_course_thesis_from_brief(
        brief,
        course_type=getattr(course, "course_type", None) or "practical_skill",
        address_form=address_form,
        human_override_hard_limits=human_override_hard_limits,
    )
    rules_context = {
        item.key: item.content_text or ""
        for item in admin_knowledge_items.list(session, is_active=True)
    }
    course_map, meta = _build_and_review_course_map(
        provider=provider,
        brief=brief,
        sources=[],
        rules_context=rules_context,
        course_creator_persona={},
        quality_mode=quality_mode,
        thesis=thesis,
    )
    # Persist preview map text for the create flow.
    from app.generation.course_map_generate import format_course_map_text

    courses.update(
        session,
        course.id,
        manual_map_text=format_course_map_text(course_map),
    )

    return summarize_map_preview(course_map, thesis=thesis, map_meta=meta)


def summarize_map_preview(
    course_map: CourseMap,
    *,
    thesis: CourseThesis | None = None,
    map_meta: dict | None = None,
) -> MapPreviewStats:
    thesis = thesis or course_map.thesis
    lessons = [r for m in course_map.modules for r in m.reels]
    mode_counts: dict[str, int] = {}
    theoryish = 0
    practiceish = 0
    for r in lessons:
        mode = r.delivery_mode or LessonDeliveryMode.CAMERA_EXPLAINER
        key = mode.value if hasattr(mode, "value") else str(mode)
        mode_counts[key] = mode_counts.get(key, 0) + 1
        if mode in {
            LessonDeliveryMode.SCREEN_DEMO,
            LessonDeliveryMode.PROJECT_BUILD,
            LessonDeliveryMode.BEFORE_AFTER,
            LessonDeliveryMode.ERROR_FIX,
            LessonDeliveryMode.CASE_STUDY,
            LessonDeliveryMode.CRITIQUE,
            LessonDeliveryMode.DESIGN_CRITIQUE,
        }:
            practiceish += 1
        else:
            theoryish += 1
    total = max(1, len(lessons))
    projects = sum(
        1
        for m in course_map.modules
        if m.module_project is not None or (m.bridge_project or "").strip()
    )
    if course_map.graduation_project or (thesis and thesis.final_project):
        projects += 1
    minutes = total_estimated_minutes(course_map)
    # Rough cost: ~map tokens + ~2 writes * lessons * ~800 tokens.
    approx_tokens = 4000 + len(lessons) * 2200
    approx_cost = round(approx_tokens / 1_000_000 * 3.0, 2)  # coarse USD ballpark
    warnings: list[str] = []
    can_start = True
    if thesis:
        if len(lessons) > thesis.hard_max_lessons and not thesis.human_override_hard_limits:
            warnings.append(
                f"Map has {len(lessons)} lessons over hard max {thesis.hard_max_lessons}"
            )
            can_start = False
        if minutes > thesis.hard_max_minutes and not thesis.human_override_hard_limits:
            warnings.append(
                f"Map estimates ~{minutes:.0f} min over hard max {thesis.hard_max_minutes}"
            )
            can_start = False
        if projects < len(course_map.modules):
            warnings.append("Some modules are missing practical projects")
            can_start = False
    if map_meta and map_meta.get("compression_merged"):
        warnings.append(
            f"Compression merged {map_meta['compression_merged']} near-duplicate pair(s)"
        )
    return MapPreviewStats(
        module_count=len(course_map.modules),
        lesson_count=len(lessons),
        delivery_mode_counts=mode_counts,
        estimated_minutes=round(minutes, 1),
        project_count=projects,
        theory_ratio_estimate=round(theoryish / total, 2),
        practice_ratio_estimate=round(practiceish / total, 2),
        approx_tokens=approx_tokens,
        approx_cost_usd=approx_cost,
        warnings=warnings,
        can_start_full_generation=can_start,
        thesis=thesis.model_dump(mode="json") if thesis else {},
        course_map=course_map.model_dump(mode="json"),
    )
