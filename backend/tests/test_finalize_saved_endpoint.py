"""POST /courses/{id}/generate/{job_id}/finalize-saved — no AI recovery."""

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.crud import courses, generation_jobs
from app.generation.domain_adapters import build_course_quality_contract
from app.generation.web_research import research_identity_payload
from app.generation.orchestrator import _build_course_brief
from app.generation.quality.context_snapshot import (
    build_generation_context_snapshot,
    fingerprint_value,
)
from app.models.enums import JobStatus, StructureMode
from app.schemas.generation import CourseMap
from app.security.request_throttle import reset_for_tests

COURSE_BODY = {
    "title": "Course",
    "audience": "audience",
    "outcome": "outcome",
    "structure_mode": StructureMode.CONNECTED_NO_MODULES.value,
    "manual_map_text": None,
    "explanation_level": "final_only",
}


def _spoken(i: int) -> str:
    return "\n".join(
        [
            (
                f"ابدأ بقياس أثر القرار الأول في درس {i} على حالة عملية واضحة"
                if i % 2
                else f"النتيجة المختلفة في درس {i} تكشف سبب اختيار القرار الثاني"
            ),
            f"نفّذ خطوة واضحة تخص درس {i} من غير حشو",
            f"راجع الناتج وتأكد إن القرار اتحقق في حالة حقيقية",
            f"لو النتيجة ضعيفة أعد نفس الخطوة بهدوء على مثال مختلف",
            f"اربط درس {i} بنتيجة شغلك اليومي بشكل مباشر",
            f"قفل درس {i} لما تقدر تعيد نفس القرار لوحدك بدون مساعدة",
            f"علامة النجاح تظهر لما تقدر تشرح فرق قبل وبعد لنفس الحالة",
            f"ممنوع تلخّص نفس الفكرة مرتين بعد ما اتشرحت",
            f"اختبر قرار درس {i} على حالة تانية قبل ما تعتبره ثابت",
            f"سجل سبب نجاح الخطوة وسبب فشل البديل في درس {i}",
            f"قارن النتيجة بالهدف الأساسي وخد قرار واضح قابل للتكرار",
            (
                f"اقفل درس {i} بتفسير مستقل يثبت إنك فهمت القرار الأول"
                if i % 2
                else f"اختم درس {i} بمقارنة جديدة تثبت إن القرار الثاني قابل للتكرار"
            ),
        ]
    )


def _capability(i: int) -> str:
    values = (
        "compose visual hierarchy from evidence",
        "diagnose color contrast with measurement",
        "repair spacing through explicit constraints",
    )
    return values[(i - 1) % len(values)]


