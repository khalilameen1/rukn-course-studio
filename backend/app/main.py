from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.middleware import AuthMiddleware
from app.config import settings
from app.db import init_db
from app.routers import admin_knowledge, auth, courses, generation, health, jobs, sources


@asynccontextmanager
async def lifespan(app: FastAPI):
    for directory in (
        settings.storage_uploads_dir,
        settings.storage_extracted_dir,
        settings.storage_outputs_dir,
        settings.storage_templates_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    init_db()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Registered after CORSMiddleware so CORS stays the outermost layer and
# preflight requests are never blocked by auth (see app/auth/middleware.py).
app.add_middleware(AuthMiddleware)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(admin_knowledge.router)
app.include_router(courses.router)
app.include_router(sources.router)
app.include_router(generation.router)
app.include_router(jobs.router)
