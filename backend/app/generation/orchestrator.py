"""The internal generation pipeline orchestrator (docs/ARCHITECTURE.md §6).

`run_generation(session, course_id)` is the only entry point. It runs the
full 8-stage pipeline synchronously against an `AIProvider` (defaulting to
`FakeProvider` - no real API calls yet) and returns the finished
`GenerationJob`.

Only `GenerationJob.current_stage` and `.progress_percent` are the
user-visible signal of progress (values match the coarse vocabulary in
docs/PRD.md FR-8: queued/reading_sources/building_map/generating/
reviewing_repetition/reviewing/exporting/done/failed - the frontend maps
these to friendlier labels, see frontend GeneratePanel.tsx STAGE_LABELS).
`log_json` holds short, structured internal log entries for
admin/debug traceability only - see app/schemas/generation_job.py, which
deliberately excludes `log_json` from what the API ever returns. Nothing in
this file returns reel-by-reel content to a caller outside the pipeline.
"""

from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session

from app.ai.fake_provider import FakeProvider
from app.ai.provider import (
    AIProvider,
    BuildCourseMapInput,
    CourseBrief,
    FinalReviewInput,
    ModuleWithReels,
    PriorReelSummary,
    RebuildFinalCourseInput,
    ReviewFiveReelsInput,
    ReviewModuleInput,
    ReviewSingleReelInput,
    ReviewTwoModulesInput,
    SourceExcerpt,
    WriteSingleReelInput,
)
from app.config import settings
from app.crud import (
    admin_knowledge_items,
    course_sources,
    course_versions,
    courses,
    generation_jobs,
    source_analyses,
)
from app.db import engine
from app.models.course import Course
from app.models.course_source import CourseSource
from app.models.enums import ExplanationLevel, JobStatus
from app.models.generation_job import GenerationJob
from app.models.source_analysis import SourceAnalysis
from app.schemas.generation import (
    CourseMap,
    FinalCourse,
    FinalModule,
    FinalReel,
    GeneratedReel,
    ModulePlan,
    ReelPlan,
    ReviewAction,
    ReviewActionType,
    ReviewResult,
    ReviewScope,
    ReviewStatus,
)
from app.services.docx_export import export_final_course_to_docx, next_version_number
from app.services.source_analysis import SHORT_SOURCE_MAX_CHARS, select_relevant_chunks
from app.validators import check_forbidden_phrases, check_length, check_opening, check_repetition

# Usable extraction outcomes - see app/services/extraction.py. Anything else
# (password_required / extraction_blocked / scanned_no_text / failed) has no
# usable extracted_text and must never be fed into generation.
USABLE_SOURCE_STATUSES = {"ready", "poor_extraction"}

# Per docs/ARCHITECTURE.md §6.9: bounded retries, never infinite loops.
MAX_REEL_REWRITE_ATTEMPTS = 2

# Progress budget: context+map = 10%, reel generation = 10-80%,
# final review = 80-90%, save internal JSON = 90-95%, DOCX export = 95-98%,
# done = 100%.
PROGRESS_AFTER_CONTEXT_AND_MAP = 10
PROGRESS_REEL_GENERATION_SPAN = 70
PROGRESS_AFTER_FINAL_REVIEW = 90
PROGRESS_AFTER_SAVE = 95
PROGRESS_AFTER_DOCX_EXPORT = 98


@dataclass
class UsableSource:
    course_source: CourseSource
    analysis: SourceAnalysis | None


