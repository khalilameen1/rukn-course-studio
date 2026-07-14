"""Two small, pure helpers that keep every AI-provider prompt lean:

- `select_rules_for_stage`: only the admin-knowledge keys relevant to a
  given pipeline stage, instead of dumping every active rule into every
  prompt regardless of relevance.
- `compile_source_context`: turns raw source material into a bounded list
  of `SourceExcerpt`s, with category-aware handling (factual extraction vs.
  a style/flow heuristic profile vs. verbatim user notes) and a simple
  total-character budget so a handful of huge/low-priority sources can
  never blow up prompt size.

Both functions are pure (no DB session, no I/O, no orchestrator import) so
they're trivially unit-testable. `app/generation/orchestrator.py` imports
this module - this module never imports the orchestrator.

`flow_reference` handling is a deliberately plain heuristic (regex/stdlib
string analysis only, no ML/NLP libraries) that describes a source's
*rhythm and delivery pattern* instead of summarizing its content - good
enough for the fake-provider era. A real AI provider could eventually
replace `_build_flow_profile_text` with genuine stylistic analysis without
changing this module's public interface.

## Source Authority Firewall

Uploaded/pasted sources must never define Rukn's language, format,
lesson/reel structure, or style - that authority comes only from Admin
Knowledge (`rukn_writing_style`, `rukn_practical_course_rules`,
`rukn_teleprompter_docx_contract`, `rukn_quality_rubric`,
`rukn_high_signal_reel_doctrine`, all loaded via
`select_rules_for_stage` above - always present, independent of any
source) and explicit user instructions (`user_notes`, always passed
through in full below). `compile_source_context` enforces this two ways:

1. Every `SourceExcerpt` it returns carries `allowed_use`/`disallowed_use`/
   `style_contamination_warning` (see `ALLOWED_USE_BY_CATEGORY` /
   `DISALLOWED_USE_BY_CATEGORY` / `STYLE_CONTAMINATION_WARNING_BY_CATEGORY`
   below) - a narrow, explicit, per-category label of what a source may and
   may never be used for, sent alongside its content so a provider is
   always told "knowledge, not tone" / "flow mechanics, not a template".
2. The returned list is ordered by a fixed authority hierarchy
   (`user_notes` > `scientific_reference` > `flow_reference` > `old_course`
   > `raw_material`), independent of the existing high/medium/low
   `priority` field (which remains a secondary signal used only for budget
   trimming, see `_trim_order`/`_apply_budget`).

`flow_reference` in particular is never allowed to become a format/content
template: it is reduced to a bounded, qualitative "flow profile"
(`build_flow_profile`) describing *how* a source is delivered - never its
actual wording, and never a summary of what it says.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.ai.provider import SourceExcerpt
from app.models.enums import SourceCategory
from app.prompts.prompt_registry import PipelineStage
from app.services.source_analysis import SHORT_SOURCE_MAX_CHARS, select_relevant_chunks

DEFAULT_MAX_TOTAL_CHARS = 6000

# Bump manually whenever `select_rules_for_stage`'s per-stage key mapping or
# `compile_source_context`'s selection/trimming/ordering logic changes
# meaningfully. Stored in every run's snapshot (see
# app/generation/run_snapshot.py, `GenerationJob.run_snapshot_json`) purely
# for traceability - so an old run's snapshot can be compared against
# whatever version is active today. Not read by anything at runtime other
# than the snapshot builder.
PROMPT_COMPILER_VERSION = "2.5"

# Stage -> the admin-knowledge keys actually relevant to it. Missing/
# inactive keys are simply omitted (never an error) - see
# app/generation/orchestrator.py `_load_active_rules`.
# `rukn_generation_presets` is deliberately never included anywhere here:
# it's for admin visibility / programmatic preset resolution, not prompt
# text (see app/generation/presets.py).
_STAGE_RULE_KEYS: dict[PipelineStage, tuple[str, ...]] = {
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
        "rukn_originality_rights_gate",
        "rukn_cost_hygiene_trusted_knowledge",
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
        "rukn_originality_rights_gate",
        "rukn_cost_hygiene_trusted_knowledge",
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
        "rukn_originality_rights_gate",
        "rukn_cost_hygiene_trusted_knowledge",
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
        "rukn_originality_rights_gate",
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
        "rukn_originality_rights_gate",
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
        "rukn_originality_rights_gate",
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
        "rukn_originality_rights_gate",
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
        "rukn_originality_rights_gate",
    ),
}


def select_rules_for_stage(all_rules: dict[str, str], stage: PipelineStage) -> dict[str, str]:
    """Only the keys in `all_rules` relevant to `stage` - a missing key is
    just omitted, never an error (an admin may not have activated it)."""
    keys = _STAGE_RULE_KEYS.get(stage, ())
    return {key: all_rules[key] for key in keys if key in all_rules}


def select_packed_rules_for_stage(
    all_rules: dict[str, str], stage: PipelineStage
) -> dict[str, str]:
    """Stage keys compacted into one Cost Hygiene pack — no full Admin dump."""
    from app.generation.knowledge_packs import build_stage_rules_pack

    return build_stage_rules_pack(select_rules_for_stage(all_rules, stage), stage)


# --- Prompt caching preparation (§8) ------------------------------------
#
# The fixed Rukn admin-knowledge keys below never change per-course - they
# are exactly what a real "stable" cache-control block would cover if/when
# Anthropic prompt caching is wired in (see app/ai/anthropic_provider.py
# and README.md "Prompt caching" for the honest current status: prepared,
# not wired - the existing `_build_prompt` serializes one big JSON blob per
# call today, mixing stable rules and dynamic per-course content in the
# same block, so there is no separate stable message block to attach
# `cache_control` to yet without a larger restructuring).
STABLE_RULE_KEYS: tuple[str, ...] = (
    "rukn_core_rules",
    "rukn_practical_course_rules",
    "rukn_writing_style",
    "rukn_forbidden_phrases",
    "rukn_quality_rubric",
    "rukn_teleprompter_docx_contract",
    "rukn_high_signal_reel_doctrine",
    "rukn_dynamic_teaching_curve",
    "rukn_creator_persona_engine",
    "rukn_creator_critic_loop",
    "rukn_student_confusion_layer",
    "rukn_master_mentor_engine",
    "rukn_market_evergreen_gates",
    "rukn_originality_rights_gate",
)


def split_stable_and_dynamic_rules(
    rules: dict[str, str],
) -> tuple[dict[str, str], dict[str, str]]:
    """Split `rules` (typically an already-per-stage-narrowed
    `rules_context`, see `select_rules_for_stage`) into `(stable, dynamic)`.

    "Stable" = the fixed `STABLE_RULE_KEYS` above, identical for every
    course/run. "Dynamic" = everything else present in `rules` (in
    practice, nothing today - every currently-seeded admin-knowledge key is
    one of the stable ones; see app/seed_admin_knowledge.py). Additive
    only: does not change `select_rules_for_stage`'s existing return shape
    or any of its callers.

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
        "analyze_speech_mechanics",
        "identify_idea_progression",
        "identify_pacing",
        "identify_escalation_and_tension",
        "identify_example_integration",
        "identify_natural_speech_patterns",
    ],
    SourceCategory.OLD_COURSE.value: [
        "reuse_useful_structure_or_content",
        "identify_strengths_and_weaknesses",
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
    ],
    SourceCategory.FLOW_REFERENCE.value: [
        "summarize_as_factual_content",
        "use_as_course_knowledge",
        "copy_wording",
        "copy_catchphrases_or_signature_lines",
        "copy_exact_hook_structure",
        "copy_verbal_style_or_creator_identity",
        "copy_distinctive_examples",
        "treat_as_rukn_format",
        "treat_as_reel_template",
        "force_same_section_order",
    ],
    SourceCategory.OLD_COURSE.value: [
        "blindly_summarize",
        "reuse_weak_parts",
        "treat_as_final_authority",
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
        "Style/flow reference only - never a format or knowledge source. Use for "
        "pacing, progression, tension, transitions, and human rhythm only. Do not "
        "copy wording, catchphrases, distinctive examples, verbal style, or creator "
        "identity, and it never overrides Rukn's own lesson/reel structure."
    ),
    SourceCategory.OLD_COURSE.value: (
        "Previous course/attempt - may be outdated; reuse selectively, verify before reuse."
    ),
    SourceCategory.RAW_MATERIAL.value: (
        "Mixed/unclear material - treat as uncertain, verify before reuse."
    ),
    SourceCategory.USER_NOTES.value: None,
}

