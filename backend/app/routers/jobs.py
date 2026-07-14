from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.config import settings
from app.crud import generation_jobs
from app.db import get_session
from app.schemas.generation_job import GenerationJobRead
from app.services.upload_safety import assert_path_under_root

router = APIRouter(prefix="/jobs", tags=["jobs"])

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@router.get("/{job_id}", response_model=GenerationJobRead)
def get_job(job_id: int, session: Session = Depends(get_session)):
    job = generation_jobs.get(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/download-partial")
def download_partial(job_id: int, session: Session = Depends(get_session)):
    """Download the partial DOCX saved when a run stopped early with usable
    work (see app/generation/orchestrator.py's error handling and
    app/services/docx_export.py `export_partial_course_to_docx`).

    Resume is not implemented (see README.md's "Generation resilience"
    section for why) - this download is the supported recovery path for a
    `partial` (or `failed`, if one happened to be saved before the final
    failure) job today.
    """
    job = generation_jobs.get(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.partial_docx_path:
        raise HTTPException(status_code=404, detail="No partial DOCX available for this job")

    path = Path(job.partial_docx_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Partial output file is missing on disk")

    safe = assert_path_under_root(path, Path(settings.storage_outputs_dir))
    return FileResponse(
        safe,
        media_type=DOCX_MEDIA_TYPE,
        filename=f"course_{job.course_id}_job_{job.id}_partial.docx",
    )