def run_generation(
    session: Session, course_id: int, provider: AIProvider | None = None
) -> GenerationJob:
    """Run the full pipeline for `course_id` and return the finished job.

    On any internal error, the job is marked FAILED with a short
    `error_message` and returned (not raised) - callers should check
    `job.status` rather than relying on an exception, per docs/PRD.md FR-10
    ("clear, actionable error state, not a raw stack trace").
    """
    provider = provider or FakeProvider()

    course = courses.get(session, course_id)
    if course is None:
        raise ValueError(f"Course {course_id} not found")

    job = generation_jobs.create(
        session,
        course_id=course_id,
        status=JobStatus.RUNNING,
        current_stage="queued",
        progress_percent=0,
        log_json=[],
    )
    logs: list[dict] = []

    def flush(**job_fields) -> None:
        nonlocal job
        job = generation_jobs.update(session, job.id, log_json=logs, **job_fields)

    try:
        # --- Steps 1-3: load context -----------------------------------
        flush(current_stage="reading_sources", progress_percent=2)
        rules_context = _load_active_rules(session)
        usable_sources = _load_usable_sources(session, course_id)
        logs.append(
            {
                "step": "load_context",
                "rules": len(rules_context),
                "sources": len(usable_sources),
            }
        )
        flush(current_stage="building_map", progress_percent=5)

        # --- Steps 4-5: build (or convert) the course map ---------------
        # Both the "manual map supplied" and "generate from scratch" cases
        # go through the same provider call: CourseBrief.manual_map_text
        # carries the branch into the provider, which is exactly what that
        # field on AIProvider's input schema exists for.
        # Map building gets source *summaries* (or full text if a source is
        # short) - never full text of a long source. See
        # app/services/source_analysis.py.
        brief = _build_course_brief(course)
        course_map = provider.build_course_map(
            BuildCourseMapInput(
                brief=brief,
                sources=_map_source_excerpts(usable_sources),
                rules_context=rules_context,
            )
        )
        total_reels = sum(len(m.reels) for m in course_map.modules)
        logs.append(
            {
                "step": "build_map",
                "source": "manual" if brief.manual_map_text else "generated",
                "modules": len(course_map.modules),
                "reels": total_reels,
            }
        )
        flush(current_stage="generating", progress_percent=PROGRESS_AFTER_CONTEXT_AND_MAP)

        # --- Steps 6-11: generate reel by reel, with layered review -----
        all_reels: list[GeneratedReel] = []
        pending_pair: tuple[ModulePlan, list[GeneratedReel]] | None = None
        reels_done = 0

        for module in course_map.modules:
            module_reels: list[GeneratedReel] = []

            for reel_plan in module.reels:
                # Reel writing gets only relevant chunks of a long source
                # (simple keyword overlap - see select_relevant_chunks), or
                # its full text if the source is short. Never a long
                # source's full text.
                generated, attempts, caught_locally = _write_and_review_reel(
                    provider=provider,
                    course_map=course_map,
                    module=module,
                    reel_plan=reel_plan,
                    prior_reels=module_reels,
                    all_reels_so_far=all_reels,
                    sources=_reel_source_excerpts(usable_sources, reel_plan),
                    rules_context=rules_context,
                )
                logs.append(
                    {
                        "step": "reel",
                        "id": reel_plan.reel_id,
                        "attempts": attempts,
                        "flagged": attempts > MAX_REEL_REWRITE_ATTEMPTS,
                        "caught_locally": caught_locally,
                    }
                )

                module_reels.append(generated)
                all_reels.append(generated)
                reels_done += 1

                progress = PROGRESS_AFTER_CONTEXT_AND_MAP + int(
                    PROGRESS_REEL_GENERATION_SPAN * reels_done / max(total_reels, 1)
                )
                flush(current_stage="generating", progress_percent=progress)

                if reels_done % 5 == 0:
                    flush(current_stage="reviewing_repetition")
                    window = all_reels[-5:]
                    result = provider.review_five_reels(
                        ReviewFiveReelsInput(reels=window, rules_context=rules_context)
                    )
                    logs.append({"step": "review_5reels", "status": result.status.value})
                    flush()

            flush(current_stage="reviewing_repetition")
            module_result = provider.review_module(
                ReviewModuleInput(
                    module=module, reels=module_reels, rules_context=rules_context
                )
            )
            logs.append(
                {
                    "step": "review_module",
                    "id": module.module_id,
                    "status": module_result.status.value,
                }
            )
            flush()

            if pending_pair is None:
                pending_pair = (module, module_reels)
            else:
                prev_module, prev_reels = pending_pair
                flush(current_stage="reviewing_repetition")
                two_result = provider.review_two_modules(
                    ReviewTwoModulesInput(
                        first=ModuleWithReels(module=prev_module, reels=prev_reels),
                        second=ModuleWithReels(module=module, reels=module_reels),
                        rules_context=rules_context,
                    )
                )
                logs.append(
                    {
                        "step": "review_2modules",
                        "ids": [prev_module.module_id, module.module_id],
                        "status": two_result.status.value,
                    }
                )
                flush()
                pending_pair = None

        if pending_pair is not None:
            logs.append({"step": "review_2modules", "skipped": "unpaired trailing module"})
            flush()

        # --- Step 12: final review ---------------------------------------
        final_result = provider.final_review(
            FinalReviewInput(
                course_map=course_map, all_reels=all_reels, rules_context=rules_context
            )
        )
        logs.append({"step": "final_review", "status": final_result.status.value})
        flush(current_stage="reviewing", progress_percent=PROGRESS_AFTER_FINAL_REVIEW)

        # --- Step 13: rebuild only if final_review actually requires it --
        if final_result.status == ReviewStatus.NEEDS_REVISION:
            final_course = provider.rebuild_final_course(
                RebuildFinalCourseInput(
                    course_map=course_map,
                    all_reels=all_reels,
                    final_review=final_result,
                    rules_context=rules_context,
                )
            )
            logs.append({"step": "rebuild_final_course", "triggered": True})
        else:
            # No AI call needed: everything already passed, so assemble the
            # already-approved content directly.
            final_course = _assemble_final_course(course_map, all_reels)
            logs.append({"step": "rebuild_final_course", "triggered": False})
        flush()

        # --- Step 14: save the final internal course JSON ---------------
        json_path = _save_internal_course_json(course_id, job.id, final_course)
        logs.append({"step": "save_internal_json", "path": str(json_path)})
        flush(current_stage="exporting", progress_percent=PROGRESS_AFTER_SAVE)

        # --- Export the DOCX and record a CourseVersion ------------------
        existing_versions = course_versions.list(session, course_id=course_id)
        version_number = next_version_number([v.version_number for v in existing_versions])
        docx_path = export_final_course_to_docx(final_course, course_id, version_number)

        # summary_text/report_text feed the frontend's explanation_level
        # display (docs/PRD.md explanation_level) - never shown for
        # "final_only", a short summary for "short_summary", the fuller
        # report only for "full_report" (kept null otherwise to signal
        # "not applicable" rather than "not generated yet").
        summary_text = _build_course_summary(course_map, all_reels, logs)
        report_text = (
            _build_course_report(course_map, all_reels, logs)
            if course.explanation_level == ExplanationLevel.FULL_REPORT
            else None
        )

        course_versions.create(
            session,
            course_id=course_id,
            version_number=version_number,
            output_docx_path=str(docx_path),
            summary_text=summary_text,
            report_text=report_text,
        )
        logs.append({"step": "export_docx", "version": version_number})
        flush(
            progress_percent=PROGRESS_AFTER_DOCX_EXPORT,
            output_docx_path=str(docx_path),
        )

        # --- Step 15: mark completed --------------------------------------
        logs.append({"step": "complete"})
        flush(status=JobStatus.COMPLETED, current_stage="done", progress_percent=100)

    except Exception as exc:  # noqa: BLE001 - convert any failure into a FAILED job
        logs.append({"step": "error", "message": str(exc)[:300]})
        flush(status=JobStatus.FAILED, current_stage="failed", error_message=str(exc)[:500])

    return job


