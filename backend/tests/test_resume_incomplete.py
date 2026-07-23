"""Unit tests for lesson-boundary resume helpers."""

from app.models.enums import JobStatus
from app.models.generation_job import GenerationJob
from app.schemas.generation import ReviewStatus
from app.schemas.generation_job import GenerationJobRead
from app.services.resume_incomplete_job import (
    job_eligible_for_incomplete_resume,
    seed_completed_reels_for_resume,
)


def _reel(reel_id: str, title: str) -> dict:
    return {
        "reel_id": reel_id,
        "module_id": "m1",
        "title": title,
        "script_text": f"نص محفوظ لـ {title}.",
        "self_check_status": ReviewStatus.PASS.value,
        "quality_status": "pass",
    }


def _map() -> dict:
    return {
        "course_title": "Test",
        "main_thread": "thread",
        "modules": [
            {
                "module_id": "m1",
                "title": "M1",
                "purpose": "learn",
                "reels": [
                    {
                        "reel_id": "r1",
                        "title": "L1",
                        "purpose": "p1",
                        "estimated_length": "2 minutes",
                    },
                    {
                        "reel_id": "r2",
                        "title": "L2",
                        "purpose": "p2",
                        "estimated_length": "2 minutes",
                    },
                ],
            }
        ],
    }


def _job(**kwargs) -> GenerationJob:
    base = dict(
        id=1,
        course_id=7,
        status=JobStatus.PARTIAL,
        course_map_json=_map(),
        completed_reels_json=[_reel("r1", "L1")],
        completed_reels_count=1,
        total_lessons_count=2,
    )
    base.update(kwargs)
    return GenerationJob(**base)


def test_partial_with_missing_lessons_is_resumable():
    assert job_eligible_for_incomplete_resume(_job()) is True


def test_completed_lessons_are_not_resumable():
    job = _job(
        completed_reels_json=[_reel("r1", "L1"), _reel("r2", "L2")],
        completed_reels_count=2,
    )
    assert job_eligible_for_incomplete_resume(job) is False


def test_seed_keeps_unique_saved_reels():
    source = _job()
    target = _job(id=2, completed_reels_json=[], completed_reels_count=0)
    seeded = seed_completed_reels_for_resume(target=target, source=source)
    assert len(seeded) == 1
    assert seeded[0]["reel_id"] == "r1"


def test_job_read_exposes_can_resume_incomplete():
    read = GenerationJobRead.model_validate(
        _job(status=JobStatus.FAILED, completed_reels_count=1, total_lessons_count=4)
    )
    assert read.can_resume_incomplete is True
    assert read.can_finalize_from_saved is False