# Authority-hierarchy ordering for `compile_source_context`'s output -
# independent of the `priority` field. Reflects: user instructions > Rukn
# Admin Knowledge (handled separately, always present - see
# `select_rules_for_stage`) > course brief (handled elsewhere in the
# orchestrator) > scientific facts > flow mechanics > old course structure.
_CATEGORY_AUTHORITY_RANK: dict[str, int] = {
    SourceCategory.USER_NOTES.value: 0,
    SourceCategory.SCIENTIFIC_REFERENCE.value: 1,
    SourceCategory.TRANSCRIPT.value: 2,
    SourceCategory.FLOW_REFERENCE.value: 3,
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
        original = int(source.memory.get("original_chars") or 0)
        text = source.text or ""
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


# --- flow_reference heuristic profile ---------------------------------
#
# Plain stdlib string/regex analysis only - no ML/NLP libraries - matching
# the rest of app/services/source_analysis.py. This describes *how* a
# source is delivered (pacing, opening/ending pattern, transitions,
# escalation, naturalness) without ever quoting it verbatim, per the "do
# not copy catchphrases/signature lines" requirement for style references.

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?\u061F])\s+")
_CONNECTOR_WORDS = ("لكن", "بس", "طيب", "لما", "but", "however", "so", "and")
_INSTRUCTION_MARKERS = (
    "خد",
    "جرب",
    "ابدأ",
    "افعل",
    "قم ب",
    "let's",
    "try",
    "start",
    "do this",
    "go ahead",
)
_SHORT_SENTENCE_WORD_THRESHOLD = 9
_CONNECTOR_DENSITY_THRESHOLD = 0.15


