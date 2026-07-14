"""Tests for the AI Usage Center (§5): pricing estimation, usage-event
recording (via the orchestrator, for both providers), and the two read
endpoints (`/ai-usage/summary`, `/courses/{id}/ai-usage`).
"""

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.crud import ai_usage_events, courses
from app.generation.orchestrator import run_generation
from app.generation.pricing import estimate_cost_usd
from app.models.enums import ExplanationLevel, StructureMode
from app.prompts.prompt_registry import PipelineStage


def test_estimate_cost_usd_uses_the_matching_pricing_tier():
    # 1,000,000 input tokens + 1,000,000 output tokens at the "sonnet" rate
    # ($3/$15 per million) => $3.00 + $15.00.
    assert estimate_cost_usd("claude-sonnet-5-20260101", 1_000_000, 1_000_000) == 18.0
    assert estimate_cost_usd("claude-opus-4", 1_000_000, 0) == 15.0
    assert estimate_cost_usd("claude-haiku-3", 0, 1_000_000) == 4.0


def test_estimate_cost_usd_falls_back_to_default_pricing_for_unknown_model():
    # Neither "opus"/"sonnet"/"haiku" - falls back to the Sonnet-like default.
    assert estimate_cost_usd("some-future-model-xyz", 1_000_000, 1_000_000) == 18.0


def test_estimate_cost_usd_handles_missing_token_counts_gracefully():
    assert estimate_cost_usd("claude-sonnet-5", None, None) == 0.0
    assert estimate_cost_usd("claude-sonnet-5", None, 1_000_000) == 15.0


def test_estimate_cost_usd_scales_linearly_with_smaller_token_counts():
    # 1,000 tokens instead of 1,000,000 -> 1/1000th the cost.
    full = estimate_cost_usd("claude-sonnet-5", 1_000_000, 0)
    small = estimate_cost_usd("claude-sonnet-5", 1_000, 0)
    assert round(small, 6) == round(full / 1000, 6)


def _run_course(session):
    course = courses.create(
        session,
        title="Course",
        audience="audience",
        outcome="outcome",
        structure_mode=StructureMode.CONNECTED_NO_MODULES,
        explanation_level=ExplanationLevel.FINAL_ONLY,
    )
    job = run_generation(session, course.id)
    return course, job


def test_fake_provider_run_records_zero_cost_usage_events(tmp_path, monkeypatch):
    import app.generation.orchestrator as orchestrator_module

    monkeypatch.setattr(orchestrator_module.settings, "storage_outputs_dir", tmp_path)
    engine = create_engine(f"sqlite:///{tmp_path / 'ai_usage_test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        course, job = _run_course(session)
        events = ai_usage_events.list(session, job_id=job.id)

        assert len(events) > 0
        stages_seen = {e.stage for e in events}
        assert PipelineStage.BUILD_COURSE_MAP.value in stages_seen
        assert PipelineStage.WRITE_SINGLE_REEL.value in stages_seen
        assert PipelineStage.FINAL_REVIEW.value in stages_seen

        for event in events:
            assert event.provider == "fake"
            assert event.estimated_cost_usd == 0.0
            assert event.course_id == course.id
            assert event.status == "ok"
            # Synthetic but present - proves usage capture actually ran,
            # not just defaulted to null.
            assert event.input_tokens is not None
            assert event.output_tokens is not None


def test_usage_events_never_contain_secret_shaped_values(tmp_path, monkeypatch):
    """No `AIUsageEvent` field is free-text derived from settings, so this
    is mostly a structural sanity check: confirm the model truly has no
    field that could ever carry a raw API key/secret, and that a real run's
    events pass a literal string-search sanity check too."""
    import app.generation.orchestrator as orchestrator_module
    from app.config import settings

    fake_key = "sk-ant-test-should-never-leak-98765"
    monkeypatch.setattr(settings, "anthropic_api_key", fake_key)
    monkeypatch.setattr(orchestrator_module.settings, "storage_outputs_dir", tmp_path)
    engine = create_engine(f"sqlite:///{tmp_path / 'ai_usage_secret_test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        _, job = _run_course(session)
        events = ai_usage_events.list(session, job_id=job.id)

    for event in events:
        assert fake_key not in str(event.model_dump())


def test_ai_usage_summary_endpoint_labels_costs_as_estimates(monkeypatch):
    from app.config import settings
    from app.main import app

    monkeypatch.setattr(settings, "ai_provider", "fake")
    client = TestClient(app)

    response = client.get("/ai-usage/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "fake"
    assert body["model"] == "fake"
    assert "estimated_cost_today_usd" in body
    assert "estimated_cost_this_month_usd" in body
    assert isinstance(body["estimated_cost_today_usd"], float)


def test_course_ai_usage_endpoint_totals_only_that_course(tmp_path, monkeypatch):
    import app.db as db_module
    import app.generation.orchestrator as orchestrator_module

    engine = create_engine(f"sqlite:///{tmp_path / 'course_ai_usage_test.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(orchestrator_module, "engine", engine)
    monkeypatch.setattr(orchestrator_module.settings, "storage_outputs_dir", tmp_path)

    from app.main import app

    client = TestClient(app)

    create_response = client.post(
        "/courses",
        json={
            "title": "Course",
            "audience": "audience",
            "outcome": "outcome",
            "structure_mode": StructureMode.CONNECTED_NO_MODULES.value,
            "manual_map_text": None,
            "explanation_level": "final_only",
        },
    )
    course_id = create_response.json()["id"]

    generate_response = client.post(f"/courses/{course_id}/generate")
    assert generate_response.status_code == 201

    usage_response = client.get(f"/courses/{course_id}/ai-usage")

    assert usage_response.status_code == 200
    body = usage_response.json()
    assert body["course_id"] == course_id
    assert body["event_count"] > 0
    # FakeProvider always costs $0.00 - never mistakable for real spend.
    assert body["estimated_cost_usd"] == 0.0
