"""Tests for app/ai/factory.py - AI_PROVIDER-driven provider selection.

Every test builds an explicit `Settings` instance rather than relying on
the developer machine's real `.env`, so these tests are deterministic
regardless of local configuration.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine

from app.ai.fake_provider import FakeProvider
from app.ai.factory import AIProviderConfigError, get_ai_provider, missing_openai_config
from app.ai.openai_provider import OpenAIProvider
from app.config import Settings


def _settings(**overrides) -> Settings:
    defaults = dict(ai_provider="fake", openai_api_key=None, ai_model_name="gpt-5.6-sol")
    defaults.update(overrides)
    return Settings(**defaults)


def test_default_provider_is_fake():
    provider = get_ai_provider(_settings(ai_provider="fake"))

    assert isinstance(provider, FakeProvider)


def test_fake_provider_needs_no_api_key_or_model_name():
    provider = get_ai_provider(_settings(ai_provider="fake", openai_api_key=None, ai_model_name=""))

    assert isinstance(provider, FakeProvider)


def test_openai_selected_when_key_and_model_configured():
    provider = get_ai_provider(
        _settings(ai_provider="openai", openai_api_key="test-key", ai_model_name="gpt-5.6-sol")
    )

    assert isinstance(provider, OpenAIProvider)
    assert provider._model_name == "gpt-5.6-sol"


def test_openai_without_api_key_fails_clearly():
    with pytest.raises(AIProviderConfigError, match="OPENAI_API_KEY"):
        get_ai_provider(_settings(ai_provider="openai", openai_api_key=None))


def test_openai_without_model_name_fails_clearly():
    with pytest.raises(AIProviderConfigError, match="AI_MODEL_NAME"):
        get_ai_provider(
            _settings(ai_provider="openai", openai_api_key="test-key", ai_model_name="")
        )


def test_openai_without_api_key_and_model_name_lists_both_missing():
    with pytest.raises(AIProviderConfigError) as exc_info:
        get_ai_provider(_settings(ai_provider="openai", openai_api_key=None, ai_model_name=""))

    message = str(exc_info.value)
    assert "OPENAI_API_KEY" in message
    assert "AI_MODEL_NAME" in message


def test_missing_openai_config_reports_both_when_unset():
    missing = missing_openai_config(
        _settings(ai_provider="openai", openai_api_key=None, ai_model_name="")
    )

    assert set(missing) == {"OPENAI_API_KEY", "AI_MODEL_NAME"}


def test_missing_openai_config_empty_when_both_set():
    missing = missing_openai_config(
        _settings(ai_provider="openai", openai_api_key="k", ai_model_name="gpt-5.6-sol")
    )

    assert missing == []


def test_openai_error_never_falls_back_to_fake():
    with pytest.raises(AIProviderConfigError):
        get_ai_provider(_settings(ai_provider="openai", openai_api_key=None))


def test_unknown_provider_fails_clearly():
    with pytest.raises(AIProviderConfigError, match="Unknown AI_PROVIDER"):
        get_ai_provider(_settings(ai_provider="something-else"))


def test_anthropic_provider_no_longer_selected():
    with pytest.raises(AIProviderConfigError, match="Unknown AI_PROVIDER"):
        get_ai_provider(
            _settings(
                ai_provider="anthropic",
                openai_api_key="k",
                ai_model_name="claude-sonnet-5",
            )
        )


def test_provider_name_is_case_and_whitespace_insensitive():
    provider = get_ai_provider(
        _settings(
            ai_provider=" OPENAI ",
            openai_api_key="k",
            ai_model_name="gpt-5.6-sol",
        )
    )

    assert isinstance(provider, OpenAIProvider)


def test_get_ai_provider_uses_module_level_settings_by_default(monkeypatch):
    import app.ai.factory as factory_module

    monkeypatch.setattr(factory_module.settings, "ai_provider", "fake")

    provider = factory_module.get_ai_provider()

    assert isinstance(provider, FakeProvider)


def test_map_preview_returns_clear_503_when_openai_misconfigured(tmp_path, monkeypatch):
    import app.db as db_module

    engine = create_engine(f"sqlite:///{tmp_path / 'factory_api_test.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db_module, "engine", engine)

    import app.ai.factory as factory_module

    monkeypatch.setattr(factory_module.settings, "ai_provider", "openai")
    monkeypatch.setattr(factory_module.settings, "openai_api_key", None)

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

    generate_response = client.post(f"/courses/{course_id}/map-preview")

    assert generate_response.status_code == 503
    assert "OPENAI_API_KEY" in generate_response.json()["detail"]
