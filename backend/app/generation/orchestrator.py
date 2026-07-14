"""The internal generation pipeline orchestrator (docs/ARCHITECTURE.md §6).

`run_generation(session, course_id)` is the only entry point. It runs the
full 8-stage pipeline synchronously against an `AIProvider` (defaulting to
whatever `app/ai/factory.py get_ai_provider()` selects via `AI_PROVIDER` -
`FakeProvider` unless real AI is explicitly configured) and returns the
finished `GenerationJob`.

Only `GenerationJob.current_stage` and `.progress_percent` are the
user-visible signal of progress (values match the coarse vocabulary in
docs/PRD.md FR-8: queued/reading_sources/building_map/generating/
reviewing_repetition/reviewing/exporting/done/failed/partial - the frontend
maps these to friendlier labels, see frontend GeneratePanel.tsx
STAGE_LABELS). `log_json` holds short, structured internal log entries for
admin/debug traceability only - see app/schemas/generation_job.py, which
deliberately excludes `log_json` from what the API ever returns. Nothing in
this file returns reel-by-reel content to a caller outside the pipeline.

Loss-safe persistence: `course_map_json` and `completed_reels_json` (see
app/models/generation_job.py) are flushed to the DB as soon as each piece
completes - the course map right after it's built, each reel right after
it's appended - so a mid-run failure never loses already-completed work.
On failure, `except Exception` below classifies the error
(app/generation/errors.py) and, if any of that persisted state exists,
builds and saves a partial DOCX and ends the job `PARTIAL` instead of
`FAILED`. There is deliberately no `resume_generation`: the two-module
review pairing (`pending_pair` below) can't be safely reconstructed from
`completed_reels_json` alone (a crash between a module's own review and
its pairing review would look identical, on resume, to one where the pairing
already ran) - see README.md's "Generation resilience" section. Partial
DOCX download is the supported recovery path for now.
"""

from dataclasses import dataclass
from pathlib import Path

from sqlmodel import Session

from app.ai.factory import get_ai_provider
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
    ai_usage_events,
    course_sources,
    course_versions,
    courses,
    generation_jobs,
    source_analyses,
)
from app.db import engine
from app.generation.budget_guard import compute_budget_warning
from app.generation.errors import classify_provider_error, error_message_for
from app.generation.output_scoring import OutputScoreReport, score_final_course
from app.generation.pricing import estimate_cost_usd
from app.generation.prompt_compiler import (
    SourceForCompiler,
    compile_source_context,
    select_rules_for_stage,
)
from app.generation.run_snapshot import build_run_snapshot
from app.models.course import Course
from app.models.course_source import CourseSource
from app.models.enums import ExplanationLevel, JobStatus
from app.models.generation_job import GenerationJob
from app.models.source_analysis import SourceAnalysis
from app.prompts.prompt_registry import PipelineStage
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
from app.services.docx_export import (
    build_partial_course_from_job,
    export_final_course_to_docx,
    export_partial_course_to_docx,
    extract_plain_text,
    next_version_number,
    render_final_course_docx,
    render_partial_course_docx,
)
from app.validators import (
    check_anti_template,
    check_forbidden_phrases,
    check_high_signal,
    check_length,
    check_opening,
    check_repetition,
)

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


def _record_usage_event(
    session: Session,
    job: GenerationJob,
    provider: AIProvider,
    stage: PipelineStage,
    preset: str,
) -> None:
    """AI Usage Center (§5): persist one `AIUsageEvent` row for the call
    that just completed on `provider`, reading `provider.last_usage` if the
    provider exposes it (deliberately `hasattr`-guarded, same decoupling
    pattern as `configure_for_run` above - this keeps `AIProvider`
    implementations entirely DB-independent; only the orchestrator, which
    already holds `session`, does the persisting).

    A provider with no `last_usage` (or one that's still `None`, e.g.
    before its first call) simply means nothing is recorded for that call -
    never an error.
    """
    usage = getattr(provider, "last_usage", None)
    if not usage:
        return

    provider_name = (settings.ai_provider or "fake").strip().lower()
    model_name = usage.get("model") or ("fake" if provider_name == "fake" else settings.ai_model_name)
    estimated_cost = 0.0 if provider_name == "fake" else estimate_cost_usd(
        model_name, usage.get("input_tokens"), usage.get("output_tokens")
    )

    ai_usage_events.create(
        session,
        job_id=job.id,
        course_id=job.course_id,
        stage=stage.value,
        provider=provider_name,
        model=model_name,
        preset=preset,
        input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
        cache_read_tokens=usage.get("cache_read_input_tokens"),
        cache_write_tokens=usage.get("cache_creation_input_tokens"),
        estimated_cost_usd=estimated_cost,
        status="ok",
    )


