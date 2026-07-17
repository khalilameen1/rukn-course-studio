from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.ai.factory import AIProviderConfigError, get_ai_provider
from app.config import settings
from app.constants import DOCX_MEDIA_TYPE
from app.crud import ai_usage_events, course_versions, courses, generation_jobs
from app.db import get_session
from app.generation.cancellation import CANCEL_REQUESTED_MESSAGE, request_cancel
from app.generation.generation_lock import claim_generation_job, generation_start_guard
from app.generation.generation_state import ACTIVE_LOCK_STATUSES, is_active_lock_status
from app.generation.job_runner import run_claimed_generation_job
from app.generation.map_lock import end_map, is_map_busy, try_begin_map
from app.models.enums import JobStatus
from app.models.generation_job import GenerationJob
from app.routers.deps import get_course_or_404
from app.schemas.ai_usage import CourseAIUsage
from app.schemas.course import CourseRead
from app.schemas.course_version import CourseVersionRead
from app.schemas.generation_job import (
    GenerateCourseRequest,
    GenerationJobRead,
    MapPreviewRequest,
    WriterTest3ReelsRequest,
    WriterTestJobRead,
    WriterTestReelPublic,
)
from app.security.request_throttle import can_generate_start, record_generate_start
from app.services.finalize_saved_job import (
    finalize_job_from_saved_lessons,
    inspect_saved_lessons,
    job_eligible_for_saved_finalize,
    try_recover_job_from_saved_lessons,
)
from app.services.generation_maintenance import release_stale_active_jobs
from app.services.upload_safety import assert_course_output_file

router = APIRouter(prefix="/courses/{course_id}", tags=["generation"])

# Tests historically patched this private name on the router module.
_release_stale_active_jobs = release_stale_active_jobs


def _get_active_job(session: Session, course_id: int) -> GenerationJob | None:
    statement = select(GenerationJob).where(
        GenerationJob.course_id == course_id,
        GenerationJob.status.in_(tuple(ACTIVE_LOCK_STATUSES)),
    )
    return session.exec(statement).first()


def _actor(request: Request) -> str | None:
    return getattr(request.state, "username", None)


@router.post("/generate-map", response_model=CourseRead)
def generate_course_map(course_id: int, session: Session = Depends(get_session)):
    """Build Final Course Map. Course-specific only — never Admin Knowledge.

    Uses the same start guard as full generate so map and DOCX runs cannot
    overlap on one course (or globally when GENERATION_GLOBAL_LOCK is on).
    """
    get_course_or_404(session, course_id)
    _release_stale_active_jobs(session)
    from app.generation.map_lock import clear_stale_map_locks

    clear_stale_map_locks(session)

    if is_map_busy(course_id):
        raise HTTPException(
            status_code=409,
            detail="A course map build is already in progress for this course.",
        )

    try:
        with generation_start_guard(course_id):
            if _get_active_job(session, course_id) is not None:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "A generation run is already active for this course. "
                        "Wait for it to finish before building the map."
                    ),
                )
            if getattr(settings, "generation_global_lock", True):
                other = session.exec(
                    select(GenerationJob).where(
                        GenerationJob.status.in_(tuple(ACTIVE_LOCK_STATUSES)),
                    )
                ).first()
                if other is not None and other.course_id != course_id:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"Another course (id={other.course_id}) already has an "
                            "active generation run. Wait for it to finish."
                        ),
                    )
            if not try_begin_map(course_id, session):
                raise HTTPException(
                    status_code=409,
                    detail="A course map build is already in progress for this course.",
                )
    except HTTPException:
        raise
    except RuntimeError as exc:
        detail = str(exc)
        if detail.startswith("GLOBAL_LOCK:"):
            raise HTTPException(
                status_code=409,
                detail=detail.removeprefix("GLOBAL_LOCK:").strip(),
            ) from exc
        raise

    from app.generation.course_map_generate import generate_and_save_course_map

    try:
        course, _map_text = generate_and_save_course_map(session, course_id)
        return course
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AIProviderConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        end_map(course_id, session)


