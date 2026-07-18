"""Structural module review — actionable, no no-op AI logging."""

from __future__ import annotations

from app.schemas.generation import (
    GeneratedReel,
    ModulePlan,
    ReviewAction,
    ReviewActionType,
    ReviewResult,
    ReviewScope,
    ReviewStatus,
)


def review_module_structure(
    *,
    module: ModulePlan,
    reels: list[GeneratedReel],
) -> ReviewResult:
    actions: list[ReviewAction] = []
    for reel in reels:
        status = (reel.quality_status or "").lower()
        if not (reel.script_text or "").strip():
            actions.append(
                ReviewAction(
                    action=ReviewActionType.REWRITE,
                    target_id=reel.reel_id,
                    reason_code="empty_script",
                    instruction="Rewrite empty lesson with real teaching content.",
                    severity="fatal",
                    requires_rewrite=True,
                )
            )
        elif status in {
            "needs_review",
            "needs_sources",
            "needs_map_revision",
            "needs_expert_review",
            "fail",
        }:
            actions.append(
                ReviewAction(
                    action=ReviewActionType.REWRITE,
                    target_id=reel.reel_id,
                    reason_code=status,
                    instruction=f"Repair lesson marked {status}.",
                    severity="serious",
                    requires_rewrite=True,
                )
            )

    if module.module_project is None and not (module.bridge_project or "").strip():
        actions.append(
            ReviewAction(
                action=ReviewActionType.ADD_MISSING_CONTEXT,
                target_id=module.module_id,
                reason_code="needs_map_revision",
                instruction="Module missing checkpoint/project — revise map architecture.",
                severity="serious",
                requires_rewrite=False,
                affects_map_or_other_lessons=True,
            )
        )

    status = ReviewStatus.NEEDS_REVISION if actions else ReviewStatus.PASS
    return ReviewResult(scope=ReviewScope.MODULE, status=status, actions=actions)
