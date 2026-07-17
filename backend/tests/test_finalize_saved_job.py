"""No-AI finalization of jobs stuck after all lessons were saved."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

import app.db as db_module
from app.crud import course_versions, courses, generation_jobs
from app.models.enums import ExplanationLevel, JobStatus, StructureMode
from app.services.finalize_saved_job import (
    finalize_job_from_saved_lessons,
    inspect_saved_lessons,
    job_eligible_for_saved_finalize,
)
from app.services.generation_maintenance import release_stale_active_jobs


def _map_and_reels(n: int = 2) -> tuple[dict, list[dict]]:
    reels = []
    for i in range(1, n + 1):
        reels.append(
            {
                "reel_id": f"r{i}",
                "module_id": "m1",
                "title": f"Lesson {i}",
                "script_text": f"Spoken script for lesson {i}.",
                "used_ideas": [],
                "used_examples": [],
                "self_check_status": "pass",
            }
        )
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


def _make_session(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'finalize.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db_module, "engine", engine)
    return engine


def test_inspect_detects_complete_unique_lessons():
    course_map, reels = _map_and_reels(3)

    class _Job:
        course_map_json = course_map
        completed_reels_json = reels
        completed_reels_count = 3
        total_lessons_count = 3

    inspection = inspect_saved_lessons(_Job())
    assert inspection.ok
    assert inspection.planned_count == 3
    assert inspection.unique_saved_count == 3


def test_inspect_rejects_duplicates_and_missing():
    course_map, reels = _map_and_reels(2)
    reels_dup = reels + [dict(reels[0])]

    class _Job:
        course_map_json = course_map
        completed_reels_json = reels_dup
        completed_reels_count = 3
        total_lessons_count = 2

    assert not inspect_saved_lessons(_Job()).ok

    class _JobMissing:
        course_map_json = course_map
        completed_reels_json = reels[:1]
        completed_reels_count = 1
        total_lessons_count = 2

    assert not inspect_saved_lessons(_JobMissing()).ok


def test_finalize_from_saved_exports_docx_and_completes(tmp_path, monkeypatch):
    engine = _make_session(tmp_path, monkeypatch)
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

    course_map, reels = _map_and_reels(2)
    with Session(engine) as session:
        course = courses.create(
            session,
            title="T",
            audience="a",
            outcome="o",
            structure_mode=StructureMode.CONNECTED_NO_MODULES,
            explanation_level=ExplanationLevel.FINAL_ONLY,
        )
        job = generation_jobs.create(
            session,
            course_id=course.id,
            status=JobStatus.RUNNING,
            current_stage="reviewing",
            progress_percent=85,
            course_map_json=course_map,
            completed_reels_json=reels,
            completed_reels_count=2,
            total_lessons_count=2,
            last_progress_message="Saving lesson 2/2",
        )
        assert job_eligible_for_saved_finalize(job)

        updated = finalize_job_from_saved_lessons(session, job)
        assert updated is not None
        assert updated.status == JobStatus.COMPLETED
        assert updated.current_stage == "done"
        assert updated.progress_percent == 100
        assert updated.output_docx_path
        assert Path(updated.output_docx_path).is_file()

        versions = course_versions.list(session, course_id=course.id)
        assert len(versions) == 1
        assert versions[0].output_docx_path == updated.output_docx_path

        backups = list((tmp_path / "storage" / "backups" / "jobs").glob(f"job_{job.id}_*.json"))
        assert len(backups) == 1

        # No second version / no crash on already-completed.
        again = finalize_job_from_saved_lessons(session, updated)
        assert again is not None
        assert again.status == JobStatus.COMPLETED
        assert len(course_versions.list(session, course_id=course.id)) == 1


def test_stale_release_finalizes_complete_lessons_instead_of_failing(tmp_path, monkeypatch):
    engine = _make_session(tmp_path, monkeypatch)
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

    course_map, reels = _map_and_reels(2)
    old = datetime.now(timezone.utc) - timedelta(minutes=20)
    with Session(engine) as session:
        course = courses.create(
            session,
            title="T",
            audience="a",
            outcome="o",
            structure_mode=StructureMode.CONNECTED_NO_MODULES,
            explanation_level=ExplanationLevel.FINAL_ONLY,
        )
        job = generation_jobs.create(
            session,
            course_id=course.id,
            status=JobStatus.RUNNING,
            current_stage="reviewing",
            progress_percent=90,
            course_map_json=course_map,
            completed_reels_json=reels,
            completed_reels_count=2,
            total_lessons_count=2,
        )
        job.updated_at = old
        job.last_saved_at = old
        session.add(job)
        session.commit()

        released = release_stale_active_jobs(
            session, max_age_minutes=90, finalize_after_minutes=8
        )
        assert released == 1
        fresh = generation_jobs.get(session, job.id)
        assert fresh.status == JobStatus.COMPLETED
        assert fresh.output_docx_path
        assert fresh.error_category is None
