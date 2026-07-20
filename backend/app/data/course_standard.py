"""Canonical RUKN Universal Skill Course Standard package.

The Markdown files are immutable product assets.  Their ordered bytes plus the
published version form the one fingerprint used by every generation stage.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.models.enums import ItemType

STANDARD_VERSION = "1.3-spoken-variety-integrity"
STANDARD_DIRECTORY = Path(__file__).resolve().parent / "rukn_universal_course_standard"
STANDARD_FILE_NAMES: tuple[str, ...] = (
    "README.md",
    "00-runtime-contract.md",
    "01-intake-and-course-thesis.md",
    "02-research-market-and-voice-calibration.md",
    "03-capability-map-and-course-architecture.md",
    "04-projects-practice-and-assessment.md",
    "05-lesson-meaning-and-writing.md",
    "06-language-terminology-and-teleprompter.md",
    "07-tools-ai-cost-and-evergreen-design.md",
    "08-quality-gates-and-rewrite-protocol.md",
    "09-delivery-contract-and-transfer.md",
    "10-generation-integrity.md",
    "11-stage-contracts-and-first-run.md",
    "12-course-family-adapters.md",
)
STANDARD_KEYS = STANDARD_FILE_NAMES
STANDARD_RELATIVE_DIRECTORY = "app/data/rukn_universal_course_standard"


def _validate_directory() -> None:
    actual = {path.name for path in STANDARD_DIRECTORY.glob("*.md")}
    expected = set(STANDARD_FILE_NAMES)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise RuntimeError(
            "Canonical course standard must contain exactly 14 Markdown files; "
            f"missing={missing}, extra={extra}"
        )


def load_standard_files() -> dict[str, str]:
    """Return every canonical file in immutable load order, failing closed."""
    _validate_directory()
    return {
        name: (STANDARD_DIRECTORY / name).read_text(encoding="utf-8")
        for name in STANDARD_FILE_NAMES
    }


def standard_fingerprint(files: dict[str, str] | None = None) -> str:
    """SHA-256 over version, file order, names, and exact UTF-8 content."""
    content = files or load_standard_files()
    if tuple(content) != STANDARD_FILE_NAMES:
        raise ValueError("Standard files are missing or not in canonical load order")
    digest = hashlib.sha256()
    digest.update(STANDARD_VERSION.encode("utf-8"))
    digest.update(b"\0")
    for name in STANDARD_FILE_NAMES:
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content[name].encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _title(content: str, fallback: str) -> str:
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def standard_seed_items() -> list[dict[str, object]]:
    files = load_standard_files()
    return [
        {
            "key": name,
            "title": _title(files[name], name),
            "item_type": ItemType.MARKDOWN,
            "content_text": files[name],
            "file_path": f"{STANDARD_RELATIVE_DIRECTORY}/{name}",
            "version": 1,
            "is_active": True,
        }
        for name in STANDARD_FILE_NAMES
    ]


def standard_manifest() -> dict[str, object]:
    files = load_standard_files()
    return {
        "standard_version": STANDARD_VERSION,
        "fingerprint": standard_fingerprint(files),
        "file_count": len(STANDARD_FILE_NAMES),
        "files": [
            {
                "order": order,
                "key": name,
                "title": _title(files[name], name),
                "file_path": f"{STANDARD_RELATIVE_DIRECTORY}/{name}",
                "content_sha256": hashlib.sha256(
                    files[name].encode("utf-8")
                ).hexdigest(),
            }
            for order, name in enumerate(STANDARD_FILE_NAMES, start=1)
        ],
    }
