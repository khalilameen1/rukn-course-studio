from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.ai.factory import AIProviderConfigError
from app.config import settings
from app.crud import ai_usage_events, course_versions, courses, generation_jobs
from app.db import get_session
from app.generation.cancellation import CANCEL_REQUESTED_MESSAGE, request_cancel
from app.generation.generation_state import ACTIVE_LOCK_STATUSES, is_active_lock_status
from app.generation.orchestrator import run_generation_job
from app.models.enums import JobStatus
from app.models.generation_job import GenerationJob
from app.routers.deps import get_course_or_404
from app.schemas.ai_usage import CourseAIUsage
from app.schemas.course import CourseRead
from app.schemas.course_version import CourseVersionRead
from app.schemas.generation_job import GenerateCourseRequest, GenerationJobRead
from app.security.request_throttle import allow_generate_start, record_generate_start
from app.services.upload_safety import assert_path_under_root

router = APIRouter(prefix="/courses/{course_id}", tags=["generation"])

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _get_active_job(session: Session, course_id: int) -> GenerationJob | None:
    statement = select(GenerationJob).where(
        GenerationJob.course_id == course_id,
        GenerationJob.status.in_(tuple(ACTIVE_LOCK_STATUSES)),
    )
    return session.exec(statement).first()


def _get_any_active_job(session: Session) -> GenerationJob | None:
    statement = select(GenerationJob).where(
        GenerationJob.status.in_(tuple(ACTIVE_LOCK_STATUSES)),
    )
    return session.exec(statement).first()


@router.post("/generate-map", response_model=CourseRead)
def generate_course_map(course_id: int, session: Session = Depends(get_session)):
    """Build Final Course Map via Creator→Student→Specialist→Mentor→rebuild.

    Saves editable map text on the course (`manual_map_text`). Course-specific
    only — never Admin Knowledge. Internal reviews are not returned.
    """
    get_course_or_404(session, course_id)
    from app.generation.course_map_generate import generate_and_save_course_map

    try:
        course, _map_text = generate_and_save_course_map(session, course_id)
        return course
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AIProviderConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/generate", response_model=GenerationJobRead)
def generate_course(
    course_id: int,
    response: Response,
    body: GenerateCourseRequest | None = None,
    session: Session = Depends(get_session),
):
    """Kick off a generation run (or return the existing active run).

    Idempotent: if a pending/running/paused job already exists, return it
    (200) instead of starting a duplicate. New runs return 201.

    Also: one active generation globally (optional), soft per-course debounce
    against double-click cost burn.
    """
    get_course_or_404(session, course_id)
    active = _get_active_job(session, course_id)
    if active is not None:
        response.status_code = 200
        return active

    if getattr(settings, "generation_global_lock", True):
        other = _get_any_active_job(session)
        if other is not None:
            response.status_code = 200
            return other

    min_interval = float(getattr(settings, "generate_min_interval_seconds", 3.0) or 0)
    if min_interval > 0 and not allow_generate_start(course_id, min_interval_seconds=min_interval):
        # Soft throttle: still never start a second Claude run; return
        # latest job for this course if any, else 429 with clear detail.
        recent = generation_jobs.list(session, course_id=course_id)
        if recent:
            response.status_code = 200
            return max(recent, key=lambda j: j.id)
        raise HTTPException(
            status_code=429,
            detail="Generation requests are temporarily throttled. Retry shortly.",
        )

    course = get_course_or_404(session, course_id)
    request = body or GenerateCourseRequest()
    updates: dict = {}
    if course.generation_quality_mode != request.generation_quality_mode:
        updates["generation_quality_mode"] = request.generation_quality_mode
    if getattr(course, "web_research_mode", None) != request.web_research_mode:
        updates["web_research_mode"] = request.web_research_mode
    if updates:
        courses.update(session, course_id, **updates)
    try:
        job = run_generation_job(
            course_id,
            generation_quality_mode=request.generation_quality_mode,
            web_research_mode=request.web_research_mode,
        )
        record_generate_start(course_id)
        response.status_code = 201
        return job
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AIProviderConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/generate/latest", response_model=GenerationJobRead)
def latest_generation_job(course_id: int, session: Session = Depends(get_session)):
    """Most recent generation job for this course (any status).

    Lets the UI restore progress/status after a page refresh without
    POSTing /generate (which could look like a new run request). 404 when
    the course has never been generated - a normal state, not an error.
    """
    get_course_or_404(session, course_id)
    jobs = generation_jobs.list(session, course_id=course_id)
    if not jobs:
        raise HTTPException(
            status_code=404, detail="No generation run for this course yet"
        )
    return max(jobs, key=lambda j: j.id)


