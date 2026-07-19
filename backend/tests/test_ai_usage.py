"""Tests for the AI Usage Center (§5): pricing estimation, usage-event
recording (via the orchestrator, for both providers), and the two read
endpoints (`/ai-usage/summary`, `/courses/{id}/ai-usage`).
"""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.crud import ai_usage_events, courses
from app.db import get_session, init_db
from app.generation.orchestrator import run_generation
from app.generation.pricing import estimate_cost_usd
from app.main import app
from app.models.enums import ExplanationLevel, StructureMode
from app.prompts.prompt_registry import PipelineStage
from app.services.ai_usage_summary import build_usage_summary, empty_usage_summary


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

    monkeypatch.setattr(settings, "ai_provider", "fake")
    monkeypatch.setattr(settings, "auth_enabled", False)
    client = TestClient(app)

    response = client.get("/ai-usage/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "fake"
    assert body["model"] == "fake"
    assert "estimated_cost_today_usd" in body
    assert "estimated_cost_this_month_usd" in body
    assert isinstance(body["estimated_cost_today_usd"], float)
    assert body["estimated_cost_today_usd"] == 0.0
    assert body["estimated_cost_this_month_usd"] == 0.0
    assert body["last_request_status"] is None


def test_ai_usage_summary_empty_table_returns_zero_summary(tmp_path, monkeypatch):
    import app.db as db_module

    engine = create_engine(f"sqlite:///{tmp_path / 'empty_usage.db'}")
    monkeypatch.setattr(db_module, "engine", engine)
    init_db()

    def override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override
    try:
        client = TestClient(app)
        response = client.get("/ai-usage/summary")
        assert response.status_code == 200
        body = response.json()
        assert body["estimated_cost_today_usd"] == 0.0
        assert body["estimated_cost_this_month_usd"] == 0.0
        assert body["last_request_status"] is None
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_ai_usage_summary_missing_table_returns_zero_summary_not_500(tmp_path, monkeypatch):
    import app.db as db_module

    engine = create_engine(f"sqlite:///{tmp_path / 'no_usage_table.db'}")
    monkeypatch.setattr(db_module, "engine", engine)

    def override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override
    try:
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/ai-usage/summary")
        assert response.status_code == 200
        body = response.json()
        assert body["estimated_cost_today_usd"] == 0.0
        assert body["estimated_cost_this_month_usd"] == 0.0
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_build_usage_summary_aggregates_events_and_decimal_cost(tmp_path):
    from datetime import datetime, timezone

    engine = create_engine(f"sqlite:///{tmp_path / 'aggregate_usage.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        ai_usage_events.create(
            session,
            job_id=None,
            course_id=None,
            stage=PipelineStage.WRITE_SINGLE_REEL.value,
            provider="anthropic",
            model="claude-sonnet-5",
            input_tokens=100,
            output_tokens=50,
            estimated_cost_usd=Decimal("0.100000"),
            status="ok",
            created_at=datetime.now(timezone.utc),
        )
        ai_usage_events.create(
            session,
            job_id=7,
            course_id=3,
            stage=PipelineStage.FINAL_REVIEW.value,
            provider="anthropic",
            model="claude-sonnet-5",
            input_tokens=200,
            output_tokens=100,
            estimated_cost_usd=0.05,
            status="ok",
            created_at=datetime.now(timezone.utc),
        )
        summary = build_usage_summary(session)

    assert summary.estimated_cost_today_usd == 0.15
    assert summary.estimated_cost_this_month_usd == 0.15
    assert summary.last_request_status == "ok"
    assert isinstance(summary.estimated_cost_today_usd, float)


def test_empty_usage_summary_shape_matches_frontend_contract():
    summary = empty_usage_summary()
    payload = summary.model_dump()
    assert set(payload) == {
        "provider",
        "model",
        "default_preset",
        "last_request_status",
        "last_request_at",
        "estimated_cost_today_usd",
        "estimated_cost_this_month_usd",
        "last_error_category",
        "last_error_message",
    }
    assert payload["estimated_cost_today_usd"] == 0.0
    assert payload["estimated_cost_this_month_usd"] == 0.0
    assert payload["last_request_status"] is None


def test_init_db_creates_ai_usage_events_table(tmp_path, monkeypatch):
    import app.db as db_module

    engine = create_engine(f"sqlite:///{tmp_path / 'init_usage.db'}")
    monkeypatch.setattr(db_module, "engine", engine)
    init_db()

    from sqlalchemy import inspect

    assert "ai_usage_events" in inspect(engine).get_table_names()


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
