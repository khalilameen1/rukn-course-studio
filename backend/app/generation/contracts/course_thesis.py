"""Course Thesis contract — required before any Course Map build."""

from __future__ import annotations

from dataclasses import dataclass

from app.ai.provider import CourseBrief
from app.models.enums import AddressForm, CourseMixType
from app.schemas.generation import CourseThesis

# Practical-course defaults from the rebuild brief (human-overridable).
PRACTICAL_DEFAULTS = {
    "target_theory_ratio": 0.25,
    "target_practice_ratio": 0.60,
    "target_lessons_min": 35,
    "target_lessons_max": 55,
    "hard_max_lessons": 60,
    "target_minutes_min": 150,
    "target_minutes_max": 210,
    "hard_max_minutes": 240,
}


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
    course_type: str = "practical_skill",
    address_form: AddressForm = AddressForm.MASCULINE,
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
    practical = (course_type or "").lower() in {
        "practical_skill",
        "practical",
        "skill",
        "applied",
    }
    defaults = PRACTICAL_DEFAULTS if practical else {
        "target_theory_ratio": 0.45,
        "target_practice_ratio": 0.40,
        "target_lessons_min": 20,
        "target_lessons_max": 45,
        "hard_max_lessons": 60,
        "target_minutes_min": 90,
        "target_minutes_max": 180,
        "hard_max_minutes": 240,
    }
    resolved_mix = mix_type or (
        CourseMixType.PRACTICAL if practical else CourseMixType.MIXED
    )
    return CourseThesis(
        final_student_outcome=(brief.outcome or brief.title or "").strip(),
        audience_and_starting_level=(brief.audience or "").strip(),
        practical_deliverable=(final_project or brief.outcome or "").strip(),
        in_scope=in_scope
        or [p for p in [(brief.outcome or "").strip(), (brief.title or "").strip()] if p],
        out_of_scope=out_of_scope
        or [
            "محتوى تسويقي تحفيزي بلا تطبيق",
            "شرح نظري ممتد بلا قرار عملي",
        ],
        course_type=course_type or "practical_skill",
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
        target_minutes_min=target_minutes_min or int(defaults["target_minutes_min"]),
        target_minutes_max=target_minutes_max or int(defaults["target_minutes_max"]),
        hard_max_minutes=hard_max_minutes or int(defaults["hard_max_minutes"]),
        target_lessons_min=target_lessons_min or int(defaults["target_lessons_min"]),
        target_lessons_max=target_lessons_max or int(defaults["target_lessons_max"]),
        hard_max_lessons=hard_max_lessons or int(defaults["hard_max_lessons"]),
        required_tools=required_tools or [],
        final_project=(final_project or brief.outcome or "المشروع النهائي للكورس").strip(),
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
