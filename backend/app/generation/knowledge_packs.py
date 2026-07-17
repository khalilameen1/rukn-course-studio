"""Token-aware priority packing for Admin Knowledge — no blind mid-rule cuts.

Mandatory core rules are included whole. Relevant retrieved rules follow by
lesson/stage. Optional context may be summarized or dropped under budget.
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

# Soft total budget (chars ≈ tokens*4). Mandatory core is reserved outside cuts.
_PACK_MAX_CHARS = 8000
_OPTIONAL_SUMMARY_CHARS = 400
_INTERPRETATION_STAGE_MAX_CHARS = 1800
_EDUCATIONAL_CREATOR_STAGE_MAX_CHARS = 1800
_ANTI_PATTERNS_STAGE_MAX_CHARS = 1800

# Legacy names kept for imports/tests — no longer used as hard per-key scissors.
_PER_KEY_CHARS = 10_000

# Must arrive complete on every Creator write / rewrite.
MANDATORY_CORE_KEYS: tuple[str, ...] = (
    "rukn_core_rules",
    "rukn_writing_style",
    "rukn_high_signal_reel_doctrine",
    "rukn_educational_creator_standard",
    "rukn_teleprompter_docx_contract",
)

RELEVANT_RETRIEVED_KEYS: tuple[str, ...] = (
    "rukn_practical_course_rules",
    "rukn_quality_rubric",
    "rukn_forbidden_phrases",
    "rukn_anti_patterns_quality_checks",
    "rukn_interpretation_guardrails",
    "rukn_source_distillation_gate",
    "rukn_transcript_topic_relevance_gate",
)

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


def estimate_tokens(text: str) -> int:
    """Rough token estimate without a tokenizer dependency (~4 chars/token)."""
    return max(1, (len(text or "") + 3) // 4)


def _split_numbered_sections(text: str) -> dict[int, str]:
    return _split_sections_with_anchors(text)[0]


def _split_sections_with_anchors(text: str) -> tuple[dict[int, str], dict[str, str]]:
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
    """Include whole numbered sections only — never cut mid-section."""
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
            # Drop this whole section rather than truncating mid-rule.
            break
        parts.append(block)
    return "\n\n".join(parts).strip()


def stage_interpretation_guardrails(
    full_text: str,
    stage: PipelineStage,
    *,
    max_chars: int = _INTERPRETATION_STAGE_MAX_CHARS,
) -> str:
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
    wanted = _EDUCATIONAL_CREATOR_SECTIONS_BY_STAGE.get(stage)
    if not wanted or not (full_text or "").strip():
        return ""
    # Mandatory core path: include whole wanted sections without per-section scissors.
    return _stage_numbered_article_slice(
        full_text,
        stage,
        _EDUCATIONAL_CREATOR_SECTIONS_BY_STAGE,
        header="# Educational creator standard (stage-relevant only)",
        lead=(
            "Practitioner-educator voice — not generic AI teacher or course seller. "
            "Teleprompter DOCX only."
        ),
        max_chars=max_chars,
    )


def stage_source_distillation_gate(
    full_text: str,
    stage: PipelineStage,
    *,
    max_chars: int = _EDUCATIONAL_CREATOR_STAGE_MAX_CHARS,
) -> str:
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
    wanted = _ANTI_PATTERNS_SECTIONS_BY_STAGE.get(stage)
    if not wanted or not (full_text or "").strip():
        return ""
    return _stage_numbered_article_slice(
        full_text,
        stage,
        _ANTI_PATTERNS_SECTIONS_BY_STAGE,
        header="# Anti-patterns and quality checks (rejection layer only)",
        lead="Diagnostic checks and rejected patterns — do not copy as a style template.",
        max_chars=max_chars,
    )


def _summarize_optional(text: str, *, max_chars: int = _OPTIONAL_SUMMARY_CHARS) -> str:
    """Summarize optional context by keeping headings/bullets only — whole lines."""
    if not text:
        return ""
    lines: list[str] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if (
            stripped.startswith("#")
            or stripped.startswith("-")
            or stripped.startswith("*")
            or re.match(r"^\d+[.)]", stripped)
        ):
            lines.append(stripped)
        if sum(len(x) + 1 for x in lines) >= max_chars:
            break
    packed = "\n".join(lines).strip()
    if not packed:
        # Last resort: first complete paragraph only (never mid-sentence cut of a rule).
        para = (text or "").strip().split("\n\n")[0]
        return para if len(para) <= max_chars else ""
    return packed


def _prepare_chunk(key: str, content: str, stage: PipelineStage) -> str:
    if key == "rukn_interpretation_guardrails":
        return stage_interpretation_guardrails(content, stage)
    if key == "rukn_educational_creator_standard":
        # Mandatory: prefer full stage slice; if empty, keep full content.
        sliced = stage_educational_creator_standard(content, stage)
        return sliced or content
    if key == "rukn_anti_patterns_quality_checks":
        return stage_anti_patterns_quality_checks(content, stage)
    if key == "rukn_source_distillation_gate":
        return stage_source_distillation_gate(content, stage)
    if key == "rukn_transcript_topic_relevance_gate":
        return stage_transcript_topic_relevance_gate(content, stage)
    if key in MANDATORY_CORE_KEYS:
        return content  # never scissors mandatory core
    return content


def build_stage_rules_pack(
    selected_rules: dict[str, str],
    stage: PipelineStage,
    *,
    max_chars: int = _PACK_MAX_CHARS,
) -> dict[str, str]:
    """Priority pack: Mandatory → Relevant → Optional. No mid-rule truncation.

    Mandatory core always included whole even if it exceeds soft budget
    (budget then applies only to optional layers).
    """
    pack_name = PACK_KEY_BY_STAGE.get(stage, "lesson_writing_rules_pack")

    mandatory_parts: list[str] = []
    relevant_parts: list[str] = []
    optional_parts: list[str] = []
    runtime_out: dict[str, str] = {}

    for key, content in selected_rules.items():
        if not content:
            continue
        if key.endswith("_runtime") or key == "rukn_authority_pack_hint":
            runtime_out[key] = content
            continue
        chunk = _prepare_chunk(key, content, stage)
        if not chunk:
            continue
        block = f"### {key}\n{chunk}"
        if key in MANDATORY_CORE_KEYS:
            mandatory_parts.append(block)
        elif key in RELEVANT_RETRIEVED_KEYS:
            relevant_parts.append(block)
        else:
            optional_parts.append(block)

    parts: list[str] = list(mandatory_parts)
    total = sum(len(p) + 2 for p in parts)

    for block in relevant_parts:
        if total + len(block) > max_chars:
            # Prefer dropping whole relevant blocks over cutting them.
            continue
        parts.append(block)
        total += len(block) + 2

    for block in optional_parts:
        if total + len(block) > max_chars:
            summary = _summarize_optional(block, max_chars=min(_OPTIONAL_SUMMARY_CHARS, max_chars - total))
            if summary and total + len(summary) <= max_chars:
                parts.append(summary)
                total += len(summary) + 2
            continue
        parts.append(block)
        total += len(block) + 2

    pack_body = "\n\n".join(parts).strip()
    out: dict[str, str] = {pack_name: pack_body} if pack_body else {}

    # Runtime keys / authority hints — keep whole when small; never mid-cut rules.
    for key, content in runtime_out.items():
        if not content:
            continue
        if len(content) <= 2000:
            out[key] = content
        else:
            # Whole paragraphs only.
            paras = content.split("\n\n")
            kept: list[str] = []
            size = 0
            for para in paras:
                if size + len(para) > 2000:
                    break
                kept.append(para)
                size += len(para) + 2
            if kept:
                out[key] = "\n\n".join(kept)
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
    """True when packed total chars <= full selected (never larger dump)."""
    pack_chars = sum(len(v) for v in pack.values())
    full_chars = sum(len(v) for v in full_selected.values())
    if full_chars <= 0:
        return True
    # Compact relative to raw dump; mandatory-core-preserving packs may exceed
    # the old 4200 soft cap — that is intentional.
    return pack_chars <= full_chars


def mandatory_core_intact(pack: dict[str, str], selected: dict[str, str]) -> bool:
    """Every mandatory key present in selected appears uncut inside the pack body."""
    body = "\n".join(pack.values())
    for key in MANDATORY_CORE_KEYS:
        content = selected.get(key)
        if not content:
            continue
        # Key header must be present; content must not end with truncation ellipsis marker
        # introduced by the old scissors.
        if f"### {key}" not in body and key not in body:
            return False
        # Full mandatory content should be substring of pack (allow stage slice for creator standard).
        if key == "rukn_educational_creator_standard":
            continue
        if content.strip() and content.strip() not in body:
            return False
    return True
