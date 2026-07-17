"""Stdlib password hashing (pbkdf2_sha256) — no bcrypt dependency in V1.

Stored form: pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>

Plaintext env values still work for local/dev (compare_digest), but production
should store a hash produced by `hash_password`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

_PREFIX = "pbkdf2_sha256"
_DEFAULT_ITERATIONS = 260_000


def hash_password(password: str, *, iterations: int = _DEFAULT_ITERATIONS) -> str:
    if not password:
        raise ValueError("password must be non-empty")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    )
    return (
        f"{_PREFIX}${iterations}$"
        f"{base64.urlsafe_b64encode(salt).decode('ascii').rstrip('=')}$"
        f"{base64.urlsafe_b64encode(digest).decode('ascii').rstrip('=')}"
    )


def is_hashed_secret(stored: str) -> bool:
    return (stored or "").startswith(f"{_PREFIX}$")


def verify_password(password: str, stored: str) -> bool:
    """Return True when `password` matches `stored` (hash or legacy plaintext)."""
    if not stored:
        return False
    if is_hashed_secret(stored):
        try:
            prefix, iter_s, salt_b64, hash_b64 = stored.split("$", 3)
        except ValueError:
            return False
        if prefix != _PREFIX:
            return False
        try:
            iterations = int(iter_s)
        except ValueError:
            return False
        pad = "=" * (-len(salt_b64) % 4)
        salt = base64.urlsafe_b64decode(salt_b64 + pad)
        pad_h = "=" * (-len(hash_b64) % 4)
        expected = base64.urlsafe_b64decode(hash_b64 + pad_h)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, iterations
        )
        return hmac.compare_digest(actual, expected)
    # Legacy plaintext env password
    try:
        return hmac.compare_digest(password, stored)
    except (TypeError, ValueError):
        return False
