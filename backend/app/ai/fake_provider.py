"""Deterministic fake AIProvider - no real API calls.

Infrastructure / pipeline stand-in only — NOT a production quality oracle.
Tests using FakeProvider must not be labeled as quality assurance of Arabic
spoken craft; use golden Arabic fixtures for that.
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
from app.generation.contracts.spoken_final_master import beats_to_plain_script
from app.generation.duration_policy import word_range_for
from app.models.enums import LessonDeliveryMode
from app.schemas.generation import (
    CourseMap,
    FinalCourse,
    FinalModule,
    FinalReel,
    GeneratedReel,
    ModulePlan,
    ModuleProject,
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
        violation_type="empty_script",
        severity="fatal",
        required_repair=f"Reel '{reel.title}' has no script text - regenerate it.",
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
    input_chars = len(input_model.model_dump_json())
    output_chars = len(output_model.model_dump_json())
    return {
        "model": "fake",
        "input_tokens": max(1, input_chars // 4),
        "output_tokens": max(1, output_chars // 4),
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }


_FAKE_SKILLS = (
    ("Contrast hierarchy", "decide visual weight", "contrast-weight"),
    ("Thumb-zone CTA", "place tap targets", "thumb-cta"),
    ("Before-after clarity", "compare messy vs clear", "before-after"),
    ("Export checklist", "export without quality loss", "export-check"),
    ("Color role mapping", "assign color jobs", "color-roles"),
    ("Crop for story", "crop for mobile story", "story-crop"),
    ("Type scale ladder", "set readable type scale", "type-scale"),
    ("Safe-margin frame", "protect edge content", "safe-margin"),
    ("Offer stack order", "order offer hierarchy", "offer-stack"),
    ("Caption skim path", "write skimmable caption", "caption-skim"),
    ("Light direction fix", "fix flat lighting", "light-fix"),
    ("Audio ducking mix", "duck music under voice", "audio-duck"),
    ("Retention beat map", "place retention beats", "retention-map"),
    ("Brand mark quiet", "place logo without noise", "brand-quiet"),
    ("Proof shot select", "pick strongest proof shot", "proof-shot"),
)


def _delivery_for_index(r_idx: int) -> LessonDeliveryMode:
    modes = [
        LessonDeliveryMode.CAMERA_EXPLAINER,
        LessonDeliveryMode.SCREEN_DEMO,
        LessonDeliveryMode.BEFORE_AFTER,
        LessonDeliveryMode.ERROR_FIX,
        LessonDeliveryMode.PROJECT_BUILD,
        LessonDeliveryMode.MICRO_CONCEPT,
    ]
    return modes[(r_idx - 1) % len(modes)]


class FakeProvider(AIProvider):
    """Deterministic stand-in for a real AI provider. Calls no external API."""

    DEFAULT_MODULE_COUNT = 2
    DEFAULT_REELS_PER_MODULE = 3

    def __init__(self) -> None:
        self.last_usage: dict | None = None

    def build_course_map(self, input: BuildCourseMapInput) -> CourseMap:
        # Content-sized estimates — never inflate to a Premium minute floor.
        phase = (input.map_phase or "first_draft").strip().lower()
        deepen = phase == "final_master"

        modules: list[ModulePlan] = []
        skill_i = 0
        for m_idx in range(1, self.DEFAULT_MODULE_COUNT + 1):
            module_id = f"m{m_idx}"
            reels: list[ReelPlan] = []
            for r_idx in range(1, self.DEFAULT_REELS_PER_MODULE + 1):
                mode = _delivery_for_index(r_idx)
                rng = word_range_for(mode)
                needs_visual = mode in {
                    LessonDeliveryMode.SCREEN_DEMO,
                    LessonDeliveryMode.PROJECT_BUILD,
                    LessonDeliveryMode.BEFORE_AFTER,
                }
                skill_title, skill_decision, skill_slug = _FAKE_SKILLS[
                    skill_i % len(_FAKE_SKILLS)
                ]
                skill_i += 1
                reels.append(
                    ReelPlan(
                        reel_id=f"{module_id}-r{r_idx}",
                        title=f"{skill_title} (M{m_idx}L{r_idx})",
                        purpose=(
                            f"Teach {skill_decision} for module {m_idx} "
                            f"using {skill_slug} — unrelated to other lessons."
                        ),
                        must_cover=[
                            f"{skill_slug}-point-a",
                            f"{skill_slug}-point-b",
                        ],
                        must_avoid=["repeating an earlier reel's example"],
                        source_hints=[f"source:{s.source_id}" for s in input.sources],
                        estimated_length=f"{(rng.target_min + rng.target_max) / 2 / 135:.1f} minutes",
                        distinct_teaching_outcome=(
                            f"Student can {skill_decision} ({skill_slug}) without help"
                        ),
                        new_skill_or_decision=skill_decision,
                        why_standalone=(
                            f"{skill_slug} is a separate decision from neighboring lessons"
                        ),
                        student_can_do_after=f"يطبق {skill_slug}",
                        delivery_mode=mode,
                        target_spoken_words_min=rng.target_min,
                        target_spoken_words_max=rng.target_max,
                        needs_screen_or_visual=needs_visual,
                        internal_visual_plan=(
                            f"Show screen steps for {skill_slug}"
                            if needs_visual
                            else ""
                        ),
                        required_assets=[f"{skill_slug}.png"] if needs_visual else [],
                        project_contribution=f"Feeds module {m_idx} project via {skill_slug}",
                        needs_natural_bridge=r_idx < self.DEFAULT_REELS_PER_MODULE,
                    )
                )
            is_last = m_idx == self.DEFAULT_MODULE_COUNT
            project = ModuleProject(
                name=f"مشروع موديول {m_idx}",
                brief=(
                    f"نفّذ تمرين تطبيقي يجمع مهارات الموديول {m_idx} في تسليم واحد"
                    if not is_last
                    else f"طبّق مهارات الموديول {m_idx} في تسليم قصير قابل للمراجعة"
                ),
                inputs_or_files=["ملف تمرين"],
                deliverable_shape="لقطة شاشة + ملف نهائي",
                pass_criteria=["ينفّذ الخطوات", "يوضح القرار"],
                skills_tested=[f"skill-{m_idx}"],
            )
            modules.append(
                ModulePlan(
                    module_id=module_id,
                    title=f"Fake topic block {m_idx} for {input.brief.title}",
                    purpose=(
                        f"Module {m_idx} role: "
                        f"{'foundation' if m_idx == 1 else 'application'} — "
                        f"toward {input.brief.outcome}"
                        if deepen
                        else (
                            f"Fake purpose for module {m_idx}, building toward: "
                            f"{input.brief.outcome}"
                        )
                    ),
                    bridge_project=None,
                    module_project=project,
                    continuous_case=f"Continuous case for {input.brief.title} module {m_idx}",
                    reels=reels,
                )
            )

        result = CourseMap(
            course_title=input.brief.title,
            main_thread=f"Fake main thread connecting all modules toward: {input.brief.outcome}",
            modules=modules,
            graduation_project=ModuleProject(
                name="مشروع التخرج",
                brief=input.brief.outcome or "Final practical deliverable",
                deliverable_shape="مشروع نهائي كامل",
                pass_criteria=["يغطي مهارات الكورس"],
                skills_tested=["capstone"],
            ),
        )
        self.last_usage = _synthetic_usage(input, result)
        return result

    def write_single_reel(self, input: WriteSingleReelInput) -> GeneratedReel:
        rid = input.reel.reel_id or "r0"
        cover0 = (input.reel.must_cover or ["point"])[0]
        used_ideas = list(input.reel.must_cover)
        used_examples = [
            (
                f"Unique case {rid}/{cover0}: "
                f"{input.reel.new_skill_or_decision or input.reel.title}"
            )
        ]

        mode = input.reel.delivery_mode or LessonDeliveryMode.CAMERA_EXPLAINER
        phase = (input.write_phase or "first_draft").strip().lower()
        ledger_blob = " ".join(
            str(v)
            for v in (input.rules_context or {}).values()
            if isinstance(v, str) and "Phrase ledger" in v
        )
        # Unique opener per reel_id — never share opening template across lessons.
        opener = (
            f"في {rid} القرار الأساسي هو {cover0} جوّه موضوع {input.reel.title}"
        )
        if "Overused templates" in ledger_blob:
            opener = (
                f"قياس نجاح {cover0} في {rid} لازم يبان من أول تطبيق على {input.reel.title}"
            )

        skill = (input.reel.new_skill_or_decision or cover0).strip()
        body = [
            f"نفّذ {point} كخطوة مستقلة مرتبطة بـ {rid} ومهارة {skill} فقط"
            for point in input.reel.must_cover
        ]
        if mode == LessonDeliveryMode.MICRO_CONCEPT:
            body = body[:1] + [
                f"الفكرة الضيقة هنا هي {skill} ومش هتتوسع لبره {rid}",
            ]
        elif mode in {LessonDeliveryMode.SCREEN_DEMO, LessonDeliveryMode.PROJECT_BUILD}:
            body = body + [
                f"افتح شاشة {rid} ونفّذ {cover0} قدامك لمهارة {skill}",
                f"راجع ناتج {rid} وتأكد إن {cover0} اتحقق داخل {skill}",
            ]
        elif mode == LessonDeliveryMode.BEFORE_AFTER:
            body = body + [
                f"قارن قبل/بعد لـ {cover0} في حالة {rid} عشان تبين فرق {skill}",
            ]

        if input.reel.needs_natural_bridge:
            closer = (
                f"بعد ما تثبت {skill} في {rid} هيبان احتياج لقرار لاحق مبني على {cover0}"
            )
        else:
            closer = f"درس {rid} اتقفل على {skill} — تقدر تعيد {cover0} لوحدك"

        if phase == "final_master":
            if any("forbidden" in (f or "").lower() for f in input.previous_review_feedback):
                opener = f"ثبت {cover0} في {rid} من غير حشو جاهز حول {input.reel.title}"
            elif input.previous_review_feedback:
                body = list(body) + [
                    f"وضحنا تطبيق {cover0} داخل {rid} لمهارة {skill} من غير قفز",
                ]

        beats = [opener, *body, closer]
        rng = word_range_for(mode)
        fillers = [
            f"جرّب {cover0} على حالة جديدة تخص {rid} و{skill}",
            f"علامة نجاح {rid} تظهر لما {skill} يبقى قابل للقياس عبر {cover0}",
            f"لو {cover0} مش واضح أعِد خطوة {rid} بهدوء مع تركيز على {skill}",
            f"اربط {skill} بنتيجة شغلك اليومي في {input.reel.title} عبر {rid}",
            f"ممنوع تخلط {rid}/{skill} بدرس تاني وهو بيتشرح",
            f"اختبر {skill} مرة تانية على مثال مختلف تمامًا عن باقي الكورس",
        ]
        for line in fillers:
            if len(" ".join(beats).split()) >= max(rng.soft_min, 80):
                break
            beats.insert(-1, line)

        script = beats_to_plain_script(beats)
        result = GeneratedReel(
            reel_id=input.reel.reel_id,
            module_id=input.module.module_id,
            title=input.reel.title,
            script_text=script,
            spoken_beats=beats,
            used_ideas=used_ideas,
            used_examples=used_examples,
            self_check_status=ReviewStatus.PASS,
            delivery_mode=mode,
            quality_status="pass",
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
                    FinalReel(
                        reel_id=reel.reel_id,
                        title=reel.title,
                        script_text=reel.script_text,
                        spoken_beats=list(reel.spoken_beats or []),
                        delivery_mode=reel.delivery_mode,
                        quality_status=reel.quality_status,
                    )
                )

            final_modules.append(
                FinalModule(
                    module_id=module.module_id,
                    title=module.title,
                    bridge_project=module.bridge_project,
                    module_project=module.module_project,
                    reels=final_reels,
                )
            )

        result = FinalCourse(
            title=input.course_map.course_title,
            modules=final_modules,
            full_text="\n\n".join(sections),
            graduation_project=input.course_map.graduation_project,
            thesis=input.course_map.thesis,
        )
        self.last_usage = _synthetic_usage(input, result)
        return result
