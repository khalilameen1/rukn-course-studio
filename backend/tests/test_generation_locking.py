"""Tests for Idempotency and Run Locking (§10) - app/routers/generation.py
`generate_course`'s duplicate-run guard.

Runs through the real FastAPI app (same pattern as
test_scenario_meta_ads_no_sources.py's `test_download_latest_docx_via_real_
api_endpoints`: a fresh temp-file engine monkeypatched onto both
`app.db.engine` and `app.generation.orchestrator.engine`) rather than
literally racing two concurrent HTTP requests - `run_generation_job` is
fully synchronous today, so there is no way to have two requests both
mid-flight in the same test process; instead this directly seeds a
`GenerationJob` row already in `PENDING`/`RUNNING` to exercise exactly the
check `generate_course` performs.
"""

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.crud import generation_jobs
from app.models.enums import JobStatus, StructureMode

COURSE_BODY = {
    "title": "Course",
    "audience": "audience",
    "outcome": "outcome",
    "structure_mode": StructureMode.CONNECTED_NO_MODULES.value,
    "manual_map_text": None,
    "explanation_level": "final_only",
}


def _make_client(tmp_path, monkeypatch):
    import app.db as db_module
    import app.generation.orchestrator as orchestrator_module

    engine = create_engine(f"sqlite:///{tmp_path / 'locking_test.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(orchestrator_module, "engine", engine)
    monkeypatch.setattr(orchestrator_module.settings, "storage_outputs_dir", tmp_path)

    from app.main import app

    return TestClient(app), engine


def _create_course(client) -> int:
    response = client.post("/courses", json=COURSE_BODY)
    assert response.status_code == 201
    return response.json()["id"]


def test_generate_returns_409_when_a_job_is_already_pending(tmp_path, monkeypatch):
    client, engine = _make_client(tmp_path, monkeypatch)
    course_id = _create_course(client)

    with Session(engine) as session:
        generation_jobs.create(
            session,
            course_id=course_id,
            status=JobStatus.PENDING,
            current_stage="queued",
            progress_percent=0,
            log_json=[],
        )

    response = client.post(f"/courses/{course_id}/generate")

    assert response.status_code == 409
    assert "already in progress" in response.json()["detail"]

    with Session(engine) as session:
        jobs = generation_jobs.list(session, course_id=course_id)
    assert len(jobs) == 1  # no second job was created


def test_generate_returns_409_when_a_job_is_already_running(tmp_path, monkeypatch):
    client, engine = _make_client(tmp_path, monkeypatch)
    course_id = _create_course(client)

    with Session(engine) as session:
        generation_jobs.create(
            session,
            course_id=course_id,
            status=JobStatus.RUNNING,
            current_stage="generating",
            progress_percent=40,
            log_json=[],
        )

    response = client.post(f"/courses/{course_id}/generate")

    assert response.status_code == 409


def test_regenerate_from_scratch_still_works_once_previous_job_is_terminal(tmp_path, monkeypatch):
    """A previous job reaching any terminal state (completed/failed/
    partial) must never block "Regenerate from Scratch" - only
    pending/running blocks a new run."""
    client, engine = _make_client(tmp_path, monkeypatch)
    course_id = _create_course(client)

    with Session(engine) as session:
        generation_jobs.create(
            session,
            course_id=course_id,
            status=JobStatus.FAILED,
            current_stage="failed",
            progress_percent=10,
            log_json=[],
            error_message="a previous unrelated failure",
        )

    response = client.post(f"/courses/{course_id}/generate")

    assert response.status_code == 201
    assert response.json()["status"] == "completed"

    with Session(engine) as session:
        jobs = generation_jobs.list(session, course_id=course_id)
    assert len(jobs) == 2


def test_no_existing_job_generates_normally(tmp_path, monkeypatch):
    client, engine = _make_client(tmp_path, monkeypatch)
    course_id = _create_course(client)

    response = client.post(f"/courses/{course_id}/generate")

    assert response.status_code == 201
    assert response.json()["status"] == "completed"