def run_generation_job(course_id: int, provider: AIProvider | None = None) -> GenerationJob:
    """Session-managing entry point - safe to call from outside a request.

    `run_generation` takes an explicit `Session` so it can be unit-tested
    directly against an isolated in-memory DB. This wrapper instead opens
    and closes its own session, which is exactly what a background
    task/worker will need to do later: a FastAPI request-scoped session is
    closed once the response is sent, long before a background task or a
    queued job actually runs.

    For MVP, `POST /courses/{course_id}/generate` calls this directly and
    waits for the result (synchronous). Switching to
    `BackgroundTasks.add_task(run_generation_job, course_id)` or a real task
    queue later needs no change to this function - it already only takes
    plain, serializable arguments (a course id, optionally a provider).
    """
    with Session(engine) as session:
        return run_generation(session, course_id, provider)


def _load_active_rules(session: Session) -> dict[str, str]:
    """key -> content_text for every active, text-based admin knowledge item.

    docx_template items have no content_text and are skipped here - they
    aren't text to inject into a prompt.
    """
    items = admin_knowledge_items.list(session, is_active=True)
    return {item.key: item.content_text for item in items if item.content_text}


def _load_usable_sources(session: Session, course_id: int) -> list[UsableSource]:
    """Only sources whose extraction actually produced usable text, paired
    with their analysis if one exists (see app/services/source_analysis.py).

    See app/services/extraction.py / app/services/source_status.py - a
    source stuck at password_required, extraction_blocked, scanned_no_text,
    or failed must never be turned into generation input.
    """
    sources = course_sources.list(session, course_id=course_id)
    usable = [
        source
        for source in sources
        if source.status in USABLE_SOURCE_STATUSES and source.extracted_text
    ]

    result: list[UsableSource] = []
    for source in usable:
        analyses = source_analyses.list(session, source_id=source.id)
        result.append(UsableSource(course_source=source, analysis=analyses[0] if analyses else None))
    return result


