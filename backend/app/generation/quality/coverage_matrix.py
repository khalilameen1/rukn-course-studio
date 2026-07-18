"""Coverage Matrix — promises, skills, lessons, projects must align before writing."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.generation.quality.contract import CourseQualityContract
from app.generation.quality.issue_codes import IssueCode
from app.models.enums import CourseMixType, LessonDeliveryMode
from app.schemas.generation import CourseMap, CourseThesis


class CoverageIssue(BaseModel):
    code: str
    detail: str
    severity: str = "fatal"


class CoverageMatrixReport(BaseModel):
    ok: bool = True
    issues: list[CoverageIssue] = Field(default_factory=list)
    theory_ratio: float = 0.0
    practice_ratio: float = 0.0

    def add(self, code: str, detail: str, severity: str = "fatal") -> None:
        self.issues.append(CoverageIssue(code=code, detail=detail, severity=severity))
        if severity in {"fatal", "serious"}:
            self.ok = False


def _is_practice_mode(mode: LessonDeliveryMode | None) -> bool:
    return mode in {
        LessonDeliveryMode.SCREEN_DEMO,
        LessonDeliveryMode.PROJECT_BUILD,
        LessonDeliveryMode.BEFORE_AFTER,
        LessonDeliveryMode.ERROR_FIX,
        LessonDeliveryMode.CASE_STUDY,
        LessonDeliveryMode.CRITIQUE,
        LessonDeliveryMode.DESIGN_CRITIQUE,
    }


def evaluate_coverage_matrix(
    course_map: CourseMap,
    *,
    thesis: CourseThesis | None = None,
    contract: CourseQualityContract | None = None,
) -> CoverageMatrixReport:
    report = CoverageMatrixReport()
    thesis = thesis or course_map.thesis
    lessons = [r for m in course_map.modules for r in m.reels]
    if not lessons:
        report.add(IssueCode.DEPTH_EMPTY.value, "Map has zero lessons")
        return report

    # Unique outcomes / learning jobs
    outcomes: dict[str, str] = {}
    for reel in lessons:
        key = (reel.distinct_teaching_outcome or reel.purpose or reel.title or "").strip().lower()
        if not key:
            report.add(
                IssueCode.DEPTH_EMPTY.value,
                f"Lesson {reel.reel_id} has no independent learning job",
                "serious",
            )
            continue
        if key in outcomes:
            report.add(
                IssueCode.DUPLICATE_LEARNING_JOB.value,
                f"{reel.reel_id} duplicates learning job of {outcomes[key]}",
                "serious",
            )
        else:
            outcomes[key] = reel.reel_id

    # Promises without lessons (coarse: outcome string should appear in some purpose/outcome)
    if thesis and thesis.final_student_outcome:
        promise = thesis.final_student_outcome.strip().lower()
        blob = " ".join(
            [
                (r.distinct_teaching_outcome or "")
                + " "
                + (r.purpose or "")
                + " "
                + (r.title or "")
                for r in lessons
            ]
        ).lower()
        # Soft check — only flag when promise has distinctive tokens unused.
        tokens = [t for t in promise.split() if len(t) >= 4][:3]
        if tokens and not any(t in blob for t in tokens):
            report.add(
                IssueCode.DEPTH_GENERIC.value,
                "Course promise not clearly covered by any lesson outcomes",
                "serious",
            )

    # Module checkpoints / projects
    mix = (
        contract.pedagogy.mix_type
        if contract
        else (thesis.mix_type if thesis else CourseMixType.PRACTICAL)
    )
    if mix == CourseMixType.PRACTICAL:
        for module in course_map.modules:
            if module.module_project is None and not (module.bridge_project or "").strip():
                report.add(
                    IssueCode.CHECKPOINT_MISSING.value,
                    f"Module {module.module_id} missing checkpoint/project",
                )
        if not (course_map.graduation_project or (thesis and thesis.final_project)):
            report.add(
                IssueCode.CHECKPOINT_MISSING.value,
                "Practical course missing graduation/final project",
                "serious",
            )

    # Theory/practice by estimated words/time proxy (lesson count weighted by mode)
    practice = sum(1 for r in lessons if _is_practice_mode(r.delivery_mode))
    theory = len(lessons) - practice
    total = max(1, len(lessons))
    report.practice_ratio = practice / total
    report.theory_ratio = theory / total

    target_practice = None
    target_theory = None
    if contract and contract.pedagogy.target_practice_ratio is not None:
        target_practice = contract.pedagogy.target_practice_ratio
        target_theory = contract.pedagogy.target_theory_ratio
    elif thesis and thesis.mix_type == CourseMixType.PRACTICAL:
        target_practice = thesis.target_practice_ratio
        target_theory = thesis.target_theory_ratio

    if target_theory is not None and report.theory_ratio > target_theory + 0.08:
        report.add(
            IssueCode.THEORY_RATIO_VIOLATION.value,
            f"Theory ratio {report.theory_ratio:.2f} exceeds contract {target_theory:.2f}",
            "fatal",
        )
    if target_practice is not None and report.practice_ratio + 0.08 < target_practice:
        report.add(
            IssueCode.THEORY_RATIO_VIOLATION.value,
            f"Practice ratio {report.practice_ratio:.2f} below contract {target_practice:.2f}",
            "serious",
        )

    # Early practice for practical domains
    if contract and contract.pedagogy.early_practice_required and lessons:
        window = min(
            len(lessons),
            max(
                1,
                int(len(lessons) * contract.pedagogy.early_practice_within_fraction),
                contract.pedagogy.early_practice_within_lessons,
            ),
        )
        if not any(_is_practice_mode(r.delivery_mode) for r in lessons[:window]):
            report.add(
                IssueCode.PROJECT_MISALIGNMENT.value,
                f"No practice lesson within first {window} lessons",
                "serious",
            )

    return report