def run_generation(
    session: Session, course_id: int, provider: AIProvider | None = None
) -> GenerationJob:
    """Run the full pipeline for `course_id` and return the finished job.

    On any internal error, the job is marked FAILED (nothing usable was
    saved yet) or PARTIAL (a course map and/or at least one completed reel
    survived - see the module docstring above) with a short, clean
    `error_message` and returned (not raised) - callers should check
    `job.status` rather than relying on an exception, per docs/PRD.md FR-10
    ("clear, actionable error state, not a raw stack trace").
    """
    # Explicit `provider` arg (tests, scripts) always wins; otherwise the
    # default provider is whatever AI_PROVIDER selects (app/ai/factory.py) -
    # FakeProvider unless real AI is explicitly configured. This can raise
    # AIProviderConfigError, which deliberately propagates uncaught here
    # (before any GenerationJob row exists) rather than being absorbed into
    # a FAILED job - see app/routers/generation.py for how callers handle it.
    provider = provider or get_ai_provider()

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
    # Initialized here (not inside `try`) so the `except` block below can
    # always safely reference them - a failure that happens before
    # `_load_active_rules`/`_load_usable_sources` complete would otherwise
    # leave these undefined right when the error path needs them for
    # output scoring/the run snapshot.
    rules_context: dict[str, str] = {}
    usable_sources: list[UsableSource] = []
    preset_value: str = course.generation_preset.value

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
        # Run snapshot metadata (§2 & §3) - immutable once written here,
        # never touched again for the rest of this run. See
        # app/generation/run_snapshot.py for exactly what's stored (hashes
        # only, never raw admin-knowledge/source text) and why this lives
        # on GenerationJob rather than Course.
        run_snapshot = build_run_snapshot(
            rules_context=rules_context,
            generation_preset=preset_value,
            source_ids_used=[u.course_source.id for u in usable_sources],
        )
        flush(run_snapshot_json=run_snapshot)
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
        # Deliberately `hasattr`-guarded rather than a method on the
        # `AIProvider` ABC (see app/ai/provider.py): this is how a real
        # provider picks up the course's actual generation_preset once per
        # run (see AnthropicProvider.configure_for_run) without every
        # stage's Input model needing to carry it - and it means
        # `FakeProvider` needs zero changes.
        if hasattr(provider, "configure_for_run"):
            provider.configure_for_run(brief.generation_preset)
        logs.append({"step": "load_brief", "preset": brief.generation_preset.value})
        course_map = provider.build_course_map(
            BuildCourseMapInput(
                brief=brief,
                sources=_map_source_excerpts(usable_sources),
                rules_context=select_rules_for_stage(rules_context, PipelineStage.BUILD_COURSE_MAP),
            )
        )
        _record_usage_event(session, job, provider, PipelineStage.BUILD_COURSE_MAP, preset_value)
        total_reels = sum(len(m.reels) for m in course_map.modules)
        logs.append(
            {
                "step": "build_map",
                "source": "manual" if brief.manual_map_text else "generated",
                "modules": len(course_map.modules),
                "reels": total_reels,
            }
        )
        flush(
            current_stage="generating",
            progress_percent=PROGRESS_AFTER_CONTEXT_AND_MAP,
            course_map_json=course_map.model_dump(mode="json"),
            last_completed_step="build_map",
        )

        # --- Steps 6-11: generate reel by reel, with layered review -----
        all_reels: list[GeneratedReel] = []
        pending_pair: tuple[ModulePlan, list[GeneratedReel]] | None = None
        reels_done = 0
        modules_done = 0

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
                    session=session,
                    job=job,
                    preset=preset_value,
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
                flush(
                    current_stage="generating",
                    progress_percent=progress,
                    completed_reels_json=[r.model_dump(mode="json") for r in all_reels],
                    completed_reels_count=reels_done,
                    last_completed_step=f"reel:{reel_plan.reel_id}",
                )

                if reels_done % 5 == 0:
                    flush(current_stage="reviewing_repetition")
                    window = all_reels[-5:]
                    result = provider.review_five_reels(
                        ReviewFiveReelsInput(
                            reels=window,
                            rules_context=select_rules_for_stage(
                                rules_context, PipelineStage.REVIEW_FIVE_REELS
                            ),
                        )
                    )
                    _record_usage_event(
                        session, job, provider, PipelineStage.REVIEW_FIVE_REELS, preset_value
                    )
                    logs.append({"step": "review_5reels", "status": result.status.value})
                    flush()

            flush(current_stage="reviewing_repetition")
            module_result = provider.review_module(
                ReviewModuleInput(
                    module=module,
                    reels=module_reels,
                    rules_context=select_rules_for_stage(rules_context, PipelineStage.REVIEW_MODULE),
                )
            )
            _record_usage_event(session, job, provider, PipelineStage.REVIEW_MODULE, preset_value)
            logs.append(
                {
                    "step": "review_module",
                    "id": module.module_id,
                    "status": module_result.status.value,
                }
            )
            modules_done += 1
            flush(
                completed_modules_count=modules_done,
                last_completed_step=f"module:{module.module_id}",
            )

            if pending_pair is None:
                pending_pair = (module, module_reels)
            else:
                prev_module, prev_reels = pending_pair
                flush(current_stage="reviewing_repetition")
                two_result = provider.review_two_modules(
                    ReviewTwoModulesInput(
                        first=ModuleWithReels(module=prev_module, reels=prev_reels),
                        second=ModuleWithReels(module=module, reels=module_reels),
                        rules_context=select_rules_for_stage(
                            rules_context, PipelineStage.REVIEW_TWO_MODULES
                        ),
                    )
                )
                _record_usage_event(
                    session, job, provider, PipelineStage.REVIEW_TWO_MODULES, preset_value
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
                course_map=course_map,
                all_reels=all_reels,
                rules_context=select_rules_for_stage(rules_context, PipelineStage.FINAL_REVIEW),
            )
        )
        _record_usage_event(session, job, provider, PipelineStage.FINAL_REVIEW, preset_value)
        logs.append({"step": "final_review", "status": final_result.status.value})
        flush(
            current_stage="reviewing",
            progress_percent=PROGRESS_AFTER_FINAL_REVIEW,
            last_completed_step="final_review",
        )

        # --- Step 13: rebuild only if final_review actually requires it --
        if final_result.status == ReviewStatus.NEEDS_REVISION:
            final_course = provider.rebuild_final_course(
                RebuildFinalCourseInput(
                    course_map=course_map,
                    all_reels=all_reels,
                    final_review=final_result,
                    rules_context=select_rules_for_stage(
                        rules_context, PipelineStage.REBUILD_FINAL_COURSE
                    ),
                )
            )
            _record_usage_event(
                session, job, provider, PipelineStage.REBUILD_FINAL_COURSE, preset_value
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

        # Output Scoring Gates (§4) - runs against the exact text the DOCX
        # was rendered from (re-rendered in-memory here purely to extract
        # plain text for scoring; `export_final_course_to_docx` above
        # already did the real render+save - this never touches, re-saves,
        # or mutates the exported file). Observational only: never blocks
        # export, regardless of result - see app/generation/output_scoring.py
        # module docstring for why.
        score_report = score_final_course(
            extract_plain_text(render_final_course_docx(final_course)),
            rules_context,
            source_texts=[
                u.course_source.extracted_text
                for u in usable_sources
                if u.course_source.extracted_text
            ],
        )
        logs.append({"step": "output_scoring", "teleprompter_clean": score_report.teleprompter_clean})

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
            last_completed_step="export_docx",
            output_score_json=score_report.model_dump(mode="json"),
        )

        # --- Step 15: mark completed --------------------------------------
        # Budget Guard (§6) - observational only, computed last so it
        # reflects this run's own usage events too; never blocks/aborts a
        # run regardless of result. `None` (no warning attached) whenever
        # no budget is configured - see app/generation/budget_guard.py.
        budget_warning = compute_budget_warning(session, course_id)
        logs.append({"step": "complete"})
        flush(
            status=JobStatus.COMPLETED,
            current_stage="done",
            progress_percent=100,
            budget_warning=budget_warning,
        )

    except Exception as exc:  # noqa: BLE001 - convert any failure into a FAILED/PARTIAL job
        logs.append({"step": "error", "message": str(exc)[:300]})
        category = classify_provider_error(exc)

        # `job` is kept current by `flush()` (see `nonlocal job` above), so
        # this reflects whatever was actually persisted before the failure
        # - not the local `course_map`/`all_reels` variables, which may not
        # exist yet or may be stale if the exception happened elsewhere.
        has_saved_work = bool(job.course_map_json) or bool(job.completed_reels_json)

        partial_docx_path: str | None = None
        partial_score_report: OutputScoreReport | None = None
        if has_saved_work:
            try:
                partial_course = build_partial_course_from_job(
                    job.course_map_json, job.completed_reels_json
                )
                saved_path = export_partial_course_to_docx(partial_course, course_id, job.id)
                partial_docx_path = str(saved_path)
                logs.append({"step": "partial_export", "path": partial_docx_path})
                # Output Scoring Gates (§4) - same function, scoring only
                # whatever partial content actually made it into the
                # partial DOCX. Wrapped in its own try/except: a scoring
                # bug must never turn an otherwise-successful partial
                # export into a worse failure.
                try:
                    partial_score_report = score_final_course(
                        extract_plain_text(render_partial_course_docx(partial_course)),
                        rules_context,
                        source_texts=[
                            u.course_source.extracted_text
                            for u in usable_sources
                            if u.course_source.extracted_text
                        ],
                    )
                except Exception as score_exc:  # noqa: BLE001
                    logs.append({"step": "output_scoring_failed", "message": str(score_exc)[:200]})
            except Exception as export_exc:  # noqa: BLE001 - a partial-export
                # failure must never crash the error path itself; the job
                # still ends PARTIAL (with course_map_json/
                # completed_reels_json intact), just without a downloadable
                # file this time.
                logs.append({"step": "partial_export_failed", "message": str(export_exc)[:200]})

        status = JobStatus.PARTIAL if has_saved_work else JobStatus.FAILED
        # Budget Guard (§6) - same as the success path, observational only.
        budget_warning = compute_budget_warning(session, course_id)
        flush(
            status=status,
            current_stage="partial" if has_saved_work else "failed",
            output_score_json=(
                partial_score_report.model_dump(mode="json") if partial_score_report else None
            ),
            budget_warning=budget_warning,
            error_message=error_message_for(category, has_saved_work=has_saved_work),
            error_category=category,
            partial_docx_path=partial_docx_path,
        )

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


