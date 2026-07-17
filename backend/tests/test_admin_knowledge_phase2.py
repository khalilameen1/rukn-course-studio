"""Phase 2 Admin Knowledge: JSON schemas, save-as-new-version, pack sections."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

import app.db as db_module
from app.config import settings
from app.auth.tokens import create_token
from app.crud import admin_knowledge_items
from app.data.admin_knowledge.json_items import (
    FORBIDDEN_PHRASES,
    GENERATION_PRESETS,
    QUALITY_RUBRIC,
)
from app.generation.knowledge_packs import (
    _split_numbered_sections,
    _split_sections_with_anchors,
)
from app.main import app
from app.models.enums import ItemType
from app.schemas.admin_knowledge_content import validate_admin_knowledge_content
from app.seed_admin_knowledge import SEED_ITEMS, seed


@pytest.fixture()
def db_client(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'ak_p2.db'}")
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


def test_seed_json_constants_pass_schema():
    validate_admin_knowledge_content(
        key="rukn_forbidden_phrases",
        item_type="json",
        content_text=json.dumps(FORBIDDEN_PHRASES),
    )
    validate_admin_knowledge_content(
        key="rukn_quality_rubric",
        item_type="json",
        content_text=json.dumps(QUALITY_RUBRIC),
    )
    validate_admin_knowledge_content(
        key="rukn_generation_presets",
        item_type="json",
        content_text=json.dumps(GENERATION_PRESETS),
    )


def test_invalid_forbidden_phrases_rejected():
    with pytest.raises(ValueError, match="schema validation"):
        validate_admin_knowledge_content(
            key="rukn_forbidden_phrases",
            item_type="json",
            content_text='{"description":"x","phrases":[]}',
        )


def test_put_content_creates_new_version(db_client, auth_headers, tmp_path, monkeypatch):
    test_client, engine = db_client
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "storage2")
    settings.storage_dir.mkdir(parents=True, exist_ok=True)

    with Session(engine) as session:
        row = next(
            i
            for i in admin_knowledge_items.list(session, key="rukn_writing_style")
            if i.is_active
        )
        old_id = row.id
        old_version = row.version

    response = test_client.put(
        f"/admin/knowledge/{old_id}?confirm=true&dry_run=false",
        headers=auth_headers,
        json={"content_text": "# Revised writing style\n\n- New bullet."},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] != old_id
    assert body["version"] == old_version + 1
    assert body["is_active"] is True
    assert "Revised writing style" in (body["content_text"] or "")

    with Session(engine) as session:
        assert admin_knowledge_items.get(session, old_id).is_active is False
        actives = [
            i
            for i in admin_knowledge_items.list(session, key="rukn_writing_style")
            if i.is_active
        ]
        assert len(actives) == 1
        assert actives[0].id == body["id"]


def test_put_in_place_overwrites_same_row(db_client, auth_headers):
    test_client, engine = db_client
    with Session(engine) as session:
        row = next(
            i
            for i in admin_knowledge_items.list(session, key="rukn_writing_style")
            if i.is_active
        )
        old_id = row.id

    response = test_client.put(
        f"/admin/knowledge/{old_id}",
        headers=auth_headers,
        json={
            "content_text": "# In-place overwrite\n",
            "in_place": True,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == old_id
    assert "In-place overwrite" in (body["content_text"] or "")


def test_section_anchor_optional_parse():
    text = "## 1. First section\n\nbody1\n\n## 2. Second {#second-id}\n\nbody2\n"
    by_num = _split_numbered_sections(text)
    assert 1 in by_num and 2 in by_num
    _, by_anchor = _split_sections_with_anchors(text)
    assert "second-id" in by_anchor
    assert "body2" in by_anchor["second-id"]


def test_seed_items_count_unchanged():
    assert len(SEED_ITEMS) == 27
