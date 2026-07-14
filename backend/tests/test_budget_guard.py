"""Tests for app/generation/budget_guard.py (§6) - warn-only, never blocks."""

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.crud import ai_usage_events
from app.generation.budget_guard import compute_budget_warning


@pytest.fixture()
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'budget_test.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _add_event(session, course_id: int, cost: float):
    ai_usage_events.create(
        session,
        job_id=None,
        course_id=course_id,
        stage="write_single_reel",
        provider="anthropic",
        model="claude-example-model",
        preset="balanced",
        input_tokens=1000,
        output_tokens=500,
        estimated_cost_usd=cost,
        status="ok",
    )


def test_no_warning_when_no_budgets_configured(session, monkeypatch):
    import app.config as config_module

    monkeypatch.setattr(config_module.settings, "ai_monthly_budget_usd", None)
    monkeypatch.setattr(config_module.settings, "ai_course_budget_usd", None)
    _add_event(session, course_id=1, cost=1_000_000.0)  # absurdly high, still must not warn

    warning = compute_budget_warning(session, course_id=1)

    assert warning is None


def test_no_warning_below_threshold(session, monkeypatch):
    import app.config as config_module

    monkeypatch.setattr(config_module.settings, "ai_course_budget_usd", 10.0)
    monkeypatch.setattr(config_module.settings, "ai_monthly_budget_usd", None)
    monkeypatch.setattr(config_module.settings, "ai_warn_at_percent", 80.0)
    _add_event(session, course_id=1, cost=7.99)  # 79.9% - just under 80%

    warning = compute_budget_warning(session, course_id=1)

    assert warning is None


def test_warning_exactly_at_threshold(session, monkeypatch):
    import app.config as config_module

    monkeypatch.setattr(config_module.settings, "ai_course_budget_usd", 10.0)
    monkeypatch.setattr(config_module.settings, "ai_monthly_budget_usd", None)
    monkeypatch.setattr(config_module.settings, "ai_warn_at_percent", 80.0)
    _add_event(session, course_id=1, cost=8.0)  # exactly 80%

    warning = compute_budget_warning(session, course_id=1)

    assert warning is not None
    assert "course's estimated AI spend" in warning


def test_warning_above_threshold(session, monkeypatch):
    import app.config as config_module

    monkeypatch.setattr(config_module.settings, "ai_course_budget_usd", 10.0)
    monkeypatch.setattr(config_module.settings, "ai_monthly_budget_usd", None)
    monkeypatch.setattr(config_module.settings, "ai_warn_at_percent", 80.0)
    _add_event(session, course_id=1, cost=9.5)

    warning = compute_budget_warning(session, course_id=1)

    assert warning is not None


def test_course_budget_is_scoped_to_the_specific_course(session, monkeypatch):
    import app.config as config_module

    monkeypatch.setattr(config_module.settings, "ai_course_budget_usd", 10.0)
    monkeypatch.setattr(config_module.settings, "ai_monthly_budget_usd", None)
    monkeypatch.setattr(config_module.settings, "ai_warn_at_percent", 80.0)
    _add_event(session, course_id=2, cost=9.5)  # a different course, well over threshold

    warning = compute_budget_warning(session, course_id=1)

    assert warning is None


def test_monthly_budget_triggers_independently_of_course_budget(session, monkeypatch):
    import app.config as config_module

    monkeypatch.setattr(config_module.settings, "ai_course_budget_usd", None)
    monkeypatch.setattr(config_module.settings, "ai_monthly_budget_usd", 5.0)
    monkeypatch.setattr(config_module.settings, "ai_warn_at_percent", 80.0)
    _add_event(session, course_id=1, cost=4.5)

    warning = compute_budget_warning(session, course_id=1)

    assert warning is not None
    assert "spend this month" in warning


def test_both_budgets_can_warn_simultaneously(session, monkeypatch):
    import app.config as config_module

    monkeypatch.setattr(config_module.settings, "ai_course_budget_usd", 5.0)
    monkeypatch.setattr(config_module.settings, "ai_monthly_budget_usd", 5.0)
    monkeypatch.setattr(config_module.settings, "ai_warn_at_percent", 80.0)
    _add_event(session, course_id=1, cost=4.5)

    warning = compute_budget_warning(session, course_id=1)

    assert "spend this month" in warning
    assert "course's estimated AI spend" in warning
