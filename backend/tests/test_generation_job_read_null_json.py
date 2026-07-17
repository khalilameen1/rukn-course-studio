"""GenerationJobRead must tolerate NULL JSON list columns from older rows."""

from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.models.enums import (
    ExplanationLevel,
    GenerationPreset,
    GenerationQualityMode,
    JobStatus,
    StructureMode,
    TargetMarket,
    WebResearchMode,
)
from app.models.generation_job import GenerationJob
from app.schemas.generation_job import GenerationJobRead


def test_generation_job_read_coerces_null_waste_warnings():
    now = datetime.now(timezone.utc)
    job = GenerationJob(
        id=1,
        course_id=1,
        status=JobStatus.COMPLETED,
        cancel_requested=False,
        current_stage="done",
        progress_percent=100,
        waste_warnings_json=None,  # type: ignore[arg-type]
        created_at=now,
        updated_at=now,
    )
    read = GenerationJobRead.model_validate(job)
    assert read.waste_warnings_json == []


def test_latest_endpoint_tolerates_null_waste_warnings(tmp_path, monkeypatch):
    import app.db as db_module
    from app.config import settings
    from app.crud import courses
    from app.main import app

    engine = create_engine(f"sqlite:///{tmp_path / 'null_json.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(settings, "storage_uploads_dir", tmp_path / "uploads")
    monkeypatch.setattr(settings, "storage_extracted_dir", tmp_path / "extracted")
    monkeypatch.setattr(settings, "storage_outputs_dir", tmp_path / "outputs")

    with Session(engine) as session:
        course = courses.create(
            session,
            title="Null JSON Course",
            audience="a",
            outcome="o",
            structure_mode=StructureMode.CONNECTED_NO_MODULES,
            explanation_level=ExplanationLevel.FINAL_ONLY,
            generation_preset=GenerationPreset.BALANCED,
            generation_quality_mode=GenerationQualityMode.PREMIUM,
            target_market=TargetMarket.EGYPT,
            web_research_mode=WebResearchMode.AUTONOMOUS_GAP_FILL,
        )
        cid = course.id

    now = datetime.now(timezone.utc)
    legacy_job = GenerationJob(
        id=99,
        course_id=cid,
        status=JobStatus.COMPLETED,
        cancel_requested=False,
        current_stage="done",
        progress_percent=100,
        log_json=[],
        completed_reels_json=[],
        waste_warnings_json=None,  # type: ignore[arg-type]
        created_at=now,
        updated_at=now,
    )

    with patch("app.routers.generation.generation_jobs.list", return_value=[legacy_job]):
        with TestClient(app) as client:
            latest = client.get(f"/courses/{cid}/generate/latest")
            assert latest.status_code == 200, latest.text
            assert latest.json()["waste_warnings_json"] == []
