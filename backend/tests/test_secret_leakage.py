"""Regression guard: an API key value must never appear in a job's saved
state, in anything printed/logged during a run, or in `/auth/diagnostics` -
only safe booleans/labels are ever allowed to surface it indirectly (see
app/auth/diagnostics.py, app/generation/errors.py).

Never calls the real Anthropic API - the "failing generation" here uses a
fake provider that raises a realistically-worded exception locally.
"""

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.ai.fake_provider import FakeProvider
from app.config import settings
from app.crud import courses
from app.generation.orchestrator import run_generation
from app.main import app
from app.models.enums import ExplanationLevel, JobStatus, StructureMode

FAKE_KEY = "sk-ant-test-should-never-leak-12345"


class RateLimitError(Exception):
    """Shaped like the real `anthropic.RateLimitError` - class name and
    429/rate-limit wording, without importing the actual package here."""


class FailingProvider(FakeProvider):
    def build_course_map(self, input):  # noqa: A002 - matches AIProvider's signature
        raise RateLimitError("Error code: 429 - rate limit exceeded")


def test_api_key_never_leaks_via_job_state_or_logs(tmp_path, monkeypatch, caplog, capsys):
    """Construct a distinctive fake key, run a simulated failing
    generation, and confirm that exact string never appears in the job's
    log_json/error_message or in anything printed/logged during the run."""
    import app.generation.orchestrator as orchestrator_module

    monkeypatch.setattr(settings, "ai_provider", "anthropic")
    monkeypatch.setattr(settings, "anthropic_api_key", FAKE_KEY)
    monkeypatch.setattr(settings, "ai_model_name", "claude-example-model")
    monkeypatch.setattr(orchestrator_module.settings, "storage_outputs_dir", tmp_path)

    engine = create_engine(f"sqlite:///{tmp_path / 'secret_leakage_test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        course = courses.create(
            session,
            title="Course",
            audience="audience",
            outcome="outcome",
            structure_mode=StructureMode.CONNECTED_NO_MODULES,
            explanation_level=ExplanationLevel.FINAL_ONLY,
        )
        job = run_generation(session, course.id, provider=FailingProvider())

    assert job.status == JobStatus.FAILED
    assert job.error_category == "rate_limit"

    assert FAKE_KEY not in str(job.log_json)
    assert FAKE_KEY not in (job.error_message or "")

    assert FAKE_KEY not in caplog.text
    captured = capsys.readouterr()
    assert FAKE_KEY not in captured.out
    assert FAKE_KEY not in captured.err


def test_api_key_never_leaks_via_diagnostics_endpoint(monkeypatch):
    from app.auth.diagnostics import build_diagnostics

    monkeypatch.setattr(settings, "ai_provider", "anthropic")
    monkeypatch.setattr(settings, "anthropic_api_key", FAKE_KEY)
    monkeypatch.setattr(settings, "ai_model_name", "claude-example-model")

    body = build_diagnostics(session=None)
    assert FAKE_KEY not in str(body)
    assert body["ai_provider"] == "anthropic"
    assert body["ai_provider_ready"] is True
    assert "anthropic_api_key" not in body
