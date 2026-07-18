"""Finalize a generation job from already-saved lessons — no AI calls.

Used when the worker dies after every lesson is persisted
(`completed_reels_json` complete) but before DOCX export / COMPLETED.
Assembles the teleprompter from saved Final Master scripts only.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlmodel import Session

from app.config import settings
from app.crud import course_versions, generation_jobs
from app.generation.course_quality_gates import format_handoff_status
from app.models.enums import JobStatus
from app.models.generation_job import GenerationJob
from app.schemas.generation import (
    CourseMap,
    FinalCourse,
    FinalModule,
    FinalReel,
    GeneratedReel,
)
from app.services.docx_export import export_final_course_to_docx, next_version_number
from app.services.json_coerce import coerce_json_dict, coerce_json_list

logger = logging.getLogger(__name__)

# Stages where lesson generation is done and only finalization/export remain.
POST_LESSON_STAGES: frozenset[str] = frozenset(
    {
        "reviewing",
        "reviewing_repetition",
        "exporting",
    }
)


@dataclass(frozen=True)
class SavedLessonsInspection:
    ok: bool
    planned_count: int
    saved_count: int
    unique_saved_count: int
    missing_reel_ids: tuple[str, ...]
    duplicate_reel_ids: tuple[str, ...]
    empty_script_reel_ids: tuple[str, ...]
    reason: str = ""


def inspect_saved_lessons(job: GenerationJob) -> SavedLessonsInspection:
    """Verify course_map + completed_reels are complete, unique, and non-empty."""
    course_map_data = coerce_json_dict(job.course_map_json)
    reels_data = coerce_json_list(job.completed_reels_json)
    if not course_map_data:
        return SavedLessonsInspection(
            ok=False,
            planned_count=0,
            saved_count=0,
            unique_saved_count=0,
            missing_reel_ids=(),
            duplicate_reel_ids=(),
            empty_script_reel_ids=(),
            reason="missing_course_map",
        )

    try:
        course_map = CourseMap.model_validate(course_map_data)
    except Exception as exc:  # noqa: BLE001
        return SavedLessonsInspection(
            ok=False,
            planned_count=0,
            saved_count=len(reels_data),
            unique_saved_count=0,
            missing_reel_ids=(),
            duplicate_reel_ids=(),
            empty_script_reel_ids=(),
            reason=f"invalid_course_map:{type(exc).__name__}",
        )

    planned_ids = [r.reel_id for m in course_map.modules for r in m.reels]
    planned_count = len(planned_ids)
    if planned_count == 0:
        return SavedLessonsInspection(
            ok=False,
            planned_count=0,
            saved_count=len(reels_data),
            unique_saved_count=0,
            missing_reel_ids=(),
            duplicate_reel_ids=(),
            empty_script_reel_ids=(),
            reason="empty_course_map",
        )

    saved_reels: list[GeneratedReel] = []
    for raw in reels_data:
        if not isinstance(raw, dict):
            continue
        try:
            saved_reels.append(GeneratedReel.model_validate(raw))
        except Exception:  # noqa: BLE001
            continue

    saved_ids = [r.reel_id for r in saved_reels]
    unique_ids = set(saved_ids)
    duplicate_reel_ids = tuple(
        sorted({rid for rid in saved_ids if saved_ids.count(rid) > 1})
    )
    missing_reel_ids = tuple(rid for rid in planned_ids if rid not in unique_ids)
    empty_script_reel_ids = tuple(
        sorted(r.reel_id for r in saved_reels if not (r.script_text or "").strip())
    )

    declared_total = int(job.total_lessons_count or 0)
    declared_done = int(job.completed_reels_count or 0)
    counts_match = (
        len(saved_reels) == planned_count
        and len(unique_ids) == planned_count
        and (declared_total == 0 or declared_total == planned_count)
        and (declared_done == 0 or declared_done == planned_count)
    )
    ok = (
        counts_match
        and not missing_reel_ids
        and not duplicate_reel_ids
        and not empty_script_reel_ids
    )
    reason = "ok" if ok else "incomplete_or_inconsistent_lessons"
    return SavedLessonsInspection(
        ok=ok,
        planned_count=planned_count,
        saved_count=len(saved_reels),
        unique_saved_count=len(unique_ids),
        missing_reel_ids=missing_reel_ids,
        duplicate_reel_ids=duplicate_reel_ids,
        empty_script_reel_ids=empty_script_reel_ids,
        reason=reason,
    )


# Active runs plus terminal runs that timed out / were abandoned after every
# lesson was already persisted (e.g. Job 51 → PARTIAL + timeout).
RECOVERABLE_STATUSES: frozenset[JobStatus] = frozenset(
    {
        JobStatus.PENDING,
        JobStatus.RUNNING,
        JobStatus.PAUSED,
        JobStatus.PARTIAL,
        JobStatus.FAILED,
        JobStatus.CANCELED,
    }
)


def job_eligible_for_saved_finalize(job: GenerationJob) -> bool:
    """True when a job can be completed from saved lessons without AI."""
    if job.status not in RECOVERABLE_STATUSES:
        return False
    if job.output_docx_path:
        return False
    stage = (job.current_stage or "").lower()
    if stage not in POST_LESSON_STAGES:
        # Also allow generating when counters already say every lesson is saved
        # (worker died after last save flush but before stage flip).
        total = int(job.total_lessons_count or 0)
        done = int(job.completed_reels_count or 0)
        if not (total > 0 and done >= total):
            return False
    return inspect_saved_lessons(job).ok


def format_stopped_after_label(last_completed_step: str | None) -> str | None:
    """User-safe label for where a run stopped (never raw log_json)."""
    if not last_completed_step:
        return None
    step = last_completed_step.strip()
    if not step:
        return None
    if step.startswith("reel:"):
        return "Saving lessons"
    if step.startswith("module:"):
        return "Module review"
    if step == "lessons_complete":
        return "All lessons saved"
    if step == "final_review":
        return "Final review"
    if step == "rebuild_final_course":
        return "Final assembly"
    if step == "save_internal_json":
        return "Saving course"
    if step == "export_docx":
        return "Teleprompter export"
    if step == "build_map":
        return "Course map"
    return step.replace("_", " ")


def try_recover_job_from_saved_lessons(
    session: Session,
    job: GenerationJob,
) -> GenerationJob:
    """If every lesson is saved, finalize to COMPLETED on read/poll (no AI)."""
    if job.status == JobStatus.COMPLETED and job.output_docx_path:
        return job
    if job.output_docx_path:
        return job
    if not job_eligible_for_saved_finalize(job):
        return job
    recovered = finalize_job_from_saved_lessons(session, job)
    return recovered if recovered is not None else job


def backup_job_snapshot(job: GenerationJob) -> Path:
    """Write a JSON snapshot under storage/backups/jobs/ before mutating."""
    backup_dir = Path(settings.storage_dir) / "backups" / "jobs"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = backup_dir / f"job_{job.id}_{stamp}.json"

    payload: dict[str, Any] = {
        "backed_up_at": stamp,
        "job": {
            "id": job.id,
            "course_id": job.course_id,
            "status": job.status.value if hasattr(job.status, "value") else str(job.status),
            "current_stage": job.current_stage,
            "progress_percent": job.progress_percent,
            "completed_reels_count": job.completed_reels_count,
            "total_lessons_count": job.total_lessons_count,
            "completed_modules_count": job.completed_modules_count,
            "last_completed_step": job.last_completed_step,
            "last_progress_message": job.last_progress_message,
            "last_saved_at": (
                job.last_saved_at.isoformat() if job.last_saved_at else None
            ),
            "output_docx_path": job.output_docx_path,
            "partial_docx_path": job.partial_docx_path,
            "error_message": job.error_message,
            "error_category": job.error_category,
            "course_map_json": coerce_json_dict(job.course_map_json),
            "completed_reels_json": coerce_json_list(job.completed_reels_json),
            "log_json": coerce_json_list(job.log_json),
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _assemble_from_saved(course_map: CourseMap, reels: list[GeneratedReel]) -> FinalCourse:
    by_id = {r.reel_id: r for r in reels}
    sections: list[str] = []
    final_modules: list[FinalModule] = []

    for module in course_map.modules:
        sections.append(f"# {module.title}")
        final_reels: list[FinalReel] = []
        for plan in module.reels:
            reel = by_id[plan.reel_id]
            sections.append(f"## {reel.title}")
            sections.append(reel.script_text)
            final_reels.append(
                FinalReel(
                    reel_id=reel.reel_id,
                    title=reel.title,
                    script_text=reel.script_text,
                    spoken_beats=list(reel.spoken_beats or []),
                    delivery_mode=reel.delivery_mode,
                    quality_status=reel.quality_status,
                )
            )
        final_modules.append(
            FinalModule(
                module_id=module.module_id,
                title=module.title,
                bridge_project=module.bridge_project,
                module_project=module.module_project,
                reels=final_reels,
            )
        )

    return FinalCourse(
        title=course_map.course_title,
        modules=final_modules,
        full_text="\n\n".join(sections),
        graduation_project=course_map.graduation_project,
        thesis=course_map.thesis,
    )


def finalize_job_from_saved_lessons(
    session: Session,
    job: GenerationJob,
    *,
    force: bool = False,
) -> GenerationJob | None:
    """Export DOCX + mark COMPLETED from saved lessons. Never calls an AI provider.

    Returns the updated job, or None if the job was not eligible / not intact.
    """
    if job.status == JobStatus.COMPLETED and job.output_docx_path:
        return job
    if not force and not job_eligible_for_saved_finalize(job):
        return None

    inspection = inspect_saved_lessons(job)
    if not inspection.ok:
        logger.warning(
            "finalize_saved_job skipped job_id=%s reason=%s missing=%s dupes=%s empty=%s",
            job.id,
            inspection.reason,
            inspection.missing_reel_ids[:8],
            inspection.duplicate_reel_ids[:8],
            inspection.empty_script_reel_ids[:8],
        )
        return None

    backup_path = backup_job_snapshot(job)
    logger.info(
        "finalize_saved_job backup job_id=%s path=%s lessons=%s",
        job.id,
        backup_path,
        inspection.planned_count,
    )

    course_map = CourseMap.model_validate(coerce_json_dict(job.course_map_json) or {})
    reels = [
        GeneratedReel.model_validate(raw)
        for raw in coerce_json_list(job.completed_reels_json)
        if isinstance(raw, dict)
    ]
    # Prefer first occurrence if any duplicate slipped past inspection.
    deduped: dict[str, GeneratedReel] = {}
    for reel in reels:
        deduped.setdefault(reel.reel_id, reel)
    ordered = [
        deduped[plan.reel_id]
        for module in course_map.modules
        for plan in module.reels
    ]
    final_course = _assemble_from_saved(course_map, ordered)

    # Recovery must never bypass quality / export blockers.
    from app.generation.export_blockers import assert_export_allowed, evaluate_export_blockers
    from app.models.enums import AddressForm

    address_form = (
        course_map.thesis.address_form if course_map.thesis else AddressForm.MASCULINE
    )
    export_report = evaluate_export_blockers(
        final_course=final_course,
        course_map=course_map,
        thesis=course_map.thesis,
        generated_reels=ordered,
        address_form=address_form,
    )
    if not export_report.ok:
        logger.warning(
            "finalize_saved_job blocked by export gates job_id=%s blockers=%s",
            job.id,
            export_report.model_dump(),
        )
        assert_export_allowed(export_report)

    existing_versions = course_versions.list(session, course_id=job.course_id)
    version_number = next_version_number([v.version_number for v in existing_versions])
    try:
        docx_path = export_final_course_to_docx(
            final_course, job.course_id, version_number
        )
    except OSError as export_os_exc:
        logger.error(
            "finalize_saved_job DOCX write failed job_id=%s: %s",
            job.id,
            export_os_exc,
        )
        return None

    summary_text = (
        f"'{course_map.course_title}' · Teleprompter DOCX ready · "
        f"{len(course_map.modules)} module(s) · {len(ordered)} lesson(s)."
    )
    try:
        course_versions.create(
            session,
            course_id=job.course_id,
            version_number=version_number,
            output_docx_path=str(docx_path),
            summary_text=summary_text,
            report_text=None,
        )
    except Exception:
        try:
            Path(docx_path).unlink(missing_ok=True)
        except OSError:
            pass
        raise

    # Keep internal JSON for debug parity with normal completion path.
    internal_dir = settings.storage_outputs_dir / str(job.course_id) / "internal"
    internal_dir.mkdir(parents=True, exist_ok=True)
    (internal_dir / f"job_{job.id}.json").write_text(
        final_course.model_dump_json(indent=2), encoding="utf-8"
    )

    logs = coerce_json_list(job.log_json)
    logs.append(
        {
            "step": "finalize_from_saved_lessons",
            "backup": str(backup_path),
            "lessons": inspection.planned_count,
            "version": version_number,
            "ai_calls": 0,
        }
    )
    logs.append({"step": "export_docx", "version": version_number})
    logs.append({"step": "complete"})

    handoff = format_handoff_status(
        lessons=inspection.planned_count,
        estimated_minutes=0,
        complete=True,
        risk_count=0,
    )
    updated = generation_jobs.update(
        session,
        job.id,
        status=JobStatus.COMPLETED,
        current_stage="done",
        progress_percent=100,
        output_docx_path=str(docx_path),
        last_completed_step="export_docx",
        completed_reels_count=inspection.planned_count,
        total_lessons_count=inspection.planned_count,
        last_progress_message=handoff,
        error_message=None,
        error_category=None,
        partial_docx_path=job.partial_docx_path,
        cancel_requested=False,
        log_json=logs,
        last_saved_at=datetime.now(timezone.utc),
    )
    logger.info(
        "finalize_saved_job completed job_id=%s course_id=%s version=%s (no AI)",
        job.id,
        job.course_id,
        version_number,
    )
    return updated
