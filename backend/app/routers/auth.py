from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from app.auth.diagnostics import build_diagnostics, build_public_diagnostics
from app.auth.login_throttle import allow_login_attempt_db
from app.auth.scopes import normalize_scopes
from app.auth.service import AuthConfigError, resolve_login
from app.auth.token_denylist import revoke_jti
from app.auth.tokens import DEFAULT_EXPIRY_DAYS, create_token, verify_token, InvalidTokenError
from app.config import settings
from app.db import get_session
from app.schemas.auth import (
    DiagnosticsResponse,
    LoginRequest,
    LoginResponse,
    MeResponse,
    PublicDiagnosticsResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> LoginResponse:
    """Check credentials and return a signed token with capability scopes."""
    client_key = request.client.host if request.client else "unknown"
    if not allow_login_attempt_db(session, client_key):
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again later.",
        )

    try:
        scopes = resolve_login(payload.username, payload.password)
    except AuthConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if scopes is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not settings.auth_secret_key:
        raise HTTPException(status_code=503, detail="AUTH_SECRET_KEY is not configured")

    token = create_token(
        payload.username,
        settings.auth_secret_key,
        DEFAULT_EXPIRY_DAYS,
        scopes=scopes,
    )
    return LoginResponse(access_token=token, token_type="bearer", scopes=scopes)


@router.get("/me", response_model=MeResponse)
def me(request: Request) -> MeResponse:
    """Returns the current user and scopes from AuthMiddleware."""
    username = getattr(request.state, "username", None)
    if not username:
        raise HTTPException(status_code=401, detail="Not authenticated")
    scopes = normalize_scopes(getattr(request.state, "scopes", None))
    return MeResponse(username=username, scopes=scopes)


@router.post("/logout", status_code=204)
def logout(request: Request, session: Session = Depends(get_session)) -> None:
    """Revoke the current bearer token (`jti`) until its natural expiry."""
    auth_header = request.headers.get("authorization", "")
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token or not settings.auth_secret_key:
        return None
    try:
        payload = verify_token(token, settings.auth_secret_key)
    except InvalidTokenError:
        return None
    jti = payload.get("jti")
    exp = payload.get("exp")
    if jti and exp:
        expires_at = datetime.fromtimestamp(int(exp), tz=timezone.utc)
        revoke_jti(
            session,
            jti,
            expires_at=expires_at,
            username=str(payload.get("sub") or "") or None,
        )
    return None


@router.get("/diagnostics", response_model=PublicDiagnosticsResponse)
def diagnostics_public() -> PublicDiagnosticsResponse:
    """Minimal public probe — safe when login itself is broken."""
    return PublicDiagnosticsResponse(**build_public_diagnostics())


@router.get("/diagnostics/full", response_model=DiagnosticsResponse)
def diagnostics_full(session: Session = Depends(get_session)) -> DiagnosticsResponse:
    """Authenticated diagnostics (CORS/storage/AI health detail)."""
    return DiagnosticsResponse(**build_diagnostics(session=session))
