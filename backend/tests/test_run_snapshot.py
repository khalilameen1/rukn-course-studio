"""Unified v2 run snapshot and fail-closed fingerprint tests."""

from copy import deepcopy

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.ai.provider import CourseBrief
from app.crud import admin_knowledge_items, courses
from app.data.admin_knowledge.seed_loader import seed
from app.data.course_standard import STANDARD_FILE_NAMES, STANDARD_VERSION, load_standard_files
from app.generation.domain_adapters import build_course_quality_contract
from app.generation.orchestrator import run_generation
from app.generation.quality.context_snapshot import (
    REQUIRED_STATE_KEYS,
    SnapshotMismatchError,
    assert_snapshot_compatible,
    build_config_inputs,
    build_generation_context_snapshot,
    fingerprint_value,
)
from app.models.enums import ExplanationLevel, GenerationPreset, StructureMode, TargetMarket
from app.schemas.generation import CourseMap, CourseThesis, ModulePlan, ReelPlan


def _brief(**changes) -> CourseBrief:
    values = {
        "title": "Course",
        "audience": "Beginners",
        "outcome": "Build one result",
        "structure_mode": StructureMode.CONNECTED_NO_MODULES,
        "explanation_level": ExplanationLevel.FINAL_ONLY,
        "generation_preset": GenerationPreset.BALANCED,
        "target_market": TargetMarket.EGYPT,
    }
    values.update(changes)
    return CourseBrief(**values)


def _thesis(**changes) -> CourseThesis:
    values = {
        "final_student_outcome": "Build one result",
        "audience_and_starting_level": "Beginners",
        "practical_deliverable": "Result",
    }
    values.update(changes)
    return CourseThesis(**values)


def _map(thesis: CourseThesis | None = None, *, title: str = "Course") -> CourseMap:
    thesis = thesis or _thesis()
    return CourseMap(
        course_title=title,
        main_thread="thread",
        thesis=thesis,
        modules=[
            ModulePlan(
                module_id="m1",
                title="Module",
                purpose="purpose",
                reels=[
                    ReelPlan(
                        reel_id="r1",
                        title="Lesson",
                        purpose="teach",
                        distinct_teaching_outcome="do",
                    )
                ],
            )
        ],
    )


def _snapshot(**changes):
    brief = changes.pop("brief", _brief())
    thesis = changes.pop("thesis", _thesis())
    course_map = changes.pop("course_map", _map(thesis))
    contract = changes.pop("contract", build_course_quality_contract(brief))
    return build_generation_context_snapshot(
        course_id=1,
        brief=brief,
        contract=contract,
        thesis=thesis,
        course_map=course_map,
        source_ids=[3],
        source_fingerprints={"3": fingerprint_value("RAW_SOURCE_BODY_DO_NOT_STORE")},
        research_blob={"facts": ["one"]},
        admin_rules=load_standard_files(),
        generation_settings={"generation_preset": "balanced", "temperature": 0},
        **changes,
    )


def test_snapshot_contains_every_required_frozen_state_and_one_fingerprint():
    snapshot = _snapshot()
    dumped = snapshot.model_dump(mode="json")

    assert snapshot.version == "2.0"
    assert set(REQUIRED_STATE_KEYS).issubset(dumped)
    assert len(snapshot.CONFIG_FINGERPRINT) == 64
    assert snapshot.ACTIVE_RULE_PACK["standard_version"] == STANDARD_VERSION
    assert snapshot.ACTIVE_RULE_PACK["file_count"] == 14
    assert "settings_fingerprint" not in dumped
    assert "admin_knowledge_snapshot" not in dumped
    assert_snapshot_compatible(dumped, action="test")


def test_snapshot_never_contains_raw_standard_or_source_text():
    snapshot = _snapshot()
    rendered = str(snapshot.model_dump(mode="json"))
    assert load_standard_files()[STANDARD_FILE_NAMES[0]] not in rendered
    assert "RAW_SOURCE_BODY_DO_NOT_STORE" not in str(snapshot.SOURCE_LEDGER)


