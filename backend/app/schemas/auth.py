from datetime import datetime

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    username: str


class DiagnosticsResponse(BaseModel):
    """Response for GET /auth/diagnostics - see app/auth/diagnostics.py.

    Every field here must be safe to return to an unauthenticated caller:
    booleans/labels only, never a credential, connection string, or API
    key value.
    """

    auth_enabled: bool
    admin_username_configured: bool
    admin_password_configured: bool
    auth_secret_key_configured: bool
    frontend_origin_configured: bool
    frontend_origin_value: str | None
    cors_origins: list[str]
    database_backend: str
    storage_dir_configured: bool
    storage_dir_exists: bool
    storage_dir_writable: bool
    # Raw AI_PROVIDER value (e.g. "fake"/"anthropic") - not a secret, just
    # which provider is selected. `ai_provider_ready` is the only signal of
    # whether it can actually run right now; never a credential/key value.
    ai_provider: str
    ai_provider_ready: bool
    # AI Provider Health (§7) - see app/auth/diagnostics.py `_provider_health`.
    # A model name is not a secret (only the API key is); "fake" when the
    # fake provider is selected.
    ai_model_name: str
    # "unknown" | "ok" - never a live network probe (see module docstring
    # in app/auth/diagnostics.py for why), derived only from whether a
    # recent successful AIUsageEvent exists. Deliberately never "error":
    # a *reachability* signal, not the same thing as "the last request
    # failed" (see last_error_category/last_error_message below for that).
    provider_reachable: str
    last_successful_request_at: datetime | None
    last_error_category: str | None
    last_error_message: str | None