def _excerpt_text_for_map(usable: UsableSource) -> str:
    """No full source text unless the source is short - otherwise its
    summary, which is exactly what course-map planning needs."""
    text = usable.course_source.extracted_text or ""
    if len(text) <= SHORT_SOURCE_MAX_CHARS:
        return text
    if usable.analysis:
        return usable.analysis.source_summary
    return text[:SHORT_SOURCE_MAX_CHARS]


def _excerpt_text_for_reel(usable: UsableSource, reel_plan: ReelPlan) -> str:
    """Relevant chunks only when writing a reel, not the whole source -
    unless the source is already short enough to just pass in full."""
    text = usable.course_source.extracted_text or ""
    if len(text) <= SHORT_SOURCE_MAX_CHARS:
        return text

    if not usable.analysis:
        return text[:SHORT_SOURCE_MAX_CHARS]

    query = " ".join([reel_plan.title, reel_plan.purpose, *reel_plan.must_cover])
    relevant = select_relevant_chunks(usable.analysis.chunks_json, query)
    if relevant:
        return "\n\n".join(chunk.get("text", "") for chunk in relevant)
    return usable.analysis.source_summary


def _map_source_excerpts(usable_sources: list[UsableSource]) -> list[SourceExcerpt]:
    return [
        SourceExcerpt(
            source_id=usable.course_source.id,
            category=usable.course_source.source_category.value,
            priority=usable.course_source.priority.value,
            text=_excerpt_text_for_map(usable),
        )
        for usable in usable_sources
    ]


def _reel_source_excerpts(
    usable_sources: list[UsableSource], reel_plan: ReelPlan
) -> list[SourceExcerpt]:
    return [
        SourceExcerpt(
            source_id=usable.course_source.id,
            category=usable.course_source.source_category.value,
            priority=usable.course_source.priority.value,
            text=_excerpt_text_for_reel(usable, reel_plan),
        )
        for usable in usable_sources
    ]


def _build_course_brief(course: Course) -> CourseBrief:
    manual_map = (course.manual_map_text or "").strip() or None
    return CourseBrief(
        title=course.title,
        audience=course.audience,
        outcome=course.outcome,
        special_notes=course.special_notes,
        structure_mode=course.structure_mode,
        explanation_level=course.explanation_level,
        manual_map_text=manual_map,
    )


