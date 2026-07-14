"""Admin Knowledge cleanup, Create Course sources/map, ROKN branding helpers."""

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.generation.admin_knowledge_cleanup import (
    dedupe_admin_knowledge,
    filter_active_primary,
)
from app.generation.course_map_generate import format_course_map_text
from app.models.enums import SourceCategory
from app.schemas.generation import CourseMap, ModulePlan, ReelPlan


@pytest.fixture()
def session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'arch.db'}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_filter_active_primary_hides_duplicates(session):
    from app.crud import admin_knowledge_items
    from app.models.enums import ItemType

    a1 = admin_knowledge_items.create(
        session,
        key="rukn_core_rules",
        title="Core v1",
        item_type=ItemType.MARKDOWN,
        content_text="old",
        is_active=True,
        version=1,
    )
    a2 = admin_knowledge_items.create(
        session,
        key="rukn_core_rules",
        title="Core v2",
        item_type=ItemType.MARKDOWN,
        content_text="new",
        is_active=True,
        version=2,
    )
    inactive = admin_knowledge_items.create(
        session,
        key="rukn_core_rules",
        title="Core backup",
        item_type=ItemType.MARKDOWN,
        content_text="backup",
        is_active=False,
        version=0,
    )
    items = admin_knowledge_items.list(session)
    primary = filter_active_primary(items)
    assert len([p for p in primary if p.key == "rukn_core_rules"]) == 1
    assert primary[-1].id == a2.id
    assert inactive.id not in {p.id for p in primary}

    report = dedupe_admin_knowledge(session, dry_run=False, confirm=True)
    assert report["deactivated_count"] >= 1
    active = [i for i in admin_knowledge_items.list(session, key="rukn_core_rules") if i.is_active]
    assert len(active) == 1
    assert active[0].id == a2.id
    assert a1.is_active is False or admin_knowledge_items.get(session, a1.id).is_active is False


def test_course_sources_belong_to_course_not_admin(session):
    from app.crud import admin_knowledge_items, course_sources, courses
    from app.models.enums import ExplanationLevel, Priority, StructureMode

    course = courses.create(
        session,
        title="T",
        audience="A",
        outcome="O",
        structure_mode=StructureMode.CONNECTED_NO_MODULES,
        explanation_level=ExplanationLevel.FINAL_ONLY,
    )
    src = course_sources.create(
        session,
        course_id=course.id,
        source_category=SourceCategory.TRANSCRIPT,
        title="Lesson tape",
        extracted_text="spoken transcript text about ads",
        priority=Priority.MEDIUM,
        status="ready",
        include_in_generation=True,
    )
    assert src.course_id == course.id
    # Never land in Admin Knowledge
    for item in admin_knowledge_items.list(session):
        blob = (item.content_text or "") + (item.title or "")
        assert "spoken transcript text about ads" not in blob


def test_manual_map_stored_on_course(session):
    from app.crud import courses
    from app.models.enums import ExplanationLevel, StructureMode

    course = courses.create(
        session,
        title="Map course",
        audience="shops",
        outcome="ads",
        structure_mode=StructureMode.CONNECTED_NO_MODULES,
        explanation_level=ExplanationLevel.FINAL_ONLY,
        manual_map_text="# Module 1\n- Lesson A",
    )
    assert "Lesson A" in (course.manual_map_text or "")


def test_format_course_map_text_editable():
    cmap = CourseMap(
        course_title="Ads",
        main_thread="profit",
        modules=[
            ModulePlan(
                module_id="m1",
                title="Start",
                purpose="open",
                reels=[
                    ReelPlan(
                        reel_id="m1-r1",
                        title="Hook",
                        purpose="hook",
                        estimated_length="3 min",
                    )
                ],
            )
        ],
    )
    text = format_course_map_text(cmap)
    assert "Ads" in text
    assert "Hook" in text


def test_user_facing_brand_is_rokn_not_rukn():
    from pathlib import Path

    roots = [
        Path(__file__).resolve().parents[2] / "frontend" / "src" / "app" / "layout.tsx",
        Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "ui" / "AppShell.tsx",
        Path(__file__).resolve().parents[2] / "frontend" / "src" / "app" / "page.tsx",
    ]
    for path in roots:
        text = path.read_text(encoding="utf-8")
        assert "ROKN Course Studio" in text
        # Product brand must not use legacy casing in these surfaces.
        assert "Rukn Course Studio" not in text
