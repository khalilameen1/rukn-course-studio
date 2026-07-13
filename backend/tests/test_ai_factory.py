"""Tests for app/ai/factory.py - AI_PROVIDER-driven provider selection.

Every test builds an explicit `Settings` instance rather than relying on
the developer machine's real `.env`, so these tests are deterministic
regardless of local configuration.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine

from app.ai.anthropic_provider import AnthropicProvider
from app.ai.fake_provider import FakeProvider
from app.ai.factory import AIProviderConfigError, get_ai_provider
from app.config import Settings


def _settings(**overrides) -> Settings:
    defaults = dict(ai_provider="fake", anthropic_api_key=None, ai_model_name="claude-sonnet-5")
    defaults.update(overrides)
    return Settings(**defaults)


def test_default_provider_is_fake():
    provider = get_ai_provider(_settings(ai_provider="fake"))

    assert isinstance(provider, FakeProvider)


def test_fake_provider_needs_no_api_key_or_model_name():
    provider = get_ai_provider(_settings(ai_provider="fake", anthropic_api_key=None, ai_model_name=""))

    assert isinstance(provider, FakeProvider)


def test_anthropic_selected_when_key_and_model_configured():
    provider = get_ai_provider(
        _settings(ai_provider="anthropic", anthropic_api_key="test-key", ai_model_name="claude-sonnet-5")
    )

    assert isinstance(provider, AnthropicProvider)
    assert provider._model_name == "claude-sonnet-5"


def test_anthropic_without_api_key_fails_clearly():
    with pytest.raises(AIProviderConfigError, match="ANTHROPIC_API_KEY"):
        get_ai_provider(_settings(ai_provider="anthropic", anthropic_api_key=None))


def test_anthropic_without_model_name_fails_clearly():
    with pytest.raises(AIProviderConfigError, match="AI_MODEL_NAME"):
        get_ai_provider(
            _settings(ai_provider="anthropic", anthropic_api_key="test-key", ai_model_name="")
        )


def test_anthropic_error_never_falls_back_to_fake():
    """A misconfigured 'anthropic' request must fail loudly, not silently
    produce fake/placeholder content."""
    with pytest.raises(AIProviderConfigError):
        get_ai_provider(_settings(ai_provider="anthropic", anthropic_api_key=None))


def test_unknown_provider_fails_clearly():
    with pytest.raises(AIProviderConfigError, match="Unknown AI_PROVIDER"):
        get_ai_provider(_settings(ai_provider="something-else"))


def test_provider_name_is_case_and_whitespace_insensitive():
    provider = get_ai_provider(_settings(ai_provider=" ANTHROPIC ", anthropic_api_key="k", ai_model_name="m"))

    assert isinstance(provider, AnthropicProvider)


def test_get_ai_provider_uses_module_level_settings_by_default(monkeypatch):
    import app.ai.factory as factory_module

    monkeypatch.setattr(factory_module.settings, "ai_provider", "fake")

    provider = factory_module.get_ai_provider()

    assert isinstance(provider, FakeProvider)


def test_generate_endpoint_returns_clear_503_when_anthropic_misconfigured(tmp_path, monkeypatch):
    """API-level check for requirement 3: a misconfigured real provider must
    fail with a clear backend error (not a raw 500 stack trace, not a
    silent fallback that generates fake content anyway)."""
    import app.db as db_module
    import app.generation.orchestrator as orchestrator_module

    engine = create_engine(f"sqlite:///{tmp_path / 'factory_api_test.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(orchestrator_module, "engine", engine)

    import app.ai.factory as factory_module

    monkeypatch.setattr(factory_module.settings, "ai_provider", "anthropic")
    monkeypatch.setattr(factory_module.settings, "anthropic_api_key", None)

    from app.main import app

    client = TestClient(app)

    create_response = client.post(
        "/courses",
        json={
            "title": "Course",
            "audience": "audience",
            "outcome": "outcome",
            "structure_mode": "connected_no_modules",
            "manual_map_text": None,
            "explanation_level": "final_only",
        },
    )
    assert create_response.status_code == 201
    course_id = create_response.json()["id"]

    generate_response = client.post(f"/courses/{course_id}/generate")

    assert generate_response.status_code == 503
    assert "ANTHROPIC_API_KEY" in generate_response.json()["detail"]
