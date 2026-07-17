from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlmodel import Session

from app.crud import admin_knowledge_items, courses
from app.db import get_session
from app.generation.admin_knowledge_cleanup import filter_active_primary
from app.routers.deps import get_course_or_404
from app.schemas.course import CourseCreate, CourseRead, CourseUpdate
from app.services.audit import record_audit
from app.services.course_idempotency import (
    lookup_idempotent_course,
    remember_idempotent_course,
)

router = APIRouter(prefix="/courses", tags=["courses"])


def _actor(request: Request) -> str | None:
    return getattr(request.state, "username", None)


@router.post("", response_model=CourseRead, status_code=201)
def create_course(
    payload: CourseCreate,
    request: Request,
    session: Session = Depends(get_session),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    """Create a course. Optional Idempotency-Key returns the prior course on retry."""
    actor = _actor(request)
    cache_key = None
    if idempotency_key:
        cache_key = f"{actor or 'anon'}:{idempotency_key.strip()}"
        existing_id = lookup_idempotent_course(cache_key)
        if existing_id is not None:
            existing = courses.get(session, existing_id)
            if existing is not None:
                return existing

    created = courses.create(session, **payload.model_dump())
    if cache_key and created.id is not None:
        remember_idempotent_course(cache_key, created.id)

    record_audit(
        session,
        action="course_create",
        actor=actor,
        affected_table="courses",
        affected_count=1,
        dry_run=False,
        confirmed=True,
        success=True,
        details={"id": created.id, "title": created.title},
    )
    return created


@router.get("", response_model=list[CourseRead])
def list_courses(session: Session = Depends(get_session)):
    return courses.list(session)


@router.get("/{course_id}/readiness", response_model=dict)
def course_readiness(course_id: int, session: Session = Depends(get_session)):
    """Course-safe summary for Start gating — never returns Admin Knowledge bodies."""
    from app.ai.factory import missing_anthropic_config
    from app.config import settings
    from app.crud import course_sources
    from app.services.source_run_honesty import (
        OVERLOAD_CHAR_BUDGET,
        classify_sources_for_run,
    )
    from app.services.source_status import (
        EXTRACTION_BLOCKED,
        FAILED,
        PASSWORD_REQUIRED,
        POOR_EXTRACTION,
        PROCESSING_FAILED,
        SCANNED_NO_TEXT,
    )

    get_course_or_404(session, course_id)
    course = courses.get(session, course_id)
    primary = filter_active_primary(admin_knowledge_items.list(session))
    sources = course_sources.list(session, course_id=course_id)
    included = [
        s
        for s in sources
        if getattr(s, "include_in_generation", True)
        and (getattr(s, "extracted_text", None) or getattr(s, "file_path", None))
    ]
    honesty = classify_sources_for_run(sources)

    from app.generation.brief_clarity import score_brief_clarity
    from app.generation.mission_brief import build_mission_brief

    clarity = score_brief_clarity(
        title=getattr(course, "title", "") or "",
        audience=getattr(course, "audience", "") or "",
        outcome=getattr(course, "outcome", "") or "",
        special_notes=getattr(course, "special_notes", None),
    )

    mission = build_mission_brief(
        title=getattr(course, "title", "") or "",
        audience=getattr(course, "audience", "") or "",
        outcome=getattr(course, "outcome", "") or "",
        clarity=clarity,
        included_source_count=len(included),
        sources_summary=honesty.get("summary"),
    )

    ranking_tips: list[str] = []
    for s in sources:
        label = (
            getattr(s, "title", None)
            or getattr(s, "original_filename", None)
            or f"source-{s.id}"
        )
        cat = getattr(s, "source_category", None)
        cat_val = cat.value if hasattr(cat, "value") else str(cat or "")
        if not getattr(s, "include_in_generation", True):
            ranking_tips.append(f"{label}: excluded")
            continue
        if s.status == POOR_EXTRACTION:
            ranking_tips.append(f"{label}: weak extract — prefer Include off")
            continue
        if s.status in {PASSWORD_REQUIRED, SCANNED_NO_TEXT, FAILED, PROCESSING_FAILED, EXTRACTION_BLOCKED}:
            ranking_tips.append(f"{label}: unusable ({s.status})")
            continue
        if cat_val == "flow_reference":
            ranking_tips.append(f"{label}: colloquial-only")
        elif cat_val in {"user_notes", "transcript"}:
            ranking_tips.append(f"{label}: notes/transcript")
        elif cat_val in {"mixed_quality_ai_course_draft", "old_course"}:
            ranking_tips.append(f"{label}: brief-only candidates (mixed draft)")
        else:
            ranking_tips.append(f"{label}: full")

    warnings_preload: list[str] = []
    if honesty.get("overload") and any(
        "weak extract" in t or "brief-only" in t for t in ranking_tips
    ):
        warnings_preload.append(
            "Library is large — turn Include off on weak/brief-only sources to protect budget."
        )

    provider = (settings.ai_provider or "fake").strip().lower()
    provider_ready = True
    provider_detail = None
    if provider == "anthropic":
        missing = missing_anthropic_config(settings)
        provider_ready = not missing
        provider_detail = (
            None if provider_ready else f"Missing: {', '.join(missing)}"
        )

    can_start = provider_ready and not clarity.get("blockers")
    blockers: list[str] = []
    if not provider_ready:
        blockers.append("AI provider is not configured.")
    blockers.extend(clarity.get("blockers") or [])
    warnings: list[str] = list(warnings_preload)
    warnings.extend(clarity.get("warnings") or [])
    if len(included) == 0:
        warnings.append(
            "No course sources are included for generation. You can still start; "
            "the run will rely on the brief and Admin Knowledge only."
        )

    password_n = sum(1 for s in sources if s.status == PASSWORD_REQUIRED)
    scanned_n = sum(1 for s in sources if s.status == SCANNED_NO_TEXT)
    failed_n = sum(
        1
        for s in sources
        if s.status in {FAILED, PROCESSING_FAILED, EXTRACTION_BLOCKED}
    )
    weak_n = sum(
        1
        for s in sources
        if s.status == POOR_EXTRACTION and getattr(s, "include_in_generation", True)
    )
    if password_n:
        warnings.append(
            f"{password_n} source(s) need a password unlock before they can be used."
        )
    if scanned_n:
        warnings.append(
            f"{scanned_n} scanned/image-only PDF(s) have no selectable text "
            "(OCR is not supported in V1 — upload a text PDF or notes instead)."
        )
    if failed_n:
        warnings.append(
            f"{failed_n} source(s) failed extraction — use Retry or replace the file."
        )
    if weak_n:
        warnings.append(
            f"{weak_n} weak extract(s) are still included — prefer cleaner files "
            "or turn Include off until fixed."
        )
    if honesty.get("overload"):
        warnings.append(
            f"Included source text is large (~{honesty['included_chars']} chars). "
            f"Generation trims toward ~{OVERLOAD_CHAR_BUDGET} characters of "
            "library context — lower-priority material may be dropped."
        )

    return {
        "course_id": course_id,
        "active_rule_key_count": len(primary),
        "source_count": len(sources),
        "included_source_count": len(included),
        "included_chars": honesty.get("included_chars", 0),
        "sources_summary": honesty.get("summary"),
        "source_ranking_tips": ranking_tips[:20],
        "overload": bool(honesty.get("overload")),
        "brief_clarity": clarity,
        "premium_recommended": bool(clarity.get("premium_recommended")),
        "mission_brief": mission,
        "provider": provider,
        "provider_ready": provider_ready,
        "provider_detail": provider_detail,
        "can_start": can_start,
        "blockers": blockers,
        "warnings": warnings,
        "message": "Admin Knowledge is global; course sources stay course-scoped.",
    }


@router.get("/{course_id}", response_model=CourseRead)
def get_course(course_id: int, session: Session = Depends(get_session)):
    return get_course_or_404(session, course_id)


@router.put("/{course_id}", response_model=CourseRead)
def update_course(
    course_id: int,
    payload: CourseUpdate,
    request: Request,
    session: Session = Depends(get_session),
):
    get_course_or_404(session, course_id)
    updated = courses.update(session, course_id, **payload.model_dump(exclude_unset=True))
    record_audit(
        session,
        action="course_update",
        actor=_actor(request),
        affected_table="courses",
        affected_count=1,
        dry_run=False,
        confirmed=True,
        success=True,
        details={"id": course_id, "fields": sorted(payload.model_dump(exclude_unset=True))},
    )
    return updated