def _local_review_single_reel(
    generated: GeneratedReel,
    all_reels_so_far: list[GeneratedReel],
    rules_context: dict[str, str],
) -> ReviewResult | None:
    """Run the local validators (app/validators/) before paying for an AI
    review call. Returns a ReviewResult if something obvious was found -
    the caller should skip the AI call and use this instead - or None if
    nothing obvious was found, meaning the real review should still run.
    """
    actions: list[ReviewAction] = []

    for match in check_forbidden_phrases(generated.script_text, rules_context):
        instruction = f"Remove the forbidden phrase '{match.phrase}'."
        if match.replacement_hint:
            instruction += f" Try instead: {match.replacement_hint}"
        actions.append(
            ReviewAction(
                action=ReviewActionType.REWRITE,
                target_id=generated.reel_id,
                reason_code="forbidden_phrase",
                instruction=instruction,
            )
        )

    for issue in check_length(generated):
        verb = "Expand" if issue.reason == "too_short" else "Shorten"
        actions.append(
            ReviewAction(
                action=ReviewActionType.REWRITE,
                target_id=generated.reel_id,
                reason_code=issue.reason,
                instruction=f"{verb} the script - it's currently {issue.word_count} words.",
            )
        )

    for match in check_repetition(generated, all_reels_so_far):
        actions.append(
            ReviewAction(
                action=ReviewActionType.REWRITE,
                target_id=generated.reel_id,
                reason_code="repetition",
                instruction=match.detail,
            )
        )

    for issue in check_opening(generated, all_reels_so_far):
        actions.append(
            ReviewAction(
                action=ReviewActionType.REWRITE,
                target_id=generated.reel_id,
                reason_code="repeated_opening",
                instruction=f"Opening repeats reel '{issue.repeats_reel_id}' - start differently.",
            )
        )

    if not actions:
        return None
    return ReviewResult(scope=ReviewScope.REEL, status=ReviewStatus.NEEDS_REVISION, actions=actions)


def _write_and_review_reel(
    *,
    provider: AIProvider,
    course_map: CourseMap,
    module: ModulePlan,
    reel_plan: ReelPlan,
    prior_reels: list[GeneratedReel],
    all_reels_so_far: list[GeneratedReel],
    sources: list[SourceExcerpt],
    rules_context: dict[str, str],
) -> tuple[GeneratedReel, int, bool]:
    """Steps 6-8: write one reel, review it, rewrite up to MAX_REEL_REWRITE_ATTEMPTS times.

    Local validators run before the AI review call on every attempt; only
    when they find nothing obvious does this actually call
    `provider.review_single_reel`. Returns (generated_reel, attempts,
    caught_locally) - `caught_locally` is True if any attempt's issue was
    found by a local validator rather than the AI reviewer.
    """
    prior_summaries = [
        PriorReelSummary(
            reel_id=r.reel_id,
            title=r.title,
            used_ideas=r.used_ideas,
            used_examples=r.used_examples,
        )
        for r in prior_reels
    ]

    attempts = 0
    feedback: list[str] = []
    caught_locally = False

    while True:
        attempts += 1
        write_input = WriteSingleReelInput(
            course_title=course_map.course_title,
            main_thread=course_map.main_thread,
            module=module,
            reel=reel_plan,
            prior_reels_in_module=prior_summaries,
            sources=sources,
            rules_context=rules_context,
            previous_review_feedback=feedback,
        )
        generated = provider.write_single_reel(write_input)

        local_result = _local_review_single_reel(generated, all_reels_so_far, rules_context)
        if local_result is not None:
            review = local_result
            caught_locally = True
        else:
            review = provider.review_single_reel(
                ReviewSingleReelInput(
                    reel_plan=reel_plan, generated_reel=generated, rules_context=rules_context
                )
            )

        if review.status == ReviewStatus.PASS or attempts > MAX_REEL_REWRITE_ATTEMPTS:
            return generated, attempts, caught_locally

        feedback = [action.instruction for action in review.actions]


