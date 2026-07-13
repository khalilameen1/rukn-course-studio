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
