"""Course-map-only generation — Creator→Student→Specialist→Mentor→Final rebuild.

Stores the editable Final Course Map on Course.manual_map_text (course-specific).
Never writes Admin Knowledge. Reviews stay internal.
"""

from __future__ import annotations

from sqlmodel import Session

from app.ai.factory import get_ai_provider
from app.ai.fake_provider import FakeProvider
from app.ai.provider import AIProvider
from app.config import settings
from app.crud import courses
from app.generation.creator_persona import compact_course_persona, plan_course_creator_persona
from app.generation.market_evergreen import compile_market_guidance
from app.generation.orchestrator import (
    _build_and_review_course_map,
    _build_course_brief,
    _load_active_rules,
    _load_usable_sources_with_memory,
    _map_source_excerpts,
    _web_facts_as_excerpts,
)
from app.generation.originality_rights import compile_originality_guidance
from app.generation.prompt_compiler import select_packed_rules_for_stage
from app.generation.trusted_sources import compile_educational_transform_guidance
from app.generation.web_research import (
    SourceMemoryItem,
    run_autonomous_gap_fill,
)
from app.models.course import Course
from app.models.enums import GenerationQualityMode, WebResearchMode
from app.prompts.prompt_registry import PipelineStage
from app.schemas.generation import CourseMap


def format_course_map_text(course_map: CourseMap) -> str:
    """Editable plain-text map for the Create Course editor (not DOCX)."""
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
        if module.bridge_project:
            lines.append(f"Bridge: {module.bridge_project}")
        lines.append("")
    return "\n".join(lines).strip()


def generate_and_save_course_map(
    session: Session,
    course_id: int,
    *,
    provider: AIProvider | None = None,
) -> tuple[Course, str]:
    """Run the locked map quality pipeline and save to course.manual_map_text."""
    course = courses.get(session, course_id)
    if course is None:
        raise ValueError(f"Course {course_id} not found")

    provider = provider or (
        FakeProvider()
        if (settings.ai_provider or "fake").strip().lower() == "fake"
        else get_ai_provider()
    )
    quality_mode = getattr(course, "generation_quality_mode", None) or GenerationQualityMode.PREMIUM
    research_mode = getattr(course, "web_research_mode", None) or WebResearchMode.AUTONOMOUS_GAP_FILL

    rules_context = _load_active_rules(session)
    usable_sources, memory_telemetry = _load_usable_sources_with_memory(session, course_id)
    memory_items: list[SourceMemoryItem] = []
    for u in usable_sources:
        mem = u.analysis.source_memory_json if u.analysis else None
        summary = (mem or {}).get("summary") or (
            u.analysis.source_summary if u.analysis else ""
        )
        if not summary:
            continue
        memory_items.append(
            SourceMemoryItem(
                title=(mem or {}).get("title")
                or u.course_source.title
                or u.course_source.original_filename
                or f"source-{u.course_source.id}",
                kind="upload",
                summary=summary,
                authority="standard",
            )
        )

    prefer_fake = (settings.ai_provider or "fake").strip().lower() == "fake"
    research_result = run_autonomous_gap_fill(
        course_title=course.title,
        audience=course.audience,
        outcome=course.outcome,
        special_notes=course.special_notes,
        memory_items=memory_items,
        mode=research_mode,
        prefer_fake=prefer_fake,
        cached_web_memory=getattr(course, "web_source_memory_json", None),
        course_id=course.id,
    )
    web_excerpts = _web_facts_as_excerpts(research_result.web_excerpts_text)
    # Clear manual map so the provider builds from brief+sources (two-pass).
    brief = _build_course_brief(course)
    brief = brief.model_copy(update={"manual_map_text": None})

    if hasattr(provider, "configure_for_run"):
        provider.configure_for_run(brief.generation_preset)

    persona = plan_course_creator_persona(
        title=brief.title, audience=brief.audience, outcome=brief.outcome
    )
    map_sources = _map_source_excerpts(usable_sources, memory_telemetry) + web_excerpts
    map_rules = select_packed_rules_for_stage(rules_context, PipelineStage.BUILD_COURSE_MAP)
    map_rules = {
        **map_rules,
        "rukn_target_market_runtime": compile_market_guidance(brief.target_market),
        "rukn_originality_runtime": compile_originality_guidance(),
        "rukn_educational_transform_runtime": compile_educational_transform_guidance(),
    }
    course_map, _meta = _build_and_review_course_map(
        provider=provider,
        brief=brief,
        sources=map_sources,
        rules_context=map_rules,
        course_creator_persona=compact_course_persona(persona),
        quality_mode=quality_mode,
    )
    map_text = format_course_map_text(course_map)
    course = courses.update(session, course_id, manual_map_text=map_text)
    assert course is not None
    return course, map_text
