from contextlib import asynccontextmanager
import logging
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlmodel import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.auth.middleware import AuthMiddleware
from app.config import settings
from app.db import engine, init_db
from app.routers import (
    admin_audit,
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
from app.data.admin_knowledge.seed_loader import seed as seed_course_standard

logger = logging.getLogger(__name__)


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
    # Fail closed: startup permanently removes legacy/custom rows and installs
    # the immutable 14-file standard when the database is not canonical.
    with Session(engine) as session:
        seed_course_standard(session)

    from app.generation.boot_safety import run_generation_boot_safety

    boot = run_generation_boot_safety()
    if boot.get("missing_job_columns"):
        logger.error(
            "Generation may fail until DB columns exist: %s",
            boot["missing_job_columns"],
        )

    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)


class CatchUnhandledErrorsMiddleware(BaseHTTPMiddleware):
    """Turn uncaught handler errors into JSON 500s *inside* the CORS stack.

    FastAPI registers `@app.exception_handler(Exception)` on
    ServerErrorMiddleware, which sits *outside* CORSMiddleware — so a bare
    Exception handler still yields 500 responses with no Access-Control-*
    headers, and the browser reports Network/CORS on generation / AI usage
    failures. Catching here (inside CORS) keeps those headers on the 500.
    Never include exception text in the body (may leak paths/SQL). Include a
    short correlation id so logs can be matched without exposing internals.
    """

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            correlation_id = uuid4().hex[:12]
            error_type = type(exc).__name__
            logger.exception(
                "Unhandled error on %s %s correlation_id=%s error_type=%s",
                request.method,
                request.url.path,
                correlation_id,
                error_type,
            )
            return JSONResponse(
                status_code=500,
                content={
                    "detail": (
                        "Internal server error. Reference ID: "
                        f"{correlation_id}"
                    ),
                    "correlation_id": correlation_id,
                    # Class name only — never exception text (may leak paths/SQL).
                    "error_type": error_type,
                },
                headers={"X-Correlation-ID": correlation_id},
            )


# Starlette's `add_middleware` prepends to the middleware list, so the
# LAST middleware added ends up OUTERMOST among *user* middleware.
# Order below → request path: CORS → Auth → CatchUnhandled → routes.
# Auth short-circuit 401s and CatchUnhandled 500s both return through CORS.
app.add_middleware(CatchUnhandledErrorsMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    # Authorization + JSON Content-Type trigger browser preflight on
    # protected POSTs (generate) and GETs (ai-usage). Accept is listed
    # explicitly so Access-Control-Request-Headers including it succeeds.
    allow_headers=["Authorization", "Content-Type", "Accept", "Idempotency-Key"],
)

app.include_router(health.router)
app.include_router(build_info.router)
app.include_router(auth.router)
app.include_router(admin_knowledge.router)
app.include_router(admin_audit.router)
app.include_router(courses.router)
app.include_router(sources.router)
app.include_router(generation.router)
app.include_router(jobs.router)
app.include_router(ai_usage.router)