def _split_sentences(text: str) -> list[str]:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return []
    return [part.strip() for part in _SENTENCE_SPLIT_RE.split(cleaned) if part.strip()]


def _avg_words_per_sentence(sentences: list[str]) -> float:
    if not sentences:
        return 0.0
    return sum(len(sentence.split()) for sentence in sentences) / len(sentences)


def _pacing_description(avg_words: float) -> str:
    if avg_words <= _SHORT_SENTENCE_WORD_THRESHOLD:
        return "short, punchy sentences"
    return "longer, flowing sentences"


def _classify_sentence_pattern(sentence: str, position: str) -> str:
    """`position` is "opening" or "ending" - only changes the phrasing,
    not the underlying (question / instruction / statement) heuristic."""
    is_question = bool(sentence) and ("؟" in sentence or "?" in sentence)
    is_instruction = bool(sentence) and any(marker in sentence for marker in _INSTRUCTION_MARKERS)

    if position == "opening":
        if is_question:
            return "opens with a question"
        if is_instruction:
            return "opens with an instruction/call to action"
        return "opens with a direct statement, no greeting"

    if is_question:
        return "ends on a question"
    if is_instruction:
        return "ends on an instruction/call to action"
    return "ends on a direct statement, no sign-off"


def _connector_count(text: str) -> int:
    lowered = (text or "").lower()
    return sum(lowered.count(word) for word in _CONNECTOR_WORDS)


def _transition_style(text: str, sentence_count: int) -> str:
    density = _connector_count(text) / max(sentence_count, 1)
    if density >= _CONNECTOR_DENSITY_THRESHOLD:
        return "frequent conversational transitions between ideas"
    return "minimal transitions - ideas move directly from one to the next"


def _naturalness_note(text: str, sentence_count: int) -> str:
    density = _connector_count(text) / max(sentence_count, 1)
    if density >= _CONNECTOR_DENSITY_THRESHOLD:
        return "sounds conversational and natural, with frequent casual connector words"
    return "more formal/structured phrasing, with fewer casual connector words"


