from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.ai.factory import AIProviderConfigError
from app.crud import ai_usage_events, course_versions
from app.db import get_session
from app.generation.orchestrator import run_generation_job
from app.models.enums import JobStatus
from app.models.generation_job import GenerationJob
from app.routers.deps import get_course_or_404
from app.schemas.ai_usage import CourseAIUsage
from app.schemas.course_version import CourseVersionRead
from app.schemas.generation_job import GenerationJobRead

router = APIRouter(prefix="/courses/{course_id}", tags=["generation"])

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# Statuses that mean "a run is actively in flight" for a course - see
# `generate_course`'s duplicate-run guard below (§10).
_ACTIVE_JOB_STATUSES = (JobStatus.PENDING, JobStatus.RUNNING)


def _has_active_job(session: Session, course_id: int) -> bool:
    statement = select(GenerationJob).where(
        GenerationJob.course_id == course_id,
        GenerationJob.status.in_(_ACTIVE_JOB_STATUSES),
    )
    return session.exec(statement).first() is not None


@router.post("/generate", response_model=GenerationJobRead, status_code=201)
def generate_course(course_id: int, session: Session = Depends(get_session)):
    """Kick off a generation run.

    Runs `run_generation_job` (see app/generation/orchestrator.py)
    synchronously for MVP - the request waits for the full pipeline to
    finish and returns the completed (or failed) job. That function is
    already structured to be handed to a background task/queue instead
    later without any change here: swap this call for
    `background_tasks.add_task(run_generation_job, course_id)` and return
    the just-created pending job instead.

    On success, this also produces a real .docx (see
    app/services/docx_export.py) and a new CourseVersion, so `/versions`
    and `/download/latest` are populated afterward. Which AIProvider the
    pipeline (docs/ARCHITECTURE.md §6) actually runs against - FakeProvider
    or a real one - is decided by `AI_PROVIDER` (app/ai/factory.py), never
    exposed here or to the frontend.

    Idempotency/run-locking (§10): rejects with 409 if a `GenerationJob`
    for this course already exists with status `pending`/`running`. Note
    on the synchronous single-process design used today: because
    `run_generation_job` runs the *entire* pipeline inside this request
    (there is no background worker, no queue), a `GenerationJob` row is
    created and immediately flipped to `RUNNING` before any AI call
    happens, and this whole request holds the DB connection/GIL for the
    full run. Two literally-concurrent requests for the same course could
    theoretically both pass this check in the narrow window between "no
    job row exists yet" and "the first job row is committed as RUNNING" -
    but that window is a single, uninterrupted synchronous Python
    function's first few lines (no I/O, no `await`), which in practice
    makes true concurrent duplication effectively impossible for this MVP.
    A real distributed lock (e.g. a DB-level advisory lock) would close
    that theoretical gap completely, but would be over-engineering for a
    single-process synchronous MVP - not added here; documented instead.
    "Regenerate from Scratch" (starting a brand-new job once the previous
    one reached a terminal state) is unaffected by this check and
    continues to work exactly as before.
    """
    get_course_or_404(session, course_id)
    if _has_active_job(session, course_id):
        raise HTTPException(
            status_code=409,
            detail="A generation run is already in progress for this course.",
        )
    try:
        return run_generation_job(course_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AIProviderConfigError as exc:
        # Server misconfiguration (e.g. AI_PROVIDER=anthropic with no API
        # key) - a clear, actionable error, not a raw stack trace and not a
        # silent fallback to a different provider.
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/ai-usage", response_model=CourseAIUsage)
def course_ai_usage(course_id: int, session: Session = Depends(get_session)):
    """This course's cumulative estimated AI spend across every run - see
    app/routers/ai_usage.py's module docstring for the same "estimated app
    usage, not a real balance" caveat."""
    get_course_or_404(session, course_id)
    events = ai_usage_events.list(session, course_id=course_id)
    total = round(sum((e.estimated_cost_usd or 0.0) for e in events), 6)
    return CourseAIUsage(course_id=course_id, estimated_cost_usd=total, event_count=len(events))


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

    return FileResponse(
        path,
        media_type=DOCX_MEDIA_TYPE,
        filename=f"course_{course_id}_v{latest.version_number}.docx",
    )
