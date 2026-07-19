"""Two small, pure helpers that keep every AI-provider prompt lean:

- `select_rules_for_stage`: validates and returns the complete immutable
  14-file RUKN standard for every pipeline stage.
- `compile_source_context`: turns raw source material into a bounded list
  of `SourceExcerpt`s, with category-aware handling (factual extraction vs.
  a Natural Colloquial Calibration heuristic profile vs. verbatim user notes)
  and a simple total-character budget so a handful of huge/low-priority
  sources can never blow up prompt size.

Both functions are pure (no DB session, no I/O, no orchestrator import) so
they're trivially unit-testable. `app/generation/orchestrator.py` imports
this module - this module never imports the orchestrator.

`flow_reference` (Natural Colloquial Calibration) handling is a deliberately
plain heuristic (regex/stdlib string analysis only, no ML/NLP libraries)
that estimates natural spoken Egyptian/Arabic language signals — never
hooks, viral structure, reel/map structure, teaching methodology, pacing
models, facts, or wording. Good enough for the fake-provider era.

## Source Authority Firewall

Uploaded/pasted sources must never define Rukn's language, format,
lesson/reel structure, or style - that authority comes only from the complete
RUKN Universal Skill Course Standard, loaded via `select_rules_for_stage`
and always present independent of any source, plus explicit user instructions
(`user_notes`, always passed
through in full below). `compile_source_context` enforces this two ways:

1. Every `SourceExcerpt` it returns carries `allowed_use`/`disallowed_use`/
   `style_contamination_warning` (see `ALLOWED_USE_BY_CATEGORY` /
   `DISALLOWED_USE_BY_CATEGORY` / `STYLE_CONTAMINATION_WARNING_BY_CATEGORY`
   below) - a narrow, explicit, per-category label of what a source may and
   may never be used for, sent alongside its content so a provider is
   always told "knowledge, not tone" / "colloquial calibration, not teaching".
2. The returned list is ordered by a fixed authority hierarchy
   (`user_notes` > `scientific_reference` > `flow_reference` > `old_course`
   > `raw_material`), independent of the existing high/medium/low
   `priority` field (which remains a secondary signal used only for budget
   trimming, see `_trim_order`/`_apply_budget`).

`flow_reference` is Natural Colloquial Calibration only — not a
professional speaking / flow / teaching / hook reference. It helps final
scripts avoid translated, stiff, robotic, or unnatural Arabic. It must
never weaken ROKN quality, structure, clarity, or educational discipline,
and has zero factual authority (including tool behavior).
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from app.ai.provider import SourceExcerpt
from app.data.course_standard import load_standard_files
from app.generation.knowledge_priority_ladder import (
    authority_label_for_category,
    authority_type_for_category,
)
from app.models.enums import SourceCategory
from app.prompts.prompt_registry import PipelineStage
from app.data.admin_knowledge_registry import STABLE_RULE_KEYS
from app.services.source_analysis import SHORT_SOURCE_MAX_CHARS, select_relevant_chunks

DEFAULT_MAX_TOTAL_CHARS = 6000

# Bump manually whenever `select_rules_for_stage`'s per-stage key mapping or
# `compile_source_context`'s selection/trimming/ordering logic changes
# meaningfully. Stored in every run's snapshot (see
# app/generation/run_snapshot.py, `GenerationJob.run_snapshot_json`) purely
# for traceability - so an old run's snapshot can be compared against
# whatever version is active today. Not read by anything at runtime other
# than the snapshot builder.
PROMPT_COMPILER_VERSION = "3.0-rukn-standard-v1.3"

def select_rules_for_stage(all_rules: dict[str, str], stage: PipelineStage) -> dict[str, str]:
    """Return all 14 canonical files, whole and ordered, for every stage.

    Generation fails closed if a file is absent or empty. There is no legacy
    per-stage slicing, optional activation, or runtime rule overlay.
    """
    del stage
    if not all_rules:
        all_rules = load_standard_files()
    missing = [key for key in STABLE_RULE_KEYS if not all_rules.get(key)]
    if missing:
        raise ValueError(f"Canonical RUKN standard is incomplete: {missing}")
    return {key: all_rules[key] for key in STABLE_RULE_KEYS}


def select_packed_rules_for_stage(
    all_rules: dict[str, str], stage: PipelineStage
) -> dict[str, str]:
    """Serialize the complete canonical standard once for the provider prompt."""
    from app.generation.knowledge_packs import build_stage_rules_pack

    return build_stage_rules_pack(select_rules_for_stage(all_rules, stage), stage)


# --- Prompt caching preparation (§8) ------------------------------------
#
# Stable keys for provider prompt caching. The canonical set is exactly the
# 14 immutable standard files.


def split_stable_and_dynamic_rules(
    rules: dict[str, str],
) -> tuple[dict[str, str], dict[str, str]]:
    """Split canonical standard files from any caller-supplied dynamic data.

    "Stable" = the fixed `STABLE_RULE_KEYS` above, identical for every
    course/run. "Dynamic" = everything else present in `rules` (in
    practice, nothing today because generation receives only the canonical
    standard). This helper is retained for provider prompt-cache boundaries.

    Scope note, stated plainly: course-specific content (the brief,
    compiled source excerpts, prior-reel summaries) is *not* part of
    `rules_context` at all today - each lives on its own field on a
    stage's Input model (see app/ai/provider.py) - so this split only
    concerns the admin-knowledge portion of a prompt. A real cache-control
    split would need those Input-model fields kept out of the "stable"
    message block too; this function does not attempt that.
    """
    stable = {key: value for key, value in rules.items() if key in STABLE_RULE_KEYS}
    dynamic = {key: value for key, value in rules.items() if key not in STABLE_RULE_KEYS}
    return stable, dynamic


# --- Source Authority Firewall: per-category allowed/disallowed use ----
#
# Every `SourceExcerpt` compiled below carries these alongside its `text`,
# so a provider is always told exactly what a source may and may never be
# used for - no uploaded source can ever imply "act like this" or "format
# like this" implicitly through its content alone. Keyed by
# `SourceCategory` value (plain strings, matching `SourceForCompiler.category`
# and `SourceExcerpt.category`).

ALLOWED_USE_BY_CATEGORY: dict[str, list[str]] = {
    SourceCategory.SCIENTIFIC_REFERENCE.value: [
        "extract_factual_knowledge",
        "identify_concepts",
        "select_relevant_content",
        "simplify_for_target_learner",
        "rephrase_into_rukn_style",
    ],
    SourceCategory.TRANSCRIPT.value: [
        "extract_factual_knowledge",
        "identify_concepts",
        "select_relevant_content",
        "simplify_for_target_learner",
        "rephrase_into_rukn_style",
    ],
    SourceCategory.FLOW_REFERENCE.value: [
        "calibrate_natural_spoken_egyptian_arabic",
        "detect_colloquial_connectors",
        "detect_non_translated_arabic_signals",
        "detect_spoken_sentence_length_feel",
        "detect_natural_soften_clarify_repeat",
        "flag_ai_smoothness_and_over_formal_risk",
        "list_expressions_not_to_imitate",
    ],
    SourceCategory.OLD_COURSE.value: [
        "extract_still_valid_facts_and_concepts_as_candidates",
        "verify_current_claims_before_use",
        "identify_strengths_and_weaknesses",
    ],
    SourceCategory.MIXED_QUALITY_AI_COURSE_DRAFT.value: [
        "extract_useful_candidates_only",
        "extract_topic_inventory_as_candidates",
        "extract_learner_objections_as_candidates",
        "extract_examples_to_rebuild_not_copy",
        "detect_discard_and_bad_patterns",
        "flag_claims_for_external_grounding",
        "apply_course_promise_relevance_gate",
        "discard_off_promise_modules_and_dumb_reels",
    ],
    SourceCategory.RAW_MATERIAL.value: [
        "classify_and_extract_useful_parts",
    ],
    SourceCategory.USER_NOTES.value: [
        "set_scope_audience_tone_constraints",
    ],
}

DISALLOWED_USE_BY_CATEGORY: dict[str, list[str]] = {
    SourceCategory.SCIENTIFIC_REFERENCE.value: [
        "imitate_source_tone",
        "copy_source_structure",
        "copy_source_wording",
        "copy_distinctive_examples",
        "close_paraphrase_or_translate_source",
        "use_as_course_format_template",
        "make_final_script_sound_like_source",
        "disguised_rewrite_of_one_source",
    ],
    SourceCategory.TRANSCRIPT.value: [
        "imitate_source_tone",
        "copy_source_structure",
        "copy_source_wording",
        "copy_source_filler",
        "close_paraphrase_or_translate_source",
        "use_as_course_format_template",
        "make_final_script_sound_like_source",
        "learn_hooks_from_transcript",
        "learn_reel_openings",
        "learn_endings",
        "learn_viral_tactics",
        "learn_lesson_structure",
        "learn_course_map_structure",
        "copy_catchphrases_or_signature_lines",
        "copy_exact_hook_structure",
        "copy_verbal_style_or_creator_identity",
        "use_tool_behavior_from_transcript",
        "copy_distinctive_examples",
    ],
    SourceCategory.FLOW_REFERENCE.value: [
        "summarize_as_factual_content",
        "use_as_course_knowledge",
        "support_factual_claims",
        "learn_hooks_from_transcript",
        "learn_reel_openings",
        "learn_endings",
        "learn_viral_tactics",
        "learn_lesson_structure",
        "learn_course_map_structure",
        "learn_pacing_model",
        "learn_teaching_methodology",
        "learn_professional_speaking_framework",
        "learn_ending_style",
        "copy_wording",
        "copy_catchphrases_or_signature_lines",
        "copy_exact_sentence_patterns",
        "copy_exact_hook_structure",
        "copy_verbal_style_or_creator_identity",
        "imitate_creator",
        "use_examples_as_content",
        "use_facts_claims_or_recommendations",
        "use_domain_terminology_from_transcript",
        "use_topic_knowledge",
        "use_tool_behavior_from_transcript",
        "copy_distinctive_examples",
        "treat_as_rukn_format",
        "treat_as_reel_template",
        "treat_as_hook_or_viral_reference",
        "treat_as_ideal_teaching_or_flow_reference",
        "assume_speaker_is_good_or_professional",
        "copy_messy_or_rambling_structure",
        "force_same_section_order",
    ],
    SourceCategory.OLD_COURSE.value: [
        "blindly_summarize",
        "reuse_weak_parts",
        "treat_as_final_authority",
        "copy_wording_hooks_loops_or_structure",
        "copy_hooks",
        "copy_artificial_loops",
        "copy_examples_verbatim",
        "treat_as_quality_reference",
        "treat_whole_draft_as_worthless",
        "ground_claims_from_draft_alone",
        "use_old_map_as_final_map",
        "reuse_old_course_structure_or_workflow",
        "let_old_course_impose_section_order",
    ],
    SourceCategory.MIXED_QUALITY_AI_COURSE_DRAFT.value: [
        "blindly_summarize",
        "reuse_weak_parts",
        "treat_as_final_authority",
        "treat_as_quality_reference",
        "treat_whole_draft_as_worthless",
        "copy_sentences",
        "copy_hooks",
        "copy_artificial_loops",
        "copy_generic_ai_phrasing",
        "copy_examples_verbatim",
        "copy_distinctive_metaphors",
        "preserve_bad_structure_by_default",
        "ground_claims_from_draft_alone",
        "use_old_map_as_final_map",
        "resend_full_draft_into_lesson_prompts",
        "preserve_off_promise_modules_because_they_exist",
        "let_old_draft_dictate_module_or_lesson_count",
        "inherit_old_draft_bloat_or_side_details",
    ],
    SourceCategory.RAW_MATERIAL.value: [
        "treat_as_verified_fact",
        "treat_as_style_or_format_authority",
    ],
    SourceCategory.USER_NOTES.value: [],
}

# `None` for user_notes deliberately: user instructions are trusted, not a
# contamination risk - there's nothing to warn a provider about.
STYLE_CONTAMINATION_WARNING_BY_CATEGORY: dict[str, str | None] = {
    SourceCategory.SCIENTIFIC_REFERENCE.value: (
        "Knowledge source only - academic/formal/translated tone must not leak into "
        "the spoken script; rephrase fully into Rukn style. Facts/concepts only — "
        "never copy wording, distinctive examples, hooks, or structure; free sources "
        "are still not free to copy."
    ),
    SourceCategory.FLOW_REFERENCE.value: (
        "Natural Colloquial Calibration only — not a professional speaking, flow, "
        "teaching, hook, or structure reference. "
        "This transcript is only for natural colloquial calibration. Use it only to "
        "avoid translated, stiff, robotic, or unnatural Arabic. Do not learn facts, "
        "hooks, structure, pacing, examples, endings, claims, terminology, or style "
        "imitation from it. Do not assume the speaker is good or that the transcript "
        "is worth copying. ROKN writing rules stay higher authority; official docs "
        "stay factual authority. This sample can never support an important claim."
    ),
    SourceCategory.TRANSCRIPT.value: (
        "Course transcript — extract teaching value only; rephrase into Rukn style. "
        "Do not copy filler, wording, tone, or structure."
    ),
    SourceCategory.OLD_COURSE.value: (
        "Mixed-quality previous course/attempt — may contain useful candidates, "
        "irrelevant modules, and defects. Apply Course Promise Relevance Gate; "
        "discard off-promise modules; extract candidates only; never copy "
        "wording/hooks/loops; never treat as quality reference; rebuild in ROKN."
    ),
    SourceCategory.MIXED_QUALITY_AI_COURSE_DRAFT.value: (
        "This is a mixed-quality previous AI-generated course draft. It may contain "
        "useful candidates, irrelevant modules, dumb reels, side details, and defects. "
        "Evaluate every segment against the current course promise before using it. "
        "Discard off-promise modules and irrelevant reels even if they are well-written. "
        "Extract only useful candidate ideas, then rebuild from scratch in ROKN quality."
    ),
    SourceCategory.RAW_MATERIAL.value: (
        "Mixed/unclear material - treat as uncertain, verify before reuse."
    ),
    SourceCategory.USER_NOTES.value: None,
}

# Authority-hierarchy ordering for `compile_source_context`'s output -
# independent of the `priority` field. Reflects: user instructions > Rukn
# The canonical RUKN standard (handled separately, always present - see
# `select_rules_for_stage`) > course brief (handled elsewhere in the
# orchestrator) > scientific facts > transcript candidates > language-only
# calibration > old-course candidates. Old course structure has no authority.
_CATEGORY_AUTHORITY_RANK: dict[str, int] = {
    SourceCategory.USER_NOTES.value: 0,
    SourceCategory.SCIENTIFIC_REFERENCE.value: 1,
    SourceCategory.TRANSCRIPT.value: 2,
    SourceCategory.FLOW_REFERENCE.value: 3,
    SourceCategory.MIXED_QUALITY_AI_COURSE_DRAFT.value: 4,
    SourceCategory.OLD_COURSE.value: 4,
    SourceCategory.RAW_MATERIAL.value: 5,
}


def _order_by_authority(excerpts: list[SourceExcerpt]) -> list[SourceExcerpt]:
    """Stable-sort `excerpts` into the fixed category authority order -
    any unrecognized category (shouldn't happen - `SourceCategory` is a
    closed enum) sorts last rather than raising."""
    return sorted(
        excerpts,
        key=lambda e: _CATEGORY_AUTHORITY_RANK.get(e.category, len(_CATEGORY_AUTHORITY_RANK)),
    )


@dataclass
class SourceForCompiler:
    """Plain input to `compile_source_context` - deliberately decoupled
    from the orchestrator's DB-backed `UsableSource`/`CourseSource` types.
    Callers convert their own source representation into this shape.

    `text` should already be Source Memory / snippet text — not a full PDF.
    `memory` is the persistent Source Memory payload when available.
    """

    source_id: int
    category: str
    priority: str
    text: str
    summary: str | None = None
    chunks: list[dict] | None = None
    memory: dict | None = None


_RAW_MATERIAL_MARKER = (
    "[Unclassified/mixed material - verify before treating anything below as fact.]\n\n"
)


def _factual_excerpt_text(source: SourceForCompiler, query_text: str) -> str:
    """Inject Source Memory snippets only — never re-send a full long PDF.

    Prefer persistent `memory` (facts/examples/terminology + relevant chunks).
    Fall back to summary + keyword chunks. Cap size hard.
    Short originals stay whole when `original_chars` is under the short cap.
    """
    from app.generation.source_memory_store import (
        MEMORY_SNIPPET_MAX_CHARS,
        format_memory_snippet,
    )

    if source.memory:
        from app.generation.source_usefulness import (
            LOW_SIGNAL_BRIEF_MAX_CHARS,
            format_low_signal_snippet,
            should_use_brief_candidates,
        )

        if should_use_brief_candidates(source.memory):
            return format_low_signal_snippet(
                source.memory, max_chars=min(MEMORY_SNIPPET_MAX_CHARS, LOW_SIGNAL_BRIEF_MAX_CHARS)
            )

        original = int(source.memory.get("original_chars") or 0)
        text = source.text or ""
        # Low-signal / brief mode never gets full short-body passthrough.
        if original and original <= SHORT_SOURCE_MAX_CHARS and text:
            # Orchestrator already put the full short body into `text`.
            return text[:SHORT_SOURCE_MAX_CHARS]
        if not original and len(text) <= SHORT_SOURCE_MAX_CHARS and text:
            return text
        return format_memory_snippet(
            source.memory,
            query_text=query_text,
            chunks=source.chunks,
            max_chars=MEMORY_SNIPPET_MAX_CHARS,
        )

    # Caller already compacted `text` via memory formatting in most paths.
    text = source.text or ""
    if len(text) <= SHORT_SOURCE_MAX_CHARS:
        return text

    if source.chunks:
        relevant = select_relevant_chunks(source.chunks, query_text)
        if relevant:
            joined = "\n\n".join(
                (chunk.get("text") or "")[:500] for chunk in relevant
            )
            return joined[:MEMORY_SNIPPET_MAX_CHARS]

    if source.summary:
        return source.summary[:MEMORY_SNIPPET_MAX_CHARS]
    return text[:SHORT_SOURCE_MAX_CHARS]


# --- flow_reference = Natural Colloquial Calibration profile ------------
#
# Plain stdlib heuristics only. This is NOT a flow / teaching / pacing /
# professional-speaking reference. It only estimates whether spoken Arabic
# signals lean colloquial vs stiff/translated/AI-smooth — never WHAT is said,
# never structure, never hooks, and never "copy this speaker".

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?\u061F])\s+")
# Colloquial / soft spoken connectors (Egyptian + light bilingual fillers).
_CONNECTOR_WORDS = (
    "لكن",
    "بس",
    "طيب",
    "لما",
    "يعني",
    "كده",
    "عشان",
    "خلاصة",
    "كمان",
    "مش",
    "اهو",
    "but",
    "so",
    "and",
)
# Stiff / MSA-leaning markers that often signal translation or textbook tone.
_STIFF_MARKERS = (
    "بالإضافة إلى",
    "من الجدير بالذكر",
    "في الختام",
    "furthermore",
    "moreover",
    "it is worth noting",
    "in conclusion",
)
_SHORT_SENTENCE_WORD_THRESHOLD = 9
_CONNECTOR_DENSITY_THRESHOLD = 0.12

# Required fence when Natural Colloquial Calibration enters a prompt.
NATURAL_COLLOQUIAL_CALIBRATION_LABEL = (
    "This transcript is only for natural colloquial calibration. "
    "Use it only to avoid translated, stiff, robotic, or unnatural Arabic. "
    "Do not learn facts, hooks, structure, pacing, examples, endings, claims, "
    "terminology, or style imitation from it."
)
# Backward-compatible alias for older tests/imports.
HUMAN_EXPLANATION_REFERENCE_LABEL = NATURAL_COLLOQUIAL_CALIBRATION_LABEL


def _split_sentences(text: str) -> list[str]:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return []
    return [part.strip() for part in _SENTENCE_SPLIT_RE.split(cleaned) if part.strip()]


def _avg_words_per_sentence(sentences: list[str]) -> float:
    if not sentences:
        return 0.0
    return sum(len(sentence.split()) for sentence in sentences) / len(sentences)


def _connector_count(text: str) -> int:
    lowered = (text or "").lower()
    return sum(lowered.count(word) for word in _CONNECTOR_WORDS)


def _stiff_marker_count(text: str) -> int:
    lowered = (text or "").lower()
    return sum(lowered.count(m.lower()) for m in _STIFF_MARKERS)


def _spoken_sentence_length_feel(avg_words: float) -> str:
    if avg_words <= _SHORT_SENTENCE_WORD_THRESHOLD:
        return f"shorter spoken lengths (avg {avg_words:.1f} words) — feel conversational, not essay-like"
    return f"longer spoken clauses (avg {avg_words:.1f} words) — keep clarity; do not turn into textbook paragraphs"


def _colloquial_connector_presence(text: str, sentence_count: int) -> str:
    density = _connector_count(text) / max(sentence_count, 1)
    if density >= _CONNECTOR_DENSITY_THRESHOLD:
        return "colloquial connectors appear at a natural spoken rate (sample only — do not copy wording)"
    return "few soft connectors — prefer natural spoken softener words over stiff MSA transitions"


def _non_translated_arabic_signal(text: str, sentence_count: int) -> str:
    stiff = _stiff_marker_count(text)
    connectors = _connector_count(text)
    if stiff >= 2 and connectors < stiff:
        return "leans translated/stiff — calibrate final script away from textbook/MSA smoothness"
    if connectors >= max(2, sentence_count // 8):
        return "leans non-translated spoken Arabic — use as language naturalness only"
    return "mixed signals — prefer ROKN colloquial writing rules; avoid literal English→Arabic feel"


def _natural_soften_clarify_repeat(sentences: list[str]) -> str:
    if len(sentences) < 3:
        return "too short to judge soften/clarify habits — keep soft, natural clarifiers when needed"
    dense_then_short = sum(
        1
        for prev, nxt in zip(sentences, sentences[1:])
        if len(prev.split()) >= 14 and len(nxt.split()) <= _SHORT_SENTENCE_WORD_THRESHOLD
    )
    words: list[str] = []
    for s in sentences:
        words.extend(w.lower() for w in s.split() if len(w) >= 4)
    repeats = sum(1 for c in Counter(words).values() if c >= 3) if words else 0
    if dense_then_short or repeats:
        return (
            "sample shows natural soften/clarify/light restatement — allow gentle clarity "
            "in final script; never copy repeated phrases as catchphrases"
        )
    return "little soften/clarify signal — final script may still clarify lightly under ROKN rules"


def _ai_smoothness_and_formal_risk(sentences: list[str], text: str) -> str:
    stiff = _stiff_marker_count(text)
    if len(sentences) < 4:
        return "too short — still avoid over-polished AI smoothness and over-formal transitions"
    lengths = [len(s.split()) for s in sentences]
    mean = sum(lengths) / len(lengths)
    variance = sum((x - mean) ** 2 for x in lengths) / len(lengths)
    if stiff >= 2:
        return "stiff/formal transition risk high — prefer ordinary spoken links, not ceremony"
    if variance < 8:
        return "even lengths risk AI-smooth delivery — keep human unevenness without becoming messy"
    return "length variety resists robotic evenness — keep that naturalness only, not the content"


def _messy_transcript_quality_guard(sentences: list[str], text: str) -> str:
    """Messy samples must not make the final script messy."""
    if len(sentences) < 6:
        return (
            "Do not assume this speaker is good or professional. "
            "Ignore any weakness; extract only broad colloquial signals."
        )
    lengths = [len(s.split()) for s in sentences]
    mega = sum(1 for n in lengths if n >= 35)
    ultra_short = sum(1 for n in lengths if n <= 2)
    fillerish = text.count("يعني") + text.count("اهم") + text.lower().count("um ")
    if mega >= 3 or ultra_short >= max(4, len(sentences) // 4) or fillerish >= 12:
        return (
            "Sample looks messy/rambling — IGNORE its structure, repetition, and weak phrasing. "
            "Extract only broad natural colloquial signals. "
            "Never make the final script messy because this transcript was messy. "
            "ROKN clarity and educational discipline win."
        )
    return (
        "Do not assume the speaker is good or worth copying. "
        "Ignore internal architecture of the transcript. "
        "ROKN writing rules remain higher authority."
    )


# Category-level reminders — never populated from source wording.
_THINGS_NOT_TO_COPY: tuple[str, ...] = (
    "facts, claims, recommendations, topic knowledge, or tool behavior",
    "examples as content or domain terminology",
    "hooks, reel openings, endings, pacing models, or lesson/course-map structure",
    "teaching methodology or professional speaking frameworks",
    "catchphrases, signature expressions, repeated templates, or creator identity",
    "messy/rambling structure or weak phrasing from this sample",
    "any phrasing that would imitate this speaker",
)

_FLOW_PROFILE_FIELD_ORDER: tuple[str, ...] = (
    "spoken_sentence_length_feel",
    "colloquial_connector_presence",
    "non_translated_arabic_signal",
    "natural_soften_clarify_repeat",
    "ai_smoothness_and_formal_risk",
    "messy_transcript_quality_guard",
)


def build_flow_profile(text: str) -> dict[str, object]:
    """Natural Colloquial Calibration profile for one `flow_reference` source.

    Language naturalness signals only — never facts, hooks, pacing models,
    teaching methodology, structure, or speaker imitation. Messy transcripts
    must not make the final script messy.
    """
    sentences = _split_sentences(text)
    if not sentences:
        empty_note = "no analyzable text - nothing to calibrate"
        return {field: empty_note for field in _FLOW_PROFILE_FIELD_ORDER} | {
            "things_not_to_copy": list(_THINGS_NOT_TO_COPY)
        }

    avg_words = _avg_words_per_sentence(sentences)
    return {
        "spoken_sentence_length_feel": _spoken_sentence_length_feel(avg_words),
        "colloquial_connector_presence": _colloquial_connector_presence(
            text, len(sentences)
        ),
        "non_translated_arabic_signal": _non_translated_arabic_signal(
            text, len(sentences)
        ),
        "natural_soften_clarify_repeat": _natural_soften_clarify_repeat(sentences),
        "ai_smoothness_and_formal_risk": _ai_smoothness_and_formal_risk(
            sentences, text
        ),
        "messy_transcript_quality_guard": _messy_transcript_quality_guard(
            sentences, text
        ),
        "things_not_to_copy": list(_THINGS_NOT_TO_COPY),
    }


build_colloquial_calibration_profile = build_flow_profile


def _serialize_flow_profile(profile: dict[str, object]) -> str:
    fields_text = "; ".join(f"{field}: {profile[field]}" for field in _FLOW_PROFILE_FIELD_ORDER)
    things_not_to_copy = "; ".join(profile["things_not_to_copy"])
    return (
        "Natural Colloquial Calibration (language naturalness sample only — "
        "NOT a flow, teaching, pacing, hook, or professional speaking reference): "
        f"{NATURAL_COLLOQUIAL_CALIBRATION_LABEL} "
        f"{fields_text}. Things not to copy from this source: {things_not_to_copy}."
    )


def _build_flow_profile_text(source: SourceForCompiler) -> str:
    return _serialize_flow_profile(build_flow_profile(source.text))


def _build_excerpt(source: SourceForCompiler, query_text: str) -> SourceExcerpt:
    from app.generation.source_isolation import wrap_untrusted
    from app.generation.source_imperfection import (
        SOURCE_MISTRUST_EXCERPT_BANNER,
        SOURCE_MISTRUST_LABEL,
    )
    from app.generation.source_origin import (
        is_transcript_derived_memory,
        prompt_labels_for_origin,
    )
    from app.generation.transcript_relevance import (
        is_transcript_colloquial_only,
        prompt_label_for_relevance,
    )

    from app.services.json_coerce import coerce_json_dict

    # Never use `memory or {}` — a non-empty JSON string is truthy and then
    # `.get` crashes (classic AI/ORM TEXT-JSON bug).
    mem = coerce_json_dict(source.memory) or {}
    origin = str(mem.get("source_origin") or "")
    transcript_derived = is_transcript_derived_memory(mem)
    colloquial_only = is_transcript_colloquial_only(mem)
    labels = list(mem.get("source_prompt_labels") or [])
    if not labels and mem.get("source_imperfection_version"):
        labels = [SOURCE_MISTRUST_LABEL]
    mistrust_prefix = ""
    if mem.get("source_imperfection_version") or labels:
        mistrust_prefix = SOURCE_MISTRUST_EXCERPT_BANNER + "\n\n"
        # Compact origin-specific one-liners only (avoid multi-KB label dumps).
        extras: list[str] = []
        if transcript_derived and not colloquial_only:
            extras.append("[transcript-derived — clean cautiously; do not copy delivery]")
        if any("OCR" in (x or "") or "OCR/scan" in (x or "") for x in labels):
            extras.append("[OCR/scan-derived — do not trust suspicious tokens]")
        if any("academic" in (x or "").lower() or "book" in (x or "").lower() for x in labels):
            extras.append("[academic/book — distill to practical spoken; no book structure]")
        if extras:
            mistrust_prefix += " ".join(extras) + "\n\n"

    if source.category == SourceCategory.FLOW_REFERENCE.value and not transcript_derived:
        # Natural colloquial calibration — still untrusted; never structure/facts.
        text = wrap_untrusted(
            _build_flow_profile_text(source),
            label=f"colloquial_calibration:{source.source_id}",
        )
    elif source.category == SourceCategory.USER_NOTES.value:
        # Notes are highest-priority data but still fenced — never override Admin.
        text = wrap_untrusted(source.text or "", label=f"user_notes:{source.source_id}")
    elif source.category in (
        SourceCategory.MIXED_QUALITY_AI_COURSE_DRAFT.value,
        SourceCategory.OLD_COURSE.value,
    ):
        text = wrap_untrusted(
            mistrust_prefix + (source.text or ""),
            label=f"mixed_quality_ai_course_draft:{source.source_id}",
        )
    elif source.category == SourceCategory.RAW_MATERIAL.value:
        text = wrap_untrusted(
            mistrust_prefix
            + _RAW_MATERIAL_MARKER
            + _factual_excerpt_text(source, query_text),
            label=f"raw_material:{source.source_id}",
        )
    elif source.category == SourceCategory.TRANSCRIPT.value or transcript_derived:
        if colloquial_only:
            body = source.text or _build_flow_profile_text(source)
            text = wrap_untrusted(
                body,
                label=f"transcript_off_topic_colloquial:{source.source_id}",
            )
        else:
            rel = mem.get("topic_relevance") or "unclear"
            prefix_parts = [SOURCE_MISTRUST_EXCERPT_BANNER]
            prefix_parts.append("[transcript-derived — clean cautiously; do not copy delivery]")
            prefix_parts.append(
                mem.get("transcript_prompt_label") or prompt_label_for_relevance(rel)
            )
            prefix = "\n\n".join(p for p in prefix_parts if p) + "\n\n"
            label_cat = (
                source.category
                if source.category != SourceCategory.TRANSCRIPT.value
                else "transcript"
            )
            text = wrap_untrusted(
                prefix + _factual_excerpt_text(source, query_text),
                label=f"{label_cat}_course_raw:{source.source_id}",
            )
    else:
        text = wrap_untrusted(
            mistrust_prefix + _factual_excerpt_text(source, query_text),
            label=f"{source.category}:{source.source_id}",
        )

    auth_type = authority_type_for_category(source.category)
    auth_label = authority_label_for_category(source.category)
    base_warning = STYLE_CONTAMINATION_WARNING_BY_CATEGORY.get(source.category)
    combined_warning = (
        f"{auth_label} {base_warning}".strip()
        if base_warning
        else auth_label
    )

    excerpt = SourceExcerpt(
        source_id=source.source_id,
        category=source.category,
        priority=source.priority,
        text=text,
        allowed_use=list(ALLOWED_USE_BY_CATEGORY.get(source.category, [])),
        disallowed_use=list(DISALLOWED_USE_BY_CATEGORY.get(source.category, [])),
        style_contamination_warning=combined_warning,
        authority_type=auth_type.value,
    )

    if colloquial_only and transcript_derived:
        from app.generation.knowledge_priority_ladder import AuthorityType
        from app.generation.transcript_relevance import OFF_TOPIC_TRANSCRIPT_LABEL

        fr = SourceCategory.FLOW_REFERENCE.value
        excerpt.authority_type = AuthorityType.NATURAL_COLLOQUIAL.value
        excerpt.allowed_use = list(ALLOWED_USE_BY_CATEGORY.get(fr, []))
        excerpt.disallowed_use = list(DISALLOWED_USE_BY_CATEGORY.get(fr, []))
        excerpt.style_contamination_warning = OFF_TOPIC_TRANSCRIPT_LABEL
    elif transcript_derived and source.memory:
        rel = mem.get("topic_relevance") or "unclear"
        label = mem.get("transcript_prompt_label") or prompt_label_for_relevance(rel)
        origin_labels = " ".join(prompt_labels_for_origin(origin))
        excerpt.style_contamination_warning = f"{combined_warning} {origin_labels} {label}".strip()
    elif mem.get("source_imperfection_version"):
        excerpt.style_contamination_warning = (
            f"{combined_warning} {SOURCE_MISTRUST_EXCERPT_BANNER}"
        ).strip()

    return excerpt


_PRIORITY_RANK = {"low": 0, "medium": 1, "high": 2}


def _trim_order(excerpts: list[SourceExcerpt]) -> list[int]:
    """Indices into `excerpts`, ordered from "trim first" to "trim last":
    lowest priority / low-signal first, `user_notes` protected until everything
    else has already been trimmed to nothing."""

    def sort_key(index: int) -> tuple[int, int, int]:
        excerpt = excerpts[index]
        protected = 1 if excerpt.category == SourceCategory.USER_NOTES.value else 0
        # Trim low-signal / brief candidate dumps first (cost hygiene).
        low_signal = 0 if "[LOW_SIGNAL" in (excerpt.text or "") else 1
        return (protected, low_signal, _PRIORITY_RANK.get(excerpt.priority, 1))

    return sorted(range(len(excerpts)), key=sort_key)


def _apply_budget(excerpts: list[SourceExcerpt], max_total_chars: int) -> list[SourceExcerpt]:
    total = sum(len(e.text) for e in excerpts)
    if total <= max_total_chars or not excerpts:
        return excerpts

    texts = [e.text for e in excerpts]
    order = _trim_order(excerpts)

    for index in order:
        if total <= max_total_chars:
            break
        current_len = len(texts[index])
        if current_len == 0:
            continue
        excess = total - max_total_chars
        cut = min(current_len, excess)
        texts[index] = texts[index][: current_len - cut]
        total -= cut

    return [
        SourceExcerpt(
            source_id=excerpt.source_id,
            category=excerpt.category,
            priority=excerpt.priority,
            text=texts[i],
            allowed_use=excerpt.allowed_use,
            disallowed_use=excerpt.disallowed_use,
            style_contamination_warning=excerpt.style_contamination_warning,
            authority_type=excerpt.authority_type,
        )
        for i, excerpt in enumerate(excerpts)
    ]


def split_sentences_for_scoring(text: str) -> list[str]:
    """Public wrapper around this module's private `_split_sentences` -
    reused by app/generation/output_scoring.py so whole-document sentence
    splitting isn't duplicated across the two modules. No behavior change:
    just exposes the same stdlib-only heuristic already used for
    `flow_reference` profiling above."""
    return _split_sentences(text)


def connector_word_density(text: str) -> float:
    """Public wrapper around this module's connector-word heuristic
    (`_connector_count`/`_CONNECTOR_DENSITY_THRESHOLD` above), reused by
    app/generation/output_scoring.py for `spoken_style_score` instead of
    re-implementing the same regex/word-list logic."""
    sentences = _split_sentences(text)
    return _connector_count(text) / max(len(sentences), 1)


def compile_source_context(
    sources: list[SourceForCompiler],
    query_text: str,
    max_total_chars: int = DEFAULT_MAX_TOTAL_CHARS,
) -> list[SourceExcerpt]:
    """Category-aware excerpts for every source, trimmed to fit within
    `max_total_chars` total, then reordered by the fixed source-authority
    hierarchy (`_order_by_authority`) - `user_notes` first, then
    `scientific_reference`, `flow_reference`, `old_course`, `raw_material`.

    Never raises: if the budget is exceeded, the lowest-priority excerpts
    are truncated first, `user_notes` protected for as long as possible -
    degrade gracefully, don't fail.
    """
    excerpts = [_build_excerpt(source, query_text) for source in sources]
    # Drop near-duplicate claim excerpts across sources (prompt cost hygiene).
    from app.generation.claim_dedup import _norm_key

    deduped: list[SourceExcerpt] = []
    seen_keys: set[str] = set()
    for excerpt in excerpts:
        key = _norm_key(excerpt.text or "") or _norm_key(getattr(excerpt, "title", "") or "")
        if not key:
            deduped.append(excerpt)
            continue
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(excerpt)
    excerpts = deduped
    # Hard-cap low-signal excerpts before shared budget (credit hygiene).
    from app.generation.source_usefulness import LOW_SIGNAL_BRIEF_MAX_CHARS

    capped: list[SourceExcerpt] = []
    for excerpt in excerpts:
        text = excerpt.text or ""
        if "[LOW_SIGNAL" in text and len(text) > LOW_SIGNAL_BRIEF_MAX_CHARS + 200:
            text = text[: LOW_SIGNAL_BRIEF_MAX_CHARS + 200]
            excerpt = SourceExcerpt(
                source_id=excerpt.source_id,
                category=excerpt.category,
                priority=excerpt.priority,
                text=text,
                allowed_use=excerpt.allowed_use,
                disallowed_use=excerpt.disallowed_use,
                style_contamination_warning=excerpt.style_contamination_warning,
                authority_type=excerpt.authority_type,
            )
        capped.append(excerpt)
    trimmed = _apply_budget(capped, max_total_chars)
    return _order_by_authority(trimmed)
