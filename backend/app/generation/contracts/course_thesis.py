"""Course Thesis contract — required before any Course Map build."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.ai.provider import CourseBrief
from app.models.enums import AddressForm, CourseFamily, CourseMixType
from app.schemas.generation import CourseThesis

# Practical-course defaults from the rebuild brief (human-overridable).
PRACTICAL_DEFAULTS = {
    "target_theory_ratio": 0.25,
    "target_practice_ratio": 0.60,
    "hard_max_lessons": 60,
    "hard_max_minutes": 240,
}


def _adaptive_size_targets(
    brief: CourseBrief,
    *,
    scope: list[str],
    required_tools: list[str],
    practical: bool,
) -> tuple[dict[str, int], list[str]]:
    """Derive course size from distinct capabilities, never a fixed lesson count."""
    raw_signals = [
        *scope,
        brief.required_final_performance,
        *required_tools,
        *brief.professional_constraints,
        *brief.high_stakes_constraints,
    ]
    capabilities: list[str] = []
    seen: set[str] = set()
    for raw in raw_signals:
        for part in re.split(r"[\n,،;؛]+|\s+(?:and|ثم|وذلك)\s+", raw or ""):
            normalized = " ".join(part.split()).strip()
            key = normalized.casefold()
            if len(normalized) < 3 or key in seen:
                continue
            seen.add(key)
            capabilities.append(normalized)
    if not capabilities:
        capabilities = [brief.outcome or brief.title]
    count = len(capabilities)
    multiplier = 3 if practical else 2
    lesson_min = max(8, min(42, count * multiplier + 6))
    lesson_max = min(60, lesson_min + max(6, count * 2))
    minute_min = max(45, lesson_min * (3 if practical else 4))
    minute_max = min(240, lesson_max * (4 if practical else 5))
    return (
        {
            "target_lessons_min": lesson_min,
            "target_lessons_max": lesson_max,
            "target_minutes_min": minute_min,
            "target_minutes_max": minute_max,
        },
        capabilities,
    )


@dataclass
class ThesisValidation:
    ok: bool
    errors: list[str]
    warnings: list[str]

    def raise_if_invalid(self) -> None:
        if not self.ok:
            raise ValueError("; ".join(self.errors))


def build_course_thesis_from_brief(
    brief: CourseBrief,
    *,
    course_type: str | None = None,
    address_form: AddressForm | None = None,
    human_override_hard_limits: bool = False,
    hard_max_lessons: int | None = None,
    hard_max_minutes: int | None = None,
    target_lessons_min: int | None = None,
    target_lessons_max: int | None = None,
    target_minutes_min: int | None = None,
    target_minutes_max: int | None = None,
    target_theory_ratio: float | None = None,
    target_practice_ratio: float | None = None,
    in_scope: list[str] | None = None,
    out_of_scope: list[str] | None = None,
    required_tools: list[str] | None = None,
    final_project: str | None = None,
    mix_type: CourseMixType | None = None,
) -> CourseThesis:
    """Build a valid thesis from the course brief + optional advanced overrides."""
    course_type = course_type or brief.course_type or "practical_skill"
    address_form = address_form or brief.address_form
    practical = (course_type or "").lower() in {
        "practical_skill",
        "practical",
        "skill",
        "applied",
    }
    defaults = PRACTICAL_DEFAULTS if practical else {
        "target_theory_ratio": 0.45,
        "target_practice_ratio": 0.40,
        "hard_max_lessons": 60,
        "hard_max_minutes": 240,
    }
    resolved_mix = mix_type or (
        CourseMixType.PRACTICAL if practical else CourseMixType.MIXED
    )
    resolved_scope = in_scope or [
        part
        for part in [(brief.outcome or "").strip(), (brief.title or "").strip()]
        if part
    ]
    resolved_tools = (
        required_tools if required_tools is not None else list(brief.available_tools)
    )
    adaptive, size_capabilities = _adaptive_size_targets(
        brief,
        scope=resolved_scope,
        required_tools=resolved_tools,
        practical=practical,
    )
    return CourseThesis(
        final_student_outcome=(
            brief.required_final_performance or brief.outcome or brief.title or ""
        ).strip(),
        audience_and_starting_level=(
            brief.learner_starting_state or brief.audience or ""
        ).strip(),
        practical_deliverable=(
            final_project
            or brief.required_final_performance
            or brief.outcome
            or ""
        ).strip(),
        in_scope=resolved_scope,
        out_of_scope=out_of_scope
        or [
            "محتوى تسويقي تحفيزي بلا تطبيق",
            "شرح نظري ممتد بلا قرار عملي",
        ],
        course_type=course_type or "practical_skill",
        course_domain=(brief.course_domain or "").strip(),
        course_specialty=(brief.course_specialty or "").strip(),
        primary_course_family=brief.primary_course_family
        or CourseFamily.GENERAL_SKILL,
        secondary_course_families=list(brief.secondary_course_families),
        target_market=brief.target_market.value,
        student_language=(brief.student_language or "ar").strip(),
        spoken_variety=(brief.spoken_variety or "neutral").strip(),
        learner_starting_state=(
            brief.learner_starting_state or brief.audience or ""
        ).strip(),
        required_final_performance=(
            brief.required_final_performance or brief.outcome or ""
        ).strip(),
        required_independence_level=(
            brief.required_independence_level or "independent_with_checklist"
        ).strip(),
        instructor_responsibility_boundaries=list(
            brief.instructor_responsibility_boundaries
        ),
        # Deliberately copy explicit intake only. Never infer personal experience.
        verified_instructor_experience=list(brief.verified_instructor_experience),
        forbidden_first_person_claims=list(brief.forbidden_first_person_claims),
        realistic_student_budget=(brief.realistic_student_budget or "").strip(),
        available_tools=list(brief.available_tools),
        professional_constraints=list(brief.professional_constraints),
        high_stakes_constraints=list(brief.high_stakes_constraints),
        mix_type=resolved_mix,
        target_theory_ratio=(
            target_theory_ratio
            if target_theory_ratio is not None
            else float(defaults["target_theory_ratio"])
        ),
        target_practice_ratio=(
            target_practice_ratio
            if target_practice_ratio is not None
            else float(defaults["target_practice_ratio"])
        ),
        target_minutes_min=target_minutes_min
        or adaptive["target_minutes_min"],
        target_minutes_max=target_minutes_max
        or adaptive["target_minutes_max"],
        hard_max_minutes=hard_max_minutes or int(defaults["hard_max_minutes"]),
        target_lessons_min=target_lessons_min
        or adaptive["target_lessons_min"],
        target_lessons_max=target_lessons_max
        or adaptive["target_lessons_max"],
        hard_max_lessons=hard_max_lessons or int(defaults["hard_max_lessons"]),
        size_basis_capabilities=size_capabilities,
        required_tools=resolved_tools,
        final_project=(
            final_project
            or brief.required_final_performance
            or brief.outcome
            or "المشروع النهائي للكورس"
        ).strip(),
        address_form=address_form,
        human_override_hard_limits=human_override_hard_limits,
    )


def validate_course_thesis(thesis: CourseThesis) -> ThesisValidation:
    errors: list[str] = []
    warnings: list[str] = []

    if not (thesis.final_student_outcome or "").strip():
        errors.append("Course Thesis missing final_student_outcome")
    if not (thesis.audience_and_starting_level or "").strip():
        errors.append("Course Thesis missing audience_and_starting_level")
    if not (thesis.practical_deliverable or "").strip():
        errors.append("Course Thesis missing practical_deliverable")
    if not thesis.in_scope:
        errors.append("Course Thesis must declare in_scope")
    if not thesis.out_of_scope:
        errors.append("Course Thesis must declare out_of_scope")
    if not (thesis.final_project or "").strip():
        errors.append("Course Thesis missing final_project")
    if not (thesis.learner_starting_state or "").strip():
        errors.append("Course Thesis missing learner_starting_state")
    if not (thesis.required_final_performance or "").strip():
        errors.append("Course Thesis missing required_final_performance")
    if not (thesis.required_independence_level or "").strip():
        errors.append("Course Thesis missing required_independence_level")

    if thesis.hard_max_lessons < 1:
        errors.append("hard_max_lessons must be >= 1")
    if thesis.hard_max_minutes < 1:
        errors.append("hard_max_minutes must be >= 1")
    if thesis.target_lessons_max > thesis.hard_max_lessons and not thesis.human_override_hard_limits:
        errors.append(
            "target_lessons_max cannot exceed hard_max_lessons without human override"
        )
    if thesis.target_minutes_max > thesis.hard_max_minutes and not thesis.human_override_hard_limits:
        errors.append(
            "target_minutes_max cannot exceed hard_max_minutes without human override"
        )

    if thesis.mix_type == CourseMixType.PRACTICAL:
        if thesis.target_practice_ratio < 0.60:
            warnings.append(
                "Practical course target_practice_ratio below 60% — "
                "raise practice/analysis share or change mix_type."
            )
        if thesis.target_theory_ratio > 0.25:
            warnings.append(
                "Practical course target_theory_ratio above 25% — "
                "pure theory should stay capped."
            )

    return ThesisValidation(ok=not errors, errors=errors, warnings=warnings)
