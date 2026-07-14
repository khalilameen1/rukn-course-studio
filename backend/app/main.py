from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from app.auth.middleware import AuthMiddleware
from app.config import settings
from app.db import engine, init_db
from app.routers import (
    admin_knowledge,
    ai_usage,
    auth,
    build_info,
    courses,
    generation,
    health,
    jobs,
    sources,
)
from app.seed_admin_knowledge import seed as seed_admin_knowledge


@asynccontextmanager
async def lifespan(app: FastAPI):
    env = (settings.environment or "").strip().lower()
    productionish = env not in {"development", "dev", "test", "local", ""}
    if productionish and not settings.auth_enabled:
        raise RuntimeError(
            "Refusing to start: ENVIRONMENT looks like production but "
            "AUTH_ENABLED is false. Set AUTH_ENABLED=true before serving."
        )
    if productionish and settings.auth_enabled and not settings.auth_secret_key:
        raise RuntimeError(
            "Refusing to start: AUTH_SECRET_KEY is required when auth is "
            "enabled in production."
        )

    for directory in (
        settings.storage_uploads_dir,
        settings.storage_extracted_dir,
        settings.storage_outputs_dir,
        settings.storage_templates_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    init_db()

    # Safe to run on every startup: seed_admin_knowledge.seed() only ever
    # creates a row for a key that has zero rows, so this never duplicates
    # an item and never overwrites one a user has since edited (see
    # app/seed_admin_knowledge.py). This is what makes the Admin Knowledge
    # Center auto-populate instead of needing a manual command every deploy.
    with Session(engine) as session:
        seed_admin_knowledge(session)

    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# Starlette's `add_middleware` prepends to the middleware list, so the
# LAST middleware added ends up OUTERMOST (it sees the request first and
# the response last) - registering AuthMiddleware first and CORSMiddleware
# second (not the other way around) is what actually makes CORS the
# outermost layer. This matters beyond just preflight: AuthMiddleware can
# short-circuit with its own 401/503 response *without* calling
# `call_next`, and only requests that pass through CORSMiddleware get
# CORS response headers added. With CORS outermost, every response -
# including auth rejections - gets proper CORS headers, so the browser can
# actually surface the real status/detail to the frontend instead of a
# generic "Failed to fetch" network error (see app/auth/middleware.py).
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health.router)
app.include_router(build_info.router)
app.include_router(auth.router)
app.include_router(admin_knowledge.router)
app.include_router(courses.router)
app.include_router(sources.router)
app.include_router(generation.router)
app.include_router(jobs.router)
app.include_router(ai_usage.router)
