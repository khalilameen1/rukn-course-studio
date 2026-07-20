"""Identity registry for the one canonical RUKN course standard."""

from __future__ import annotations

from dataclasses import dataclass

from app.data.course_standard import (
    STANDARD_FILE_NAMES,
    STANDARD_RELATIVE_DIRECTORY,
    STANDARD_VERSION,
    load_standard_files,
    standard_fingerprint,
)
from app.prompts.prompt_registry import PipelineStage


@dataclass(frozen=True)
class KeyInfo:
    title: str
    description: str
    order: int


def _title(content: str, fallback: str) -> str:
    return next(
        (line[2:].strip() for line in content.splitlines() if line.startswith("# ")),
        fallback,
    )


_FILES = load_standard_files()
KEY_CATALOG: dict[str, KeyInfo] = {
    name: KeyInfo(
        title=_title(_FILES[name], name),
        description="Canonical RUKN v1.3 control-system file (read-only).",
        order=order,
    )
    for order, name in enumerate(STANDARD_FILE_NAMES, start=1)
}

REQUIRED_KEYS: frozenset[str] = frozenset(STANDARD_FILE_NAMES)
REFRESHABLE_DEFAULT_KEYS: tuple[str, ...] = STANDARD_FILE_NAMES
EXCLUDED_FROM_STAGE_PACKS: frozenset[str] = frozenset()
STABLE_RULE_KEYS: tuple[str, ...] = STANDARD_FILE_NAMES
ALL_SYSTEM_KEYS: frozenset[str] = REQUIRED_KEYS

# README requires every file to be loaded before planning or writing.  Every
# current pipeline stage therefore receives the same ordered package.
STAGE_RULE_KEYS: dict[PipelineStage, tuple[str, ...]] = {
    stage: STANDARD_FILE_NAMES for stage in PipelineStage
}


def key_info_public() -> list[dict[str, object]]:
    fingerprint = standard_fingerprint(_FILES)
    return [
        {
            "key": name,
            "title": KEY_CATALOG[name].title,
            "description": KEY_CATALOG[name].description,
            "order": KEY_CATALOG[name].order,
            "file_path": f"{STANDARD_RELATIVE_DIRECTORY}/{name}",
            "standard_version": STANDARD_VERSION,
            "standard_fingerprint": fingerprint,
            "required": True,
            "refreshable": False,
            "in_stage_packs": True,
            "stable": True,
            "read_only": True,
        }
        for name in STANDARD_FILE_NAMES
    ]
