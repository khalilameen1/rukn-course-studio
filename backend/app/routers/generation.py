from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.crud import course_versions
from app.db import get_session
from app.generation.orchestrator import run_generation_job
from app.routers.deps import get_course_or_404
from app.schemas.course_version import CourseVersionRead
from app.schemas.generation_job import GenerationJobRead

router = APIRouter(prefix="/courses/{course_id}", tags=["generation"])

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


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
    and `/download/latest` are populated afterward. The pipeline itself
    (docs/ARCHITECTURE.md §6) still runs against FakeProvider - no real AI
    call happens yet, so the script content is a placeholder.
    """
    get_course_or_404(session, course_id)
    try:
        return run_generation_job(course_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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
