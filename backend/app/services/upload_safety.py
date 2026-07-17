"""Upload safety — size limits, filename sanitize, path confinement, MIME sniff."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import HTTPException, UploadFile

# Defaults; overridable via settings when present.
DEFAULT_MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
DEFAULT_MAX_NOTES_CHARS = 200_000
ALLOWED_EXTENSIONS = frozenset({".docx", ".pdf", ".txt", ".md"})

_UNSAFE_NAME_RE = re.compile(r"[^\w.\- ()\u0600-\u06FF]+", re.UNICODE)

# Declared MIME types we accept (client-supplied Content-Type is advisory).
ALLOWED_MIME_TYPES = frozenset(
    {
        "application/pdf",
        "application/x-pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "application/octet-stream",  # browsers often send this; magic bytes decide
        "text/plain",
        "text/markdown",
        "text/x-markdown",
        "",
        "application/zip",  # DOCX is a zip; some clients send this
    }
)


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
            status_code=415,
            detail=(
                f"Unsupported file type '{suffix or 'unknown'}'. "
                f"Allowed: {sorted(ALLOWED_EXTENSIONS)}"
            ),
        )
    return suffix


def assert_content_matches_extension(data: bytes, suffix: str) -> None:
    """Reject obvious extension/MIME mismatches via magic bytes.

    Encrypted/corrupt PDFs still pass the header check and are rejected later
    by extraction with a clear status — we never execute uploaded bytes.
    """
    suffix = (suffix or "").lower()
    head = data[:8] if data else b""
    if suffix == ".pdf":
        if not data.startswith(b"%PDF"):
            raise HTTPException(
                status_code=400,
                detail="File content is not a valid PDF (missing %PDF header).",
            )
        return
    if suffix == ".docx":
        # DOCX is a ZIP package (PK..). Plain OLE .doc is rejected.
        if not data.startswith(b"PK"):
            raise HTTPException(
                status_code=400,
                detail="File content is not a valid DOCX (expected ZIP/PK header).",
            )
        return
    if suffix in (".txt", ".md"):
        # Reject binary dumps pretending to be text (NUL in the head).
        sample = data[:4096]
        if b"\x00" in sample:
            raise HTTPException(
                status_code=400,
                detail="File content looks binary; only plain text/markdown is allowed.",
            )
        return
    raise HTTPException(status_code=400, detail=f"Unsupported file type '{suffix}'.")


def assert_declared_mime_ok(content_type: str | None) -> None:
    raw = (content_type or "").split(";")[0].strip().lower()
    if raw and raw not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported Content-Type '{raw}'. Allowed uploads: PDF, DOCX, TXT, MD.",
        )


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


def assert_course_output_file(path: Path, *, course_id: int, outputs_root: Path) -> Path:
    """Serve only files under `outputs/{course_id}/` (not any file in outputs/).

    Senior-engineer classic: `assert_path_under_root` alone still allows
    IDOR if a row's path points at another course's DOCX in the same root.
    """
    safe = assert_path_under_root(path, outputs_root)
    course_dir = (outputs_root / str(course_id)).resolve()
    try:
        safe.relative_to(course_dir)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Output file does not belong to this course.",
        ) from exc
    if not safe.is_file():
        raise HTTPException(status_code=404, detail="Output file is missing on disk")
    return safe
