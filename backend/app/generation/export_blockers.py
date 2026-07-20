"""Hard export blockers — needs_review / fatal / map / project failures block DOCX."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.generation.contracts.spoken_final_master import validate_spoken_export_text
from app.generation.duration_policy import word_range_for, words_outside_hard_range_reason
from app.generation.egyptian_arabic_gate import run_spoken_variety_integrity_gate
from app.generation.phrase_ledger import PhraseLedger
from app.generation.quality.contract import CourseQualityContract
from app.generation.quality.context_snapshot import fingerprint_value
from app.generation.quality.coverage_matrix import evaluate_coverage_matrix
from app.generation.quality.issue_codes import EXPORT_BLOCKING_STATUSES, IssueCode
from app.generation.terminology_map import default_terminology_map
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


class ExportBlockedError(RuntimeError):
    """The accepted state failed one or more non-bypassable export gates."""


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
    evidence_ledger: dict | None = None,
    expected_config_fingerprint: str | None = None,
    probe_mode: bool = False,
) -> ExportGateReport:
    report = ExportGateReport()
    thesis = thesis or (final_course.thesis if final_course else None) or (
        course_map.thesis if course_map else None
    )
    cmap = course_map
    if quality_contract is not None:
        address_form = quality_contract.language.address_form or address_form

    if cmap and thesis and not probe_mode:
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

        final_module_by_id = {module.module_id: module for module in final_course.modules}
        missing_final_projects = [
            module.module_id
            for module in cmap.modules
            if (
                module.module_project is not None
                or (module.bridge_project or "").strip()
            )
            and (
                module.module_id not in final_module_by_id
                or final_module_by_id[module.module_id].module_project is None
            )
        ]
        if require_projects and missing_final_projects:
            report.blockers.append(
                ExportBlocker(
                    "course",
                    IssueCode.CHECKPOINT_MISSING.value,
                    "Final course dropped module projects: "
                    + ", ".join(missing_final_projects),
                )
            )

        coverage = evaluate_coverage_matrix(cmap, thesis=thesis, contract=quality_contract)
        for issue in coverage.issues:
            if issue.severity in {"fatal", "serious"}:
                report.blockers.append(
                    ExportBlocker("course", issue.code, issue.detail)
                )

        planned_ids = [reel.reel_id for module in cmap.modules for reel in module.reels]
        final_ids = [
            reel.reel_id for module in final_course.modules for reel in module.reels
        ]
        missing_ids = [reel_id for reel_id in planned_ids if reel_id not in final_ids]
        extra_ids = [reel_id for reel_id in final_ids if reel_id not in planned_ids]
        duplicate_ids = sorted(
            {reel_id for reel_id in final_ids if final_ids.count(reel_id) > 1}
        )
        if missing_ids or extra_ids or duplicate_ids:
            report.blockers.append(
                ExportBlocker(
                    "course",
                    "course_shape_mismatch",
                    f"missing={missing_ids}; extra={extra_ids}; duplicates={duplicate_ids}",
                )
            )

    if phrase_ledger:
        for fail in phrase_ledger.diversity_failures():
            report.blockers.append(
                ExportBlocker("course", "phrase_template_repetition", fail)
            )

    reels = generated_reels or []
    if cmap and not probe_mode:
        from app.generation.quality.cross_scope_review import review_cross_scope

        cross_scope = review_cross_scope(
            course_map=cmap,
            generated_reels=reels,
        )
        for finding in cross_scope.blocking_findings:
            target = (
                finding.target_reel_ids[0]
                if len(finding.target_reel_ids) == 1
                else None
            )
            report.blockers.append(
                ExportBlocker(
                    "lesson" if target else "course",
                    finding.code,
                    f"{finding.detail} Required action: {finding.required_action}.",
                    reel_id=target,
                )
            )

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
            if gen:
                quality_report = dict(gen.quality_report or {})
                unresolved: list[str] = []
                for note in list(quality_report.get("notes") or []):
                    if not isinstance(note, dict):
                        continue
                    if str(note.get("severity") or "").lower() in {"fatal", "serious"}:
                        unresolved.append(
                            str(
                                note.get("violation_type")
                                or note.get("code")
                                or note.get("detail")
                                or "unresolved review finding"
                            )
                        )
                for section in ("structural_module_gate", "cross_scope_review"):
                    value = quality_report.get(section)
                    if not isinstance(value, dict):
                        continue
                    for finding in list(value.get("findings") or value.get("issues") or []):
                        if isinstance(finding, dict) and str(
                            finding.get("severity") or ""
                        ).lower() in {"fatal", "serious"}:
                            unresolved.append(
                                str(finding.get("code") or finding.get("detail") or section)
                            )
                if unresolved:
                    report.blockers.append(
                        ExportBlocker(
                            "lesson",
                            "unresolved_review_findings",
                            "; ".join(unresolved[:4]),
                            reel_id=reel.reel_id,
                        )
                    )

                semantic = dict(quality_report.get("semantic_contract") or {})
                if semantic.get("missing_fields") or semantic.get("remaining_filler_count"):
                    report.blockers.append(
                        ExportBlocker(
                            "lesson",
                            "semantic_contract_failure",
                            "Accepted lesson has missing semantic fields or filler",
                            reel_id=reel.reel_id,
                        )
                    )

                acceptance = dict(quality_report.get("final_text_acceptance") or {})
                actual_fingerprint = fingerprint_value(reel.script_text or "")
                acceptance_gates = (
                    "semantic_gate_passed",
                    "terminology_gate_passed",
                    "spoken_variety_gate_passed",
                    "teleprompter_gate_passed",
                )
                if not acceptance or not acceptance.get("accepted"):
                    report.blockers.append(
                        ExportBlocker(
                            "lesson",
                            "missing_final_text_acceptance",
                            "Saved lesson lacks a complete FINAL_TEXT_ACCEPTED record",
                            reel_id=reel.reel_id,
                        )
                    )
                elif acceptance.get("text_fingerprint") != actual_fingerprint:
                    report.blockers.append(
                        ExportBlocker(
                            "lesson",
                            "accepted_text_fingerprint_mismatch",
                            "Saved text changed after its final gate fingerprint",
                            reel_id=reel.reel_id,
                        )
                    )
                elif not all(acceptance.get(key) is True for key in acceptance_gates):
                    report.blockers.append(
                        ExportBlocker(
                            "lesson",
                            "incomplete_final_gate_record",
                            "One identical text fingerprint did not pass every final gate",
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
                language = (
                    quality_contract.language.model_dump(mode="json")
                    if quality_contract is not None
                    else {}
                )
                arabic = run_spoken_variety_integrity_gate(
                    body,
                    address_form=address_form,
                    spoken_variety=str(
                        language.get("presenter_dialect") or "egyptian"
                    ),
                    course_domain=(
                        quality_contract.pedagogy.course_domain
                        if quality_contract is not None
                        else ""
                    ),
                )
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
            hard_reason = words_outside_hard_range_reason(body, delivery_mode=mode)
            override = (
                dict((gen.quality_report or {}).get("hard_limit_override") or {})
                if gen
                else {}
            )
            override_valid = bool(
                thesis
                and thesis.human_override_hard_limits
                and str(override.get("reason") or "").strip()
                and str(override.get("scope") or "").strip() == reel.reel_id
                and str(
                    override.get("recorded_in_config_fingerprint") or ""
                ).strip()
                and (
                    expected_config_fingerprint is None
                    or override.get("recorded_in_config_fingerprint")
                    == expected_config_fingerprint
                )
            )
            if hard_reason and not override_valid:
                mode_range = word_range_for(mode)
                report.blockers.append(
                    ExportBlocker(
                        "lesson",
                        IssueCode.WORD_RANGE.value,
                        f"{hard_reason}; required={mode_range.hard_min}-{mode_range.hard_max}",
                        reel_id=reel.reel_id,
                    )
                )
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
            awkward_terms = default_terminology_map().find_awkward_literals(body)
            if awkward_terms:
                report.blockers.append(
                    ExportBlocker(
                        "lesson",
                        "terminology_failure",
                        "Awkward literal terms remain: " + ", ".join(awkward_terms),
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
    if evidence_ledger:
        from app.generation.evidence_provenance import mark_evidence_used_in_scripts

        marked = mark_evidence_used_in_scripts(
            evidence_ledger,
            [
                reel.script_text or ""
                for module in final_course.modules
                for reel in module.reels
            ],
        )
        for entry in marked.entries:
            if not entry.used_in_script:
                continue
            if entry.support_status not in {"supported", "omitted"}:
                report.blockers.append(
                    ExportBlocker(
                        "course",
                        IssueCode.UNSUPPORTED_CLAIM.value,
                        "A used claim remains weak or unsupported",
                    )
                )
            if entry.risk_flag and entry.support_status != "supported":
                report.blockers.append(
                    ExportBlocker(
                        "course",
                        "unresolved_high_stakes_claim",
                        "A used high-stakes claim lacks supported evidence",
                    )
                )

    try:
        from app.services.docx_verification import (
            DocxVerificationError,
            assert_final_course_ready_for_docx,
        )

        assert_final_course_ready_for_docx(final_course)
    except DocxVerificationError as exc:
        report.blockers.append(
            ExportBlocker(
                "course",
                IssueCode.TELEPROMPTER_LAYOUT_FAIL.value,
                str(exc),
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
        raise ExportBlockedError(f"DOCX export blocked — {details}")
