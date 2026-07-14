"""Production destructive-action safety: dry-run, confirm, backup, audit, seed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app import models  # noqa: F401
from app.config import settings
from app.crud import admin_knowledge_items
from app.generation.admin_knowledge_cleanup import dedupe_admin_knowledge
from app.models.audit_log import AuditLog
from app.models.enums import ItemType
from app.seed_admin_knowledge import main as seed_main
from app.seed_admin_knowledge import refresh_defaults, seed
from app.services.admin_knowledge_backup import snapshot_admin_knowledge
from app.services.audit import list_recent


@pytest.fixture()
def session(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "storage")
    (tmp_path / "storage").mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{tmp_path / 'safe.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_cleanup_dry_run_changes_nothing_and_audits(session):
    admin_knowledge_items.create(
        session,
        key="k1",
        title="a",
        content_text="1",
        item_type=ItemType.MARKDOWN,
        is_active=True,
        version=1,
    )
    admin_knowledge_items.create(
        session,
        key="k1",
        title="b",
        content_text="2",
        item_type=ItemType.MARKDOWN,
        is_active=True,
        version=2,
    )
    before = [i.is_active for i in admin_knowledge_items.list(session)]
    report = dedupe_admin_knowledge(session, dry_run=True, confirm=False)
    assert report["applied"] is False
    assert report["would_deactivate_count"] == 1
    after = [i.is_active for i in admin_knowledge_items.list(session)]
    assert before == after
    audits = list_recent(session)
    assert any(a.action == "admin_knowledge_cleanup" and a.dry_run for a in audits)


def test_cleanup_confirm_deactivates_only_and_writes_backup(session, tmp_path):
    admin_knowledge_items.create(
        session,
        key="k1",
        title="a",
        content_text="1",
        item_type=ItemType.MARKDOWN,
        is_active=True,
        version=1,
    )
    admin_knowledge_items.create(
        session,
        key="k1",
        title="b",
        content_text="2",
        item_type=ItemType.MARKDOWN,
        is_active=True,
        version=2,
    )
    custom = admin_knowledge_items.create(
        session,
        key="custom_unique_key",
        title="mine",
        content_text="keep",
        item_type=ItemType.MARKDOWN,
        is_active=True,
        version=1,
    )
    report = dedupe_admin_knowledge(session, dry_run=False, confirm=True)
    assert report["applied"] is True
    assert report["deactivated_count"] == 1
    assert Path(report["backup"]["path"]).is_file()
    active_k1 = [i for i in admin_knowledge_items.list(session, key="k1") if i.is_active]
    assert len(active_k1) == 1
    assert active_k1[0].title == "b"
    still = admin_knowledge_items.get(session, custom.id)
    assert still is not None and still.is_active is True and still.content_text == "keep"
    # Deactivate, do not delete duplicates
    assert len(admin_knowledge_items.list(session, key="k1")) == 2
    audits = list_recent(session)
    assert any(
        a.action == "admin_knowledge_cleanup" and a.confirmed and not a.dry_run for a in audits
    )


def test_snapshot_export_includes_all_rows(session):
    admin_knowledge_items.create(
        session,
        key="x",
        title="t",
        content_text="body",
        item_type=ItemType.MARKDOWN,
        is_active=True,
        version=1,
    )
    meta = snapshot_admin_knowledge(session, reason="test")
    data = json.loads(Path(meta["path"]).read_text(encoding="utf-8"))
    assert data["count"] == 1
    assert data["items"][0]["content_text"] == "body"


def test_refresh_defaults_requires_confirm(session):
    seed(session)
    with pytest.raises(RuntimeError, match="confirmed"):
        refresh_defaults(session, confirmed=False)


def test_refresh_defaults_cli_without_confirm_exits_2():
    assert seed_main(["--refresh-defaults"]) == 2


def test_startup_seed_is_non_destructive(session):
    seed(session)
    custom = admin_knowledge_items.create(
        session,
        key="operator_custom_rule",
        title="Custom",
        content_text="do not touch",
        item_type=ItemType.MARKDOWN,
        is_active=True,
        version=1,
    )
    edited = admin_knowledge_items.list(session, key="rukn_core_rules")[0]
    admin_knowledge_items.update(session, edited.id, content_text="operator edit")
    seed(session)
    assert admin_knowledge_items.get(session, custom.id).content_text == "do not touch"
    assert admin_knowledge_items.get(session, edited.id).content_text == "operator edit"


def test_refresh_preserves_custom_unique_knowledge(session):
    seed(session)
    custom = admin_knowledge_items.create(
        session,
        key="my_shop_voice",
        title="Voice",
        content_text="custom",
        item_type=ItemType.MARKDOWN,
        is_active=True,
        version=1,
    )
    refresh_defaults(session, confirmed=True)
    row = admin_knowledge_items.get(session, custom.id)
    assert row is not None
    assert row.content_text == "custom"
    assert row.is_active is True
