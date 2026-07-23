"""Continue generation from incomplete saved lessons (lesson-boundary resume).

Creates a new job that reuses Final Master scripts already persisted on a
stopped run, then generates only the missing reel_ids. Mid-stage gate
checkpoints are not reconstructed — module/course gates re-run from the
first incomplete module forward.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.enums import JobStatus
from app.models.generation_job import GenerationJob
from app.services.finalize_saved_job import inspect_saved_lessons
from app.services.json_coerce import coerce_json_list


_RESUMABLE_STATUSES = frozenset(
    {
        JobStatus.PARTIAL,
        JobStatus.FAILED,
        JobStatus.CANCELED,
    }
)


def job_eligible_for_incomplete_resume(job: GenerationJob) -> bool:
    """True when some (not all) lessons are saved and the run is terminal."""
    status = job.status
    status_val = status.value if hasattr(status, "value") else str(status or "")
    try:
        status_enum = JobStatus(status_val)
    except ValueError:
        return False
    if status_enum not in _RESUMABLE_STATUSES:
        return False
    if job.output_docx_path:
        return False
    inspection = inspect_saved_lessons(job)
    if inspection.planned_count <= 0:
        return False
    if inspection.unique_saved_count <= 0:
        return False
    # All lessons saved → finalize-saved path, not resume.
    if not inspection.missing_reel_ids:
        return False
    # Reject empty/broken saved scripts — force regenerate from scratch.
    if inspection.empty_script_reel_ids:
        return False
    return True


def find_resumable_job(session: Session, course_id: int) -> GenerationJob | None:
    """Latest terminal job for this course that can continue from saved lessons."""
    statement = (
        select(GenerationJob)
        .where(GenerationJob.course_id == course_id)
        .order_by(GenerationJob.id.desc())
    )
    for job in session.exec(statement).all():
        if job_eligible_for_incomplete_resume(job):
            return job
    return None


def seed_completed_reels_for_resume(
    *,
    target: GenerationJob,
    source: GenerationJob,
) -> list[dict]:
    """Copy unique non-empty saved reels from `source` onto resume seed payload."""
    inspection = inspect_saved_lessons(source)
    if not job_eligible_for_incomplete_resume(source):
        raise ValueError(inspection.reason or "source job is not resumable")

    kept: list[dict] = []
    seen: set[str] = set()
    empty = set(inspection.empty_script_reel_ids)
    for raw in coerce_json_list(source.completed_reels_json):
        if not isinstance(raw, dict):
            continue
        reel_id = str(raw.get("reel_id") or "").strip()
        if not reel_id or reel_id in seen or reel_id in empty:
            continue
        script = str(raw.get("script_text") or "").strip()
        if not script:
            continue
        seen.add(reel_id)
        kept.append(raw)
    if not kept:
        raise ValueError("no usable saved lessons to resume from")
    return kept
