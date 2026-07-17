"""Compact stage-specific Admin Knowledge packs — no full table dump.

Builds short instruction packs from selected rukn_* keys so prompts receive
only what the stage needs (cost hygiene).
"""

from __future__ import annotations

import re

from app.data.admin_knowledge.pack_sections import (
    ANTI_PATTERNS_SECTIONS_BY_STAGE,
    EDUCATIONAL_CREATOR_SECTIONS_BY_STAGE,
    INTERPRETATION_SECTIONS_BY_STAGE,
    SOURCE_DISTILLATION_SECTIONS_BY_STAGE,
    TRANSCRIPT_TOPIC_RELEVANCE_SECTIONS_BY_STAGE,
)
from app.prompts.prompt_registry import PipelineStage

# Soft cap per packed article / total pack.
_PER_KEY_CHARS = 900
_PACK_MAX_CHARS = 4200
_INTERPRETATION_STAGE_MAX_CHARS = 900
_EDUCATIONAL_CREATOR_STAGE_MAX_CHARS = 900
_ANTI_PATTERNS_STAGE_MAX_CHARS = 900

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

# Back-compat aliases for tests that imported private maps from this module.
_INTERPRETATION_SECTIONS_BY_STAGE = INTERPRETATION_SECTIONS_BY_STAGE
_EDUCATIONAL_CREATOR_SECTIONS_BY_STAGE = EDUCATIONAL_CREATOR_SECTIONS_BY_STAGE
_SOURCE_DISTILLATION_SECTIONS_BY_STAGE = SOURCE_DISTILLATION_SECTIONS_BY_STAGE
_TRANSCRIPT_TOPIC_RELEVANCE_SECTIONS_BY_STAGE = TRANSCRIPT_TOPIC_RELEVANCE_SECTIONS_BY_STAGE
_ANTI_PATTERNS_SECTIONS_BY_STAGE = ANTI_PATTERNS_SECTIONS_BY_STAGE

# `## N. Title` or `## N. Title {#anchor}` — number remains the pack contract.
_SECTION_HEADER_RE = re.compile(
    r"^##\s+(\d+)\.\s+.*?(?:\s+\{#([a-z0-9\-]+)\})?\s*$",
    re.MULTILINE,
)


def _split_numbered_sections(text: str) -> dict[int, str]:
    """Parse `## N. Title` / `## N. Title {#anchor}` blocks.

    Returns sections keyed by number. Optional anchors are also indexed under
    a parallel attribute for future named maps (`_section_anchors` on the
    returned dict is not used — see `_split_sections_with_anchors`).
    """
    return _split_sections_with_anchors(text)[0]


def _split_sections_with_anchors(text: str) -> tuple[dict[int, str], dict[str, str]]:
    """Return `(by_number, by_anchor)` for numbered Admin Knowledge articles."""
    headers = list(_SECTION_HEADER_RE.finditer(text or ""))
    by_number: dict[int, str] = {}
    by_anchor: dict[str, str] = {}
    for i, match in enumerate(headers):
        num = int(match.group(1))
        start = match.start()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        block = text[start:end].strip()
        by_number[num] = block
        anchor = match.group(2)
        if anchor:
            by_anchor[anchor] = block
    return by_number, by_anchor


def _stage_numbered_article_slice(
    full_text: str,
    stage: PipelineStage,
    sections_by_stage: dict[PipelineStage, tuple[int, ...]],
    *,
    header: str,
    lead: str,
    max_chars: int,
) -> str:
    wanted = sections_by_stage.get(stage)
    if not wanted or not (full_text or "").strip():
        return ""
    sections = _split_numbered_sections(full_text)
    parts = [header, lead]
    for num in wanted:
        block = sections.get(num)
        if not block:
            continue
        candidate = "\n\n".join(parts + [block])
        if len(candidate) > max_chars:
            break
        parts.append(block)
    return "\n\n".join(parts).strip()


def stage_interpretation_guardrails(
    full_text: str,
    stage: PipelineStage,
    *,
    max_chars: int = _INTERPRETATION_STAGE_MAX_CHARS,
) -> str:
    """Compact stage-relevant subset — never resend all 25 points every call."""
    wanted = _INTERPRETATION_SECTIONS_BY_STAGE.get(stage)
    if not wanted or not (full_text or "").strip():
        return ""
    return _stage_numbered_article_slice(
        full_text,
        stage,
        _INTERPRETATION_SECTIONS_BY_STAGE,
        header="# Interpretation guardrails (stage-relevant only)",
        lead="Clarify ROKN rule intent — no new features/output types.",
        max_chars=max_chars,
    )


