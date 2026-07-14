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

`self.last_usage` (AI Usage Center, §5) is set after every method call to
a small deterministic *synthetic* token estimate derived from input/output
text length - never real usage, since no real API call ever happens here.
`estimated_cost_usd` computed from this is always `0.0` (see
app/generation/orchestrator.py `_record_usage_event` - it recognizes
`provider == "fake"` and never applies real pricing to it), so this is
purely for UI/testing symmetry with `AnthropicProvider.last_usage`, never
mistakable for real spend.
"""

from pydantic import BaseModel

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


def _synthetic_usage(input_model: BaseModel, output_model: BaseModel) -> dict:
    """Deterministic, clearly-synthetic token estimate - roughly 4
    characters per token, the same rough heuristic often used to
    ballpark-estimate token counts without a real tokenizer."""
    input_chars = len(input_model.model_dump_json())
    output_chars = len(output_model.model_dump_json())
    return {
        "model": "fake",
        "input_tokens": max(1, input_chars // 4),
        "output_tokens": max(1, output_chars // 4),
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }


class FakeProvider(AIProvider):
    """Deterministic stand-in for a real AI provider. Calls no external API."""

    DEFAULT_MODULE_COUNT = 2
    DEFAULT_REELS_PER_MODULE = 3

    def __init__(self) -> None:
        # Same shape/purpose as `AnthropicProvider.last_usage` - see this
        # module's docstring for why costs derived from it are always 0.0.
        self.last_usage: dict | None = None

    def build_course_map(self, input: BuildCourseMapInput) -> CourseMap:
        modules: list[ModulePlan] = []
        for m_idx in range(1, self.DEFAULT_MODULE_COUNT + 1):
            module_id = f"m{m_idx}"
            reels = [
                ReelPlan(
                    reel_id=f"{module_id}-r{r_idx}",
                    # Same reasoning as the module title above: plain
                    # descriptive text, no "Reel N" self-numbering.
                    title=f"Fake lesson topic {r_idx} for module {m_idx}",
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
                    # Plain descriptive title, no "Module N:" prefix - the
                    # DOCX exporter (app/services/docx_export.py) is solely
                    # responsible for that numbering, so a title containing
                    # its own prefix would render doubled ("Module 1 —
                    # Module 1: ...").
                    title=f"Fake topic block {m_idx} for {input.brief.title}",
                    purpose=f"Fake purpose for module {m_idx}, building toward: {input.brief.outcome}",
                    bridge_project=(
                        f"Fake bridge project connecting module {m_idx} to module {m_idx + 1}"
                        if m_idx < self.DEFAULT_MODULE_COUNT
                        else None
                    ),
                    reels=reels,
                )
            )

        result = CourseMap(
            course_title=input.brief.title,
            main_thread=f"Fake main thread connecting all modules toward: {input.brief.outcome}",
            modules=modules,
        )
        self.last_usage = _synthetic_usage(input, result)
        return result

    def write_single_reel(self, input: WriteSingleReelInput) -> GeneratedReel:
        used_ideas = list(input.reel.must_cover)
        used_examples = [f"Fake example illustrating '{input.reel.title}'"]

        # Deliberately written as spoken-style placeholder lines, not
        # labeled meta text (no "Purpose:"/"- covers:" style notes) - even
        # fake output should already look like a lecturer script, not
        # internal planning notes, per the teleprompter DOCX contract.
        script_lines = [
            f"يلا نبدأ في {input.reel.title} على طول من غير مقدمات.",
            *[f"النقطة دي مهمة: {point}." for point in input.reel.must_cover],
            "كده كفاية للجزء ده، وجاهزين نكمل اللي جاي بعده.",
        ]

        result = GeneratedReel(
            reel_id=input.reel.reel_id,
            module_id=input.module.module_id,
            title=input.reel.title,
            script_text="\n".join(script_lines),
            used_ideas=used_ideas,
            used_examples=used_examples,
            self_check_status=ReviewStatus.PASS,
        )
        self.last_usage = _synthetic_usage(input, result)
        return result

    def review_single_reel(self, input: ReviewSingleReelInput) -> ReviewResult:
        empty = [input.generated_reel] if not input.generated_reel.script_text.strip() else []
        result = _result_for(ReviewScope.REEL, empty)
        self.last_usage = _synthetic_usage(input, result)
        return result

    def review_five_reels(self, input: ReviewFiveReelsInput) -> ReviewResult:
        empty = [r for r in input.reels if not r.script_text.strip()]
        result = _result_for(ReviewScope.FIVE_REELS, empty)
        self.last_usage = _synthetic_usage(input, result)
        return result

    def review_module(self, input: ReviewModuleInput) -> ReviewResult:
        empty = [r for r in input.reels if not r.script_text.strip()]
        result = _result_for(ReviewScope.MODULE, empty)
        self.last_usage = _synthetic_usage(input, result)
        return result

    def review_two_modules(self, input: ReviewTwoModulesInput) -> ReviewResult:
        all_reels = input.first.reels + input.second.reels
        empty = [r for r in all_reels if not r.script_text.strip()]
        result = _result_for(ReviewScope.TWO_MODULES, empty)
        self.last_usage = _synthetic_usage(input, result)
        return result

    def final_review(self, input: FinalReviewInput) -> ReviewResult:
        empty = [r for r in input.all_reels if not r.script_text.strip()]
        result = _result_for(ReviewScope.FINAL, empty)
        self.last_usage = _synthetic_usage(input, result)
        return result

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

        result = FinalCourse(
            title=input.course_map.course_title,
            modules=final_modules,
            full_text="\n\n".join(sections),
        )
        self.last_usage = _synthetic_usage(input, result)
        return result