def _to_source_for_compiler(usable: UsableSource) -> SourceForCompiler:
    return SourceForCompiler(
        source_id=usable.course_source.id,
        category=usable.course_source.source_category.value,
        priority=usable.course_source.priority.value,
        text=usable.course_source.extracted_text or "",
        summary=usable.analysis.source_summary if usable.analysis else None,
        chunks=usable.analysis.chunks_json if usable.analysis else None,
    )


def _map_source_excerpts(usable_sources: list[UsableSource]) -> list[SourceExcerpt]:
    """Map building gets source summaries (or full text if a source is
    short) - never full text of a long source. See
    app/generation/prompt_compiler.py `compile_source_context` (empty
    query text means no reel-specific chunk selection happens here)."""
    sources = [_to_source_for_compiler(usable) for usable in usable_sources]
    return compile_source_context(sources, query_text="")


def _reel_source_excerpts(
    usable_sources: list[UsableSource], reel_plan: ReelPlan
) -> list[SourceExcerpt]:
    """Reel writing gets only relevant chunks of a long source, or its full
    text if the source is short. Never a long source's full text."""
    sources = [_to_source_for_compiler(usable) for usable in usable_sources]
    query = " ".join([reel_plan.title, reel_plan.purpose, *reel_plan.must_cover])
    return compile_source_context(sources, query_text=query)


