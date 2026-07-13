from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
STORAGE_DIR = REPO_ROOT / "storage"


class Settings(BaseSettings):
    """Application configuration, overridable via environment variables or .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Rukn Course Studio API"
    environment: str = "development"

    database_url: str = f"sqlite:///{BACKEND_DIR / 'rukn_course_studio.db'}"

    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    storage_uploads_dir: Path = STORAGE_DIR / "uploads"
    storage_extracted_dir: Path = STORAGE_DIR / "extracted"
    storage_outputs_dir: Path = STORAGE_DIR / "outputs"
    storage_templates_dir: Path = STORAGE_DIR / "templates"

    # Which AIProvider implementation the orchestrator uses by default - see
    # app/ai/factory.py `get_ai_provider`. "fake" (the default) needs no
    # further configuration. "anthropic" additionally requires
    # ANTHROPIC_API_KEY (and, in practice, AI_MODEL_NAME) to be set, or
    # get_ai_provider raises a clear config error instead of silently
    # falling back to FakeProvider.
    ai_provider: str = "fake"

    # AnthropicProvider (see app/ai/anthropic_provider.py). `ai_model_name`
    # is the ONLY place a model name should ever be set - never hardcode a
    # model string anywhere else.
    anthropic_api_key: str | None = None
    ai_model_name: str = "claude-sonnet-5"

    # Single-admin-user auth for this internal MVP (see app/auth/). No
    # multi-user accounts, registration, roles, or OAuth - one username/
    # password pair from the environment, guarding every route except
    # GET /health and POST /auth/login (see app/auth/middleware.py).
    auth_enabled: bool = True
    admin_username: str | None = None
    admin_password: str | None = None
    auth_secret_key: str | None = None


settings = Settings()