def _map_and_reels(n: int = 2) -> tuple[dict, list[dict]]:
    reels = []
    for i in range(1, n + 1):
        script = _spoken(i)
        text_fingerprint = fingerprint_value(script)
        reels.append({
            "reel_id": f"r{i}",
            "module_id": "m1",
            "title": f"Lesson {i}",
            "script_text": script,
            "used_ideas": [],
            "used_examples": [],
            "self_check_status": "pass",
            "quality_status": "pass",
            "delivery_mode": "error_fix",
            "quality_report": {
                "notes": [],
                "semantic_contract": {
                    "missing_fields": [],
                    "remaining_filler_count": 0,
                },
                "language_rewrite_record": {
                    "after_text_fingerprint": text_fingerprint,
                    "semantic_preserved": True,
                },
                "final_text_acceptance": {
                    "text_fingerprint": text_fingerprint,
                    "semantic_gate_passed": True,
                    "terminology_gate_passed": True,
                    "spoken_variety_gate_passed": True,
                    "teleprompter_gate_passed": True,
                    "term_ledger_fingerprint": fingerprint_value({"term": i}),
                    "phrase_ledger_after_fingerprint": fingerprint_value({"phrase": i}),
                    "accepted": True,
                },
            },
        })
    course_map = {
        "course_title": "Test Course",
        "main_thread": "thread",
        "modules": [
            {
                "module_id": "m1",
                "title": "Module 1",
                "purpose": "learn",
                "bridge_project": None,
                "module_project": {
                    "name": "مشروع موديول 1",
                    "brief": "نفّذ تمرين تطبيقي قصير",
                    "deliverable_shape": "ملف نهائي",
                    "pass_criteria": ["ينفّذ المطلوب"],
                    "skills_tested": [_capability(1)],
                },
                "reels": [
                    {
                        "reel_id": f"r{i}",
                        "title": f"Lesson {i} unique skill {i}",
                        "purpose": f"teach skill {i} only",
                        "distinct_teaching_outcome": _capability(i),
                        "new_skill_or_decision": _capability(i),
                        "student_can_do_after": _capability(i),
                        "project_contribution": _capability(i),
                        "must_cover": [f"skill-{i}-core"],
                        "must_avoid": [],
                        "source_hints": [],
                        "estimated_length": "2 minutes",
                        "delivery_mode": "error_fix",
                        "lesson_semantic_contract": {
                            "learner_before": f"before skill-{i}",
                            "learner_after": f"after skill-{i}",
                            "exact_capability_change": _capability(i),
                            "strongest_non_obvious_meaning": f"meaning skill-{i}",
                            "misconception_or_failure": f"failure skill-{i}",
                            "causal_explanation": f"cause skill-{i}",
                            "proof_example_or_demonstration": f"proof skill-{i}",
                            "learner_test_or_action": f"action skill-{i}",
                            "boundary_or_exception": f"boundary skill-{i}",
                            "real_tension": f"tension skill-{i}",
                            "complete_payoff": f"payoff skill-{i}",
                            "earned_next_need": f"next skill-{i}",
                            "escalation_role": f"escalation skill-{i}",
                            "sequence_dependency": f"sequence skill-{i}",
                        },
                    }
                    for i in range(1, n + 1)
                ],
            }
        ],
        "graduation_project": {
            "name": "مشروع التخرج",
            "brief": "تسليم نهائي يجمع مهارات الكورس",
            "deliverable_shape": "مشروع كامل",
            "pass_criteria": ["يغطي المهارات"],
            "skills_tested": [_capability(i) for i in range(1, n + 1)],
        },
        "thesis": {
            "final_student_outcome": "o",
            "audience_and_starting_level": "a",
            "practical_deliverable": "d",
            "in_scope": ["in"],
            "out_of_scope": ["out"],
            "mix_type": "practical",
            "hard_max_lessons": 60,
            "hard_max_minutes": 240,
            "final_project": "final",
        },
    }
    return course_map, reels


def _run_snapshot(course, course_map: dict) -> dict:
    brief = _build_course_brief(course)
    parsed_map = CourseMap.model_validate(course_map)
    contract = build_course_quality_contract(
        brief,
        course_type=getattr(course, "course_type", None) or "practical_skill",
        address_form=parsed_map.thesis.address_form,
    )
    return build_generation_context_snapshot(
        course_id=course.id,
        brief=brief,
        contract=contract,
        thesis=parsed_map.thesis,
        course_map=parsed_map,
        research_blob=research_identity_payload({}, {}),
        quality_mode="premium",
        web_research_mode="autonomous_gap_fill",
        generation_settings={
            "generation_preset": brief.generation_preset.value,
            "structure_mode": brief.structure_mode.value,
            "explanation_level": brief.explanation_level.value,
        },
    ).model_dump(mode="json")


def _client(tmp_path, monkeypatch):
    import app.db as db_module
    engine = create_engine(f"sqlite:///{tmp_path / 'finalize_ep.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(
        "app.services.finalize_saved_job.settings.storage_dir", tmp_path / "storage"
    )
    monkeypatch.setattr(
        "app.services.finalize_saved_job.settings.storage_outputs_dir",
        tmp_path / "storage" / "outputs",
    )
    monkeypatch.setattr(
        "app.services.docx_export.settings.storage_outputs_dir",
        tmp_path / "storage" / "outputs",
    )
    from app.main import app

    reset_for_tests()
    return TestClient(app), engine


