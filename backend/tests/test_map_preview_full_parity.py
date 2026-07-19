"""The approved map preview is the immutable full-generation planning input."""

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.ai.fake_provider import FakeProvider
from app.crud import courses, generation_jobs
from app.data.admin_knowledge.seed_loader import seed
from app.generation.map_preview import (
    assert_approved_map_ready,
    build_map_preview,
)
from app.generation.contracts.course_thesis import build_course_thesis_from_brief
from app.ai.provider import CourseBrief
from app.generation.orchestrator import run_generation
from app.generation.quality.context_snapshot import SnapshotMismatchError
from app.models.enums import (
    ExplanationLevel,
    GenerationQualityMode,
    StructureMode,
    WebResearchMode,
)


def _course(session: Session):
    return courses.create(
        session,
        title="Inventory decisions",
        audience="Beginner shop owner",
        outcome="Decide visual weight with contrast",
        structure_mode=StructureMode.CONNECTED_NO_MODULES,
        explanation_level=ExplanationLevel.FINAL_ONLY,
        generation_quality_mode=GenerationQualityMode.PREVIEW,
        web_research_mode=WebResearchMode.DISABLED,
    )


def _engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'preview_parity.db'}")
    SQLModel.metadata.create_all(engine)
    return engine


def test_approved_preview_validates_exact_current_inputs(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        seed(session)
        course = _course(session)
        stats = build_map_preview(
            session,
            course.id,
            provider=FakeProvider(),
            quality_mode=GenerationQualityMode.PREVIEW,
            web_research_mode=WebResearchMode.DISABLED,
        )
        frozen = deepcopy(course.generation_context_snapshot_json)
        assert stats.snapshot_fingerprint
        assert stats.map_text == course.manual_map_text
        assert frozen["CONFIG_INPUTS"]["APPROVED_MAP"] == stats.course_map
        coverage = frozen["COVERAGE_MATRIX"]
        assert coverage["promise_to_lessons"]
        assert coverage["capability_rows"]
        assert coverage["project_rows"]

        approved = assert_approved_map_ready(
            session,
            course.id,
            approved_snapshot_fingerprint=stats.snapshot_fingerprint,
            quality_mode=GenerationQualityMode.PREVIEW,
            web_research_mode=WebResearchMode.DISABLED,
            human_override_hard_limits=False,
        )
        assert approved["CONFIG_FINGERPRINT"] == stats.snapshot_fingerprint

        courses.update(session, course.id, outcome="A different promise")
        with pytest.raises(SnapshotMismatchError, match="configuration changed"):
            assert_approved_map_ready(
                session,
                course.id,
                approved_snapshot_fingerprint=stats.snapshot_fingerprint,
                quality_mode=GenerationQualityMode.PREVIEW,
                web_research_mode=WebResearchMode.DISABLED,
                human_override_hard_limits=False,
            )


def test_generate_api_requires_and_attaches_approved_snapshot(
    tmp_path, monkeypatch
):
    import app.db as db_module
    import app.routers.generation as generation_router

    engine = _engine(tmp_path)
    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(
        generation_router,
        "run_claimed_generation_job",
        lambda *_args, **_kwargs: None,
    )
    with Session(engine) as session:
        seed(session)
        course = _course(session)
        stats = build_map_preview(
            session,
            course.id,
            provider=FakeProvider(),
            quality_mode=GenerationQualityMode.PREVIEW,
            web_research_mode=WebResearchMode.DISABLED,
        )
        course_id = course.id

    from app.main import app

    with TestClient(app) as client:
        missing = client.post(
            f"/courses/{course_id}/generate",
            json={
                "generation_quality_mode": "preview",
                "web_research_mode": "disabled",
            },
        )
        assert missing.status_code == 409

        started = client.post(
            f"/courses/{course_id}/generate",
            json={
                "generation_quality_mode": "preview",
                "web_research_mode": "disabled",
                "map_preview_confirmed": True,
                "approved_snapshot_fingerprint": stats.snapshot_fingerprint,
            },
        )
        assert started.status_code == 201, started.text

    with Session(engine) as session:
        jobs = generation_jobs.list(session, course_id=course_id)
        assert len(jobs) == 1
        job = jobs[0]
        assert job.run_snapshot_json["CONFIG_FINGERPRINT"] == (
            stats.snapshot_fingerprint
        )
        assert job.run_snapshot_json["STAGE_CONTRACT_STATE"][
            "map_preview_confirmed"
        ] is True
        assert job.course_map_json == stats.course_map


def test_generate_map_route_is_removed_from_openapi():
    from app.main import app

    paths = app.openapi()["paths"]
    assert "/courses/{course_id}/generate-map" not in paths
    assert "/courses/{course_id}/map-preview" in paths


def test_course_size_is_derived_from_capabilities_not_a_fixed_lesson_count():
    base = {
        "title": "Operations",
        "audience": "Beginner",
        "outcome": "Run one checklist",
        "structure_mode": StructureMode.CONNECTED_NO_MODULES,
        "explanation_level": ExplanationLevel.FINAL_ONLY,
    }
    simple = build_course_thesis_from_brief(CourseBrief(**base))
    complex_brief = CourseBrief(
        **base,
        required_final_performance=(
            "Diagnose demand، choose reorder level، validate exceptions، "
            "document the decision، monitor drift"
        ),
        available_tools=["Spreadsheet", "POS export", "Forecast sheet"],
        professional_constraints=[
            "separate tax treatment from inventory policy",
            "handle missing data explicitly",
        ],
    )
    complex_thesis = build_course_thesis_from_brief(complex_brief)

    assert complex_thesis.size_derivation == "capability_based"
    assert len(complex_thesis.size_basis_capabilities) > len(
        simple.size_basis_capabilities
    )
    assert complex_thesis.target_lessons_min > simple.target_lessons_min


class _StopAtFirstLessonProvider(FakeProvider):
    def __init__(self):
        super().__init__()
        self.map_calls = 0

    def build_course_map(self, input):  # noqa: A002
        self.map_calls += 1
        raise AssertionError("full generation must not rebuild the approved map")

    def write_single_reel(self, input):  # noqa: A002
        raise RuntimeError("test stop before writing any complete lesson")


def test_full_pipeline_consumes_approved_map_without_rebuilding(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as session:
        seed(session)
        course = _course(session)
        stats = build_map_preview(
            session,
            course.id,
            provider=FakeProvider(),
            quality_mode=GenerationQualityMode.PREVIEW,
            web_research_mode=WebResearchMode.DISABLED,
        )
        approved = assert_approved_map_ready(
            session,
            course.id,
            approved_snapshot_fingerprint=stats.snapshot_fingerprint,
            quality_mode=GenerationQualityMode.PREVIEW,
            web_research_mode=WebResearchMode.DISABLED,
            human_override_hard_limits=False,
        )
        approved["STAGE_CONTRACT_STATE"]["map_preview_confirmed"] = True
        job = generation_jobs.create(
            session,
            course_id=course.id,
            status="pending",
            current_stage="queued",
            generation_quality_mode=GenerationQualityMode.PREVIEW,
            web_research_mode=WebResearchMode.DISABLED,
            run_snapshot_json=approved,
            course_map_json=stats.course_map,
        )
        provider = _StopAtFirstLessonProvider()
        stopped = run_generation(
            session,
            course.id,
            provider=provider,
            generation_quality_mode=GenerationQualityMode.PREVIEW,
            web_research_mode=WebResearchMode.DISABLED,
            existing_job_id=job.id,
        )

        assert provider.map_calls == 0
        assert stopped.completed_reels_count == 0
        assert stopped.status.value in {"partial", "failed"}
        assert stopped.error_category != "config_fingerprint_mismatch"
