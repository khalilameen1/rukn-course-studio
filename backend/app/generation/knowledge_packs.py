"""Compact stage-specific Admin Knowledge packs — no full table dump.

Builds short instruction packs from selected rukn_* keys so prompts receive
only what the stage needs (cost hygiene).
"""

from __future__ import annotations

import re
from app.prompts.prompt_registry import PipelineStage

# Soft cap per packed article / total pack.
_PER_KEY_CHARS = 900
_PACK_MAX_CHARS = 4200

# Pack names → pipeline stages that use them.
MAP_PLANNING_STAGES = {PipelineStage.BUILD_COURSE_MAP}
LESSON_WRITING_STAGES = {
    PipelineStage.WRITE_SINGLE_REEL,
    PipelineStage.REBUILD_FINAL_COURSE,
}
REVIEW_STAGES = {
    PipelineStage.REVIEW_SINGLE_REEL,
    PipelineStage.REVIEW_FIVE_REELS,
    PipelineStage.REVIEW_MODULE,
    PipelineStage.REVIEW_TWO_MODULES,
    PipelineStage.FINAL_REVIEW,
}
FINAL_EXPORT_STAGES = {PipelineStage.FINAL_REVIEW, PipelineStage.REBUILD_FINAL_COURSE}

PACK_KEY_BY_STAGE: dict[PipelineStage, str] = {
    PipelineStage.BUILD_COURSE_MAP: "map_planning_rules_pack",
    PipelineStage.WRITE_SINGLE_REEL: "lesson_writing_rules_pack",
    PipelineStage.REVIEW_SINGLE_REEL: "review_rules_pack",
    PipelineStage.REVIEW_FIVE_REELS: "review_rules_pack",
    PipelineStage.REVIEW_MODULE: "review_rules_pack",
    PipelineStage.REVIEW_TWO_MODULES: "review_rules_pack",
    PipelineStage.FINAL_REVIEW: "final_export_rules_pack",
    PipelineStage.REBUILD_FINAL_COURSE: "final_export_rules_pack",
}


def _compact_article(text: str, *, max_chars: int = _PER_KEY_CHARS) -> str:
    """Keep headings + lead bullets; drop long examples."""
    if not text:
        return ""
    lines = []
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        # Prefer headings, bullets, numbered rules, short imperatives.
        if (
            stripped.startswith("#")
            or stripped.startswith("-")
            or stripped.startswith("*")
            or re.match(r"^\d+[.)]", stripped)
            or len(stripped) <= 160
        ):
            lines.append(stripped)
        elif len(stripped) <= 220:
            lines.append(stripped[:200] + ("…" if len(stripped) > 200 else ""))
    packed = "\n".join(lines).strip() or text[:max_chars]
    if len(packed) > max_chars:
        return packed[: max_chars - 1].rstrip() + "…"
    return packed


def build_stage_rules_pack(
    selected_rules: dict[str, str],
    stage: PipelineStage,
    *,
    max_chars: int = _PACK_MAX_CHARS,
) -> dict[str, str]:
    """Collapse selected Admin Knowledge into one compact pack key.

    Returns a dict with a single pack key (plus any tiny runtime keys already
    outside Admin Knowledge that callers may merge later). Original full
    articles are NOT forwarded.
    """
    pack_name = PACK_KEY_BY_STAGE.get(stage, "lesson_writing_rules_pack")
    parts: list[str] = []
    total = 0
    for key, content in selected_rules.items():
        if key.startswith("rukn_") and key.endswith("_runtime"):
            # Runtime guidance stays as its own short key.
            continue
        chunk = _compact_article(content)
        if not chunk:
            continue
        block = f"### {key}\n{chunk}"
        if total + len(block) > max_chars:
            remain = max_chars - total - 20
            if remain > 80:
                parts.append(block[:remain] + "…")
            break
        parts.append(block)
        total += len(block) + 2

    pack_body = "\n\n".join(parts).strip()
    out: dict[str, str] = {pack_name: pack_body} if pack_body else {}

    # Pass through compact runtime keys and authority-pack hints unchanged.
    for key, content in selected_rules.items():
        if key.endswith("_runtime") and content:
            out[key] = content[:1200]
        elif key == "rukn_authority_pack_hint" and content:
            out[key] = content[:800]
    return out


def select_and_pack_rules(
    all_rules: dict[str, str],
    stage: PipelineStage,
    *,
    select_fn,
) -> dict[str, str]:
    """select_rules_for_stage then pack — cost-hygiene entry point."""
    selected = select_fn(all_rules, stage)
    return build_stage_rules_pack(selected, stage)


def pack_is_compact(pack: dict[str, str], full_selected: dict[str, str]) -> bool:
    """True when packed total chars << full selected articles."""
    pack_chars = sum(len(v) for v in pack.values())
    full_chars = sum(len(v) for v in full_selected.values())
    if full_chars <= 0:
        return True
    return pack_chars < full_chars and pack_chars <= _PACK_MAX_CHARS