def _assemble_final_course(course_map: CourseMap, all_reels: list[GeneratedReel]) -> FinalCourse:
    """Deterministic, no-AI-call assembly used when final_review already passed.

    Intentionally separate from any provider's `rebuild_final_course`: this
    path exists precisely to avoid an unnecessary (and, for a real provider,
    potentially expensive) AI call when nothing actually needs fixing.
    """
    sections: list[str] = []
    final_modules: list[FinalModule] = []

    for module in course_map.modules:
        sections.append(f"# {module.title}")
        module_reels = [r for r in all_reels if r.module_id == module.module_id]

        final_reels: list[FinalReel] = []
        for reel in module_reels:
            sections.append(f"## {reel.title}")
            sections.append(reel.script_text)
            final_reels.append(
                FinalReel(reel_id=reel.reel_id, title=reel.title, script_text=reel.script_text)
            )

        if module.bridge_project:
            sections.append(f"[Bridge project] {module.bridge_project}")

        final_modules.append(
            FinalModule(
                module_id=module.module_id,
                title=module.title,
                bridge_project=module.bridge_project,
                reels=final_reels,
            )
        )

    return FinalCourse(
        title=course_map.course_title,
        modules=final_modules,
        full_text="\n\n".join(sections),
    )


def _build_course_summary(
    course_map: CourseMap, all_reels: list[GeneratedReel], logs: list[dict]
) -> str:
    """Short, human-readable summary - shown to the user when
    Course.explanation_level is "short_summary" (see frontend GeneratePanel.tsx)."""
    flagged = [e["id"] for e in logs if e.get("step") == "reel" and e.get("flagged")]
    summary = (
        f"'{course_map.course_title}' was generated with "
        f"{len(course_map.modules)} module(s) and {len(all_reels)} reel(s)."
    )
    if flagged:
        summary += f" {len(flagged)} reel(s) were flagged during review and may need a look."
    else:
        summary += " All reels passed review."
    return summary


def _build_course_report(
    course_map: CourseMap, all_reels: list[GeneratedReel], logs: list[dict]
) -> str:
    """Longer, structured report - shown to the user only when
    Course.explanation_level is "full_report" (see frontend GeneratePanel.tsx)."""
    lines = [f"Course: {course_map.course_title}", f"Main thread: {course_map.main_thread}", ""]

    for module in course_map.modules:
        reel_count = sum(1 for r in all_reels if r.module_id == module.module_id)
        line = f"- {module.title} ({reel_count} reel(s))"
        if module.bridge_project:
            line += f" -> bridge project: {module.bridge_project}"
        lines.append(line)

    review_steps = [
        e
        for e in logs
        if e.get("step") in ("review_5reels", "review_module", "review_2modules", "final_review")
    ]
    flagged_needing_revision = sum(1 for e in review_steps if e.get("status") == "needs_revision")
    lines.append("")
    lines.append(
        f"Review checkpoints run: {len(review_steps)} "
        f"({flagged_needing_revision} found something to revise)."
    )

    flagged_reels = [e["id"] for e in logs if e.get("step") == "reel" and e.get("flagged")]
    if flagged_reels:
        lines.append(f"Reels flagged after max retries: {', '.join(flagged_reels)}.")

    return "\n".join(lines)


def _save_internal_course_json(course_id: int, job_id: int, final_course: FinalCourse) -> Path:
    """Save under storage/outputs/{course_id}/internal/ - clearly separated
    from the user-facing DOCX path (storage/outputs/{course_id}/v{n}.docx),
    since this JSON must never be treated as a deliverable."""
    output_dir = settings.storage_outputs_dir / str(course_id) / "internal"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"job_{job_id}.json"
    path.write_text(final_course.model_dump_json(indent=2), encoding="utf-8")
    return path
