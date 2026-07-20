"""Static and functional phase-11 runtime integrity checks."""

from pathlib import Path

from sqlmodel import SQLModel, create_engine

from app.ai.anthropic_provider import AnthropicProvider
from app.ai.fake_provider import FakeProvider
from app.ai.provider import AIProvider
from app.prompts.prompt_registry import PROMPT_SPECS, PROMPTS_DIR


def test_runtime_never_imports_database_engine_by_value():
    app_root = Path(__file__).parents[1] / "app"
    offenders: list[str] = []
    for path in app_root.rglob("*.py"):
        if path == app_root / "db" / "__init__.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "from app.db import engine" in text:
            offenders.append(str(path.relative_to(app_root)))
    assert offenders == []


def test_run_generation_job_binds_to_current_monkeypatched_engine(tmp_path, monkeypatch):
    import app.db as db_pkg
    import app.generation.orchestrator as orchestrator

    current_engine = create_engine(f"sqlite:///{tmp_path / 'dynamic.db'}")
    SQLModel.metadata.create_all(current_engine)
    monkeypatch.setattr(db_pkg, "engine", current_engine)
    observed: dict[str, object] = {}

    def fake_run_generation(session, course_id, provider, **kwargs):
        observed["bind"] = session.get_bind()
        observed["course_id"] = course_id
        observed["provider"] = provider
        observed["kwargs"] = kwargs
        return "ok"

    monkeypatch.setattr(orchestrator, "run_generation", fake_run_generation)
    provider = FakeProvider()

    result = orchestrator.run_generation_job(42, provider=provider)

    assert result == "ok"
    assert observed["bind"] is current_engine
    assert observed["course_id"] == 42
    assert observed["provider"] is provider


def test_prompt_registry_has_no_dead_files_or_provider_methods():
    registered_files = {spec.filename for spec in PROMPT_SPECS.values()}
    tracked_prompt_files = {path.name for path in PROMPTS_DIR.glob("*.md")}
    runtime_callers = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (Path(__file__).parents[1] / "app" / "generation").rglob("*.py")
    )

    assert tracked_prompt_files == registered_files
    for spec in PROMPT_SPECS.values():
        assert spec.provider_method in AIProvider.__dict__
        assert spec.provider_method in AnthropicProvider.__dict__
        assert spec.provider_method in FakeProvider.__dict__
        assert f"provider.{spec.provider_method}(" in runtime_callers
