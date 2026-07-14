"""Upload safety — size limits, filename sanitize, path confinement."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import HTTPException, UploadFile

# Defaults; overridable via settings when present.
DEFAULT_MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
DEFAULT_MAX_NOTES_CHARS = 200_000
ALLOWED_EXTENSIONS = frozenset({".docx", ".pdf", ".txt", ".md"})

_UNSAFE_NAME_RE = re.compile(r"[^\w.\- ()\u0600-\u06FF]+", re.UNICODE)


def sanitize_filename(name: str | None, *, fallback: str = "upload") -> str:
    """Safe display filename — never used as a storage path segment."""
    raw = (name or "").strip() or fallback
    # Drop any path components (traversal / absolute paths).
    raw = Path(raw.replace("\\", "/")).name
    cleaned = _UNSAFE_NAME_RE.sub("_", raw).strip("._") or fallback
    return cleaned[:180]


def assert_allowed_extension(filename: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{suffix or 'unknown'}'. "
                f"Allowed: {sorted(ALLOWED_EXTENSIONS)}"
            ),
        )
    return suffix


async def read_upload_capped(
    file: UploadFile, *, max_bytes: int = DEFAULT_MAX_UPLOAD_BYTES
) -> bytes:
    """Read upload with a hard size cap — reject oversized clearly."""
    chunks: list[bytes] = []
    total = 0
    while True:
        piece = await file.read(1024 * 64)
        if not piece:
            break
        total += len(piece)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum allowed size is {max_bytes} bytes.",
            )
        chunks.append(piece)
    data = b"".join(chunks)
    if not data:
        raise HTTPException(status_code=400, detail="Empty or unreadable file.")
    return data


def assert_notes_length(text: str, *, max_chars: int = DEFAULT_MAX_NOTES_CHARS) -> None:
    if len(text or "") > max_chars:
        raise HTTPException(
            status_code=400,
            detail=f"Pasted text too long. Maximum {max_chars} characters.",
        )
    if not (text or "").strip():
        raise HTTPException(status_code=400, detail="Pasted text is empty.")


def assert_path_under_root(path: Path, root: Path) -> Path:
    """Prevent path traversal when deleting/serving stored files."""
    resolved = path.resolve()
    root_resolved = root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid stored file path.") from exc
    return resolved
