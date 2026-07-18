"""Hard export blockers — needs_review / fatal / map / project failures block DOCX."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.generation.contracts.spoken_final_master import validate_spoken_export_text
from app.generation.duration_policy import words_outside_hard_range_reason
from app.generation.egyptian_arabic_gate import run_egyptian_arabic_gate
from app.generation.phrase_ledger import PhraseLedger
from app.generation.quality.contract import CourseQualityContract
from app.generation.quality.issue_codes import EXPORT_BLOCKING_STATUSES, IssueCode
from app.models.enums import AddressForm, CourseMixType, LessonDeliveryMode
from app.schemas.generation import CourseMap, CourseThesis, FinalCourse, GeneratedReel


@dataclass
class ExportBlocker:
    level: str  # course | lesson
    code: str
    detail: str
    reel_id: str | None = None


@dataclass
class ExportGateReport:
    blockers: list[ExportBlocker] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.blockers

    def model_dump(self) -> dict:
        return {
            "ok": self.ok,
            "blockers": [
                {
                    "level": b.level,
                    "code": b.code,
                    "detail": b.detail,
                    "reel_id": b.reel_id,
                }
                for b in self.blockers
            ],
        }


def _lesson_count(course_map: CourseMap) -> int:
    return sum(len(m.reels) for m in course_map.modules)


def evaluate_export_blockers(
    *,
    final_course: FinalCourse,
    course_map: CourseMap | None = None,
    thesis: CourseThesis | None = None,
    generated_reels: list[GeneratedReel] | None = None,
    phrase_ledger: PhraseLedger | None = None,
    address_form: AddressForm = AddressForm.MASCULINE,
    quality_contract: CourseQualityContract | None = None,
) -> ExportGateReport:
    report = ExportGateReport()
    thesis = thesis or (final_course.thesis if final_course else None) or (
        course_map.thesis if course_map else None
    )
    cmap = course_map
    if quality_contract is not None:
        address_form = quality_contract.language.address_form or address_form

    if cmap and thesis:
        n = _lesson_count(cmap)
        hard_max = (
            quality_contract.delivery.hard_max_lessons
            if quality_contract is not None
            else thesis.hard_max_lessons
        )
        if n > hard_max and not thesis.human_override_hard_limits:
            report.blockers.append(
                ExportBlocker(
                    "course",
                    "map_over_hard_max_lessons",
                    f"{n} lessons > hard_max_lessons={hard_max}",
                )
            )
        # Detect remaining near-duplicates with the same dual-signal used by compression.
        from app.generation.map_compression import _semantically_similar

        plans = [r for m in cmap.modules for r in m.reels]
        dup_hits = 0
        for i, a in enumerate(plans):
            for b in plans[i + 1 :]:
                if _semantically_similar(a, b):
                    dup_hits += 1
        if dup_hits:
            report.blockers.append(
                ExportBlocker(
                    "course",
                    "semantic_duplication",
                    f"Map still has {dup_hits} near-duplicate lesson pair(s)",
                )
            )
        missing_projects = [
            m.module_id
            for m in cmap.modules
            if m.module_project is None and not (m.bridge_project or "").strip()
        ]
        require_projects = thesis.mix_type == CourseMixType.PRACTICAL
        if quality_contract is not None:
            require_projects = (
                quality_contract.delivery.module_checkpoint_policy
                == "required_for_practical"
                and quality_contract.pedagogy.mix_type == CourseMixType.PRACTICAL
            ) or (
                quality_contract.delivery.module_checkpoint_policy == "required"
            )
        if require_projects and missing_projects:
            report.blockers.append(
                ExportBlocker(
                    "course",
                    IssueCode.CHECKPOINT_MISSING.value,
                    f"Modules without projects: {', '.join(missing_projects)}",
                )
            )
        if require_projects and not (
            final_course.graduation_project or (thesis.final_project or "").strip()
        ):
            report.blockers.append(
                ExportBlocker(
                    "course",
                    IssueCode.CHECKPOINT_MISSING.value,
                    "Practical course missing graduation/final project",
                )
            )
        if quality_contract is not None and quality_contract.evidence.require_expert_review_before_export:
            report.blockers.append(
                ExportBlocker(
                    "course",
                    IssueCode.EXPERT_REVIEW_REQUIRED.value,
                    "Domain risk requires expert review before export",
                )
            )

    if phrase_ledger:
        for fail in phrase_ledger.diversity_failures():
            report.blockers.append(
                ExportBlocker("course", "phrase_template_repetition", fail)
            )

    reels = generated_reels or []
    reel_by_id = {r.reel_id: r for r in reels}
    for module in final_course.modules:
        for reel in module.reels:
            status = (reel.quality_status or "").lower()
            gen = reel_by_id.get(reel.reel_id)
            if gen and (gen.quality_status or "").lower() in {"needs_review", "fail"}:
                status = gen.quality_status.lower()
            if status in EXPORT_BLOCKING_STATUSES or (
                gen and gen.self_check_status.value == "needs_revision"
            ):
                report.blockers.append(
                    ExportBlocker(
                        "lesson",
                        status if status in EXPORT_BLOCKING_STATUSES else "needs_review_or_fatal",
                        f"Lesson flagged {status or 'needs_revision'} — export blocked",
                        reel_id=reel.reel_id,
                    )
                )
            body = reel.script_text or ""
            if not body.strip():
                report.blockers.append(
                    ExportBlocker(
                        "lesson",
                        "empty_script",
                        "Empty spoken script",
                        reel_id=reel.reel_id,
                    )
                )
                continue
            spoken_check = validate_spoken_export_text(body)
            if not spoken_check.ok:
                report.blockers.append(
                    ExportBlocker(
                        "lesson",
                        "metadata_leak",
                        "; ".join(spoken_check.errors[:3]),
                        reel_id=reel.reel_id,
                    )
                )
            apply_egyptian = True
            apply_english = False
            if quality_contract is not None:
                apply_egyptian = quality_contract.language.apply_egyptian_spoken_qa
                apply_english = quality_contract.language.apply_english_spoken_qa
            if apply_egyptian:
                arabic = run_egyptian_arabic_gate(body, address_form=address_form)
                for issue in arabic.issues:
                    if issue.severity in ("fatal", "serious"):
                        report.blockers.append(
                            ExportBlocker(
                                "lesson",
                                issue.code,
                                issue.detail,
                                reel_id=reel.reel_id,
                            )
                        )
            if apply_english:
                from app.generation.quality.english_spoken_gate import run_english_spoken_gate

                eng = run_english_spoken_gate(body)
                for issue in eng.issues:
                    if issue.severity in ("fatal", "serious"):
                        report.blockers.append(
                            ExportBlocker(
                                "lesson",
                                issue.code,
                                issue.detail,
                                reel_id=reel.reel_id,
                            )
                        )
            mode = reel.delivery_mode
            if gen and gen.delivery_mode:
                mode = gen.delivery_mode
            n_words = len(body.split())
            if quality_contract is not None:
                d = quality_contract.delivery
                if n_words < d.minimum_reel_words:
                    report.blockers.append(
                        ExportBlocker(
                            "lesson",
                            IssueCode.WORD_RANGE.value,
                            f"spoken_words={n_words} < minimum_reel_words={d.minimum_reel_words}",
                            reel_id=reel.reel_id,
                        )
                    )
                elif n_words > d.maximum_reel_words:
                    report.blockers.append(
                        ExportBlocker(
                            "lesson",
                            IssueCode.WORD_RANGE.value,
                            f"spoken_words={n_words} > maximum_reel_words={d.maximum_reel_words}",
                            reel_id=reel.reel_id,
                        )
                    )
            else:
                reason = words_outside_hard_range_reason(body, delivery_mode=mode)
                if reason and n_words < 40:
                    report.blockers.append(
                        ExportBlocker(
                            "lesson",
                            "empty_teaching_or_too_short",
                            reason,
                            reel_id=reel.reel_id,
                        )
                    )
                elif reason and n_words > 600:
                    report.blockers.append(
                        ExportBlocker(
                            "lesson",
                            "hard_length_overflow",
                            reason,
                            reel_id=reel.reel_id,
                        )
                    )
            # Screen lessons need visual plan on the map reel.
            if cmap and mode in {
                LessonDeliveryMode.SCREEN_DEMO,
                LessonDeliveryMode.PROJECT_BUILD,
            }:
                plan = _find_plan(cmap, reel.reel_id)
                if plan and not plan.internal_visual_plan and not plan.required_assets:
                    report.blockers.append(
                        ExportBlocker(
                            "lesson",
                            "screen_without_visual_plan",
                            "Screen/demo lesson missing internalVisualPlan/requiredAssets",
                            reel_id=reel.reel_id,
                        )
                    )
    return report


def _find_plan(course_map: CourseMap, reel_id: str):
    for m in course_map.modules:
        for r in m.reels:
            if r.reel_id == reel_id:
                return r
    return None


def assert_export_allowed(report: ExportGateReport) -> None:
    if not report.ok:
        details = "; ".join(f"{b.code}:{b.detail}" for b in report.blockers[:8])
        raise RuntimeError(f"DOCX export blocked — {details}")