@router.post("/generate", response_model=GenerationJobRead, status_code=201)
def generate_course(
    course_id: int,
    response: Response,
    background_tasks: BackgroundTasks,
    http_request: Request,
    body: GenerateCourseRequest | None = None,
    session: Session = Depends(get_session),
):
    """Claim a generation slot and return the job immediately (async worker).

    Idempotent: if a pending/running/paused job already exists, return it
    (200) without starting another pipeline. New claims return 201 and run
    off-request via BackgroundTasks (single-worker V1).
    """
    get_course_or_404(session, course_id)
    _release_stale_active_jobs(session)
    from app.generation.map_lock import clear_stale_map_locks

    clear_stale_map_locks(session)

    if is_map_busy(course_id):
        raise HTTPException(
            status_code=409,
            detail="A course map build is in progress. Wait for it to finish.",
        )

    min_interval = float(getattr(settings, "generate_min_interval_seconds", 3.0) or 0)
    if min_interval > 0 and not can_generate_start(
        course_id, min_interval_seconds=min_interval
    ):
        active = _get_active_job(session, course_id)
        if active is not None:
            response.status_code = 200
            return active
        raise HTTPException(
            status_code=429,
            detail="Generation requests are temporarily throttled. Retry shortly.",
        )

    course = get_course_or_404(session, course_id)
    request_body = body or GenerateCourseRequest()
    updates: dict = {}
    if course.generation_quality_mode != request_body.generation_quality_mode:
        updates["generation_quality_mode"] = request_body.generation_quality_mode
    if getattr(course, "web_research_mode", None) != request_body.web_research_mode:
        updates["web_research_mode"] = request_body.web_research_mode
    if updates:
        courses.update(session, course_id, **updates)

    try:
        # Fail fast before claiming a slot if the provider cannot run.
        get_ai_provider()
        from app.generation.generation_preflight import (
            check_storage_disk,
            generation_preflight,
        )

        pre = generation_preflight()
        if not pre.get("ok"):
            raise AIProviderConfigError(
                "; ".join(pre.get("blockers") or ["Generation preflight failed."])
            )
        disk_err = check_storage_disk()
        if disk_err:
            raise HTTPException(status_code=507, detail=disk_err)
    except AIProviderConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        with generation_start_guard(course_id):
            if is_map_busy(course_id):
                raise HTTPException(
                    status_code=409,
                    detail="A course map build is in progress. Wait for it to finish.",
                )
            claimed, created = claim_generation_job(
                session,
                course_id,
                generation_quality_mode=request_body.generation_quality_mode,
                web_research_mode=request_body.web_research_mode,
            )
            job_id = claimed.id
    except HTTPException:
        raise
    except RuntimeError as exc:
        detail = str(exc)
        if detail.startswith("GLOBAL_LOCK:"):
            raise HTTPException(
                status_code=409,
                detail=detail.removeprefix("GLOBAL_LOCK:").strip(),
            ) from exc
        raise

    if not created:
        response.status_code = 200
        return claimed

    record_generate_start(course_id)
    background_tasks.add_task(
        run_claimed_generation_job,
        course_id,
        job_id=job_id,
        generation_quality_mode=request_body.generation_quality_mode,
        web_research_mode=request_body.web_research_mode,
    )

    from app.services.audit import record_audit

    record_audit(
        session,
        action="generation_start",
        actor=_actor(http_request),
        affected_table="generation_jobs",
        affected_count=1,
        dry_run=False,
        confirmed=True,
        success=True,
        details={"course_id": course_id, "job_id": job_id, "async": True},
    )
    response.status_code = 201
    # Re-read so response reflects queued/pending claim (worker runs after).
    return generation_jobs.get(session, job_id) or claimed


