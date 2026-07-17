"""POST /courses/{id}/generate/{job_id}/finalize-saved — no AI recovery."""

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.crud import generation_jobs
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


def _map_and_reels(n: int = 2) -> tuple[dict, list[dict]]:
    reels = [
        {
            "reel_id": f"r{i}",
            "module_id": "m1",
            "title": f"Lesson {i}",
            "script_text": f"Spoken script for lesson {i}.",
            "used_ideas": [],
            "used_examples": [],
            "self_check_status": "pass",
        }
        for i in range(1, n + 1)
    ]
    course_map = {
        "course_title": "Test Course",
        "main_thread": "thread",
        "modules": [
            {
                "module_id": "m1",
                "title": "Module 1",
                "purpose": "learn",
                "bridge_project": None,
                "reels": [
                    {
                        "reel_id": f"r{i}",
                        "title": f"Lesson {i}",
                        "purpose": "p",
                        "must_cover": [],
                        "must_avoid": [],
                        "source_hints": [],
                        "estimated_length": "short",
                    }
                    for i in range(1, n + 1)
                ],
            }
        ],
    }
    return course_map, reels


def _client(tmp_path, monkeypatch):
    import app.db as db_module
    import app.generation.orchestrator as orchestrator_module

    engine = create_engine(f"sqlite:///{tmp_path / 'finalize_ep.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(orchestrator_module, "engine", engine)
    monkeypatch.setattr(
        "app.services.finalize_saved_job.settings.storage_dir", tmp_path / "storage"
    )
    monkeypatch.setattr(
        "app.services.finalize_saved_job.settings.storage_outputs_dir",
        tmp_path / "storage" / "outputs",
    )
    monkeypatch.setattr(
        "app.services.docx_export.settings.storage_outputs_dir",
        tmp_path / "storage" / "outputs",
    )
    from app.main import app

    reset_for_tests()
    return TestClient(app), engine


def test_finalize_saved_endpoint_completes_partial_timeout_job(tmp_path, monkeypatch):
    client, engine = _client(tmp_path, monkeypatch)
    course_id = client.post("/courses", json=COURSE_BODY).json()["id"]
    course_map, reels = _map_and_reels(2)

    with Session(engine) as session:
        job = generation_jobs.create(
            session,
            course_id=course_id,
            status=JobStatus.PARTIAL,
            current_stage="failed",
            progress_percent=85,
            course_map_json=course_map,
            completed_reels_json=reels,
            completed_reels_count=2,
            total_lessons_count=2,
            last_completed_step="reel:r2",
            error_category="timeout",
            error_message="Generation stopped after saving completed sections.",
            partial_docx_path=str(tmp_path / "partial.docx"),
        )
        job_id = job.id

    response = client.post(f"/courses/{course_id}/generate/{job_id}/finalize-saved")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["current_stage"] == "done"
    assert body["progress_percent"] == 100
    assert body["output_docx_path"]
    assert body["error_message"] is None
    assert body["can_finalize_from_saved"] is False
    assert body["can_download_completed"] is True


def test_finalize_saved_rejects_incomplete_lessons(tmp_path, monkeypatch):
    client, engine = _client(tmp_path, monkeypatch)
    course_id = client.post("/courses", json=COURSE_BODY).json()["id"]
    course_map, reels = _map_and_reels(2)

    with Session(engine) as session:
        job = generation_jobs.create(
            session,
            course_id=course_id,
            status=JobStatus.PARTIAL,
            current_stage="failed",
            course_map_json=course_map,
            completed_reels_json=reels[:1],
            completed_reels_count=1,
            total_lessons_count=2,
        )
        job_id = job.id

    response = client.post(f"/courses/{course_id}/generate/{job_id}/finalize-saved")
    assert response.status_code == 409


def test_job_read_exposes_recovery_flags(tmp_path, monkeypatch):
    client, engine = _client(tmp_path, monkeypatch)
    course_id = client.post("/courses", json=COURSE_BODY).json()["id"]
    course_map, reels = _map_and_reels(2)

    with Session(engine) as session:
        job = generation_jobs.create(
            session,
            course_id=course_id,
            status=JobStatus.PARTIAL,
            current_stage="failed",
            course_map_json=course_map,
            completed_reels_json=reels,
            completed_reels_count=2,
            total_lessons_count=2,
            partial_docx_path="/tmp/p.docx",
            last_completed_step="final_review",
        )
        job_id = job.id

    # Avoid auto-recover on GET by temporarily breaking force path? GET will
    # recover — call before recover by reading through schema on create path.
    # Instead assert flags on a failed incomplete job that won't auto-complete.
    with Session(engine) as session:
        incomplete = generation_jobs.create(
            session,
            course_id=course_id,
            status=JobStatus.PARTIAL,
            current_stage="failed",
            course_map_json=course_map,
            completed_reels_json=reels[:1],
            completed_reels_count=1,
            total_lessons_count=2,
            partial_docx_path="/tmp/p2.docx",
            last_completed_step="reel:r1",
        )
        incomplete_id = incomplete.id

    body = client.get(f"/jobs/{incomplete_id}?course_id={course_id}").json()
    assert body["can_download_completed"] is True
    assert body["can_finalize_from_saved"] is False
    assert body["stopped_after_label"] == "Saving lessons"

    # Full job recovers on GET — after recover, finalize flag is false.
    full = client.get(f"/jobs/{job_id}?course_id={course_id}").json()
    assert full["status"] == "completed"
    assert full["can_finalize_from_saved"] is False
    assert full["can_download_completed"] is True
