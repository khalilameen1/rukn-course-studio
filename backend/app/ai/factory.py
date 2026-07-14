"""Selects which `AIProvider` implementation the orchestrator uses.

This is the ONLY place that decides between `FakeProvider` and
`AnthropicProvider` - the orchestrator (app/generation/orchestrator.py)
just calls `get_ai_provider()` and never constructs a concrete provider
itself. Selection is driven entirely by `Settings.ai_provider`
(`AI_PROVIDER` env var, see backend/.env.example):

- `fake` (default) - always available, no configuration required.
- `anthropic` - requires `ANTHROPIC_API_KEY` and `AI_MODEL_NAME` to both be
  set. If either is missing, this raises `AIProviderConfigError` instead of
  silently falling back to `FakeProvider` - a misconfigured "real" run
  should fail clearly, not quietly produce placeholder content.

Nothing here is frontend-visible: the frontend never sees provider/model
names, only the coarse job status (docs/PRD.md FR-8).
"""

from app.ai.anthropic_provider import AnthropicProvider
from app.ai.fake_provider import FakeProvider
from app.ai.provider import AIProvider
from app.config import Settings, settings

SUPPORTED_PROVIDERS = ("fake", "anthropic")


class AIProviderConfigError(RuntimeError):
    """Raised when `AI_PROVIDER` is set to a value that cannot actually run
    (unknown provider, or "anthropic" without its required configuration).
    Callers (see app/routers/generation.py) should turn this into a clear,
    actionable backend error - never a raw stack trace and never a silent
    fallback to a different provider than the one configured."""


def missing_anthropic_config(config: Settings) -> list[str]:
    """Env var names still required for `AI_PROVIDER=anthropic` that are
    currently unset.

    Shared by `get_ai_provider` below (raises `AIProviderConfigError` if
    non-empty) and `app/auth/diagnostics.py` (`ai_provider_ready`), so the
    two can never quietly diverge on what "configured" means.
    """
    return [
        env_name
        for env_name, value in (
            ("ANTHROPIC_API_KEY", config.anthropic_api_key),
            ("AI_MODEL_NAME", config.ai_model_name),
        )
        if not value
    ]


def get_ai_provider(config: Settings = settings) -> AIProvider:
    provider_name = (config.ai_provider or "fake").strip().lower()

    if provider_name == "fake":
        return FakeProvider()

    if provider_name == "anthropic":
        missing = missing_anthropic_config(config)
        if missing:
            raise AIProviderConfigError(
                "AI_PROVIDER=anthropic requires "
                f"{' and '.join(missing)} to be set (see backend/.env.example). "
                "Set the missing value(s), or set AI_PROVIDER=fake to use the "
                "deterministic fake provider instead."
            )
        return AnthropicProvider(
            api_key=config.anthropic_api_key, model_name=config.ai_model_name
        )

    raise AIProviderConfigError(
        f"Unknown AI_PROVIDER '{config.ai_provider}'. "
        f"Supported values: {', '.join(SUPPORTED_PROVIDERS)}."
    )
