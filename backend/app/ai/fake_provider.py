"""Deterministic fake AIProvider - no real API calls.

Every method is a pure function of its input: same input in, exact same
output out, every time (no randomness, no clock, no network). This exists
so the generation orchestrator and its tests can be built against a
working, fast, free `AIProvider` before any real model is wired in - see
docs/BUILD_PLAN.md Phase 4+.

`review_*` methods do the one bit of real "logic" a fake can meaningfully
do: flag reels whose `script_text` is empty as needing a rewrite. This lets
pipeline tests exercise both the pass path and the revision path without
needing an actual model to judge quality.
"""

from app.ai.provider import (
    AIProvider,
    BuildCourseMapInput,
    FinalReviewInput,
    RebuildFinalCourseInput,
    ReviewFiveReelsInput,
    ReviewModuleInput,
    ReviewSingleReelInput,
    ReviewTwoModulesInput,
    WriteSingleReelInput,
)
from app.schemas.generation import (
    CourseMap,
    FinalCourse,
    FinalModule,
    FinalReel,
    GeneratedReel,
    ModulePlan,
    ReelPlan,
    ReviewAction,
    ReviewActionType,
    ReviewResult,
    ReviewScope,
    ReviewStatus,
)


def _empty_script_action(reel: GeneratedReel) -> ReviewAction:
    return ReviewAction(
        action=ReviewActionType.REWRITE,
        target_id=reel.reel_id,
        reason_code="empty_script",
        instruction=f"Reel '{reel.title}' has no script text - regenerate it.",
    )


def _result_for(scope: ReviewScope, empty_reels: list[GeneratedReel]) -> ReviewResult:
    if not empty_reels:
        return ReviewResult(scope=scope, status=ReviewStatus.PASS, actions=[])
    return ReviewResult(
        scope=scope,
        status=ReviewStatus.NEEDS_REVISION,
        actions=[_empty_script_action(reel) for reel in empty_reels],
    )


class FakeProvider(AIProvider):
    """Deterministic stand-in for a real AI provider. Calls no external API."""

    DEFAULT_MODULE_COUNT = 2
    DEFAULT_REELS_PER_MODULE = 3

    def build_course_map(self, input: BuildCourseMapInput) -> CourseMap:
        modules: list[ModulePlan] = []
        for m_idx in range(1, self.DEFAULT_MODULE_COUNT + 1):
            module_id = f"m{m_idx}"
            reels = [
                ReelPlan(
                    reel_id=f"{module_id}-r{r_idx}",
                    title=f"{input.brief.title} - Module {m_idx} Reel {r_idx}",
                    purpose=f"Fake purpose for module {m_idx} reel {r_idx}.",
                    # Includes m_idx so must_cover is unique across the whole
                    # course, not just within one module - otherwise every
                    # module's "reel 1" would look like a repeat of every
                    # other module's "reel 1" to the repetition checker.
                    must_cover=[f"fake point {m_idx}.{r_idx}.1", f"fake point {m_idx}.{r_idx}.2"],
                    must_avoid=["repeating an earlier reel's example"],
                    source_hints=[f"source:{s.source_id}" for s in input.sources],
                    estimated_length="45-60 seconds",
                )
                for r_idx in range(1, self.DEFAULT_REELS_PER_MODULE + 1)
            ]
            modules.append(
                ModulePlan(
                    module_id=module_id,
                    title=f"Module {m_idx}: {input.brief.title}",
                    purpose=f"Fake purpose for module {m_idx}, building toward: {input.brief.outcome}",
                    bridge_project=(
                        f"Fake bridge project connecting module {m_idx} to module {m_idx + 1}"
                        if m_idx < self.DEFAULT_MODULE_COUNT
                        else None
                    ),
                    reels=reels,
                )
            )

        return CourseMap(
            course_title=input.brief.title,
            main_thread=f"Fake main thread connecting all modules toward: {input.brief.outcome}",
            modules=modules,
        )

    def write_single_reel(self, input: WriteSingleReelInput) -> GeneratedReel:
        used_ideas = list(input.reel.must_cover)
        used_examples = [f"Fake example illustrating '{input.reel.title}'"]

        script_lines = [
            f"[FAKE SCRIPT] {input.reel.title}",
            f"Purpose: {input.reel.purpose}",
            *[f"- covers: {point}" for point in input.reel.must_cover],
        ]

        return GeneratedReel(
            reel_id=input.reel.reel_id,
            module_id=input.module.module_id,
            title=input.reel.title,
            script_text="\n".join(script_lines),
            used_ideas=used_ideas,
            used_examples=used_examples,
            self_check_status=ReviewStatus.PASS,
        )

    def review_single_reel(self, input: ReviewSingleReelInput) -> ReviewResult:
        empty = [input.generated_reel] if not input.generated_reel.script_text.strip() else []
        return _result_for(ReviewScope.REEL, empty)

    def review_five_reels(self, input: ReviewFiveReelsInput) -> ReviewResult:
        empty = [r for r in input.reels if not r.script_text.strip()]
        return _result_for(ReviewScope.FIVE_REELS, empty)

    def review_module(self, input: ReviewModuleInput) -> ReviewResult:
        empty = [r for r in input.reels if not r.script_text.strip()]
        return _result_for(ReviewScope.MODULE, empty)

    def review_two_modules(self, input: ReviewTwoModulesInput) -> ReviewResult:
        all_reels = input.first.reels + input.second.reels
        empty = [r for r in all_reels if not r.script_text.strip()]
        return _result_for(ReviewScope.TWO_MODULES, empty)

    def final_review(self, input: FinalReviewInput) -> ReviewResult:
        empty = [r for r in input.all_reels if not r.script_text.strip()]
        return _result_for(ReviewScope.FINAL, empty)

    def rebuild_final_course(self, input: RebuildFinalCourseInput) -> FinalCourse:
        sections: list[str] = []
        final_modules: list[FinalModule] = []

        for module in input.course_map.modules:
            sections.append(f"# {module.title}")
            module_reels = [r for r in input.all_reels if r.module_id == module.module_id]

            final_reels: list[FinalReel] = []
            for reel in module_reels:
                sections.append(f"## {reel.title}")
                sections.append(reel.script_text)
                final_reels.append(
                    FinalReel(reel_id=reel.reel_id, title=reel.title, script_text=reel.script_text)
                )

            if module.bridge_project:
                sections.append(f"[Bridge project] {module.bridge_project}")

            final_modules.append(
                FinalModule(
                    module_id=module.module_id,
                    title=module.title,
                    bridge_project=module.bridge_project,
                    reels=final_reels,
                )
            )

        return FinalCourse(
            title=input.course_map.course_title,
            modules=final_modules,
            full_text="\n\n".join(sections),
        )
