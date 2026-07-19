"""Tests for app/generation/run_snapshot.py (§2 & §3) - both the pure
`build_run_snapshot` helper and, via `run_generation`, genuine immutability
of a stored snapshot after the admin-knowledge content it was built from
is later edited.
"""

import hashlib

from sqlmodel import Session, SQLModel, create_engine

from app.crud import admin_knowledge_items, courses
from app.data.admin_knowledge.seed_loader import seed
from app.data.course_standard import STANDARD_FILE_NAMES, load_standard_files
from app.generation.orchestrator import run_generation
from app.generation.prompt_compiler import PROMPT_COMPILER_VERSION
from app.generation.run_snapshot import HASH_LENGTH, build_run_snapshot
from app.models.enums import ExplanationLevel, StructureMode
from app.version import get_app_commit


def _short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:HASH_LENGTH]


def test_build_run_snapshot_shape_and_hashing():
    rules_context = {
        STANDARD_FILE_NAMES[0]: "Some standard text",
        STANDARD_FILE_NAMES[1]: "Runtime contract text",
    }

    snapshot = build_run_snapshot(
        rules_context=rules_context,
        generation_preset="balanced",
        source_ids_used=[3, 7],
    )

    assert snapshot["admin_knowledge_snapshot"] == {
        STANDARD_FILE_NAMES[0]: _short_hash("Some standard text"),
        STANDARD_FILE_NAMES[1]: _short_hash("Runtime contract text"),
    }
    assert snapshot["prompt_compiler_version"] == PROMPT_COMPILER_VERSION
    assert snapshot["generation_preset"] == "balanced"
    assert snapshot["provider"] == "fake"
    assert snapshot["model"] == "fake"
    assert snapshot["source_ids_used"] == [3, 7]
    assert snapshot["app_commit"] == get_app_commit()
    assert snapshot["created_at"]


def test_build_run_snapshot_never_includes_raw_admin_knowledge_text():
    long_secret_looking_text = "AUTH_SECRET_KEY=super-secret-value-should-never-appear"
    rules_context = {STANDARD_FILE_NAMES[0]: long_secret_looking_text}

    snapshot = build_run_snapshot(
        rules_context=rules_context, generation_preset="balanced", source_ids_used=[]
    )

    assert long_secret_looking_text not in str(snapshot)
    # Only a short hex hash for that key, never the content itself.
    assert len(snapshot["admin_knowledge_snapshot"][STANDARD_FILE_NAMES[0]]) == HASH_LENGTH


def test_build_run_snapshot_reports_anthropic_model_only_when_configured(monkeypatch):
    import app.config as config_module

    monkeypatch.setattr(config_module.settings, "ai_provider", "anthropic")
    monkeypatch.setattr(config_module.settings, "ai_model_name", "claude-example-model")

    snapshot = build_run_snapshot(rules_context={}, generation_preset="balanced", source_ids_used=[])

    assert snapshot["provider"] == "anthropic"
    assert snapshot["model"] == "claude-example-model"


def test_generation_restores_edited_standard_before_snapshot(tmp_path, monkeypatch):
    import app.generation.orchestrator as orchestrator_module

    monkeypatch.setattr(orchestrator_module.settings, "storage_outputs_dir", tmp_path)

    engine = create_engine(f"sqlite:///{tmp_path / 'snapshot_test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        seed(session)
        key = STANDARD_FILE_NAMES[0]
        original_text = load_standard_files()[key]
        item = admin_knowledge_items.list(session, key=key)[0]
        admin_knowledge_items.update(session, item.id, content_text="attempted mutation")
        course = courses.create(
            session,
            title="Course",
            audience="audience",
            outcome="outcome",
            structure_mode=StructureMode.CONNECTED_NO_MODULES,
            explanation_level=ExplanationLevel.FINAL_ONLY,
        )
        job = run_generation(session, course.id)
        original_hash = job.run_snapshot_json["admin_knowledge_snapshot"][key]
        assert original_hash == _short_hash(original_text)
        restored = admin_knowledge_items.list(session, key=key)[0]
        assert restored.content_text == original_text
