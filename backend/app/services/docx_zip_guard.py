"""Guard against zip bombs / path tricks inside DOCX (ZIP) packages.

AI-generated upload pipelines often open DOCX with python-docx without
checking uncompressed size — a classic zip-bomb DoS.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

# Hard caps for a course-source DOCX (teleprompter inputs, not media packs).
MAX_DOCX_MEMBERS = 2_000
MAX_DOCX_UNCOMPRESSED_BYTES = 80 * 1024 * 1024  # 80 MB uncompressed total
MAX_DOCX_SINGLE_MEMBER_BYTES = 40 * 1024 * 1024  # 40 MB per entry
MAX_DOCX_COMPRESSION_RATIO = 100.0  # compressed→uncompressed blow-up


def assert_docx_zip_safe(path: Path | str) -> None:
    """Raise ValueError if the ZIP looks hostile before python-docx opens it."""
    zpath = Path(path)
    try:
        with zipfile.ZipFile(zpath, "r") as zf:
            infos = zf.infolist()
    except zipfile.BadZipFile as exc:
        raise ValueError("File is not a valid DOCX/ZIP package.") from exc

    if len(infos) > MAX_DOCX_MEMBERS:
        raise ValueError("DOCX has too many internal files.")

    total_uncomp = 0
    for info in infos:
        name = (info.filename or "").replace("\\", "/")
        if name.startswith("/") or name.startswith("../") or "/../" in f"/{name}/":
            raise ValueError("DOCX contains an unsafe internal path.")
        if info.file_size < 0 or info.compress_size < 0:
            raise ValueError("DOCX has invalid zip entry sizes.")
        if info.file_size > MAX_DOCX_SINGLE_MEMBER_BYTES:
            raise ValueError("DOCX contains an oversized internal file.")
        if info.compress_size > 0:
            ratio = info.file_size / max(info.compress_size, 1)
            if ratio > MAX_DOCX_COMPRESSION_RATIO and info.file_size > 1_000_000:
                raise ValueError("DOCX compression ratio looks like a zip bomb.")
        total_uncomp += info.file_size
        if total_uncomp > MAX_DOCX_UNCOMPRESSED_BYTES:
            raise ValueError("DOCX uncompressed size exceeds the safety limit.")