def stage_educational_creator_standard(
    full_text: str,
    stage: PipelineStage,
    *,
    max_chars: int = _EDUCATIONAL_CREATOR_STAGE_MAX_CHARS,
) -> str:
    """Compact stage-relevant creator voice standard — not the full article."""
    wanted = _EDUCATIONAL_CREATOR_SECTIONS_BY_STAGE.get(stage)
    if not wanted or not (full_text or "").strip():
        return ""
    sections = _split_numbered_sections(full_text)
    parts = [
        "# Educational creator standard (stage-relevant only)",
        (
            "Practitioner-educator voice — not generic AI teacher or course seller. "
            "Teleprompter DOCX only."
        ),
    ]
    per_section_cap = 150 if stage == PipelineStage.WRITE_SINGLE_REEL else 220
    for num in wanted:
        block = sections.get(num)
        if not block:
            continue
        block = _compact_article(block, max_chars=per_section_cap)
        candidate = "\n\n".join(parts + [block])
        if len(candidate) > max_chars:
            break
        parts.append(block)
    return "\n\n".join(parts).strip()


def stage_source_distillation_gate(
    full_text: str,
    stage: PipelineStage,
    *,
    max_chars: int = _EDUCATIONAL_CREATOR_STAGE_MAX_CHARS,
) -> str:
    """Distillation rules slice — sources are raw material, not authority."""
    return _stage_numbered_article_slice(
        full_text,
        stage,
        _SOURCE_DISTILLATION_SECTIONS_BY_STAGE,
        header="# Source distillation gate (stage-relevant only)",
        lead="All sources are distilled raw material — never copy format or assume authority.",
        max_chars=max_chars,
    )


def stage_transcript_topic_relevance_gate(
    full_text: str,
    stage: PipelineStage,
    *,
    max_chars: int = _EDUCATIONAL_CREATOR_STAGE_MAX_CHARS,
) -> str:
    """Transcript relevance slice — same-topic raw material vs off-topic colloquial only."""
    return _stage_numbered_article_slice(
        full_text,
        stage,
        _TRANSCRIPT_TOPIC_RELEVANCE_SECTIONS_BY_STAGE,
        header="# Transcript topic relevance gate (stage-relevant only)",
        lead=(
            "Classify every transcript: same_topic raw material vs off_topic "
            "colloquial calibration only."
        ),
        max_chars=max_chars,
    )


def stage_anti_patterns_quality_checks(
    full_text: str,
    stage: PipelineStage,
    *,
    max_chars: int = _ANTI_PATTERNS_STAGE_MAX_CHARS,
) -> str:
    """Rejection/checklist slice — never a writing template or good-example bank."""
    wanted = _ANTI_PATTERNS_SECTIONS_BY_STAGE.get(stage)
    if not wanted or not (full_text or "").strip():
        return ""
    sections = _split_numbered_sections(full_text)
    parts = [
        "# Anti-patterns and quality checks (rejection layer only)",
        "Diagnostic checks and rejected patterns — do not copy as a style template.",
    ]
    per_section_cap = 200
    for num in wanted:
        block = sections.get(num)
        if not block:
            continue
        block = _compact_article(block, max_chars=per_section_cap)
        candidate = "\n\n".join(parts + [block])
        if len(candidate) > max_chars:
            break
        parts.append(block)
    return "\n\n".join(parts).strip()


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

    `rukn_interpretation_guardrails`, `rukn_educational_creator_standard`, and
    `rukn_anti_patterns_quality_checks` are replaced with stage-relevant slices
    before packing.
    """
    pack_name = PACK_KEY_BY_STAGE.get(stage, "lesson_writing_rules_pack")
    # Reserve space for authority hint + runtime keys appended below.
    reserve = 0
    for key, content in selected_rules.items():
        if key.endswith("_runtime") and content:
            reserve += min(len(content), 1200) + 2
        elif key == "rukn_authority_pack_hint" and content:
            reserve += min(len(content), 800) + 2
    article_budget = max(max_chars - reserve, 800)

    parts: list[str] = []
    total = 0
    for key, content in selected_rules.items():
        if key.startswith("rukn_") and key.endswith("_runtime"):
            # Runtime guidance stays as its own short key.
            continue
        if key == "rukn_authority_pack_hint":
            continue
        if key == "rukn_interpretation_guardrails":
            chunk = stage_interpretation_guardrails(content, stage)
        elif key == "rukn_educational_creator_standard":
            chunk = stage_educational_creator_standard(content, stage)
        elif key == "rukn_anti_patterns_quality_checks":
            chunk = stage_anti_patterns_quality_checks(content, stage)
        elif key == "rukn_source_distillation_gate":
            chunk = stage_source_distillation_gate(content, stage)
        elif key == "rukn_transcript_topic_relevance_gate":
            chunk = stage_transcript_topic_relevance_gate(content, stage)
        else:
            chunk = _compact_article(content)
        if not chunk:
            continue
        block = f"### {key}\n{chunk}"
        if total + len(block) > article_budget:
            remain = article_budget - total - 20
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
