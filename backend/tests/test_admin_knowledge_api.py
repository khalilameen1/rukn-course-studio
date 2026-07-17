"""HTTP API tests for Admin Knowledge Center — list, auth, dedupe, seed safety."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

import app.db as db_module
from app.auth.tokens import create_token
from app.config import settings
from app.crud import admin_knowledge_items
from app.main import app
from app.models.enums import ItemType
from app.seed_admin_knowledge import refresh_defaults, seed

client = TestClient(app)


@pytest.fixture()
def db_client(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'admin_api.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db_module, "engine", engine)
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


ADMIN_ROUTES = [
    ("GET", "/admin/knowledge"),
    ("POST", "/admin/knowledge"),
    ("PUT", "/admin/knowledge/1"),
    ("DELETE", "/admin/knowledge/1"),
    ("POST", "/admin/knowledge/1/activate"),
    ("POST", "/admin/knowledge/cleanup-duplicates"),
]


@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
def test_admin_knowledge_routes_require_auth_when_enabled(method, path, monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "auth_secret_key", "test-secret-key")
    response = client.request(method, path)
    assert response.status_code in (401, 403, 404)


def test_list_default_returns_one_primary_per_key(db_client, auth_headers):
    test_client, engine = db_client
    with Session(engine) as session:
        admin_knowledge_items.create(
            session,
            key="rukn_core_rules",
            title="Duplicate core",
            item_type=ItemType.MARKDOWN,
            content_text="dup",
            is_active=True,
            version=99,
        )
    response = test_client.get("/admin/knowledge", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()
    keys = [i["key"] for i in items]
    assert keys.count("rukn_core_rules") == 1


def test_list_include_inactive_shows_archives(db_client, auth_headers):
    test_client, engine = db_client
    with Session(engine) as session:
        admin_knowledge_items.create(
            session,
            key="rukn_core_rules",
            title="Inactive backup",
            item_type=ItemType.MARKDOWN,
            content_text="backup",
            is_active=False,
            version=0,
        )
    default = test_client.get("/admin/knowledge", headers=auth_headers).json()
    all_rows = test_client.get(
        "/admin/knowledge?active_only=false&include_inactive=true",
        headers=auth_headers,
    ).json()
    assert len(all_rows) >= len(default) + 1


def test_seed_does_not_overwrite_edited_row(db_client):
    _, engine = db_client
    with Session(engine) as session:
        row = admin_knowledge_items.list(session, key="rukn_core_rules")[0]
        admin_knowledge_items.update(session, row.id, content_text="operator-edited-core")
        seed(session)
        reloaded = admin_knowledge_items.get(session, row.id)
        assert reloaded.content_text == "operator-edited-core"


def test_refresh_defaults_requires_confirm(db_client):
    _, engine = db_client
    with Session(engine) as session:
        with pytest.raises(RuntimeError, match="confirmed=True"):
            refresh_defaults(session, confirmed=False)


def test_update_is_active_deactivates_sibling_versions(db_client, auth_headers):
    test_client, engine = db_client
    with Session(engine) as session:
        older = admin_knowledge_items.list(session, key="rukn_core_rules")[0]
        newer = admin_knowledge_items.create(
            session,
            key="rukn_core_rules",
            title="Newer core",
            item_type=ItemType.MARKDOWN,
            content_text="newer",
            is_active=False,
            version=older.version + 1,
        )
        newer_id = newer.id
        older_id = older.id

    response = test_client.put(
        f"/admin/knowledge/{newer_id}",
        headers=auth_headers,
        json={"is_active": True},
    )
    assert response.status_code == 200
    with Session(engine) as session:
        assert admin_knowledge_items.get(session, newer_id).is_active is True
        assert admin_knowledge_items.get(session, older_id).is_active is False


def test_course_transcript_text_not_in_admin_knowledge(db_client, auth_headers):
    test_client, _ = db_client
    course = test_client.post(
        "/courses",
        headers=auth_headers,
        json={
            "title": "Scoped",
            "audience": "shops",
            "outcome": "ads",
            "structure_mode": "connected_no_modules",
        },
    ).json()
    unique = "UNIQUE_COURSE_TRANSCRIPT_MARKER_XYZ_123"
    test_client.post(
        f"/courses/{course['id']}/sources/notes",
        headers=auth_headers,
        json={
            "text": unique,
            "title": "Tape",
            "source_category": "transcript",
            "priority": "medium",
            "include_in_generation": True,
        },
    )
    admin_items = test_client.get("/admin/knowledge", headers=auth_headers).json()
    blob = " ".join((i.get("content_text") or "") + (i.get("title") or "") for i in admin_items)
    assert unique not in blob


def test_create_active_deactivates_sibling_primary(db_client, auth_headers):
    test_client, engine = db_client
    with Session(engine) as session:
        existing = [
            i
            for i in admin_knowledge_items.list(session, key="rukn_forbidden_phrases")
            if i.is_active
        ]
        assert len(existing) == 1
        old_id = existing[0].id

    response = test_client.post(
        "/admin/knowledge",
        headers=auth_headers,
        json={
            "key": "rukn_forbidden_phrases",
            "title": "Replacement phrases",
            "item_type": "json",
            "content_text": json.dumps(
                {
                    "description": "test",
                    "phrases": [
                        {
                            "phrase": "bad phrase",
                            "severity": "high",
                            "replacement_hint": "cut it",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            "is_active": True,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["is_active"] is True
    assert body["version"] >= 2
    assert body["id"] != old_id

    with Session(engine) as session:
        assert admin_knowledge_items.get(session, old_id).is_active is False
        actives = [
            i
            for i in admin_knowledge_items.list(session, key="rukn_forbidden_phrases")
            if i.is_active
        ]
        assert len(actives) == 1
        assert actives[0].id == body["id"]


def test_catalog_endpoint_lists_system_keys(db_client, auth_headers):
    test_client, _ = db_client
    response = test_client.get("/admin/knowledge/catalog", headers=auth_headers)
    assert response.status_code == 200
    rows = response.json()
    keys = {r["key"] for r in rows}
    assert "rukn_cost_hygiene_trusted_knowledge" in keys
    assert "rukn_generation_presets" in keys
    hygiene = next(r for r in rows if r["key"] == "rukn_cost_hygiene_trusted_knowledge")
    assert hygiene["stable"] is True
