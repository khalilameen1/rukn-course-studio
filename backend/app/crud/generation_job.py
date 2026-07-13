from app.crud.base import CRUDBase
from app.models.generation_job import GenerationJob

generation_jobs = CRUDBase(GenerationJob)
