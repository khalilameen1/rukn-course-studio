"""Phase 1: canonical package, hard purge, fingerprint, and read-only API."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app import models  # noqa: F401
from app.config import settings
from app.data.admin_knowledge.seed_loader import canonical_items, reset_standard, seed
from app.data.admin_knowledge_registry import STABLE_RULE_KEYS, STAGE_RULE_KEYS
from app.data.course_standard import (
    STANDARD_DIRECTORY,
    STANDARD_FILE_NAMES,
    STANDARD_VERSION,
    load_standard_files,
    standard_fingerprint,
    standard_manifest,
)
from app.db import get_session
from app.generation.knowledge_packs import build_stage_rules_pack
from app.main import app
from app.models.admin_knowledge import AdminKnowledgeItem
from app.models.course import Course
from app.models.enums import ItemType, StructureMode
from app.models.generation_job import GenerationJob
from app.prompts.prompt_registry import PipelineStage

EXPECTED_STANDARD_FINGERPRINT = (
    "6dc4cd43dac482eea646492659116eb321f14f0f64ff9739a165d4194ea3fe94"
)


@pytest.fixture()
def engine(tmp_path, monkeypatch):
    storage = tmp_path / "storage"
    storage.mkdir()
    monkeypatch.setattr(settings, "storage_dir", storage)
    db_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(db_engine)
    return db_engine


def test_embedded_package_is_exactly_14_ordered_markdown_files():
    actual = tuple(path.name for path in STANDARD_DIRECTORY.glob("*.md"))
    assert set(actual) == set(STANDARD_FILE_NAMES)
    assert len(actual) == 14
    files = load_standard_files()
    assert tuple(files) == STANDARD_FILE_NAMES
    assert STANDARD_VERSION == "1.3-spoken-variety-integrity"
    assert standard_manifest()["file_count"] == 14


def test_fingerprint_covers_version_order_names_and_content():
    files = load_standard_files()
    original = standard_fingerprint(files)
    assert original == EXPECTED_STANDARD_FINGERPRINT
    changed = dict(files)
    changed[STANDARD_FILE_NAMES[-1]] += "\nchanged"
    assert standard_fingerprint(changed) != original
    reversed_files = dict(reversed(list(files.items())))
    with pytest.raises(ValueError, match="canonical load order"):
        standard_fingerprint(reversed_files)


def test_every_generation_stage_uses_the_whole_standard():
    files = load_standard_files()
    assert STABLE_RULE_KEYS == STANDARD_FILE_NAMES
    assert set(STAGE_RULE_KEYS) == set(PipelineStage)
    for stage, keys in STAGE_RULE_KEYS.items():
        assert keys == STANDARD_FILE_NAMES
        pack = build_stage_rules_pack(files, stage)
        body = "\n".join(pack.values())
        for name in STANDARD_FILE_NAMES:
            assert body.count(f"### {name}") == 1
            assert body.count(files[name]) == 1


def test_seed_permanently_purges_legacy_rows_snapshots_and_backup_files(engine):
    with Session(engine) as session:
        session.add(
            AdminKnowledgeItem(
                key="retired_custom_key",
                title="Retired",
                item_type=ItemType.MARKDOWN,
                content_text="old rules",
                version=9,
                is_active=False,
            )
        )
        course = Course(
            title="Old course",
            audience="Learner",
            outcome="Outcome",
            structure_mode=StructureMode.CONNECTED_NO_MODULES,
            active_rules_snapshot_json={"retired_custom_key": "hash"},
            generation_context_snapshot_json={"admin_knowledge_fingerprint": "old"},
        )
        session.add(course)
        session.commit()
        session.refresh(course)
        session.add(
            GenerationJob(
                course_id=course.id,
                run_snapshot_json={
                    "admin_knowledge_snapshot": {"retired_custom_key": "hash"}
                },
            )
        )
        session.commit()

        backup_dir = Path(settings.storage_dir) / "backups" / "admin_knowledge"
        backup_dir.mkdir(parents=True)
        (backup_dir / "retired.json").write_text("{}", encoding="utf-8")

        report = seed(session)
        assert report["changed"] is True
        assert report["inserted_rows"] == 14
        assert report["cleared_course_snapshots"] == 1
        assert report["cleared_job_snapshots"] == 1
        assert report["deleted_backup_files"] == 1
        assert not backup_dir.exists()

        rows = list(session.exec(select(AdminKnowledgeItem)))
        assert [row.key for row in canonical_items(session)] == list(STANDARD_FILE_NAMES)
        assert len(rows) == 14
        assert all(row.is_active and row.version == 1 for row in rows)
        assert not any(row.key == "retired_custom_key" for row in rows)

        session.refresh(course)
        assert course.active_rules_snapshot_json is None
        assert course.generation_context_snapshot_json is None
        job = session.exec(select(GenerationJob)).one()
        assert job.run_snapshot_json is None

        row_ids = [row.id for row in canonical_items(session)]
        assert seed(session)["changed"] is False
        assert [row.id for row in canonical_items(session)] == row_ids


def test_reset_always_rebuilds_exact_package(engine):
    with Session(engine) as session:
        seed(session)
        first = canonical_items(session)[0]
        first.content_text = "tampered"
        session.add(first)
        session.commit()
        report = reset_standard(session)
        assert report["removed_rows"] == 14
        assert report["inserted_rows"] == 14
        assert canonical_items(session)[0].content_text == load_standard_files()["README.md"]


def test_admin_api_is_ordered_read_only_and_exposes_manifest(engine):
    with Session(engine) as session:
        seed(session)

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    client = TestClient(app)
    try:
        rows = client.get("/admin/knowledge")
        assert rows.status_code == 200
        assert [row["key"] for row in rows.json()] == list(STANDARD_FILE_NAMES)

        manifest = client.get("/admin/knowledge/manifest")
        assert manifest.status_code == 200
        assert manifest.json()["standard_version"] == STANDARD_VERSION
        assert manifest.json()["file_count"] == 14

        assert client.post("/admin/knowledge", json={}).status_code == 405
        assert client.put("/admin/knowledge/1", json={}).status_code in {404, 405}
        assert client.delete("/admin/knowledge/1").status_code in {404, 405}
        assert client.post("/admin/knowledge/reset").status_code == 400
        reset = client.post("/admin/knowledge/reset?confirm=true")
        assert reset.status_code == 200
        assert reset.json()["inserted_rows"] == 14
    finally:
        app.dependency_overrides.clear()
