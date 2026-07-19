"""Writer test: exactly 3 reels using the production Creator / review / gates path.

Uses a three-lesson test map and the production lesson review/rewrite path,
while skipping full-course generation, final review, projects, and web research.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlmodel import Session

from app.ai.factory import get_ai_provider
from app.ai.provider import AIProvider
from app.crud import (
    course_sources,
    course_versions,
    courses,
    generation_jobs,
)
from app.generation.contracts.spoken_final_master import ensure_spoken_beats
from app.generation.contracts.course_thesis import build_course_thesis_from_brief
from app.generation.contracts.lesson_semantic import attach_lesson_semantic_contracts
from app.generation.duration_policy import (
    count_spoken_words,
    estimate_spoken_minutes,
    word_range_for,
)
from app.generation.phrase_ledger import PhraseLedger
from app.generation.quality.context_snapshot import (
    assert_snapshot_compatible,
    build_generation_context_snapshot,
    fingerprint_value,
)
from app.generation.quality.coverage_matrix import evaluate_coverage_matrix
from app.generation.voice_profile import build_voice_profile_from_calibration_texts
from app.models.enums import (
    AddressForm,
    GenerationJobKind,
    GenerationQualityMode,
    JobStatus,
    LessonDeliveryMode,
)
from app.models.generation_job import GenerationJob
from app.schemas.generation import (
    CourseMap,
    FinalCourse,
    FinalModule,
    FinalReel,
    GeneratedReel,
    ModulePlan,
    ReelPlan,
    ReviewStatus,
)
from app.services.docx_export import export_final_course_to_docx, next_version_number


@dataclass
class WriterTestTopic:
    title: str
    purpose: str = ""


def _topic_to_reel_plan(topic: WriterTestTopic, index: int, *, linked: bool) -> ReelPlan:
    mode = LessonDeliveryMode.CAMERA_EXPLAINER
    rng = word_range_for(mode)
    return ReelPlan(
        reel_id=f"wt-r{index}",
        title=topic.title.strip(),
        purpose=(topic.purpose or topic.title).strip(),
        must_cover=[topic.title.strip()],
        must_avoid=["في الريل الجاي", "في الدرس الجاي"],
        estimated_length="2.0 minutes",
        distinct_teaching_outcome=f"يطبق فكرة: {topic.title.strip()}",
        new_skill_or_decision=topic.title.strip(),
        why_standalone="Writer-test topic requires independent teaching value",
        student_can_do_after=f"يقدر يطبّق: {topic.title.strip()}",
        delivery_mode=mode,
        target_spoken_words_min=rng.target_min,
        target_spoken_words_max=rng.target_max,
        needs_natural_bridge=bool(linked and index < 3),
    )


def run_writer_test_3_reels(
    session: Session,
    course_id: int,
    *,
    topics: list[WriterTestTopic],
    series_linked: bool = False,
    series_context: str = "",
    idempotency_key: str | None = None,
    provider: AIProvider | None = None,
    quality_mode: GenerationQualityMode | None = None,
    retry_reel_id: str | None = None,
    existing_job_id: int | None = None,
) -> GenerationJob:
    """Generate exactly three production-quality reels for writer testing."""
    if len(topics) != 3:
        raise ValueError("Writer test requires exactly 3 topics")

    course = courses.get(session, course_id)
    if course is None:
        raise ValueError(f"Course {course_id} not found")

    # Idempotency: return existing completed/partial job with same key.
    if idempotency_key and existing_job_id is None:
        for job in generation_jobs.list(session, course_id=course_id):
            snap = job.run_snapshot_json or {}
            generation_settings = (
                (snap.get("CONFIG_INPUTS") or {}).get("GENERATION_SETTINGS") or {}
            )
            if generation_settings.get("idempotency_key") != idempotency_key:
                continue
            if generation_settings.get("job_kind") != GenerationJobKind.WRITER_TEST_3_REELS.value:
                continue
            if job.status in {JobStatus.COMPLETED, JobStatus.PARTIAL, JobStatus.RUNNING}:
                return job

    provider = provider or get_ai_provider()
    quality_mode = quality_mode or getattr(
        course, "generation_quality_mode", GenerationQualityMode.PREMIUM
    )

    from app.generation.orchestrator import _load_active_rules

    rules_context = _load_active_rules(session)
    sources = [
        s
        for s in course_sources.list(session, course_id=course_id)
        if (s.extracted_text or "").strip()
        and s.include_in_generation
        and s.status in {"ready", "poor_extraction"}
    ]
    flow_texts = [
        s.extracted_text or ""
        for s in sources
        if str(getattr(s.source_category, "value", s.source_category)) == "flow_reference"
    ]
    voice_profile = build_voice_profile_from_calibration_texts(flow_texts)
    phrase_ledger = PhraseLedger()

    prior_results: dict[str, dict] = {}
    if existing_job_id is not None:
        job = generation_jobs.get(session, existing_job_id)
        if job is None or job.course_id != course_id:
            raise ValueError("Writer test job not found for course")
        prior_results = {
            r.get("reel_id"): r
            for r in (job.completed_reels_json or [])
            if isinstance(r, dict) and r.get("reel_id")
        }
        generation_jobs.update(session, job.id, status=JobStatus.RUNNING, current_stage="generating")
        session.refresh(job)
    else:
        job = generation_jobs.create(
            session,
            course_id=course_id,
            status=JobStatus.RUNNING,
            current_stage="generating",
            progress_percent=5,
            generation_quality_mode=quality_mode,
        )

    from app.generation.domain_adapters import build_course_quality_contract
    from app.generation.orchestrator import (
        _build_course_brief,
        _load_usable_sources,
        _map_source_excerpts,
        _write_and_review_reel,
    )

    brief = _build_course_brief(course)
    contract = build_course_quality_contract(
        brief,
        course_domain=getattr(course, "course_domain", None),
        course_type=getattr(course, "course_type", None),
    )
    thesis = build_course_thesis_from_brief(
        brief,
        course_type=getattr(course, "course_type", None) or "practical_skill",
        address_form=contract.language.address_form,
        hard_max_lessons=contract.delivery.hard_max_lessons,
        hard_max_minutes=contract.delivery.hard_max_minutes,
    )
    usable = _load_usable_sources(session, course_id)
    source_excerpts = _map_source_excerpts(usable)
    # Prefer conceptual / applied / error-fix shaped topics when titles allow.
    plans = [
        _topic_to_reel_plan(topic, i + 1, linked=series_linked) for i, topic in enumerate(topics)
    ]
    if len(plans) == 3:
        plans[0] = plans[0].model_copy(
            update={"delivery_mode": LessonDeliveryMode.CAMERA_EXPLAINER}
        )
        plans[1] = plans[1].model_copy(
            update={
                "delivery_mode": LessonDeliveryMode.SCREEN_DEMO,
                "needs_screen_or_visual": True,
                "internal_visual_plan": "Show one concrete screen step for the topic",
                "required_assets": ["writer-test-screen.png"],
            }
        )
        plans[2] = plans[2].model_copy(
            update={"delivery_mode": LessonDeliveryMode.ERROR_FIX}
        )
    module = ModulePlan(
        module_id="wt",
        title=series_context.strip() or "اختبار الكاتب",
        purpose="Writer test module",
        reels=plans,
    )
    course_map = CourseMap(
        course_title=course.title,
        main_thread=series_context or "writer-test",
        modules=[module],
        thesis=thesis,
    )
    course_map = attach_lesson_semantic_contracts(course_map)
    module = course_map.modules[0]
    plans = list(module.reels)

    coverage = evaluate_coverage_matrix(course_map, thesis=thesis, contract=contract)
    provider_name = "fake" if provider.__class__.__name__ == "FakeProvider" else provider.__class__.__name__
    model_name = getattr(provider, "model", None) or "fake"
    run_snapshot_model = build_generation_context_snapshot(
        course_id=course_id,
        brief=brief,
        contract=contract,
        thesis=thesis,
        course_map=course_map,
        source_ids=[source.id for source in sources if source.id is not None],
        source_fingerprints={
            str(source.id): fingerprint_value(source.extracted_text or "")
            for source in sources
            if source.id is not None
        },
        source_metadata={
            str(source.id): {
                "category": source.source_category.value,
                "priority": source.priority.value,
                "include_in_generation": source.include_in_generation,
            }
            for source in sources
            if source.id is not None
        },
        research_blob={},
        admin_rules=rules_context,
        provider_name=provider_name,
        model_name=model_name,
        quality_mode=quality_mode.value,
        web_research_mode="disabled",
        coverage_matrix=coverage.model_dump(mode="json"),
        generation_settings={
            "generation_preset": brief.generation_preset.value,
            "structure_mode": brief.structure_mode.value,
            "explanation_level": brief.explanation_level.value,
            "job_kind": GenerationJobKind.WRITER_TEST_3_REELS.value,
            "idempotency_key": idempotency_key,
            "series_linked": series_linked,
            "series_context": series_context,
            "topics": [{"title": topic.title, "purpose": topic.purpose} for topic in topics],
            "voice_profile_version": voice_profile.version,
        },
    )
    if job.run_snapshot_json:
        assert_snapshot_compatible(
            job.run_snapshot_json,
            current_config_inputs=run_snapshot_model.CONFIG_INPUTS,
            action="resume writer test",
        )
    else:
        generation_jobs.update(
            session,
            job.id,
            run_snapshot_json=run_snapshot_model.model_dump(mode="json"),
            course_map_json=course_map.model_dump(mode="json"),
        )
        session.refresh(job)

    results: list[GeneratedReel] = []
    usage_total_in = 0
    usage_total_out = 0
    reel_results: list[dict[str, Any]] = []

    for plan in plans:
        if retry_reel_id and plan.reel_id != retry_reel_id:
            prior = prior_results.get(plan.reel_id)
            if prior:
                results.append(GeneratedReel.model_validate(prior))
                reel_results.append(prior)
                continue

        generated, _writes, _local, needs_review = _write_and_review_reel(
            provider=provider,
            course_map=course_map,
            module=module,
            reel_plan=plan,
            prior_reels=results,
            all_reels_so_far=results,
            sources=source_excerpts,
            rules_context=rules_context,
            quality_mode=quality_mode,
            target_market=brief.target_market,
            market_special_notes=brief.special_notes,
            realistic_student_budget=brief.realistic_student_budget,
            available_tools=brief.available_tools,
            phrase_ledger=phrase_ledger,
            voice_profile=voice_profile,
            address_form=contract.language.address_form or AddressForm.MASCULINE,
        )

        text = generated.script_text or ""
        if "في الريل الجاي" in text or "في الدرس الجاي" in text:
            needs_review = True
            generated = generated.model_copy(
                update={
                    "quality_status": "needs_review",
                    "self_check_status": ReviewStatus.NEEDS_REVISION,
                }
            )

        generated = ensure_spoken_beats(generated)
        usage = getattr(provider, "last_usage", None) or {}
        usage_total_in += int(usage.get("input_tokens") or 0)
        usage_total_out += int(usage.get("output_tokens") or 0)
        words = count_spoken_words(generated.script_text)
        seconds = (
            estimate_spoken_minutes(
                generated.script_text, delivery_mode=LessonDeliveryMode.CAMERA_EXPLAINER
            )
            * 60
        )
        payload = {
            **generated.model_dump(mode="json"),
            "word_count": words,
            "estimated_seconds": round(seconds, 1),
            "quality_status": "needs_review" if needs_review else generated.quality_status,
            "input_tokens": int(usage.get("input_tokens") or 0),
            "output_tokens": int(usage.get("output_tokens") or 0),
            "script_text_final_master": None
            if needs_review
            else generated.script_text,
        }
        results.append(generated)
        reel_results.append(payload)
        generation_jobs.update(
            session,
            job.id,
            completed_reels_json=list(reel_results),
            completed_reels_count=len(reel_results),
            total_lessons_count=3,
            progress_percent=min(90, 10 + 25 * len(reel_results)),
            course_map_json=course_map.model_dump(mode="json"),
        )
        session.refresh(job)

    pass_reels = [
        r
        for r in results
        if (r.quality_status or "pass") == "pass"
        and r.self_check_status != ReviewStatus.NEEDS_REVISION
    ]
    final_course = FinalCourse(
        title=f"اختبار الكاتب — {course.title}",
        modules=[
            FinalModule(
                module_id="wt",
                title=module.title,
                reels=[
                    FinalReel(
                        reel_id=r.reel_id,
                        title=r.title,
                        script_text=r.script_text,
                        spoken_beats=list(r.spoken_beats or []),
                        quality_status=r.quality_status,
                    )
                    for r in pass_reels
                ],
            )
        ],
        full_text="",
    )

    any_fail = any(
        (r.get("quality_status") or "") in {"needs_review", "fail"} for r in reel_results
    )
    versions = course_versions.list(session, course_id=course_id)
    version_number = next_version_number([v.version_number for v in versions])
    update_fields: dict[str, Any] = {
        "course_map_json": course_map.model_dump(mode="json"),
        "completed_reels_json": reel_results,
        "completed_reels_count": len(reel_results),
        "total_lessons_count": 3,
        "status": JobStatus.COMPLETED if not any_fail else JobStatus.PARTIAL,
        "current_stage": "done" if not any_fail else "partial",
        "progress_percent": 100,
        "estimated_usage_summary": f"~{usage_total_in + usage_total_out} tokens (writer test)",
        "last_progress_message": (
            "Writer test complete"
            if not any_fail
            else "Writer test partial — retry failed reel"
        ),
        "needs_review_count": sum(
            1 for r in reel_results if (r.get("quality_status") or "") != "pass"
        ),
    }
    if pass_reels:
        assert_snapshot_compatible(
            job.run_snapshot_json,
            current_config_inputs=run_snapshot_model.CONFIG_INPUTS,
            action="export writer test",
        )
        docx_path = export_final_course_to_docx(final_course, course_id, version_number)
        if any_fail:
            update_fields["partial_docx_path"] = str(docx_path)
        else:
            update_fields["output_docx_path"] = str(docx_path)

    generation_jobs.update(session, job.id, **update_fields)
    session.refresh(job)
    return job
