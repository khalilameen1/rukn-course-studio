"""Tests for app/seed_admin_knowledge.py - idempotent seed + safe refresh."""

import json

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.crud import admin_knowledge_items
from app.models.enums import ItemType
from app.seed_admin_knowledge import (
    FORBIDDEN_PHRASES,
    HIGH_SIGNAL_REEL_DOCTRINE,
    QUALITY_RUBRIC,
    REFRESHABLE_DEFAULT_KEYS,
    REQUIRED_KEYS,
    TELEPROMPTER_DOCX_CONTRACT,
    main,
    refresh_defaults,
    seed,
)


@pytest.fixture()
def session(tmp_path, monkeypatch):
    from app import models  # noqa: F401 — register AuditLog etc.
    from app.config import settings

    monkeypatch.setattr(settings, "storage_dir", tmp_path / "storage")
    (tmp_path / "storage").mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_seed_creates_every_required_key(session):
    seed(session)

    keys = {item.key for item in admin_knowledge_items.list(session)}
    for required_key in REQUIRED_KEYS:
        assert required_key in keys


def test_seed_is_idempotent_does_not_duplicate_rows(session):
    seed(session)
    seed(session)
    seed(session)

    for required_key in REQUIRED_KEYS:
        rows = admin_knowledge_items.list(session, key=required_key)
        assert len(rows) == 1


def test_seed_does_not_overwrite_a_user_edited_item(session):
    seed(session)
    original = admin_knowledge_items.list(session, key="rukn_core_rules")[0]

    admin_knowledge_items.update(session, original.id, content_text="User's own edited text")

    seed(session)

    reloaded = admin_knowledge_items.list(session, key="rukn_core_rules")
    assert len(reloaded) == 1
    assert reloaded[0].content_text == "User's own edited text"


def test_seed_does_not_overwrite_a_deactivated_item(session):
    """Re-running seed must not reactivate/replace an item a user deliberately
    turned off, either - "already has at least one row" is enough to skip."""
    seed(session)
    original = admin_knowledge_items.list(session, key="rukn_quality_rubric")[0]

    admin_knowledge_items.update(session, original.id, is_active=False)
    seed(session)

    reloaded = admin_knowledge_items.list(session, key="rukn_quality_rubric")
    assert len(reloaded) == 1
    assert reloaded[0].is_active is False


def test_teleprompter_contract_item_states_what_the_docx_is_and_is_not(session):
    seed(session)

    item = admin_knowledge_items.list(session, key="rukn_teleprompter_docx_contract")[0]
    content = item.content_text.lower()

    assert "teleprompter" in content
    assert "not a book" in content
    assert "not a student handout" in content
    assert "not a preparation report" in content
    assert "prepared by ai" in content


def test_generation_presets_item_lists_all_five_presets_with_balanced_default(session):
    seed(session)

    item = admin_knowledge_items.list(session, key="rukn_generation_presets")[0]
    data = json.loads(item.content_text)
    assert data["default"] == "balanced"
    ids = {p["id"] for p in data["presets"]}
    assert ids == {"conservative", "balanced", "creative", "fusion", "strict_teleprompter"}


def test_high_signal_doctrine_item_states_hook_loop_and_adversarial_process(session):
    seed(session)

    item = admin_knowledge_items.list(session, key="rukn_high_signal_reel_doctrine")[0]
    content = item.content_text.lower()
    assert "hook" in content
    assert "loop" in content
    assert "high-signal" in content or "high signal" in content
    assert "draft a" in content
    assert "adversarial" in content
    assert "master version" in content
    assert "variable length" in content
    assert "template" in content
    assert "scientific" in content


def test_refresh_defaults_updates_selected_keys_and_keeps_backup(session):
    seed(session)
    old = admin_knowledge_items.list(session, key="rukn_forbidden_phrases")[0]
    admin_knowledge_items.update(session, old.id, content_text='{"phrases":[]}')

    refreshed = refresh_defaults(session, confirmed=True)
    assert "rukn_forbidden_phrases" in refreshed

    rows = admin_knowledge_items.list(session, key="rukn_forbidden_phrases")
    assert len(rows) == 2
    active = next(r for r in rows if r.is_active)
    backups = [r for r in rows if not r.is_active]
    assert len(backups) == 1
    assert backups[0].content_text == '{"phrases":[]}'
    assert "(backup " in backups[0].title
    assert active.version == old.version + 1
    assert json.loads(active.content_text)["phrases"] == FORBIDDEN_PHRASES["phrases"]

    # Doctrine / rubric / contract refresh to current code defaults.
    doctrine = next(
        r for r in admin_knowledge_items.list(session, key="rukn_high_signal_reel_doctrine") if r.is_active
    )
    assert doctrine.content_text == HIGH_SIGNAL_REEL_DOCTRINE
    rubric = next(
        r for r in admin_knowledge_items.list(session, key="rukn_quality_rubric") if r.is_active
    )
    assert json.loads(rubric.content_text)["checks"] == QUALITY_RUBRIC["checks"]
    contract = next(
        r
        for r in admin_knowledge_items.list(session, key="rukn_teleprompter_docx_contract")
        if r.is_active
    )
    assert contract.content_text == TELEPROMPTER_DOCX_CONTRACT


def test_refresh_defaults_does_not_touch_unrelated_custom_or_core_keys(session):
    seed(session)
    core = admin_knowledge_items.list(session, key="rukn_core_rules")[0]
    admin_knowledge_items.update(session, core.id, content_text="Custom core rules")

    admin_knowledge_items.create(
        session,
        key="my_custom_rules",
        title="My Custom Rules",
        item_type=ItemType.MARKDOWN,
        content_text="do not touch",
        version=1,
        is_active=True,
    )

    refresh_defaults(session, confirmed=True)

    core_after = admin_knowledge_items.list(session, key="rukn_core_rules")
    assert len(core_after) == 1
    assert core_after[0].content_text == "Custom core rules"

    custom = admin_knowledge_items.list(session, key="my_custom_rules")
    assert len(custom) == 1
    assert custom[0].content_text == "do not touch"

    presets = admin_knowledge_items.list(session, key="rukn_generation_presets")
    assert len(presets) == 1  # not in REFRESHABLE_DEFAULT_KEYS


def test_refresh_defaults_cli_requires_confirm(monkeypatch):
    # Avoid touching the real DB in main()'s init_db/engine path - this
    # test only asserts the confirm gate exits before work.
    monkeypatch.setattr("app.seed_admin_knowledge.init_db", lambda: None)
    code = main(["--refresh-defaults"])
    assert code == 2


def test_refreshable_keys_are_documented_subset():
    # Guard against accidentally refreshing every SEED item.
    assert "rukn_forbidden_phrases" in REFRESHABLE_DEFAULT_KEYS
    assert "rukn_quality_rubric" in REFRESHABLE_DEFAULT_KEYS
    assert "rukn_high_signal_reel_doctrine" in REFRESHABLE_DEFAULT_KEYS
    assert "rukn_teleprompter_docx_contract" in REFRESHABLE_DEFAULT_KEYS
    assert "rukn_core_rules" not in REFRESHABLE_DEFAULT_KEYS
    assert "rukn_generation_presets" not in REFRESHABLE_DEFAULT_KEYS
