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
    promise_to_lessons: dict[str, list[str]] = Field(default_factory=dict)
    capability_rows: list[dict[str, object]] = Field(default_factory=list)
    project_rows: list[dict[str, object]] = Field(default_factory=list)

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
    lesson_to_module = {
        reel.reel_id: module.module_id
        for module in course_map.modules
        for reel in module.reels
    }
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
        report.capability_rows.append(
            {
                "lesson_id": reel.reel_id,
                "module_id": lesson_to_module.get(reel.reel_id, ""),
                "capability": (
                    reel.new_skill_or_decision
                    or reel.distinct_teaching_outcome
                    or reel.purpose
                ),
                "learner_after": reel.student_can_do_after,
                "project_contribution": reel.project_contribution,
                "prerequisites": list(reel.prerequisite_lesson_ids),
            }
        )

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
            report.promise_to_lessons[promise] = []
        else:
            matching = [
                reel.reel_id
                for reel in lessons
                if not tokens
                or any(
                    token
                    in " ".join(
                        [
                            reel.title or "",
                            reel.purpose or "",
                            reel.distinct_teaching_outcome or "",
                            reel.student_can_do_after or "",
                        ]
                    ).lower()
                    for token in tokens
                )
            ]
            report.promise_to_lessons[promise] = matching

    # Module checkpoints / projects (v1.7: final module has no project;
    # there is no graduation_project after the last module — the last
    # non-final module project is the bounded integrated readiness proof.)
    mix = (
        contract.pedagogy.mix_type
        if contract
        else (thesis.mix_type if thesis else CourseMixType.PRACTICAL)
    )
    if mix == CourseMixType.PRACTICAL:
        modules = list(course_map.modules)
        for index, module in enumerate(modules):
            is_final_module = index == len(modules) - 1
            project = module.module_project
            has_bridge = bool((module.bridge_project or "").strip())
            if is_final_module:
                if project is not None or has_bridge:
                    report.add(
                        IssueCode.PROJECT_MISALIGNMENT.value,
                        f"Final module {module.module_id} must not carry a project",
                        "serious",
                    )
                continue
            if project is None and not has_bridge:
                report.add(
                    IssueCode.CHECKPOINT_MISSING.value,
                    f"Module {module.module_id} missing checkpoint/project",
                )
                continue
            contributing = [
                reel.reel_id
                for reel in module.reels
                if (reel.project_contribution or "").strip()
            ]
            tested = list(project.skills_tested) if project is not None else []
            report.project_rows.append(
                {
                    "module_id": module.module_id,
                    "project_name": project.name if project is not None else "bridge_project",
                    "skills_tested": tested,
                    "contributing_lessons": contributing,
                }
            )
            if not tested and not contributing:
                report.add(
                    IssueCode.PROJECT_MISALIGNMENT.value,
                    f"Module {module.module_id} project is not linked to taught capabilities",
                    "serious",
                )
        if len(modules) >= 2 and not report.project_rows:
            report.add(
                IssueCode.CHECKPOINT_MISSING.value,
                "Practical course missing inter-module readiness project",
                "serious",
            )
        # Ignore legacy graduation_project if a model still emits one.
        if course_map.graduation_project:
            report.project_rows.append(
                {
                    "module_id": "graduation",
                    "project_name": course_map.graduation_project.name,
                    "skills_tested": list(
                        course_map.graduation_project.skills_tested
                    ),
                    "contributing_lessons": [
                        reel.reel_id
                        for reel in lessons
                        if (reel.project_contribution or "").strip()
                    ],
                }
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

    if target_theory is not None and report.theory_ratio > target_theory + 0.10:
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
