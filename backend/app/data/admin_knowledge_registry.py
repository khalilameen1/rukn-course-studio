"""Canonical Admin Knowledge key registry.

Single source of truth for which keys are required, refreshable, stage-selected,
and prompt-cache-stable. Seed content stays in `admin_knowledge_seed.py`;
stage packing stays in `knowledge_packs.py`. This module owns *identity* only.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.prompts.prompt_registry import PipelineStage


@dataclass(frozen=True)
class KeyInfo:
    """Human-facing metadata for Admin UI / ops docs."""

    title: str
    description: str
    required: bool = True
    refreshable: bool = False
    """If True, CLI/API refresh-defaults may replace the active row from seed."""


# --- Catalog (titles/descriptions for every system key we ship) ------------

KEY_CATALOG: dict[str, KeyInfo] = {
    "rukn_core_rules": KeyInfo(
        title="Core Voice & Delivery Rules",
        description="Non-negotiable tone and delivery rules for every generated script.",
        refreshable=False,
    ),
    "rukn_practical_course_rules": KeyInfo(
        title="Practical Course Structure Rules",
        description="Connected modules, bridge projects, and real-world examples.",
        refreshable=False,
    ),
    "rukn_writing_style": KeyInfo(
        title="Writing Style Rules",
        description="Short, natural sentences — no filler, no clichés.",
        refreshable=False,
    ),
    "rukn_forbidden_phrases": KeyInfo(
        title="Forbidden Phrases",
        description="Phrases that must never appear in a generated script.",
        refreshable=True,
    ),
    "rukn_quality_rubric": KeyInfo(
        title="Quality Rubric",
        description="Checks applied when reviewing a course during generation.",
        refreshable=True,
    ),
    "rukn_teleprompter_docx_contract": KeyInfo(
        title="Teleprompter DOCX Contract",
        description="Defines what the final DOCX is — and is not.",
        refreshable=True,
    ),
    "rukn_high_signal_reel_doctrine": KeyInfo(
        title="High-Signal Reel Doctrine",
        description="Hooks, organic loops, variable length, Draft/Critic/Master — viral without bait.",
        refreshable=True,
    ),
    "rukn_dynamic_teaching_curve": KeyInfo(
        title="Dynamic Teaching Curve",
        description="Anti-flatness / pacing curve for lessons.",
        refreshable=True,
    ),
    "rukn_creator_persona_engine": KeyInfo(
        title="Creator Persona Engine",
        description="Stable lecturer persona across reels.",
        refreshable=True,
    ),
    "rukn_creator_critic_loop": KeyInfo(
        title="Creator–Critic Loop",
        description="Multi-agent draft/review contract (internal only).",
        refreshable=True,
    ),
    "rukn_student_confusion_layer": KeyInfo(
        title="Student Confusion Layer",
        description="Anticipates learner confusion before Final Master.",
        refreshable=True,
    ),
    "rukn_master_mentor_engine": KeyInfo(
        title="Master Mentor Engine",
        description="Mentor-level review guidance (internal only).",
        refreshable=True,
    ),
    "rukn_market_evergreen_gates": KeyInfo(
        title="Market & Evergreen Gates",
        description="Market freshness and evergreen checks.",
        refreshable=True,
    ),
    "rukn_official_tool_docs_gate": KeyInfo(
        title="Official Tool Docs Gate",
        description="Prefer official current tool documentation.",
        refreshable=True,
    ),
    "rukn_originality_rights_gate": KeyInfo(
        title="Originality & Rights Gate",
        description="Avoid rights-risky copying from sources.",
        refreshable=True,
    ),
    "rukn_cost_hygiene_trusted_knowledge": KeyInfo(
        title="Cost Hygiene & Trusted Knowledge",
        description="Token budget and trusted-knowledge reuse rules.",
        refreshable=True,
    ),
    "rukn_knowledge_priority_ladder": KeyInfo(
        title="Knowledge Priority Ladder",
        description="Authority order: promise → official → sources → inference.",
        refreshable=True,
    ),
    "rukn_grounded_claims_gate": KeyInfo(
        title="Grounded Claims Gate",
        description="Claims must be grounded in allowed evidence.",
        refreshable=True,
    ),
    "rukn_source_authority_firewall": KeyInfo(
        title="Source Authority Firewall",
        description="Per-category allowed/disallowed source uses.",
        refreshable=True,
    ),
    "rukn_interpretation_guardrails": KeyInfo(
        title="Interpretation Guardrails",
        description="Limits on stretching source meaning.",
        refreshable=True,
    ),
    "rukn_educational_creator_standard": KeyInfo(
        title="Educational Creator Standard",
        description="Teaching quality bar for Final Master scripts.",
        refreshable=True,
    ),
    "rukn_anti_patterns_quality_checks": KeyInfo(
        title="Anti-Patterns Quality Checks",
        description="Local checks for known script anti-patterns.",
        refreshable=True,
    ),
    "rukn_source_distillation_gate": KeyInfo(
        title="Source Distillation Gate",
        description="Distill sources before generation; avoid full dumps.",
        refreshable=True,
    ),
    "rukn_transcript_topic_relevance_gate": KeyInfo(
        title="Transcript Topic Relevance Gate",
        description="Keep transcripts on-topic for the course promise.",
        refreshable=True,
    ),
    "rukn_source_imperfection_gate": KeyInfo(
        title="Source Imperfection Gate",
        description="Tolerate imperfect sources without inventing polish.",
        refreshable=True,
    ),
    "rukn_generation_presets": KeyInfo(
        title="Generation Presets",
        description="Named presets for ops visibility (not injected into stage packs).",
        refreshable=False,
    ),
}

# Seeded but retired / optional — not required for generation.
OPTIONAL_SEED_KEYS: frozenset[str] = frozenset({"rukn-spoken-style-bank"})

# Required for a healthy install (must appear in seed + DB after seed()).
REQUIRED_KEYS: frozenset[str] = frozenset(
    key for key, info in KEY_CATALOG.items() if info.required
)

# Safe to replace from code via refresh-defaults (never core voice / presets).
REFRESHABLE_DEFAULT_KEYS: tuple[str, ...] = tuple(
    sorted(key for key, info in KEY_CATALOG.items() if info.refreshable)
)

# Intentionally excluded from every stage pack (still required in DB).
EXCLUDED_FROM_STAGE_PACKS: frozenset[str] = frozenset({"rukn_generation_presets"})

# Per-stage Admin Knowledge keys (DB-backed only — no runtime-injected keys).
STAGE_RULE_KEYS: dict[PipelineStage, tuple[str, ...]] = {
    PipelineStage.BUILD_COURSE_MAP: (
        "rukn_core_rules",
        "rukn_practical_course_rules",
        "rukn_high_signal_reel_doctrine",
        "rukn_dynamic_teaching_curve",
        "rukn_creator_persona_engine",
        "rukn_creator_critic_loop",
        "rukn_student_confusion_layer",
        "rukn_master_mentor_engine",
        "rukn_market_evergreen_gates",
        "rukn_official_tool_docs_gate",
        "rukn_originality_rights_gate",
        "rukn_cost_hygiene_trusted_knowledge",
        "rukn_knowledge_priority_ladder",
        "rukn_source_authority_firewall",
        "rukn_interpretation_guardrails",
        "rukn_educational_creator_standard",
        "rukn_source_distillation_gate",
        "rukn_transcript_topic_relevance_gate",
        "rukn_source_imperfection_gate",
    ),
    PipelineStage.WRITE_SINGLE_REEL: (
        "rukn_core_rules",
        "rukn_practical_course_rules",
        "rukn_writing_style",
        "rukn_high_signal_reel_doctrine",
        "rukn_dynamic_teaching_curve",
        "rukn_creator_persona_engine",
        "rukn_creator_critic_loop",
        "rukn_student_confusion_layer",
        "rukn_master_mentor_engine",
        "rukn_teleprompter_docx_contract",
        "rukn_market_evergreen_gates",
        "rukn_official_tool_docs_gate",
        "rukn_originality_rights_gate",
        "rukn_cost_hygiene_trusted_knowledge",
        "rukn_knowledge_priority_ladder",
        "rukn_source_authority_firewall",
        "rukn_grounded_claims_gate",
        "rukn_interpretation_guardrails",
        "rukn_educational_creator_standard",
        "rukn_source_distillation_gate",
        "rukn_transcript_topic_relevance_gate",
        "rukn_source_imperfection_gate",
    ),
    PipelineStage.REVIEW_SINGLE_REEL: (
        "rukn_writing_style",
        "rukn_high_signal_reel_doctrine",
        "rukn_dynamic_teaching_curve",
        "rukn_creator_persona_engine",
        "rukn_creator_critic_loop",
        "rukn_student_confusion_layer",
        "rukn_master_mentor_engine",
        "rukn_forbidden_phrases",
        "rukn_quality_rubric",
        "rukn_market_evergreen_gates",
        "rukn_official_tool_docs_gate",
        "rukn_originality_rights_gate",
        "rukn_cost_hygiene_trusted_knowledge",
        "rukn_knowledge_priority_ladder",
        "rukn_source_authority_firewall",
        "rukn_interpretation_guardrails",
        "rukn_educational_creator_standard",
        "rukn_anti_patterns_quality_checks",
        "rukn_source_distillation_gate",
        "rukn_transcript_topic_relevance_gate",
        "rukn_source_imperfection_gate",
    ),
    PipelineStage.REVIEW_FIVE_REELS: (
        "rukn_writing_style",
        "rukn_high_signal_reel_doctrine",
        "rukn_dynamic_teaching_curve",
        "rukn_creator_persona_engine",
        "rukn_creator_critic_loop",
        "rukn_student_confusion_layer",
        "rukn_master_mentor_engine",
        "rukn_forbidden_phrases",
        "rukn_quality_rubric",
        "rukn_market_evergreen_gates",
        "rukn_official_tool_docs_gate",
        "rukn_originality_rights_gate",
        "rukn_knowledge_priority_ladder",
        "rukn_source_authority_firewall",
        "rukn_interpretation_guardrails",
        "rukn_educational_creator_standard",
        "rukn_anti_patterns_quality_checks",
        "rukn_source_distillation_gate",
        "rukn_transcript_topic_relevance_gate",
        "rukn_source_imperfection_gate",
    ),
    PipelineStage.REVIEW_MODULE: (
        "rukn_writing_style",
        "rukn_high_signal_reel_doctrine",
        "rukn_dynamic_teaching_curve",
        "rukn_creator_persona_engine",
        "rukn_creator_critic_loop",
        "rukn_student_confusion_layer",
        "rukn_master_mentor_engine",
        "rukn_forbidden_phrases",
        "rukn_quality_rubric",
        "rukn_market_evergreen_gates",
        "rukn_official_tool_docs_gate",
        "rukn_originality_rights_gate",
        "rukn_knowledge_priority_ladder",
        "rukn_source_authority_firewall",
        "rukn_interpretation_guardrails",
        "rukn_educational_creator_standard",
        "rukn_anti_patterns_quality_checks",
        "rukn_source_distillation_gate",
        "rukn_transcript_topic_relevance_gate",
        "rukn_source_imperfection_gate",
    ),
    PipelineStage.REVIEW_TWO_MODULES: (
        "rukn_writing_style",
        "rukn_high_signal_reel_doctrine",
        "rukn_dynamic_teaching_curve",
        "rukn_creator_persona_engine",
        "rukn_creator_critic_loop",
        "rukn_student_confusion_layer",
        "rukn_master_mentor_engine",
        "rukn_forbidden_phrases",
        "rukn_quality_rubric",
        "rukn_market_evergreen_gates",
        "rukn_official_tool_docs_gate",
        "rukn_originality_rights_gate",
        "rukn_knowledge_priority_ladder",
        "rukn_source_authority_firewall",
        "rukn_interpretation_guardrails",
        "rukn_educational_creator_standard",
        "rukn_anti_patterns_quality_checks",
        "rukn_source_distillation_gate",
        "rukn_transcript_topic_relevance_gate",
        "rukn_source_imperfection_gate",
    ),
    PipelineStage.FINAL_REVIEW: (
        "rukn_forbidden_phrases",
        "rukn_quality_rubric",
        "rukn_high_signal_reel_doctrine",
        "rukn_dynamic_teaching_curve",
        "rukn_creator_persona_engine",
        "rukn_creator_critic_loop",
        "rukn_student_confusion_layer",
        "rukn_master_mentor_engine",
        "rukn_teleprompter_docx_contract",
        "rukn_market_evergreen_gates",
        "rukn_official_tool_docs_gate",
        "rukn_originality_rights_gate",
        "rukn_knowledge_priority_ladder",
        "rukn_source_authority_firewall",
        "rukn_grounded_claims_gate",
        "rukn_interpretation_guardrails",
        "rukn_educational_creator_standard",
        "rukn_anti_patterns_quality_checks",
        "rukn_source_distillation_gate",
        "rukn_transcript_topic_relevance_gate",
        "rukn_source_imperfection_gate",
    ),
    PipelineStage.REBUILD_FINAL_COURSE: (
        "rukn_writing_style",
        "rukn_high_signal_reel_doctrine",
        "rukn_dynamic_teaching_curve",
        "rukn_creator_persona_engine",
        "rukn_creator_critic_loop",
        "rukn_student_confusion_layer",
        "rukn_master_mentor_engine",
        "rukn_forbidden_phrases",
        "rukn_teleprompter_docx_contract",
        "rukn_market_evergreen_gates",
        "rukn_official_tool_docs_gate",
        "rukn_originality_rights_gate",
        "rukn_knowledge_priority_ladder",
        "rukn_source_authority_firewall",
        "rukn_grounded_claims_gate",
        "rukn_interpretation_guardrails",
        "rukn_educational_creator_standard",
        "rukn_anti_patterns_quality_checks",
        "rukn_source_distillation_gate",
        "rukn_transcript_topic_relevance_gate",
        "rukn_source_imperfection_gate",
    ),
}


def _union_stage_keys() -> frozenset[str]:
    keys: set[str] = set()
    for stage_keys in STAGE_RULE_KEYS.values():
        keys.update(stage_keys)
    return frozenset(keys)


# Prompt-cache stable set = every DB key that can appear in a stage pack.
# (Must include rukn_cost_hygiene_trusted_knowledge — previously drifted.)
STABLE_RULE_KEYS: tuple[str, ...] = tuple(sorted(_union_stage_keys()))

ALL_SYSTEM_KEYS: frozenset[str] = frozenset(KEY_CATALOG) | OPTIONAL_SEED_KEYS


def key_info_public() -> list[dict[str, object]]:
    """JSON-friendly catalog for Admin UI / diagnostics."""
    rows: list[dict[str, object]] = []
    for key, info in sorted(KEY_CATALOG.items()):
        rows.append(
            {
                "key": key,
                "title": info.title,
                "description": info.description,
                "required": info.required,
                "refreshable": info.refreshable,
                "in_stage_packs": key not in EXCLUDED_FROM_STAGE_PACKS
                and key in _union_stage_keys(),
                "stable": key in STABLE_RULE_KEYS,
            }
        )
    return rows