def _build_course_brief(course: Course) -> CourseBrief:
    manual_map = (course.manual_map_text or "").strip() or None
    return CourseBrief(
        title=course.title,
        audience=course.audience,
        outcome=course.outcome,
        special_notes=course.special_notes,
        structure_mode=course.structure_mode,
        explanation_level=course.explanation_level,
        generation_preset=course.generation_preset,
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

    for issue in check_high_signal(generated.script_text):
        actions.append(
            ReviewAction(
                action=ReviewActionType.REWRITE,
                target_id=generated.reel_id,
                reason_code=issue.reason_code,
                instruction=issue.detail,
            )
        )

    # Cross-reel anti-template (only meaningful once prior siblings exist).
    for issue in check_anti_template([*all_reels_so_far, generated]):
        if issue.target_id != generated.reel_id:
            continue
        actions.append(
            ReviewAction(
                action=ReviewActionType.REWRITE,
                target_id=generated.reel_id,
                reason_code=issue.reason_code,
                instruction=issue.detail,
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
    session: Session | None = None,
    job: GenerationJob | None = None,
    preset: str | None = None,
) -> tuple[GeneratedReel, int, bool]:
    """Steps 6-8: write one reel, review it, rewrite up to MAX_REEL_REWRITE_ATTEMPTS times.

    Local validators run before the AI review call on every attempt; only
    when they find nothing obvious does this actually call
    `provider.review_single_reel`. Returns (generated_reel, attempts,
    caught_locally) - `caught_locally` is True if any attempt's issue was
    found by a local validator rather than the AI reviewer.

    `rules_context` here is the full active-rules dict (see
    `_load_active_rules`); each provider call below narrows it to just the
    keys relevant to that specific stage (see
    app/generation/prompt_compiler.py `select_rules_for_stage`) instead of
    sending every active rule to every call.

    `session`/`job`/`preset` are optional (default `None`) purely so this
    function stays directly callable exactly as before from tests that
    don't have a `GenerationJob`/DB session at hand (see
    `backend/tests/test_orchestrator.py`) - when any is `None`, usage-event
    recording (AI Usage Center, §5) is silently skipped for this reel
    rather than raising.
    """
    write_rules = select_rules_for_stage(rules_context, PipelineStage.WRITE_SINGLE_REEL)
    review_rules = select_rules_for_stage(rules_context, PipelineStage.REVIEW_SINGLE_REEL)

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
            rules_context=write_rules,
            previous_review_feedback=feedback,
        )
        generated = provider.write_single_reel(write_input)
        if session is not None and job is not None and preset is not None:
            _record_usage_event(session, job, provider, PipelineStage.WRITE_SINGLE_REEL, preset)

        local_result = _local_review_single_reel(generated, all_reels_so_far, review_rules)
        if local_result is not None:
            review = local_result
            caught_locally = True
        else:
            review = provider.review_single_reel(
                ReviewSingleReelInput(
                    reel_plan=reel_plan, generated_reel=generated, rules_context=review_rules
                )
            )
            if session is not None and job is not None and preset is not None:
                _record_usage_event(session, job, provider, PipelineStage.REVIEW_SINGLE_REEL, preset)

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
