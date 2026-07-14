"""Redact credentials from logs, errors, and diagnostic strings.

Never log or return ANTHROPIC_API_KEY, passwords, or auth secrets.
"""

from __future__ import annotations

import re
from typing import Any

# Known Anthropic / generic secret shapes plus env-style KEY=value leaks.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(
        r"(?i)\b(ANTHROPIC_API_KEY|AUTH_SECRET_KEY|ADMIN_PASSWORD|"
        r"DATABASE_URL|SMOKE_ADMIN_PASSWORD)\s*[=:]\s*\S+"
    ),
    re.compile(r"(?i)(api[_-]?key|password|secret[_-]?key)\s*[=:]\s*\S+"),
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*"),
)

REDACTED = "[REDACTED]"


def redact_secrets(text: str | None) -> str:
    """Return a copy of `text` with credential-looking substrings removed."""
    if not text:
        return ""
    out = str(text)
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub(REDACTED, out)
    return out


def redact_for_log(entry: Any) -> Any:
    """Recursively redact string values in log structures."""
    if isinstance(entry, str):
        return redact_secrets(entry)
    if isinstance(entry, dict):
        return {k: redact_for_log(v) for k, v in entry.items()}
    if isinstance(entry, list):
        return [redact_for_log(v) for v in entry]
    return entry


def contains_secret(text: str | None, known: str | None = None) -> bool:
    """True if `text` still contains an unredacted-looking secret or `known`."""
    if not text:
        return False
    if known and known in text:
        return True
    return redact_secrets(text) != text