def test_config_fingerprint_changes_for_every_output_affecting_input():
    base = build_config_inputs(
        active_rule_pack={"standard_version": "1.3", "fingerprint": "rules-a"},
        brief={"title": "A"},
        thesis={"outcome": "A"},
        source_ledger=[{"source_id": 1, "content_sha256": "a"}],
        research_result={"facts": ["a"]},
        market="egypt",
        course_type="practical_skill",
        language_profile={"presenter_language": "ar"},
        address_form="masculine",
        quality_mode="premium",
        provider_name="fake",
        model_name="fake",
        generation_settings={"temperature": 0},
        approved_map={"modules": ["a"]},
    )
    mutations = {
        "package version": ("STANDARD_PACKAGE", {"standard_version": "1.4", "fingerprint": "rules-b"}),
        "brief": ("BRIEF", {"title": "B"}),
        "thesis": ("COURSE_THESIS", {"outcome": "B"}),
        "selected sources": ("SELECTED_SOURCES", [{"source_id": 2, "content_sha256": "b"}]),
        "research result": ("RESEARCH_RESULT_SHA256", fingerprint_value({"facts": ["b"]})),
        "market": ("MARKET", "gulf"),
        "course type": ("COURSE_TYPE", "language_learning"),
        "language profile": ("LANGUAGE_PROFILE", {"presenter_language": "en"}),
        "address form": ("ADDRESS_FORM", "feminine"),
        "quality mode": ("QUALITY_MODE", "preview"),
        "model": ("MODEL", "model-b"),
        "generation settings": ("GENERATION_SETTINGS", {"temperature": 1}),
        "approved map": ("APPROVED_MAP", {"modules": ["b"]}),
    }
    baseline = fingerprint_value(base)
    for label, (key, value) in mutations.items():
        changed = deepcopy(base)
        changed[key] = value
        assert fingerprint_value(changed) != baseline, label


def test_mismatch_prevents_resume_and_export():
    snapshot = _snapshot()
    changed = deepcopy(snapshot.CONFIG_INPUTS)
    changed["MODEL"] = "different-model"

    with pytest.raises(SnapshotMismatchError, match="output-affecting configuration changed"):
        assert_snapshot_compatible(snapshot, current_config_inputs=changed, action="resume")
    with pytest.raises(SnapshotMismatchError, match="output-affecting configuration changed"):
        assert_snapshot_compatible(snapshot, current_config_inputs=changed, action="export")


def test_tampering_with_embedded_inputs_invalidates_frozen_snapshot():
    snapshot = _snapshot().model_dump(mode="json")
    snapshot["CONFIG_INPUTS"]["BRIEF"]["title"] = "tampered"
    with pytest.raises(SnapshotMismatchError, match="does not match embedded inputs"):
        assert_snapshot_compatible(snapshot, action="resume")


def test_generation_freezes_snapshot_and_seed_preserves_canonical_v2(tmp_path, monkeypatch):
    import app.generation.orchestrator as orchestrator_module

    monkeypatch.setattr(orchestrator_module.settings, "storage_outputs_dir", tmp_path)
    engine = create_engine(f"sqlite:///{tmp_path / 'snapshot_test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        seed(session)
        course = courses.create(
            session,
            title="Course",
            audience="audience",
            outcome="outcome",
            structure_mode=StructureMode.CONNECTED_NO_MODULES,
            explanation_level=ExplanationLevel.FINAL_ONLY,
        )
        job = run_generation(session, course.id)
        frozen = deepcopy(job.run_snapshot_json)
        assert frozen and frozen["STAGE_CONTRACT_STATE"]["lesson_writing"] == "pending"

        item = admin_knowledge_items.list(session, key=STANDARD_FILE_NAMES[0])[0]
        admin_knowledge_items.update(session, item.id, content_text="attempted mutation")
        seed(session)
        session.refresh(job)

        assert job.run_snapshot_json == frozen
        assert_snapshot_compatible(job.run_snapshot_json, action="inspect old run")