@router.post("/generate/{job_id}/cancel", response_model=GenerationJobRead)
def cancel_generation(
    course_id: int, job_id: int, request: Request, session: Session = Depends(get_session)
):
    """Request cooperative cancel for an active job.

    Does not release the generation lock until the orchestrator stops between
    stages. While the worker is still running, status stays active and
    `cancel_requested` is true.
    """
    from app.services.audit import record_audit

    get_course_or_404(session, course_id)
    job = generation_jobs.get(session, job_id)
    if job is None or job.course_id != course_id:
        raise HTTPException(status_code=404, detail="Generation job not found")
    if not is_active_lock_status(job.status):
        return job
    if job.cancel_requested:
        return job
    updated = request_cancel(session, job_id)
    if updated.last_progress_message != CANCEL_REQUESTED_MESSAGE:
        updated = generation_jobs.update(
            session,
            job_id,
            last_progress_message=CANCEL_REQUESTED_MESSAGE,
        )
    record_audit(
        session,
        action="generation_cancel",
        actor=getattr(request.state, "username", None),
        affected_table="generation_jobs",
        affected_count=1,
        dry_run=False,
        confirmed=True,
        success=True,
        details={"course_id": course_id, "job_id": job_id},
    )
    return updated



@router.get("/ai-usage", response_model=CourseAIUsage)
def course_ai_usage(course_id: int, session: Session = Depends(get_session)):
    """This course's cumulative estimated AI spend across every run - see
    app/routers/ai_usage.py's module docstring for the same "estimated app
    usage, not a real balance" caveat."""
    from app.crud import generation_jobs

    get_course_or_404(session, course_id)
    events = ai_usage_events.list(session, course_id=course_id)
    total = round(sum((e.estimated_cost_usd or 0.0) for e in events), 6)
    jobs = generation_jobs.list(session, course_id=course_id)
    latest = max(jobs, key=lambda j: j.id) if jobs else None
    panel = getattr(latest, "usage_by_stage_json", None) or {}
    return CourseAIUsage(
        course_id=course_id,
        estimated_cost_usd=total,
        event_count=len(events),
        cost_per_completed_lesson=panel.get("cost_per_completed_lesson"),
        web_searches_count=(
            panel.get("web_searches_count")
            if panel
            else getattr(latest, "web_searches_count", None)
        ),
        source_memories_reused=(
            panel.get("source_memories_reused")
            if panel
            else getattr(latest, "reused_source_memory_count", None)
        ),
        research_memory_reuses=panel.get("research_memory_reuses"),
        warnings=list(panel.get("warnings") or getattr(latest, "waste_warnings_json", None) or []),
    )


@router.get("/versions", response_model=list[CourseVersionRead])
def list_versions(course_id: int, session: Session = Depends(get_session)):
    get_course_or_404(session, course_id)
    return course_versions.list(session, course_id=course_id)


@router.get("/download/latest")
def download_latest_version(course_id: int, session: Session = Depends(get_session)):
    get_course_or_404(session, course_id)

    versions = course_versions.list(session, course_id=course_id)
    if not versions:
        raise HTTPException(
            status_code=404, detail="No generated version available for this course yet"
        )

    latest = max(versions, key=lambda v: v.version_number)
    path = Path(latest.output_docx_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Output file is missing on disk")

    safe = assert_path_under_root(path, Path(settings.storage_outputs_dir))
    return FileResponse(
        safe,
        media_type=DOCX_MEDIA_TYPE,
        filename=f"course_{course_id}_v{latest.version_number}.docx",
    )