@router.get("/generate/latest", response_model=GenerationJobRead)
def latest_generation_job(course_id: int, session: Session = Depends(get_session)):
    """Most recent generation job for this course (any status).

    Releases abandoned active jobs so the UI does not show a false Running
    state after a crashed/timed-out worker.
    """
    get_course_or_404(session, course_id)
    _release_stale_active_jobs(session)
    jobs = generation_jobs.list(session, course_id=course_id)
    if not jobs:
        raise HTTPException(
            status_code=404, detail="No generation run for this course yet"
        )
    latest = max(jobs, key=lambda j: j.id)
    return try_recover_job_from_saved_lessons(session, latest)


@router.post("/generate/{job_id}/cancel", response_model=GenerationJobRead)
def cancel_generation(
    course_id: int, job_id: int, request: Request, session: Session = Depends(get_session)
):
    """Request cooperative cancel for an active job."""
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
        actor=_actor(request),
        affected_table="generation_jobs",
        affected_count=1,
        dry_run=False,
        confirmed=True,
        success=True,
        details={"course_id": course_id, "job_id": job_id},
    )
    return updated


@router.post("/generate/{job_id}/finalize-saved", response_model=GenerationJobRead)
def finalize_saved_generation(
    course_id: int, job_id: int, request: Request, session: Session = Depends(get_session)
):
    """Assemble Teleprompter DOCX from already-saved lessons — no AI calls.

    Enterprise recovery for runs that saved every Final Master lesson but
    stopped during final review/export (timeout, cancel, worker death).
    """
    from app.services.audit import record_audit

    get_course_or_404(session, course_id)
    job = generation_jobs.get(session, job_id)
    if job is None or job.course_id != course_id:
        raise HTTPException(status_code=404, detail="Generation job not found")

    if job.status == JobStatus.COMPLETED and job.output_docx_path:
        return job

    if is_active_lock_status(job.status) and not job_eligible_for_saved_finalize(job):
        raise HTTPException(
            status_code=409,
            detail=(
                "This run is still active and lessons are not fully saved yet. "
                "Wait for it to finish or stop it first."
            ),
        )

    inspection = inspect_saved_lessons(job)
    if not inspection.ok:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot finish from saved lessons — "
                f"{inspection.reason.replace('_', ' ')} "
                f"({inspection.unique_saved_count}/{inspection.planned_count} unique lessons)."
            ),
        )

    updated = finalize_job_from_saved_lessons(session, job, force=True)
    if updated is None or updated.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=500,
            detail="Could not write the Teleprompter DOCX from saved lessons.",
        )

    record_audit(
        session,
        action="generation_finalize_saved",
        actor=_actor(request),
        affected_table="generation_jobs",
        affected_count=1,
        dry_run=False,
        confirmed=True,
        success=True,
        details={
            "course_id": course_id,
            "job_id": job_id,
            "lessons": inspection.planned_count,
            "ai_calls": 0,
        },
    )
    return updated


@router.get("/ai-usage", response_model=CourseAIUsage)
def course_ai_usage(course_id: int, session: Session = Depends(get_session)):
    """This course's cumulative estimated AI spend across every run."""
    get_course_or_404(session, course_id)
    events = ai_usage_events.list(session, course_id=course_id)
    total = round(sum((e.estimated_cost_usd or 0.0) for e in events), 6)
    jobs = generation_jobs.list(session, course_id=course_id)
    from app.services.json_coerce import coerce_json_dict, coerce_json_list

    latest = max(jobs, key=lambda j: j.id) if jobs else None
    panel = coerce_json_dict(getattr(latest, "usage_by_stage_json", None)) or {}
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
        warnings=list(
            panel.get("warnings")
            or coerce_json_list(getattr(latest, "waste_warnings_json", None))
        ),
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
    safe = assert_course_output_file(
        path, course_id=course_id, outputs_root=Path(settings.storage_outputs_dir)
    )
    return FileResponse(
        safe,
        media_type=DOCX_MEDIA_TYPE,
        filename=f"course_{course_id}_v{latest.version_number}.docx",
    )


