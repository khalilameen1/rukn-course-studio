"""Phase 3: refresh-defaults API, restore dry-run/apply, Anthropic stable cache."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

import app.db as db_module
from app.auth.tokens import create_token
from app.config import settings
from app.crud import admin_knowledge_items
from app.data.admin_knowledge_registry import REFRESHABLE_DEFAULT_KEYS
from app.main import app
from app.seed_admin_knowledge import seed
from app.services.admin_knowledge_backup import (
    restore_admin_knowledge,
    snapshot_admin_knowledge,
)


@pytest.fixture()
def db_client(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'ak_p3.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "storage")
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    with Session(engine) as session:
        seed(session)
    with TestClient(app) as test_client:
        yield test_client, engine


@pytest.fixture()
def auth_headers(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "admin_username", "admin")
    monkeypatch.setattr(settings, "admin_password", "s3cret")
    monkeypatch.setattr(settings, "auth_secret_key", "test-secret-key")
    token = create_token("admin", "test-secret-key")
    return {"Authorization": f"Bearer {token}"}


def test_refresh_defaults_api_dry_run(db_client, auth_headers):
    test_client, _ = db_client
    response = test_client.post(
        "/admin/knowledge/refresh-defaults?dry_run=true&confirm=false",
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["applied"] is False
    assert body["dry_run"] is True
    assert body["would_refresh_count"] >= 1
    assert set(body["would_refresh"]).issubset(set(REFRESHABLE_DEFAULT_KEYS))


def test_refresh_defaults_api_apply(db_client, auth_headers):
    test_client, engine = db_client
    key = next(iter(REFRESHABLE_DEFAULT_KEYS))
    with Session(engine) as session:
        row = admin_knowledge_items.list(session, key=key, is_active=True)[0]
        admin_knowledge_items.update(
            session, row.id, content_text="operator-edited-refreshable"
        )
        before_id = row.id

    response = test_client.post(
        "/admin/knowledge/refresh-defaults?dry_run=false&confirm=true",
        headers=auth_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["applied"] is True
    assert key in body["refreshed"]

    with Session(engine) as session:
        old = admin_knowledge_items.get(session, before_id)
        assert old is not None
        assert old.is_active is False
        assert old.content_text == "operator-edited-refreshable"
        active = admin_knowledge_items.list(session, key=key, is_active=True)
        assert len(active) == 1
        assert active[0].id != before_id
        assert active[0].content_text != "operator-edited-refreshable"


def test_list_key_versions(db_client, auth_headers):
    test_client, engine = db_client
    with Session(engine) as session:
        row = admin_knowledge_items.list(session, key="rukn_core_rules")[0]
        admin_knowledge_items.create(
            session,
            key="rukn_core_rules",
            title="Archive",
            item_type=row.item_type,
            content_text="old",
            is_active=False,
            version=0,
        )

    response = test_client.get(
        "/admin/knowledge/keys/rukn_core_rules/versions",
        headers=auth_headers,
    )
    assert response.status_code == 200
    versions = response.json()
    assert len(versions) >= 2
    assert all(v["key"] == "rukn_core_rules" for v in versions)


def test_restore_dry_run_and_apply(db_client, auth_headers, tmp_path):
    _, engine = db_client
    with Session(engine) as session:
        snap = snapshot_admin_knowledge(session, reason="phase3_test")
        from pathlib import Path

        path = Path(snap["path"])
        row = admin_knowledge_items.list(session, key="rukn_core_rules", is_active=True)[0]
        admin_knowledge_items.update(
            session, row.id, content_text="mutated-before-restore"
        )
        before_version = row.version

        dry = restore_admin_knowledge(session, path, dry_run=True, confirm=False)
        assert dry["applied"] is False
        assert dry["would_restore_count"] >= 1

        applied = restore_admin_knowledge(
            session, path, dry_run=False, confirm=True, actor="test"
        )
        assert applied["applied"] is True
        assert applied["restored_count"] >= 1

        active = admin_knowledge_items.list(
            session, key="rukn_core_rules", is_active=True
        )[0]
        assert active.version > before_version
        assert active.content_text != "mutated-before-restore"


def test_list_backups_endpoint(db_client, auth_headers):
    test_client, engine = db_client
    with Session(engine) as session:
        snapshot_admin_knowledge(session, reason="list_test")

    response = test_client.get("/admin/knowledge/backups", headers=auth_headers)
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) >= 1
    assert "name" in rows[0]
