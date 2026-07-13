from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.crud import generation_jobs
from app.db import get_session
from app.schemas.generation_job import GenerationJobRead

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=GenerationJobRead)
def get_job(job_id: int, session: Session = Depends(get_session)):
    job = generation_jobs.get(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
