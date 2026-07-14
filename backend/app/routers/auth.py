from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from app.auth.diagnostics import build_diagnostics
from app.auth.service import AuthConfigError, verify_credentials
from app.auth.tokens import DEFAULT_EXPIRY_DAYS, create_token
from app.config import settings
from app.db import get_session
from app.schemas.auth import DiagnosticsResponse, LoginRequest, LoginResponse, MeResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    """Check username/password against ADMIN_USERNAME/ADMIN_PASSWORD and
    return a signed token valid for 7 days. Never logs the password."""
    try:
        valid = verify_credentials(payload.username, payload.password)
    except AuthConfigError as exc:
        # Server isn't configured for login at all - a 503, not a 401, so
        # this is never confused with "wrong password".
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not valid:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_token(payload.username, settings.auth_secret_key, DEFAULT_EXPIRY_DAYS)
    return LoginResponse(access_token=token, token_type="bearer")


@router.get("/me", response_model=MeResponse)
def me(request: Request) -> MeResponse:
    """Returns the current user, as identified by AuthMiddleware from the
    request's bearer token (see app/auth/middleware.py)."""
    username = getattr(request.state, "username", None)
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return MeResponse(username=username)


@router.post("/logout", status_code=204)
def logout() -> None:
    """No server-side session to invalidate for this MVP - the frontend
    simply discards its token. Kept as an endpoint for a consistent
    frontend logout call / future session storage."""
    return None


@router.get("/diagnostics", response_model=DiagnosticsResponse)
def diagnostics(session: Session = Depends(get_session)) -> DiagnosticsResponse:
    """Public, secret-free status check for diagnosing login/CORS/storage
    misconfiguration in production (e.g. FRONTEND_ORIGIN never set on
    Render), plus AI Provider Health (§7). Deliberately public - see
    app/auth/middleware.py PUBLIC_ROUTES - since it needs to be reachable
    even when login itself is broken. See app/auth/diagnostics.py for
    exactly what is/isn't returned."""
    return DiagnosticsResponse(**build_diagnostics(session=session))