def test_finalize_saved_endpoint_completes_partial_timeout_job(tmp_path, monkeypatch):
    client, engine = _client(tmp_path, monkeypatch)
    course_id = client.post("/courses", json=COURSE_BODY).json()["id"]
    course_map, reels = _map_and_reels(2)

    with Session(engine) as session:
        course = courses.get(session, course_id)
        job = generation_jobs.create(
            session,
            course_id=course_id,
            status=JobStatus.PARTIAL,
            current_stage="failed",
            progress_percent=85,
            course_map_json=course_map,
            completed_reels_json=reels,
            completed_reels_count=2,
            total_lessons_count=2,
            last_completed_step="reel:r2",
            error_category="timeout",
            error_message="Generation stopped after saving completed sections.",
            partial_docx_path=str(tmp_path / "partial.docx"),
            run_snapshot_json=_run_snapshot(course, course_map),
        )
        job_id = job.id

    response = client.post(f"/courses/{course_id}/generate/{job_id}/finalize-saved")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["current_stage"] == "done"
    assert body["progress_percent"] == 100
    assert body["output_docx_path"]
    assert body["error_message"] is None
    assert body["can_finalize_from_saved"] is False
    assert body["can_download_completed"] is True


def test_finalize_saved_rejects_incomplete_lessons(tmp_path, monkeypatch):
    client, engine = _client(tmp_path, monkeypatch)
    course_id = client.post("/courses", json=COURSE_BODY).json()["id"]
    course_map, reels = _map_and_reels(2)

    with Session(engine) as session:
        course = courses.get(session, course_id)
        job = generation_jobs.create(
            session,
            course_id=course_id,
            status=JobStatus.PARTIAL,
            current_stage="failed",
            course_map_json=course_map,
            completed_reels_json=reels[:1],
            completed_reels_count=1,
            total_lessons_count=2,
        )
        job_id = job.id

    response = client.post(f"/courses/{course_id}/generate/{job_id}/finalize-saved")
    assert response.status_code == 409


def test_finalize_saved_rejects_config_fingerprint_drift(tmp_path, monkeypatch):
    client, engine = _client(tmp_path, monkeypatch)
    course_id = client.post("/courses", json=COURSE_BODY).json()["id"]
    course_map, reels = _map_and_reels(2)

    with Session(engine) as session:
        course = courses.get(session, course_id)
        job = generation_jobs.create(
            session,
            course_id=course_id,
            status=JobStatus.PARTIAL,
            current_stage="failed",
            course_map_json=course_map,
            completed_reels_json=reels,
            completed_reels_count=2,
            total_lessons_count=2,
            run_snapshot_json=_run_snapshot(course, course_map),
        )
        course.title = "Changed after snapshot freeze"
        session.add(course)
        session.commit()
        job_id = job.id

    response = client.post(f"/courses/{course_id}/generate/{job_id}/finalize-saved")
    assert response.status_code == 409
    assert "configuration changed" in response.json()["detail"].lower()


def test_job_read_exposes_recovery_flags(tmp_path, monkeypatch):
    client, engine = _client(tmp_path, monkeypatch)
    course_id = client.post("/courses", json=COURSE_BODY).json()["id"]
    course_map, reels = _map_and_reels(2)

    with Session(engine) as session:
        course = courses.get(session, course_id)
        job = generation_jobs.create(
            session,
            course_id=course_id,
            status=JobStatus.PARTIAL,
            current_stage="failed",
            course_map_json=course_map,
            completed_reels_json=reels,
            completed_reels_count=2,
            total_lessons_count=2,
            partial_docx_path="/tmp/p.docx",
            last_completed_step="final_review",
            run_snapshot_json=_run_snapshot(course, course_map),
        )
        job_id = job.id

    # Avoid auto-recover on GET by temporarily breaking force path? GET will
    # recover — call before recover by reading through schema on create path.
    # Instead assert flags on a failed incomplete job that won't auto-complete.
    with Session(engine) as session:
        incomplete = generation_jobs.create(
            session,
            course_id=course_id,
            status=JobStatus.PARTIAL,
            current_stage="failed",
            course_map_json=course_map,
            completed_reels_json=reels[:1],
            completed_reels_count=1,
            total_lessons_count=2,
            partial_docx_path="/tmp/p2.docx",
            last_completed_step="reel:r1",
        )
        incomplete_id = incomplete.id

    body = client.get(f"/jobs/{incomplete_id}?course_id={course_id}").json()
    assert body["can_download_completed"] is True
    assert body["can_finalize_from_saved"] is False
    assert body["stopped_after_label"] == "Saving lessons"

    # Full job recovers on GET — after recover, finalize flag is false.
    full = client.get(f"/jobs/{job_id}?course_id={course_id}").json()
    assert full["status"] == "completed"
    assert full["can_finalize_from_saved"] is False
    assert full["can_download_completed"] is True
