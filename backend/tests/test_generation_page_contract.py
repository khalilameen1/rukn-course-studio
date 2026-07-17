"""Generation page contract: async claim, public progress, readiness, debounce."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.crud import generation_jobs
from app.generation.public_progress import sanitize_progress_message
from app.models.enums import JobStatus, StructureMode
from app.security.request_throttle import reset_for_tests

COURSE_BODY = {
    "title": "Course",
    "audience": "audience",
    "outcome": "outcome",
    "structure_mode": StructureMode.CONNECTED_NO_MODULES.value,
    "manual_map_text": None,
    "explanation_level": "final_only",
}


def _client(tmp_path, monkeypatch):
    import app.db as db_module
    import app.generation.orchestrator as orchestrator_module

    engine = create_engine(f"sqlite:///{tmp_path / 'gen_ux.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(orchestrator_module, "engine", engine)
    monkeypatch.setattr(orchestrator_module.settings, "storage_outputs_dir", tmp_path)
    from app.main import app

    reset_for_tests()
    return TestClient(app), engine


def test_sanitize_progress_strips_agent_names():
    assert "critic" not in sanitize_progress_message("Running specialist critic").lower()
    assert "mentor" not in sanitize_progress_message("Consulting master mentor").lower()


def test_generate_returns_claimed_job_then_completes(tmp_path, monkeypatch):
    client, engine = _client(tmp_path, monkeypatch)
    course_id = client.post("/courses", json=COURSE_BODY).json()["id"]

    response = client.post(f"/courses/{course_id}/generate")
    assert response.status_code == 201
    body = response.json()
    assert "run_snapshot_json" not in body
    assert "internal_risk_count" not in body
    assert "public_stage_label" in body

    # BackgroundTasks finished under TestClient; poll shows completed.
    latest = client.get(f"/jobs/{body['id']}?course_id={course_id}")
    assert latest.json()["status"] == "completed"


def test_debounce_returns_active_or_429(tmp_path, monkeypatch):
    client, engine = _client(tmp_path, monkeypatch)
    course_id = client.post("/courses", json=COURSE_BODY).json()["id"]

    with Session(engine) as session:
        job = generation_jobs.create(
            session,
            course_id=course_id,
            status=JobStatus.RUNNING,
            current_stage="generating",
            progress_percent=20,
            log_json=[],
        )
        jid = job.id

    # Stamp debounce by recording a start, then immediate second POST.
    from app.security.request_throttle import record_generate_start

    record_generate_start(course_id)
    response = client.post(f"/courses/{course_id}/generate")
    assert response.status_code == 200
    assert response.json()["id"] == jid


def test_readiness_includes_provider_and_sources(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    course_id = client.post("/courses", json=COURSE_BODY).json()["id"]
    readiness = client.get(f"/courses/{course_id}/readiness")
    assert readiness.status_code == 200
    body = readiness.json()
    assert body["can_start"] is True
    assert "included_source_count" in body
    assert "provider_ready" in body
    assert "warnings" in body
