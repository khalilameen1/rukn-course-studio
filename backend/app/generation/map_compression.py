"""Map Compression Pass — merge/reject inflated or duplicate lessons before scripts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.generation.contracts.lesson_blueprint import ensure_reel_blueprint_defaults
from app.schemas.generation import CourseMap, CourseThesis, ModulePlan, ReelPlan
from app.validators.similarity import text_similarity

_TOKEN_RE = re.compile(r"[\w\u0600-\u06FF]{3,}")


@dataclass
class CompressionReport:
    merged_pairs: list[tuple[str, str]] = field(default_factory=list)
    removed_reel_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    lesson_count_before: int = 0
    lesson_count_after: int = 0
    estimated_minutes_after: float = 0.0

    @property
    def ok(self) -> bool:
        return not self.errors


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text or "")}


def _outcome_blob(reel: ReelPlan) -> str:
    parts = [
        reel.title,
        reel.purpose,
        reel.distinct_teaching_outcome,
        reel.new_skill_or_decision,
        " ".join(reel.must_cover or []),
        " ".join(reel.already_taught_forbid_repeat or []),
    ]
    return " ".join(p for p in parts if p)


_STOP = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "student",
    "learner",
    "teach",
    "execute",
    "executes",
    "executed",
    "solo",
    "only",
    "skill",
    "lesson",
    "unique",
    "distinct",
    "outcome",
    "purpose",
    "can",
    "apply",
    "decide",
    "workshop",
    "mastery",
    "alone",
    "standalone",
    "operator",
    "core",
    "check",
    "end",
    "into",
    "neighbors",
    "without",
    "loss",
    "cannot",
    "fold",
    "perform",
    "after",
    "minutes",
    "minute",
    "reel",
    "module",
    "course",
    "as",
}


def _content_tokens(text: str) -> set[str]:
    return {t for t in _tokens(text) if t not in _STOP and len(t) >= 4}


def _semantically_similar(a: ReelPlan, b: ReelPlan) -> bool:
    """Semantic-ish duplicate check: similarity score + shared content tokens.

    Dual signal required — never merge on shared boilerplate words alone.
    Template strings like "Learner executes X end-to-end alone" must not merge
    distinct X/Y lessons just because SequenceMatcher scores the shell highly.
    """
    outcome_a = (a.distinct_teaching_outcome or a.purpose or a.title or "").strip()
    outcome_b = (b.distinct_teaching_outcome or b.purpose or b.title or "").strip()
    outcome_sim = text_similarity(outcome_a, outcome_b)
    title_sim = text_similarity(a.title or "", b.title or "")

    title_overlap = _content_tokens(a.title or "") & _content_tokens(b.title or "")
    skill_overlap = _content_tokens(a.new_skill_or_decision or "") & _content_tokens(
        b.new_skill_or_decision or ""
    )
    outcome_overlap = _content_tokens(outcome_a) & _content_tokens(outcome_b)

    # Exact field reuse (true duplicates).
    for field in ("title", "distinct_teaching_outcome", "learning_goal", "new_skill_or_decision"):
        av = str(getattr(a, field, "") or "").strip()
        bv = str(getattr(b, field, "") or "").strip()
        if av and bv and av == bv:
            return True

    # Distinctive anchor required: shared content in title, skill, or outcome.
    distinctive = title_overlap | skill_overlap | outcome_overlap
    if not distinctive:
        return False

    content_a = _content_tokens(_outcome_blob(a))
    content_b = _content_tokens(_outcome_blob(b))
    if not content_a or not content_b:
        return outcome_sim >= 0.9 and title_sim >= 0.85 and bool(distinctive)
    overlap = len(content_a & content_b) / max(1, min(len(content_a), len(content_b)))
    # Require strong overlap of distinctive content tokens AND high outcome similarity.
    if outcome_sim >= 0.86 and overlap >= 0.7 and (title_overlap or skill_overlap or len(outcome_overlap) >= 1):
        # If outcomes only share boilerplate-stripped nothing unique besides one
        # token that is the whole skill name in both — good. If SequenceMatcher
        # is high only because of English shells, title/skill overlap will be empty
        # and outcome_overlap will also be empty → already rejected above.
        return True
    if title_sim >= 0.9 and overlap >= 0.75 and title_overlap:
        return True
    return False


def _merge_reel(keeper: ReelPlan, donor: ReelPlan) -> ReelPlan:
    must_cover = list(dict.fromkeys([*(keeper.must_cover or []), *(donor.must_cover or [])]))
    must_avoid = list(dict.fromkeys([*(keeper.must_avoid or []), *(donor.must_avoid or [])]))
    forbid = list(
        dict.fromkeys(
            [*(keeper.already_taught_forbid_repeat or []), *(donor.already_taught_forbid_repeat or [])]
        )
    )
    return keeper.model_copy(
        update={
            "must_cover": must_cover,
            "must_avoid": must_avoid,
            "already_taught_forbid_repeat": forbid,
            "why_standalone": keeper.why_standalone
            or donor.why_standalone
            or "Merged related teaching into one standalone lesson.",
            "purpose": keeper.purpose or donor.purpose,
        }
    )


def _normalize_module(module: ModulePlan) -> ModulePlan:
    reels = [ensure_reel_blueprint_defaults(r) for r in module.reels]
    return module.model_copy(update={"reels": reels})


def compress_course_map(
    course_map: CourseMap,
    *,
    thesis: CourseThesis | None = None,
) -> tuple[CourseMap, CompressionReport]:
    """Merge near-duplicate lessons; enforce thesis hard limits afterward."""
    from app.generation.course_map_quality import total_estimated_minutes

    thesis = thesis or course_map.thesis
    report = CompressionReport()
    modules_out: list[ModulePlan] = []
    before = sum(len(m.reels) for m in course_map.modules)
    report.lesson_count_before = before

    for module in course_map.modules:
        mod = _normalize_module(module)
        kept: list[ReelPlan] = []
        for reel in mod.reels:
            # Out-of-scope heuristic vs thesis.
            if thesis and thesis.out_of_scope:
                blob = _outcome_blob(reel).lower()
                if any(
                    (phrase or "").strip().lower()
                    and (phrase or "").strip().lower() in blob
                    for phrase in thesis.out_of_scope
                    if len((phrase or "").strip()) >= 8
                ):
                    report.removed_reel_ids.append(reel.reel_id)
                    report.warnings.append(
                        f"Removed out-of-scope lesson {reel.reel_id}: {reel.title}"
                    )
                    continue

            merged_into = False
            for i, existing in enumerate(kept):
                if _semantically_similar(existing, reel):
                    kept[i] = _merge_reel(existing, reel)
                    report.merged_pairs.append((existing.reel_id, reel.reel_id))
                    report.removed_reel_ids.append(reel.reel_id)
                    merged_into = True
                    break
            if not merged_into:
                # Thin shells with no distinct outcome → drop when neighbors exist.
                if (
                    kept
                    and not (reel.distinct_teaching_outcome or reel.purpose or "").strip()
                    and not reel.must_cover
                ):
                    report.removed_reel_ids.append(reel.reel_id)
                    report.warnings.append(f"Dropped empty shell lesson {reel.reel_id}")
                    continue
                kept.append(reel)
        modules_out.append(mod.model_copy(update={"reels": kept}))

    # Drop empty modules created by compression.
    modules_out = [m for m in modules_out if m.reels]
    if not modules_out:
        report.errors.append("Map compression removed every lesson — map is unusable.")
        return course_map, report

    compressed = course_map.model_copy(
        update={"modules": modules_out, "thesis": thesis or course_map.thesis}
    )
    after = sum(len(m.reels) for m in compressed.modules)
    report.lesson_count_after = after
    report.estimated_minutes_after = total_estimated_minutes(compressed)

    if thesis:
        if after > thesis.hard_max_lessons and not thesis.human_override_hard_limits:
            report.errors.append(
                f"Course map has {after} lessons which exceeds hard_max_lessons="
                f"{thesis.hard_max_lessons}. Compress further or raise the hard "
                "limit with an explicit human override."
            )
        if (
            report.estimated_minutes_after > thesis.hard_max_minutes
            and not thesis.human_override_hard_limits
        ):
            report.errors.append(
                f"Course map estimates ~{report.estimated_minutes_after:.0f} minutes "
                f"which exceeds hard_max_minutes={thesis.hard_max_minutes}."
            )
    return compressed, report


def enforce_map_hard_limits(
    course_map: CourseMap,
    *,
    thesis: CourseThesis | None = None,
    allow_one_recompress: bool = True,
) -> tuple[CourseMap, CompressionReport]:
    """Compress once; if still over hard max, fail clearly (do not start scripts)."""
    thesis = thesis or course_map.thesis
    compressed, report = compress_course_map(course_map, thesis=thesis)
    if report.ok:
        return compressed, report
    if allow_one_recompress and report.errors:
        # Second pass: more aggressive adjacent merges inside modules.
        aggressive = _aggressive_adjacent_merge(compressed)
        compressed2, report2 = compress_course_map(aggressive, thesis=thesis)
        report2.warnings = list(report.warnings) + list(report2.warnings)
        report2.merged_pairs = list(report.merged_pairs) + list(report2.merged_pairs)
        if not report2.ok:
            report2.errors = [
                "Map still exceeds hard limits after compression — refusing to "
                "generate lesson scripts.",
                *report2.errors,
            ]
        return compressed2, report2
    return compressed, report


def _aggressive_adjacent_merge(course_map: CourseMap) -> CourseMap:
    modules: list[ModulePlan] = []
    for module in course_map.modules:
        reels = list(module.reels)
        if len(reels) < 2:
            modules.append(module)
            continue
        new_reels: list[ReelPlan] = [reels[0]]
        for reel in reels[1:]:
            prev = new_reels[-1]
            if _semantically_similar(prev, reel):
                new_reels[-1] = _merge_reel(prev, reel)
            else:
                new_reels.append(reel)
        modules.append(module.model_copy(update={"reels": new_reels}))
    return course_map.model_copy(update={"modules": modules})
