from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.config import settings
from app.constants import DOCX_MEDIA_TYPE
from app.crud import generation_jobs
from app.db import get_session
from app.schemas.generation_job import GenerationJobRead
from app.services.generation_maintenance import release_stale_active_jobs
from app.services.upload_safety import assert_course_output_file

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _get_job_for_course(session: Session, job_id: int, course_id: int):
    """Bind job reads to a course — closes cross-course IDOR on /jobs/{id}."""
    job = generation_jobs.get(session, job_id)
    if job is None or job.course_id != course_id:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}", response_model=GenerationJobRead)
def get_job(
    job_id: int,
    course_id: int = Query(..., description="Owning course id (required)."),
    session: Session = Depends(get_session),
):
    # Release abandoned actives so polling does not show a false Running state.
    release_stale_active_jobs(session)
    return _get_job_for_course(session, job_id, course_id)


@router.get("/{job_id}/download-partial")
def download_partial(
    job_id: int,
    course_id: int = Query(..., description="Owning course id (required)."),
    session: Session = Depends(get_session),
):
    """Download the partial DOCX saved when a run stopped early with usable
    work (see app/generation/orchestrator.py's error handling and
    app/services/docx_export.py `export_partial_course_to_docx`).

    Resume is not implemented (see README.md's "Generation resilience"
    section for why) - this download is the supported recovery path for a
    `partial` (or `failed`, if one happened to be saved before the final
    failure) job today.
    """
    job = _get_job_for_course(session, job_id, course_id)
    if not job.partial_docx_path:
        raise HTTPException(status_code=404, detail="No partial DOCX available for this job")

    path = Path(job.partial_docx_path)
    safe = assert_course_output_file(
        path, course_id=job.course_id, outputs_root=Path(settings.storage_outputs_dir)
    )
    return FileResponse(
        safe,
        media_type=DOCX_MEDIA_TYPE,
        filename=f"course_{job.course_id}_job_{job.id}_partial.docx",
    )
