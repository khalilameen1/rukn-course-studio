"""Generation must load one active primary Admin Knowledge row per key."""

from sqlmodel import Session, SQLModel, create_engine

from app.crud import admin_knowledge_items
from app.generation.orchestrator import _load_active_rules
from app.models.enums import ItemType


def test_load_active_rules_uses_primary_when_duplicates_exist(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'rules.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        admin_knowledge_items.create(
            session,
            key="rukn_test_rule",
            title="older",
            item_type=ItemType.MARKDOWN,
            content_text="OLD RULE TEXT",
            is_active=True,
            version=1,
        )
        admin_knowledge_items.create(
            session,
            key="rukn_test_rule",
            title="newer",
            item_type=ItemType.MARKDOWN,
            content_text="NEW RULE TEXT",
            is_active=True,
            version=2,
        )
        admin_knowledge_items.create(
            session,
            key="rukn_test_rule",
            title="inactive",
            item_type=ItemType.MARKDOWN,
            content_text="INACTIVE",
            is_active=False,
            version=0,
        )
        rules = _load_active_rules(session)
        assert rules["rukn_test_rule"] == "NEW RULE TEXT"
        assert "INACTIVE" not in rules.values()


def test_inactive_admin_knowledge_not_loaded(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'rules2.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        admin_knowledge_items.create(
            session,
            key="rukn_inactive_only",
            title="off",
            item_type=ItemType.MARKDOWN,
            content_text="should not load",
            is_active=False,
        )
        rules = _load_active_rules(session)
        assert "rukn_inactive_only" not in rules


def test_source_authority_firewall_reaches_map_stage_packed_rules():
    from app.generation.prompt_compiler import select_packed_rules_for_stage
    from app.prompts.prompt_registry import PipelineStage
    from app.seed_admin_knowledge import SEED_ITEMS

    all_rules = {item["key"]: item["content_text"] for item in SEED_ITEMS if item.get("content_text")}
    packed = select_packed_rules_for_stage(all_rules, PipelineStage.BUILD_COURSE_MAP)
    body = " ".join(packed.values()).lower()
    assert "source" in body
    assert "authority" in body or "firewall" in body or "untrusted" in body
