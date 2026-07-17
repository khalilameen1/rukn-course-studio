from datetime import datetime

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    scopes: list[str] = []


class MeResponse(BaseModel):
    username: str
    scopes: list[str] = []


class PublicDiagnosticsResponse(BaseModel):
    """Minimal unauthenticated probe — no CORS origins, models, or error text."""

    ok: bool = True
    auth_enabled: bool
    auth_secret_key_configured: bool
    database_backend: str
    ai_provider_ready: bool


class DiagnosticsResponse(BaseModel):
    """Response for GET /auth/diagnostics/full (authenticated).

    Every field here must be safe to return to an authenticated operator:
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
    ai_provider: str
    ai_provider_ready: bool
    ai_model_name: str
    provider_reachable: str
    last_successful_request_at: datetime | None
    last_error_category: str | None
    last_error_message: str | None
