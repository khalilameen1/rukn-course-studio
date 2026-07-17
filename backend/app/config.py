from pathlib import Path, PurePosixPath

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.cors_origins import normalize_cors_origins, normalize_origin

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
STORAGE_DIR = REPO_ROOT / "storage"


DEFAULT_LOCAL_DATABASE_URL = f"sqlite:///{BACKEND_DIR / 'rukn_course_studio.db'}"


def build_sqlite_url(db_path: str) -> str:
    """Build a SQLAlchemy `sqlite:///` URL from an absolute POSIX filesystem
    path (e.g. Render's persistent disk mount). Four slashes total: the
    `sqlite://` scheme separator plus the path's own leading `/` - see
    SQLITE_DB_PATH below."""
    path = PurePosixPath(db_path)
    if not path.is_absolute():
        raise ValueError(f"SQLITE_DB_PATH must be an absolute path, got: {db_path!r}")
    return f"sqlite:///{path}"


def normalize_database_url(url: str) -> str:
    """SQLAlchemy 1.4+ only recognizes the `postgresql://` dialect name, not
    the older `postgres://` scheme some providers still hand out - rewrite
    it defensively so a provider-supplied URL never fails with a
    `NoSuchModuleError` at engine-creation time."""
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


class Settings(BaseSettings):
    """Application configuration, overridable via environment variables or .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "ROKN Course Studio API"
    environment: str = "development"

    # Highest priority: if set, used as-is (after normalizing the
    # `postgres://` -> `postgresql://` scheme). This is how production talks
    # to Postgres (e.g. Render's Internal Database URL). Unset locally, so
    # local dev keeps using plain SQLite - see `_resolve_database_url`.
    database_url: str | None = None

    # Fallback-only override for where a local SQLite file lives (e.g.
    # Render's persistent disk, before this app had Postgres support) -
    # simpler than hand-building a `sqlite:///` URL. Only takes effect when
    # DATABASE_URL is unset; ignored otherwise. Unset by default, which
    # leaves local dev's SQLite default below completely unchanged.
    sqlite_db_path: str | None = None

    @model_validator(mode="after")
    def _resolve_database_url(self) -> "Settings":
        """Priority: DATABASE_URL > SQLITE_DB_PATH > local SQLite default.

        Keeps local dev working with zero configuration (no DATABASE_URL,
        no SQLITE_DB_PATH -> plain local SQLite file) while letting
        production set exactly one of DATABASE_URL (Postgres, recommended)
        or SQLITE_DB_PATH (SQLite-on-disk, temporary/legacy) without either
        setting silently overriding the other.
        """
        if self.database_url:
            self.database_url = normalize_database_url(self.database_url)
        elif self.sqlite_db_path:
            self.database_url = build_sqlite_url(self.sqlite_db_path)
        else:
            self.database_url = DEFAULT_LOCAL_DATABASE_URL
        return self

    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Deploy-time convenience for the common single-frontend case - avoids
    # hand-writing a `CORS_ORIGINS` JSON array just to allow one origin.
    # Merged into `cors_origins` below if set; `CORS_ORIGINS` still works
    # as-is (e.g. for allowing more than one origin) and takes precedence
    # if both happen to be set.
    frontend_origin: str | None = None

    @model_validator(mode="after")
    def _merge_frontend_origin(self) -> "Settings":
        # Trailing slash / path paste mistakes break CORS exact-match.
        self.frontend_origin = normalize_origin(self.frontend_origin)
        self.cors_origins = normalize_cors_origins(list(self.cors_origins or []))
        if self.frontend_origin and self.frontend_origin not in self.cors_origins:
            self.cors_origins = [*self.cors_origins, self.frontend_origin]
        return self

    # Base directory for all uploaded/extracted/generated files (see the
    # four *_dir settings below), overridable as a single STORAGE_DIR env
    # var (e.g. Render's persistent disk mount). Each of the four can still
    # be overridden individually if ever needed - they only default from
    # this value when left unset.
    storage_dir: Path = STORAGE_DIR

    storage_uploads_dir: Path | None = None
    storage_extracted_dir: Path | None = None
    storage_outputs_dir: Path | None = None
    storage_templates_dir: Path | None = None

    # Upload safety (course sources).
    max_upload_bytes: int = 25 * 1024 * 1024
    max_notes_chars: int = 200_000

    @model_validator(mode="after")
    def _resolve_storage_dirs(self) -> "Settings":
        self.storage_uploads_dir = self.storage_uploads_dir or self.storage_dir / "uploads"
        self.storage_extracted_dir = self.storage_extracted_dir or self.storage_dir / "extracted"
        self.storage_outputs_dir = self.storage_outputs_dir or self.storage_dir / "outputs"
        self.storage_templates_dir = self.storage_templates_dir or self.storage_dir / "templates"
        return self

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

    # How long to wait for a single Anthropic API call before giving up
    # (ANTHROPIC_REQUEST_TIMEOUT_SECONDS env var). Optional to set - a sane
    # default (120s) means a hung request still surfaces as a clean,
    # classifiable timeout error (see app/generation/errors.py) instead of
    # hanging the generation run indefinitely.
    anthropic_request_timeout_seconds: float = 120.0

    # Auth for this internal MVP (see app/auth/). Admin gets full scopes;
    # optional OPERATOR_* credentials get courses:* only (no Admin Knowledge).
    auth_enabled: bool = True
    admin_username: str | None = None
    admin_password: str | None = None
    auth_secret_key: str | None = None
    operator_username: str | None = None
    operator_password: str | None = None

    # Budget Guard (see app/generation/budget_guard.py) - observational
    # only, never blocks/aborts a run. Both budgets default to `None`
    # (unset): if neither is set, nothing is computed or warned about at
    # all. `ai_warn_at_percent` only matters once at least one budget is
    # set.
    ai_monthly_budget_usd: float | None = None
    ai_course_budget_usd: float | None = None
    ai_warn_at_percent: float = 80.0

    # Optional emergency spend kill-switch (bugs only). Empty/None = disabled.
    # When estimated spend for a job (or process-wide course spend since job
    # start tracking via AIUsageEvent for the job) reaches this USD total,
    # generation stops cleanly with PARTIAL + partial DOCX if available.
    # Env: AI_RUNAWAY_HARD_CAP_USD
    ai_runaway_hard_cap_usd: float | None = None

    # Soft debounce between *new* generation starts for the same course
    # (active-job reuse is still immediate). Env: GENERATE_MIN_INTERVAL_SECONDS
    generate_min_interval_seconds: float = 3.0

    # When True (default), only one generation job may be active globally
    # across all courses. Env: GENERATION_GLOBAL_LOCK
    generation_global_lock: bool = True

    # Generation runs off the HTTP request via BackgroundTasks (single
    # Uvicorn worker expected). Multi-worker: keep generation_global_lock
    # and Postgres advisory locks; do not rely on in-process map/throttle
    # maps alone. Env: documented in app/generation/job_runner.py

    # Orphan upload file retention (days). 0 disables purge. Env: SOURCE_RETENTION_DAYS
    source_retention_days: int = 90


settings = Settings()
