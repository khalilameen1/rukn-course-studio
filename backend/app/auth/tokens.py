"""Minimal signed session tokens for the single-admin-user MVP.

Deliberately not a JWT library - this is just enough HMAC-signed, expiring
token to authenticate the one admin user, using only stdlib. See
docs/ARCHITECTURE constraints: no auth framework/dependency for a
single-user MVP.

Format: "<base64url payload json>.<base64url HMAC-SHA256 signature>"
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

DEFAULT_EXPIRY_DAYS = 7


class InvalidTokenError(Exception):
    """Raised when a token is malformed, unsigned, tampered with, or expired."""


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(payload_b64: str, secret_key: str) -> str:
    digest = hmac.new(
        secret_key.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
    ).digest()
    return _b64encode(digest)


def create_token(
    username: str, secret_key: str, expiry_days: int = DEFAULT_EXPIRY_DAYS
) -> str:
    payload = {"sub": username, "exp": int(time.time()) + expiry_days * 86400}
    payload_b64 = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _sign(payload_b64, secret_key)
    return f"{payload_b64}.{signature}"


def verify_token(token: str, secret_key: str) -> dict:
    """Verify signature and expiry, returning the decoded payload (with `sub`).

    Raises `InvalidTokenError` for any malformed, tampered, or expired token.
    """
    try:
        payload_b64, signature = token.split(".", 1)
    except ValueError as exc:
        raise InvalidTokenError("Malformed token") from exc

    expected_signature = _sign(payload_b64, secret_key)
    if not hmac.compare_digest(signature, expected_signature):
        raise InvalidTokenError("Invalid token signature")

    try:
        payload = json.loads(_b64decode(payload_b64))
    except (ValueError, json.JSONDecodeError) as exc:
        raise InvalidTokenError("Malformed token payload") from exc

    if not isinstance(payload, dict) or "sub" not in payload or "exp" not in payload:
        raise InvalidTokenError("Malformed token payload")

    if payload["exp"] < time.time():
        raise InvalidTokenError("Token has expired")

    return payload
