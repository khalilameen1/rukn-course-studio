"""Integrated Editorial Review — Student + Critic + Mentor as one structured review.

Produces actionable notes. Creator remains the only writer of Final Master.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.generation.egyptian_arabic_gate import run_spoken_variety_integrity_gate
from app.generation.master_mentor import mentor_advice_hints_for_script
from app.generation.specialist_critic import CRITIC_LEAK_SUBSTRINGS
from app.generation.student_confusion import student_clarity_hints_for_script
from app.generation.terminology_map import default_terminology_map
from app.models.enums import AddressForm, GenerationQualityMode
from app.schemas.generation import (
    GeneratedReel,
    ReelPlan,
    ReviewAction,
    ReviewActionType,
    ReviewResult,
    ReviewScope,
    ReviewStatus,
)

MAX_CREATOR_REWRITES = 2


@dataclass
class EditorialNote:
    violation_type: str
    severity: str  # fatal | serious | minor
    evidence: str
    required_repair: str
    requires_rewrite: bool = True
    affects_map_or_other_lessons: bool = False

    def to_review_action(self, target_id: str) -> ReviewAction:
        return ReviewAction(
            action=ReviewActionType.REWRITE
            if self.requires_rewrite
            else ReviewActionType.KEEP,
            target_id=target_id,
            reason_code=self.violation_type,
            instruction=self.required_repair,
            violation_type=self.violation_type,
            severity=self.severity,
            evidence=self.evidence,
            required_repair=self.required_repair,
            requires_rewrite=self.requires_rewrite,
            affects_map_or_other_lessons=self.affects_map_or_other_lessons,
        )


@dataclass
class IntegratedEditorialReport:
    notes: list[EditorialNote] = field(default_factory=list)
    status: ReviewStatus = ReviewStatus.PASS

    def model_dump(self) -> dict:
        return {
            "status": self.status.value,
            "notes": [
                {
                    "violation_type": n.violation_type,
                    "severity": n.severity,
                    "evidence": n.evidence,
                    "required_repair": n.required_repair,
                    "requires_rewrite": n.requires_rewrite,
                    "affects_map_or_other_lessons": n.affects_map_or_other_lessons,
                }
                for n in self.notes
            ],
        }


def _has_substantive(notes: list[EditorialNote]) -> bool:
    return any(n.severity in ("fatal", "serious") for n in notes)


def run_integrated_editorial_review(
    *,
    reel_plan: ReelPlan,
    draft: GeneratedReel,
    prior_scripts: list[str],
    address_form: AddressForm = AddressForm.MASCULINE,
    quality_mode: GenerationQualityMode = GenerationQualityMode.PREMIUM,
    provider_review: ReviewResult | None = None,
    language_profile: dict | None = None,
    course_domain: str = "",
) -> IntegratedEditorialReport:
    """Deterministic + optional provider notes → one structured report."""
    notes: list[EditorialNote] = []
    text = draft.script_text or ""

    if not text.strip():
        notes.append(
            EditorialNote(
                "empty_script",
                "fatal",
                "",
                "Write a real spoken Final Master — script is empty.",
            )
        )

    profile = dict(language_profile or {})
    if bool(profile.get("apply_egyptian_spoken_qa", True)):
        arabic = run_spoken_variety_integrity_gate(
            text,
            address_form=address_form,
            spoken_variety=str(profile.get("presenter_dialect") or "egyptian"),
            course_domain=course_domain,
        )
        for issue in arabic.issues:
            notes.append(
                EditorialNote(
                    issue.code,
                    issue.severity,
                    issue.detail,
                    f"Rewrite in natural spoken Egyptian while preserving every semantic contract field: {issue.detail}",
                    requires_rewrite=issue.severity != "minor",
                )
            )

    awkward = default_terminology_map().find_awkward_literals(text)
    for term in awkward:
        notes.append(
            EditorialNote(
                "awkward_terminology",
                "serious",
                term,
                f"Replace literal «{term}» with natural spoken phrasing first.",
            )
        )

    # Student clarity (compact hints).
    for hint in student_clarity_hints_for_script(text)[:4]:
        detail = getattr(hint, "detail", str(hint))
        notes.append(
            EditorialNote(
                getattr(hint, "reason_code", "student_clarity"),
                "serious",
                detail[:160],
                f"Clarify for a confused student: {detail}",
            )
        )

    for hint in mentor_advice_hints_for_script(text)[:3]:
        detail = getattr(hint, "detail", str(hint))
        notes.append(
            EditorialNote(
                getattr(hint, "reason_code", "mentor_craft"),
                "minor",
                detail[:160],
                f"Improve spoken craft: {detail}",
                requires_rewrite=False,
            )
        )

    # Critic leak presence in draft is fatal for export cleanliness.
    lower = text.lower()
    for leak in CRITIC_LEAK_SUBSTRINGS:
        if leak.lower() in lower:
            notes.append(
                EditorialNote(
                    "review_leak",
                    "fatal",
                    leak,
                    "Remove review/critic metadata from spoken script.",
                )
            )

    # Thin teaching: very short scripts with no concrete teaching payload.
    words = text.split()
    cover = [p for p in (reel_plan.must_cover or []) if (p or "").strip()]
    if 0 < len(words) < 40:
        cover_reflected = bool(cover) and any((p or "").lower() in lower for p in cover[:2])
        # If must_cover is set, require reflection; if unset, still reject shell scripts.
        if cover and not cover_reflected:
            notes.append(
                EditorialNote(
                    "empty_teaching",
                    "fatal",
                    f"only {len(words)} words; must_cover not taught",
                    "Teach a real skill/decision — short empty reel is not allowed.",
                )
            )
        elif not cover and len(words) < 12:
            notes.append(
                EditorialNote(
                    "empty_teaching",
                    "fatal",
                    f"only {len(words)} words",
                    "Teach a real skill/decision — short empty reel is not allowed.",
                )
            )

    # Provider bundle notes (Premium).
    if provider_review and provider_review.status != ReviewStatus.PASS:
        for action in provider_review.actions:
            sev = "serious"
            code = (action.reason_code or "review").lower()
            if code in {"empty_script", "hallucination", "fatal"}:
                sev = "fatal"
            notes.append(
                EditorialNote(
                    code,
                    sev,
                    (action.instruction or "")[:180],
                    action.instruction or "Apply structured repair in Creator rewrite.",
                    requires_rewrite=True,
                    affects_map_or_other_lessons=code
                    in {"merge", "delete", "repetition", "duplicate"},
                )
            )

    # Duplication vs prior lessons.
    if prior_scripts and text.strip():
        from app.validators.similarity import text_similarity

        for prev in prior_scripts[-12:]:
            # High bar — template shells with different skill tokens must not
            # false-positive; real restatements still trip ~0.9+.
            if text_similarity(text, prev) >= 0.92:
                notes.append(
                    EditorialNote(
                        "semantic_repetition",
                        "serious",
                        "high similarity to a prior lesson",
                        "Rewrite with a new skill/decision; do not restate prior lesson.",
                        affects_map_or_other_lessons=True,
                    )
                )
                break

    status = (
        ReviewStatus.NEEDS_REVISION if _has_substantive(notes) else ReviewStatus.PASS
    )
    # Preview still runs gates but tolerates minor-only.
    if quality_mode == GenerationQualityMode.PREVIEW and not any(
        n.severity == "fatal" for n in notes
    ):
        # Keep serious issues — Preview is cheaper, not a quality bypass.
        pass
    return IntegratedEditorialReport(notes=notes, status=status)


def review_result_from_editorial(
    report: IntegratedEditorialReport, *, target_id: str
) -> ReviewResult:
    actions = [n.to_review_action(target_id) for n in report.notes if n.requires_rewrite]
    return ReviewResult(
        scope=ReviewScope.REEL,
        status=report.status,
        actions=actions,
    )


def unresolved_fatal_or_serious(report: IntegratedEditorialReport) -> bool:
    return any(n.severity in ("fatal", "serious") for n in report.notes)