def _escalation_pattern(sentences: list[str]) -> str:
    if len(sentences) < 3:
        return "steady pacing throughout"

    third = max(1, len(sentences) // 3)
    first_avg = _avg_words_per_sentence(sentences[:third])
    last_avg = _avg_words_per_sentence(sentences[-third:])
    if last_avg < first_avg * 0.75:
        return "builds up then lands on short, punchy closing lines"
    return "steady pacing throughout"


def _opening_energy(first_sentence: str) -> str:
    words = len(first_sentence.split())
    if words <= _SHORT_SENTENCE_WORD_THRESHOLD:
        return "high energy - short, punchy opening line"
    return "calmer, more measured opening line"


def _idea_progression(avg_words: float, sentence_count: int) -> str:
    if avg_words <= _SHORT_SENTENCE_WORD_THRESHOLD:
        return f"moves through many short ideas in quick succession ({sentence_count} short beats)"
    return f"develops fewer ideas at greater length before moving on ({sentence_count} longer beats)"


def _split_thirds(sentences: list[str]) -> tuple[list[str], list[str], list[str]]:
    third = max(1, len(sentences) // 3)
    first = sentences[:third]
    last = sentences[-third:]
    middle = sentences[third : len(sentences) - third]
    return first, middle or first, last


def _tension_curve(sentences: list[str]) -> str:
    if len(sentences) < 6:
        return "too short for a clear tension arc - stays level throughout"

    first, middle, last = _split_thirds(sentences)
    first_avg = _avg_words_per_sentence(first)
    mid_avg = _avg_words_per_sentence(middle)
    last_avg = _avg_words_per_sentence(last)
    if mid_avg >= first_avg and last_avg < mid_avg * 0.8:
        return "rises through the middle then sharply releases near the end"
    if last_avg < first_avg * 0.75:
        return "gradually tightens toward a punchier ending"
    return "stays relatively level, no sharp rise-and-release"


def _climax_or_turning_point(sentences: list[str]) -> str:
    """Position-based only (never the sentence's actual wording): flags
    *where* the shortest, punchiest interior line sits, not what it says."""
    if len(sentences) < 4:
        return "no distinct single climax - too short for a turning point"

    interior = sentences[1:-1]
    shortest_idx = min(range(len(interior)), key=lambda i: len(interior[i].split()))
    relative_pos = (shortest_idx + 1) / len(sentences)
    if relative_pos < 0.4:
        return "a short, punchy turning-point line appears early, before the main build-up"
    if relative_pos > 0.7:
        return "a short, punchy turning-point line appears late, near the ending"
    return "a short, punchy turning-point line appears roughly in the middle"


def _example_integration(sentences: list[str]) -> str:
    count = sum(1 for s in sentences if any(marker in s for marker in _INSTRUCTION_MARKERS))
    density = count / max(len(sentences), 1)
    if density == 0:
        return "stays conceptual throughout - no concrete instruction/example markers detected"
    if density >= 0.3:
        return "frequent concrete examples/instructions woven throughout"
    return "occasional concrete examples/instructions, not the main structure"


# Generic, category-level reminders only - deliberately never populated
# from the source's actual text, so this list itself can never leak a
# catchphrase/signature line/exact wording back out.
_THINGS_NOT_TO_COPY: tuple[str, ...] = (
    "this source's exact opening line wording",
    "any repeated catchphrases or signature lines",
    "this source's overall section order",
    "verbal style or creator identity",
    "distinctive examples or signature teaching moves",
    "any phrasing that would imitate the source author",
)

_FLOW_PROFILE_FIELD_ORDER: tuple[str, ...] = (
    "opening_energy",
    "hook_mechanism",
    "pacing",
    "transition_style",
    "idea_progression",
    "escalation_pattern",
    "tension_curve",
    "climax_or_turning_point",
    "example_integration",
    "ending_motion",
    "natural_speech_notes",
)


def build_flow_profile(text: str) -> dict[str, object]:
    """The full 12-field heuristic "flow profile" for one `flow_reference`
    source: describes HOW it's delivered (energy/hook/pacing/transitions/
    idea progression/escalation/tension/climax/examples/ending/
    naturalness), never WHAT it says. Every value is a qualitative
    description built purely from sentence-length stats and regex-detected
    connector/instruction/question markers (stdlib `re` only, no ML/NLP) -
    never a literal phrase lifted from `text`, so it can never itself leak
    a catchphrase or become a content/format template.

    Bounded output size regardless of input length/structure: values are
    fixed category labels (occasionally with a small count baked in), not
    proportional excerpts of the source.
    """
    sentences = _split_sentences(text)
    if not sentences:
        empty_note = "no analyzable text - nothing to profile"
        return {field: empty_note for field in _FLOW_PROFILE_FIELD_ORDER} | {
            "things_not_to_copy": list(_THINGS_NOT_TO_COPY)
        }

    avg_words = _avg_words_per_sentence(sentences)

    return {
        "opening_energy": _opening_energy(sentences[0]),
        "hook_mechanism": _classify_sentence_pattern(sentences[0], "opening"),
        "pacing": f"{_pacing_description(avg_words)} (avg {avg_words:.1f} words/sentence)",
        "transition_style": _transition_style(text, len(sentences)),
        "idea_progression": _idea_progression(avg_words, len(sentences)),
        "escalation_pattern": _escalation_pattern(sentences),
        "tension_curve": _tension_curve(sentences),
        "climax_or_turning_point": _climax_or_turning_point(sentences),
        "example_integration": _example_integration(sentences),
        "ending_motion": _classify_sentence_pattern(sentences[-1], "ending"),
        "natural_speech_notes": _naturalness_note(text, len(sentences)),
        "things_not_to_copy": list(_THINGS_NOT_TO_COPY),
    }


def _serialize_flow_profile(profile: dict[str, object]) -> str:
    fields_text = "; ".join(f"{field}: {profile[field]}" for field in _FLOW_PROFILE_FIELD_ORDER)
    things_not_to_copy = "; ".join(profile["things_not_to_copy"])
    return (
        "Flow/style reference (heuristic profile, not a factual excerpt or quote of "
        "the source, and never a format/structure template): "
        f"{fields_text}. Things not to copy from this source: {things_not_to_copy}."
    )


def _build_flow_profile_text(source: SourceForCompiler) -> str:
    return _serialize_flow_profile(build_flow_profile(source.text))


def _build_excerpt(source: SourceForCompiler, query_text: str) -> SourceExcerpt:
    from app.generation.source_isolation import wrap_untrusted

    if source.category == SourceCategory.FLOW_REFERENCE.value:
        # Flow profile is derived heuristics — still untrusted as style orders.
        text = wrap_untrusted(
            _build_flow_profile_text(source),
            label=f"flow_profile:{source.source_id}",
        )
    elif source.category == SourceCategory.USER_NOTES.value:
        # Notes are highest-priority data but still fenced — never override Admin.
        text = wrap_untrusted(source.text or "", label=f"user_notes:{source.source_id}")
    elif source.category == SourceCategory.RAW_MATERIAL.value:
        text = wrap_untrusted(
            _RAW_MATERIAL_MARKER + _factual_excerpt_text(source, query_text),
            label=f"raw_material:{source.source_id}",
        )
    else:
        text = wrap_untrusted(
            _factual_excerpt_text(source, query_text),
            label=f"{source.category}:{source.source_id}",
        )

    return SourceExcerpt(
        source_id=source.source_id,
        category=source.category,
        priority=source.priority,
        text=text,
        allowed_use=list(ALLOWED_USE_BY_CATEGORY.get(source.category, [])),
        disallowed_use=list(DISALLOWED_USE_BY_CATEGORY.get(source.category, [])),
        style_contamination_warning=STYLE_CONTAMINATION_WARNING_BY_CATEGORY.get(source.category),
    )


_PRIORITY_RANK = {"low": 0, "medium": 1, "high": 2}


def _trim_order(excerpts: list[SourceExcerpt]) -> list[int]:
    """Indices into `excerpts`, ordered from "trim first" to "trim last":
    lowest priority first, `user_notes` protected until everything else
    has already been trimmed to nothing."""

    def sort_key(index: int) -> tuple[int, int]:
        excerpt = excerpts[index]
        protected = 1 if excerpt.category == SourceCategory.USER_NOTES.value else 0
        return (protected, _PRIORITY_RANK.get(excerpt.priority, 1))

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
    trimmed = _apply_budget(excerpts, max_total_chars)
    return _order_by_authority(trimmed)
