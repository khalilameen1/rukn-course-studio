"""Tests for app/generation/run_snapshot.py (§2 & §3) - both the pure
`build_run_snapshot` helper and, via `run_generation`, genuine immutability
of a stored snapshot after the admin-knowledge content it was built from
is later edited.
"""

import hashlib

from sqlmodel import Session, SQLModel, create_engine

from app.crud import admin_knowledge_items, courses
from app.generation.orchestrator import run_generation
from app.generation.prompt_compiler import PROMPT_COMPILER_VERSION
from app.generation.run_snapshot import HASH_LENGTH, build_run_snapshot
from app.models.enums import ExplanationLevel, ItemType, StructureMode
from app.version import get_app_commit


def _short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:HASH_LENGTH]


def test_build_run_snapshot_shape_and_hashing():
    rules_context = {
        "rukn_core_rules": "Some core rule text",
        "rukn_forbidden_phrases": '{"phrases": []}',
    }

    snapshot = build_run_snapshot(
        rules_context=rules_context,
        generation_preset="balanced",
        source_ids_used=[3, 7],
    )

    assert snapshot["admin_knowledge_snapshot"] == {
        "rukn_core_rules": _short_hash("Some core rule text"),
        "rukn_forbidden_phrases": _short_hash('{"phrases": []}'),
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
    rules_context = {"rukn_core_rules": long_secret_looking_text}

    snapshot = build_run_snapshot(
        rules_context=rules_context, generation_preset="balanced", source_ids_used=[]
    )

    assert long_secret_looking_text not in str(snapshot)
    # Only a short hex hash for that key, never the content itself.
    assert len(snapshot["admin_knowledge_snapshot"]["rukn_core_rules"]) == HASH_LENGTH


def test_build_run_snapshot_reports_anthropic_model_only_when_configured(monkeypatch):
    import app.config as config_module

    monkeypatch.setattr(config_module.settings, "ai_provider", "anthropic")
    monkeypatch.setattr(config_module.settings, "ai_model_name", "claude-example-model")

    snapshot = build_run_snapshot(rules_context={}, generation_preset="balanced", source_ids_used=[])

    assert snapshot["provider"] == "anthropic"
    assert snapshot["model"] == "claude-example-model"


def test_run_snapshot_is_immutable_after_admin_knowledge_is_later_edited(tmp_path, monkeypatch):
    import app.generation.orchestrator as orchestrator_module

    monkeypatch.setattr(orchestrator_module.settings, "storage_outputs_dir", tmp_path)

    engine = create_engine(f"sqlite:///{tmp_path / 'snapshot_test.db'}")
    SQLModel.metadata.create_all(engine)

    original_text = "Original rule text, active during the first run."
    with Session(engine) as session:
        course = courses.create(
            session,
            title="Course",
            audience="audience",
            outcome="outcome",
            structure_mode=StructureMode.CONNECTED_NO_MODULES,
            explanation_level=ExplanationLevel.FINAL_ONLY,
        )
        item = admin_knowledge_items.create(
            session,
            key="rukn_core_rules",
            title="Core rules",
            item_type=ItemType.MARKDOWN,
            content_text=original_text,
            is_active=True,
        )

        job = run_generation(session, course.id)
        job_id = job.id
        course_id = course.id
        original_hash = job.run_snapshot_json["admin_knowledge_snapshot"]["rukn_core_rules"]
        assert original_hash == _short_hash(original_text)

        # Edit the admin knowledge item *after* the run completed.
        admin_knowledge_items.update(session, item.id, content_text="Edited rule text, changed later.")

    # The already-stored job snapshot must still reflect the pre-edit
    # content - never silently updated by the later edit.
    with Session(engine) as session:
        from app.crud import generation_jobs

        reloaded_job = generation_jobs.get(session, job_id)
        assert (
            reloaded_job.run_snapshot_json["admin_knowledge_snapshot"]["rukn_core_rules"]
            == original_hash
        )
        assert reloaded_job.run_snapshot_json["admin_knowledge_snapshot"][
            "rukn_core_rules"
        ] != _short_hash("Edited rule text, changed later.")

        # A brand-new run, by contrast, must pick up the edited content.
        new_job = run_generation(session, course_id)
        assert new_job.run_snapshot_json["admin_knowledge_snapshot"][
            "rukn_core_rules"
        ] == _short_hash("Edited rule text, changed later.")
