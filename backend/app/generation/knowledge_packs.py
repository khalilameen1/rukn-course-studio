"""Pack the canonical RUKN standard without slicing or legacy overlays."""

from __future__ import annotations

from app.data.course_standard import STANDARD_FILE_NAMES
from app.prompts.prompt_registry import PipelineStage

MANDATORY_CORE_KEYS: tuple[str, ...] = STANDARD_FILE_NAMES
RELEVANT_RETRIEVED_KEYS: tuple[str, ...] = ()
_PER_KEY_CHARS = 10_000_000

MAP_PLANNING_STAGES = {PipelineStage.BUILD_COURSE_MAP}
LESSON_WRITING_STAGES = {
    PipelineStage.WRITE_SINGLE_REEL,
    PipelineStage.REBUILD_FINAL_COURSE,
}
REVIEW_STAGES = {
    PipelineStage.REVIEW_SINGLE_REEL,
    PipelineStage.FINAL_REVIEW,
}
FINAL_EXPORT_STAGES = {
    PipelineStage.FINAL_REVIEW,
    PipelineStage.REBUILD_FINAL_COURSE,
}
PACK_KEY_BY_STAGE: dict[PipelineStage, str] = {
    stage: "rukn_universal_course_standard" for stage in PipelineStage
}


def estimate_tokens(text: str) -> int:
    return max(1, (len(text or "") + 3) // 4)


def build_stage_rules_pack(
    selected_rules: dict[str, str],
    stage: PipelineStage,
    *,
    max_chars: int | None = None,
) -> dict[str, str]:
    """Return all 14 files, whole and ordered, for every generation stage.

    ``max_chars`` remains in the signature for callers but cannot truncate the
    canonical standard.  Prompt caching, not rule deletion, controls cost.
    """
    del max_chars
    missing = [key for key in STANDARD_FILE_NAMES if not selected_rules.get(key)]
    if missing:
        raise ValueError(f"Canonical standard is incomplete for {stage.value}: {missing}")
    body = "\n\n".join(
        f"### {key}\n{selected_rules[key]}" for key in STANDARD_FILE_NAMES
    )
    return {PACK_KEY_BY_STAGE[stage]: body}


def select_and_pack_rules(
    all_rules: dict[str, str],
    stage: PipelineStage,
    *,
    select_fn,
) -> dict[str, str]:
    return build_stage_rules_pack(select_fn(all_rules, stage), stage)


def pack_is_compact(pack: dict[str, str], full_selected: dict[str, str]) -> bool:
    """The canonical pack may add headings but never duplicates file content."""
    body = "\n".join(pack.values())
    return all(body.count(content) == 1 for content in full_selected.values() if content)


def mandatory_core_intact(pack: dict[str, str], selected: dict[str, str]) -> bool:
    body = "\n".join(pack.values())
    return all(
        f"### {key}" in body and selected.get(key, "").strip() in body
        for key in STANDARD_FILE_NAMES
    )
