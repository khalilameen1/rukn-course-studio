"""Cooperative cancel / generation-lock tests."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.ai.fake_provider import FakeProvider
from app.crud import generation_jobs
from app.generation.cancellation import CANCEL_REQUESTED_MESSAGE, GenerationCanceled, stop_job_if_cancel_requested
from app.generation.orchestrator import run_generation
from app.models.enums import JobStatus, StructureMode

COURSE_BODY = {
    "title": "Course",
    "audience": "audience",
    "outcome": "outcome",
    "structure_mode": StructureMode.CONNECTED_NO_MODULES.value,
    "manual_map_text": None,
    "explanation_level": "final_only",
}


@pytest.fixture()
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'cancel_orchestrator.db'}")
    from app.db import init_db

    import app.db as db_module

    db_module.engine = engine
    init_db()
    with Session(engine) as s:
        yield s


def _make_client(tmp_path, monkeypatch):
    import app.db as db_module
    import app.generation.orchestrator as orchestrator_module

    engine = create_engine(f"sqlite:///{tmp_path / 'cancel_test.db'}")
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


class CancelAfterNReelsProvider(FakeProvider):
    """Simulates POST /cancel after N reels fully complete."""

    def __init__(self, session: Session, course_id: int, after: int):
        super().__init__()
        self._session = session
        self._course_id = course_id
        self._after = after
        self._finished_reels: set[str] = set()
        self.final_review_calls = 0

    def _running_job_id(self) -> int | None:
        jobs = generation_jobs.list(self._session, course_id=self._course_id)
        running = [j for j in jobs if j.status == JobStatus.RUNNING]
        if not running:
            return None
        return max(running, key=lambda j: j.id).id

    def write_single_reel(self, input):  # noqa: A002
        result = super().write_single_reel(input)
        if getattr(input, "write_phase", "first_draft") != "final_master":
            return result
        reel_id = input.reel.reel_id
        if reel_id in self._finished_reels:
            return result
        self._finished_reels.add(reel_id)
        if len(self._finished_reels) < self._after:
            return result
        job_id = self._running_job_id()
        if job_id is not None:
            generation_jobs.update(
                self._session,
                job_id,
                cancel_requested=True,
                last_progress_message=CANCEL_REQUESTED_MESSAGE,
            )
        return result

    def final_review(self, input):
        self.final_review_calls += 1
        return super().final_review(input)


def test_cancel_during_running_job_blocks_immediate_duplicate_generate(tmp_path, monkeypatch):
    client, engine = _make_client(tmp_path, monkeypatch)
    course_id = _create_course(client)

    with Session(engine) as session:
        job = generation_jobs.create(
            session,
            course_id=course_id,
            status=JobStatus.RUNNING,
            current_stage="generating",
            progress_percent=20,
            log_json=[],
        )
        job_id = job.id

    cancel_resp = client.post(f"/courses/{course_id}/generate/{job_id}/cancel")
    assert cancel_resp.status_code == 200
    body = cancel_resp.json()
    assert body["status"] == "running"
    assert body["cancel_requested"] is True
    assert body["last_progress_message"] == CANCEL_REQUESTED_MESSAGE

    gen_resp = client.post(f"/courses/{course_id}/generate")
    assert gen_resp.status_code == 200
    assert gen_resp.json()["id"] == job_id

    with Session(engine) as session:
        assert len(generation_jobs.list(session, course_id=course_id)) == 1


def test_stop_job_if_cancel_requested_finalizes_running_job(session, tmp_path, monkeypatch):
    import app.generation.orchestrator as orchestrator_module

    monkeypatch.setattr(orchestrator_module.settings, "storage_outputs_dir", tmp_path)

    from app.crud import courses
    from app.models.enums import ExplanationLevel, StructureMode

    course = courses.create(
        session,
        title="Stop helper course",
        audience="audience",
        outcome="outcome",
        structure_mode=StructureMode.CONNECTED_NO_MODULES,
        explanation_level=ExplanationLevel.FINAL_ONLY,
    )
    job = generation_jobs.create(
        session,
        course_id=course.id,
        status=JobStatus.RUNNING,
        current_stage="generating",
        progress_percent=25,
        log_json=[],
        completed_reels_json=[{"reel_id": "m1-r1", "title": "L1", "script_text": "hello"}],
        completed_reels_count=1,
    )
    generation_jobs.update(session, job.id, cancel_requested=True)
    job = generation_jobs.get(session, job.id)
    logs: list[dict] = []

    def flush(**fields):
        nonlocal job
        return generation_jobs.update(session, job.id, log_json=logs, **fields)

    with pytest.raises(GenerationCanceled) as exc_info:
        stop_job_if_cancel_requested(session, job, course.id, logs, flush)
    stopped = exc_info.value.job
    assert stopped.status == JobStatus.CANCELED
    assert stopped.completed_reels_count == 1


def test_lock_released_only_after_canceled_run_stops(tmp_path, monkeypatch, session):
    import app.generation.orchestrator as orchestrator_module

    monkeypatch.setattr(orchestrator_module.settings, "storage_outputs_dir", tmp_path)

    from app.crud import courses
    from app.models.enums import ExplanationLevel, StructureMode

    course = courses.create(
        session,
        title="Cancel lock course",
        audience="audience",
        outcome="outcome",
        structure_mode=StructureMode.CONNECTED_NO_MODULES,
        explanation_level=ExplanationLevel.FINAL_ONLY,
    )
    provider = CancelAfterNReelsProvider(session, course.id, after=1)
    job = run_generation(session, course.id, provider=provider)

    assert job.status == JobStatus.CANCELED
    assert job.cancel_requested is False
    assert job.completed_reels_count == 1

    fresh = run_generation(session, course.id)
    assert fresh.status == JobStatus.COMPLETED
    assert fresh.id != job.id


def test_canceled_job_saves_completed_progress(tmp_path, monkeypatch, session):
    import app.generation.orchestrator as orchestrator_module

    monkeypatch.setattr(orchestrator_module.settings, "storage_outputs_dir", tmp_path)

    from app.crud import courses
    from app.models.enums import ExplanationLevel, StructureMode

    course = courses.create(
        session,
        title="Cancel progress course",
        audience="audience",
        outcome="outcome",
        structure_mode=StructureMode.CONNECTED_NO_MODULES,
        explanation_level=ExplanationLevel.FINAL_ONLY,
    )
    provider = CancelAfterNReelsProvider(session, course.id, after=2)
    job = run_generation(session, course.id, provider=provider)

    assert job.status == JobStatus.CANCELED
    assert job.completed_reels_count == 2
    assert len(job.completed_reels_json) == 2
    assert job.course_map_json is not None
    assert job.partial_docx_path


def test_is_cancel_requested_reads_persisted_flag(session):
    from app.crud import courses
    from app.generation.cancellation import is_cancel_requested
    from app.models.enums import ExplanationLevel, StructureMode

    course = courses.create(
        session,
        title="Flag course",
        audience="audience",
        outcome="outcome",
        structure_mode=StructureMode.CONNECTED_NO_MODULES,
        explanation_level=ExplanationLevel.FINAL_ONLY,
    )
    job = generation_jobs.create(
        session,
        course_id=course.id,
        status=JobStatus.RUNNING,
        current_stage="generating",
        progress_percent=0,
        log_json=[],
    )
    generation_jobs.update(session, job.id, cancel_requested=True)
    assert is_cancel_requested(session, job.id) is True


def test_canceled_job_does_not_continue_into_later_stages(tmp_path, monkeypatch, session):
    import app.generation.orchestrator as orchestrator_module

    monkeypatch.setattr(orchestrator_module.settings, "storage_outputs_dir", tmp_path)

    from app.crud import courses
    from app.models.enums import ExplanationLevel, StructureMode

    course = courses.create(
        session,
        title="Cancel stage course",
        audience="audience",
        outcome="outcome",
        structure_mode=StructureMode.CONNECTED_NO_MODULES,
        explanation_level=ExplanationLevel.FINAL_ONLY,
    )
    provider = CancelAfterNReelsProvider(session, course.id, after=1)
    job = run_generation(session, course.id, provider=provider)

    assert job.status == JobStatus.CANCELED
    assert provider.final_review_calls == 0


def test_new_generation_after_safe_cancellation_works(tmp_path, monkeypatch):
    client, engine = _make_client(tmp_path, monkeypatch)
    course_id = _create_course(client)

    first = client.post(f"/courses/{course_id}/generate")
    assert first.status_code == 201
    first_id = first.json()["id"]

    with Session(engine) as session:
        generation_jobs.update(
            session,
            first_id,
            status=JobStatus.CANCELED,
            cancel_requested=False,
            current_stage="canceled",
            last_progress_message="Generation canceled",
        )

    second = client.post(f"/courses/{course_id}/generate")
    assert second.status_code == 201
    assert second.json()["id"] != first_id
    assert second.json()["status"] == "completed"
