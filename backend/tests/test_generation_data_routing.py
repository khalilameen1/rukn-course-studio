"""End-to-end data routing: course sources stay course-scoped; Admin Knowledge stays global."""

from dataclasses import asdict

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.ai.fake_provider import FakeProvider
from app.ai.provider import BuildCourseMapInput, WriteSingleReelInput
from app.crud import admin_knowledge_items, course_sources, courses, source_analyses
from app.generation.knowledge_packs import build_stage_rules_pack
from app.generation.orchestrator import run_generation
from app.generation.prompt_compiler import (
    select_packed_rules_for_stage,
    select_rules_for_stage,
)
from app.prompts.prompt_registry import PipelineStage
from app.generation.source_memory_store import build_source_memory_payload
from app.models.enums import (
    ExplanationLevel,
    ItemType,
    Priority,
    SourceCategory,
    StructureMode,
)
from app.seed_admin_knowledge import SEED_ITEMS
from app.services.source_analysis import analyze_source_text


@pytest.fixture()
def session(tmp_path, monkeypatch):
    import app.generation.orchestrator as orchestrator_module

    engine = create_engine(f"sqlite:///{tmp_path / 'route.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(orchestrator_module.settings, "storage_outputs_dir", tmp_path)
    with Session(engine) as s:
        for item in SEED_ITEMS:
            if not admin_knowledge_items.list(s, key=item["key"]):
                admin_knowledge_items.create(
                    s,
                    key=item["key"],
                    title=item["title"],
                    item_type=item["item_type"],
                    content_text=item.get("content_text"),
                    file_path=item.get("file_path"),
                    is_active=True,
                )
        yield s


SAME_TOPIC = (
    "Meta ads for Egyptian boutique shops. ROAS measurement and campaign setup. "
    "Common mistake: small budgets need proof before scaling."
)
OFF_TOPIC = "How to bake sourdough bread fermentation starter kitchen recipe flour yeast."
MIXED_DRAFT = (
    "# Module 1\nLesson: Meta ads for Cairo shops\n"
    "Believe in yourself hustle harder.\n"
    "Useful: test one creative variable before scaling spend."
)
MAP_TEXT = "Module 1: Foundations\n  Lesson 1: Campaign setup"


class TraceProvider(FakeProvider):
    def __init__(self):
        super().__init__()
        self.map_calls: list[BuildCourseMapInput] = []
        self.reel_calls: list[WriteSingleReelInput] = []

    def build_course_map(self, data: BuildCourseMapInput):
        self.map_calls.append(data)
        return super().build_course_map(data)

    def write_single_reel(self, data: WriteSingleReelInput):
        self.reel_calls.append(data)
        return super().write_single_reel(data)


def _attach_source(session, course_id, text, category, *, memory_extra=None):
    source = course_sources.create(
        session,
        course_id=course_id,
        source_category=category,
        priority=Priority.MEDIUM,
        status="ready",
        extracted_text=text,
        include_in_generation=True,
    )
    built = analyze_source_text(text, category.value)
    memory = build_source_memory_payload(
        title=f"{category.value}.txt",
        category=category.value,
        extracted_text=text,
        summary=built.source_summary,
        chunks=[asdict(c) for c in built.chunks],
        key_points=built.key_points,
        avoid_points=built.avoid_points,
        course_promise={
            "title": "Meta Ads for Egyptian Shops",
            "audience": "shop owners",
            "outcome": "profitable Meta ads",
            "course_map_text": MAP_TEXT,
            "target_market": "egypt",
        }
        if category == SourceCategory.TRANSCRIPT
        else None,
    )
    if memory_extra:
        memory.update(memory_extra)
    source_analyses.create(
        session,
        source_id=source.id,
        chunks_json=[asdict(c) for c in built.chunks],
        source_summary=built.source_summary,
        key_points_json=built.key_points,
        avoid_points_json=built.avoid_points,
        source_memory_json=memory,
    )
    return source


def test_course_sources_never_appear_in_admin_knowledge(session):
    course = courses.create(
        session,
        title="Meta Ads for Egyptian Shops",
        audience="shop owners",
        outcome="profitable Meta ads",
        structure_mode=StructureMode.CONNECTED_NO_MODULES,
        explanation_level=ExplanationLevel.FINAL_ONLY,
        manual_map_text=MAP_TEXT,
    )
    marker = "ROUTING_MARKER_SAME_TOPIC_999"
    _attach_source(session, course.id, marker + " " + SAME_TOPIC, SourceCategory.TRANSCRIPT)
    for item in admin_knowledge_items.list(session):
        blob = (item.content_text or "") + (item.title or "")
        assert marker not in blob


def test_map_stage_excludes_flow_reference_and_uses_packed_admin_rules(session):
    course = courses.create(
        session,
        title="Meta Ads for Egyptian Shops",
        audience="shop owners",
        outcome="profitable Meta ads",
        structure_mode=StructureMode.CONNECTED_NO_MODULES,
        explanation_level=ExplanationLevel.FINAL_ONLY,
        manual_map_text=MAP_TEXT,
    )
    _attach_source(session, course.id, SAME_TOPIC, SourceCategory.TRANSCRIPT)
    _attach_source(session, course.id, OFF_TOPIC, SourceCategory.FLOW_REFERENCE)
    _attach_source(session, course.id, MIXED_DRAFT, SourceCategory.MIXED_QUALITY_AI_COURSE_DRAFT)

    provider = TraceProvider()
    run_generation(session, course.id, provider=provider)
    assert provider.map_calls
    map_input = provider.map_calls[0]

    categories = {s.category for s in map_input.sources}
    assert SourceCategory.FLOW_REFERENCE.value not in categories

    for src in map_input.sources:
        assert "UNTRUSTED_REFERENCE_MATERIAL" in src.text

    rules = {item.key: item.content_text for item in admin_knowledge_items.list(session, is_active=True)}
    packed = select_packed_rules_for_stage(rules, PipelineStage.BUILD_COURSE_MAP)
    pack_chars = sum(len(v) for v in packed.values())
    full_chars = sum(len(v) for v in select_rules_for_stage(rules, PipelineStage.BUILD_COURSE_MAP).values())
    assert pack_chars < full_chars
    assert pack_chars <= 6000

    assert provider.reel_calls
    reel_rules = select_packed_rules_for_stage(rules, PipelineStage.WRITE_SINGLE_REEL)
    assert "lesson_writing_rules_pack" in reel_rules
    assert "teleprompter" in " ".join(reel_rules.values()).lower() or any(
        "teleprompter" in k for k in reel_rules
    )


def test_mixed_draft_memory_not_full_dump_in_map_prompt(session):
    long_draft = MIXED_DRAFT + ("Believe in yourself. " * 500)
    memory = build_source_memory_payload(
        title="draft.docx",
        category="mixed_quality_ai_course_draft",
        extracted_text=long_draft,
        course_promise={
            "title": "Meta Ads",
            "audience": "shops",
            "outcome": "ads",
            "course_map_text": MAP_TEXT,
        },
    )
    from app.generation.source_memory_store import compiler_text_from_memory

    compact = compiler_text_from_memory(
        memory=memory,
        summary=memory.get("summary"),
        chunks=[],
        query_text="Meta ads",
        fallback_text=long_draft,
        category="mixed_quality_ai_course_draft",
    )
    assert len(compact) < len(long_draft) // 2


def test_packed_rules_never_include_full_seed_articles():
    all_rules = {item["key"]: item["content_text"] for item in SEED_ITEMS if item.get("content_text")}
    for stage in (
        PipelineStage.BUILD_COURSE_MAP,
        PipelineStage.WRITE_SINGLE_REEL,
        PipelineStage.FINAL_REVIEW,
    ):
        packed = build_stage_rules_pack(select_rules_for_stage(all_rules, stage), stage)
        joined = "\n".join(packed.values())
        for item in SEED_ITEMS:
            content = item.get("content_text") or ""
            if len(content) > 1200:
                assert content not in joined
