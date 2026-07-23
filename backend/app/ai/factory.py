"""Selects which `AIProvider` implementation the orchestrator uses.

This is the ONLY place that decides between `FakeProvider` and
`OpenAIProvider` - the orchestrator (app/generation/orchestrator.py)
just calls `get_ai_provider()` and never constructs a concrete provider
itself. Selection is driven entirely by `Settings.ai_provider`
(`AI_PROVIDER` env var, see backend/.env.example):

- `fake` (default for local/tests) - always available, no configuration required.
- `openai` (production) - requires `OPENAI_API_KEY` and `AI_MODEL_NAME`
  (default `gpt-5.6-sol`). If either is missing, this raises
  `AIProviderConfigError` instead of silently falling back to `FakeProvider`.

Nothing here is frontend-visible beyond coarse diagnostics readiness.
"""

from app.ai.fake_provider import FakeProvider
from app.ai.openai_provider import OpenAIProvider
from app.ai.provider import AIProvider
from app.config import Settings, settings

SUPPORTED_PROVIDERS = ("fake", "openai")


class AIProviderConfigError(RuntimeError):
    """Raised when `AI_PROVIDER` is set to a value that cannot actually run
    (unknown provider, or "openai" without its required configuration).
    Callers (see app/routers/generation.py) should turn this into a clear,
    actionable backend error - never a raw stack trace and never a silent
    fallback to a different provider than the one configured."""


def missing_openai_config(config: Settings) -> list[str]:
    """Env var names still required for `AI_PROVIDER=openai` that are
    currently unset.

    Shared by `get_ai_provider` below (raises `AIProviderConfigError` if
    non-empty) and `app/auth/diagnostics.py` (`ai_provider_ready`), so the
    two can never quietly diverge on what "configured" means.
    """
    return [
        env_name
        for env_name, value in (
            ("OPENAI_API_KEY", config.openai_api_key),
            ("AI_MODEL_NAME", config.ai_model_name),
        )
        if not value
    ]


# Temporary compatibility for old tests; remove after one clean release.
missing_anthropic_config = missing_openai_config


def get_ai_provider(config: Settings = settings) -> AIProvider:
    import os

    provider_name = (config.ai_provider or "fake").strip().lower()

    # Credit-safe / pytest guard — never construct a paid provider.
    if os.environ.get("RUKN_CREDIT_SAFE_TESTS") == "1":
        from app.generation.quality.network_guard import record_real_provider_attempt

        if provider_name != "fake":
            record_real_provider_attempt(provider_name)
        return FakeProvider()

    if provider_name == "fake":
        return FakeProvider()

    if provider_name == "openai":
        missing = missing_openai_config(config)
        if missing:
            raise AIProviderConfigError(
                "AI_PROVIDER=openai requires "
                f"{' and '.join(missing)} to be set (see backend/.env.example). "
                "Set the missing value(s), or set AI_PROVIDER=fake for tests."
            )
        from app.generation.generation_preflight import validate_ai_model_name

        model_err = validate_ai_model_name(config.ai_model_name)
        if model_err:
            raise AIProviderConfigError(model_err)
        return OpenAIProvider(
            api_key=config.openai_api_key, model_name=config.ai_model_name
        )

    raise AIProviderConfigError(
        f"Unknown AI_PROVIDER '{config.ai_provider}'. "
        f"Supported values: {', '.join(SUPPORTED_PROVIDERS)}."
    )
