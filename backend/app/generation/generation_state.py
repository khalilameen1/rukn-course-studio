"""Generation run state machine — persisted stages + allowed statuses.

V1: pending/running/partial/completed/failed + canceled/paused.
Stages are coarse machine labels stored on GenerationJob.current_stage;
user-facing progress messages stay on the locked coarse vocabulary.
"""

from __future__ import annotations

from enum import Enum

from app.models.enums import JobStatus

# Active lock holds: concurrent Generate must not start a second run.
ACTIVE_LOCK_STATUSES: frozenset[JobStatus] = frozenset(
    {JobStatus.PENDING, JobStatus.RUNNING, JobStatus.PAUSED}
)

# Statuses that release the generation lock.
LOCK_RELEASE_STATUSES: frozenset[JobStatus] = frozenset(
    {
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.PARTIAL,
        JobStatus.CANCELED,
    }
)


class GenerationStage(str, Enum):
    """Internal machine stages — persisted on GenerationJob.current_stage."""

    QUEUED = "queued"
    SOURCE_MEMORY = "source_memory"
    RESEARCH_MEMORY = "research_memory"
    COURSE_MAP_FIRST_DRAFT = "course_map_first_draft"
    COURSE_MAP_REVIEW = "course_map_review"
    COURSE_MAP_FINAL = "course_map_final"
    LESSON_FIRST_DRAFT = "lesson_first_draft"
    STUDENT_REVIEW = "student_review"
    SPECIALIST_REVIEW = "specialist_review"
    MENTOR_REVIEW = "mentor_review"
    LESSON_FINAL_REWRITE = "lesson_final_rewrite"
    LESSON_SAVED = "lesson_saved"
    EXPORT_DOCX = "export_docx"
    DONE = "done"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELED = "canceled"


# Coarse UI-facing aliases still used by existing progress flushes.
LEGACY_UI_STAGES = frozenset(
    {
        "queued",
        "reading_sources",
        "building_map",
        "generating",
        "reviewing_repetition",
        "reviewing",
        "exporting",
        "done",
        "failed",
        "partial",
    }
)


def is_active_lock_status(status: JobStatus | str) -> bool:
    if isinstance(status, str):
        try:
            status = JobStatus(status)
        except ValueError:
            return False
    return status in ACTIVE_LOCK_STATUSES