def _writer_test_job_read(job) -> WriterTestJobRead:
    snap = job.run_snapshot_json or {}
    raw_reels = snap.get("writer_test_results") or job.completed_reels_json or []
    public: list[WriterTestReelPublic] = []
    for raw in raw_reels:
        if not isinstance(raw, dict):
            continue
        status = str(raw.get("quality_status") or "pass")
        is_master = status == "pass" and bool(raw.get("script_text_final_master"))
        report = raw.get("quality_report") or {}
        notes = report.get("notes") if isinstance(report, dict) else None
        summary = ""
        if isinstance(notes, list) and notes:
            summary = "; ".join(
                str(n.get("violation_type") or n.get("required_repair") or "")[:80]
                for n in notes[:4]
                if isinstance(n, dict)
            )
        script = ""
        if is_master:
            script = str(raw.get("script_text_final_master") or raw.get("script_text") or "")
        elif status == "pass":
            script = str(raw.get("script_text") or "")
        public.append(
            WriterTestReelPublic(
                reel_id=str(raw.get("reel_id") or ""),
                title=str(raw.get("title") or ""),
                script_text=script,
                word_count=int(raw.get("word_count") or 0),
                estimated_seconds=float(raw.get("estimated_seconds") or 0),
                quality_status=status,
                quality_summary=summary,
                input_tokens=int(raw.get("input_tokens") or 0),
                output_tokens=int(raw.get("output_tokens") or 0),
                is_final_master=is_master or status == "pass",
            )
        )
    return WriterTestJobRead(
        job=GenerationJobRead.model_validate(job),
        job_kind=str(snap.get("job_kind") or "writer_test_3_reels"),
        settings_fingerprint=snap.get("settings_fingerprint"),
        series_linked=bool(snap.get("series_linked")),
        reels=public,
    )


@router.post("/writer-test-3-reels", response_model=WriterTestJobRead, status_code=201)
def writer_test_3_reels(
    course_id: int,
    body: WriterTest3ReelsRequest,
    session: Session = Depends(get_session),
):
    """Run production writer path for exactly three topics (no full course map)."""
    get_course_or_404(session, course_id)
    if len(body.topics) != 3:
        raise HTTPException(status_code=422, detail="Exactly 3 topics are required")
    from app.generation.writer_test import WriterTestTopic, run_writer_test_3_reels

    try:
        job = run_writer_test_3_reels(
            session,
            course_id,
            topics=[
                WriterTestTopic(title=t.title, purpose=t.purpose) for t in body.topics
            ],
            series_linked=body.series_linked,
            series_context=body.series_context or "",
            idempotency_key=body.idempotency_key,
            quality_mode=body.generation_quality_mode,
            retry_reel_id=body.retry_reel_id,
            existing_job_id=body.existing_job_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AIProviderConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return _writer_test_job_read(job)


@router.get("/writer-test-3-reels/{job_id}", response_model=WriterTestJobRead)
def get_writer_test_job(
    course_id: int, job_id: int, session: Session = Depends(get_session)
):
    """Resume a saved writer-test result without consuming new tokens."""
    get_course_or_404(session, course_id)
    job = generation_jobs.get(session, job_id)
    if job is None or job.course_id != course_id:
        raise HTTPException(status_code=404, detail="Writer test job not found")
    snap = job.run_snapshot_json or {}
    if snap.get("job_kind") != "writer_test_3_reels":
        raise HTTPException(status_code=404, detail="Not a writer-test job")
    return _writer_test_job_read(job)


@router.post("/map-preview")
def map_preview(
    course_id: int,
    body: MapPreviewRequest | None = None,
    session: Session = Depends(get_session),
):
    """Build Course Thesis + compressed Course Map only; return cost/size preview."""
    get_course_or_404(session, course_id)
    request_body = body or MapPreviewRequest()
    from app.generation.map_preview import build_map_preview
    from app.generation.errors import UnusableOutputError

    try:
        stats = build_map_preview(
            session,
            course_id,
            quality_mode=request_body.generation_quality_mode,
            human_override_hard_limits=request_body.human_override_hard_limits,
        )
    except UnusableOutputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AIProviderConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return stats.model_dump()
