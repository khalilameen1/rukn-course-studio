"""Golden / unit tests for the synthetic creator persona layer."""

from app.generation.creator_persona import (
    format_persona_for_prompt,
    plan_course_creator_persona,
    plan_lesson_persona_state,
    plan_module_persona_adjustment,
)
from app.generation.prompt_compiler import SourceForCompiler, compile_source_context
from app.generation.teleprompter_checks import find_forbidden_substrings
from app.schemas.generation import (
    FinalCourse,
    FinalModule,
    FinalReel,
    GeneratedReel,
    ModulePlan,
    ReelPlan,
)
from app.services.docx_export import extract_plain_text, render_final_course_docx
from app.validators.creator_persona_checker import (
    check_creator_persona_script,
    check_persona_allows_calm_non_viral,
    check_persona_allows_strong_corrective,
    flat_machine_script_flagged,
)
from app.validators.high_signal_checker import check_high_signal


def _module_with_reels() -> ModulePlan:
    return ModulePlan(
        module_id="m1",
        title="Ads fundamentals",
        purpose="foundation",
        reels=[
            ReelPlan(
                reel_id="m1-r1",
                title="Quiet definition",
                purpose="intro overview foundation",
                must_cover=["define"],
                estimated_length="short",
            ),
            ReelPlan(
                reel_id="m1-r2",
                title="Fix the myth",
                purpose="common mistake correction wrong default",
                must_cover=["wrong tip"],
                estimated_length="medium",
            ),
        ],
    )


def test_persona_does_not_copy_named_creator_or_catchphrase():
    issues = check_creator_persona_script(
        "زي ما بيقول أحمد دائماً في التريند: خليك نجم.",
        reel_id="r1",
    )
    assert any(i.reason_code == "named_creator_imitation" for i in issues)

    fake = check_creator_persona_script("يا نجم السوشيال المدفع هتنجح فوراً", reel_id="r1")
    assert any(i.reason_code == "fake_egyptian_ai_tone" for i in fake)


def test_persona_allows_calm_non_viral_lessons():
    course = plan_course_creator_persona(
        title="Photoshop ads", audience="beginners", outcome="usable ad"
    )
    module = _module_with_reels()
    adj = plan_module_persona_adjustment(
        module=module,
        module_index=0,
        total_modules=2,
        course_persona=course,
        module_role="foundation",
    )
    state = plan_lesson_persona_state(
        reel=module.reels[0],
        reel_index=0,
        reels_in_module=2,
        module_adjustment=adj,
        lesson_hook_strength="quiet",
    )
    assert check_persona_allows_calm_non_viral(state)
    assert state.viral_intent in ("quiet_useful", "technical_spine")


def test_persona_allows_strong_corrective_when_justified():
    course = plan_course_creator_persona(
        title="Meta ads", audience="shop owners", outcome="better ads"
    )
    module = _module_with_reels()
    adj = plan_module_persona_adjustment(
        module=module,
        module_index=1,
        total_modules=2,
        course_persona=course,
        module_role="correction",
    )
    state = plan_lesson_persona_state(
        reel=module.reels[1],
        reel_index=1,
        reels_in_module=2,
        module_adjustment=adj,
        lesson_teaching_energy="sharp",
    )
    assert check_persona_allows_strong_corrective(state)


def test_overhyped_ordinary_topic_flagged_when_quiet_intent():
    from app.generation.creator_persona import LessonPersonaState

    quiet = LessonPersonaState(
        real_point="define a term",
        misunderstanding_to_challenge="none",
        confidence_heat="quiet",
        save_share_reason="clarity",
        viral_intent="quiet_useful",
        fake_risk="hype",
    )
    issues = check_creator_persona_script(
        "السر اللي محدش يعرفه عن تعريف الزرار.",
        reel_id="r1",
        lesson_persona=quiet,
    )
    assert any(i.reason_code == "viral_when_should_be_quiet" for i in issues)
    assert any(i.reason_code == "overhyped_hook" for i in check_high_signal(
        "السر اللي محدش يعرفه عن تعريف الزرار."
    ))


def test_superlative_spam_and_flat_machine_flagged():
    spam = (
        "أكبر سر وأكبر غلط وأخطر حاجة وأكتر حاجة "
        "most important and biggest mistake and most dangerous tip."
    )
    issues = check_creator_persona_script(spam, reel_id="r1")
    assert any(i.reason_code == "superlative_spam" for i in issues)

    body = " كلمة" * 40
    reels = [
        GeneratedReel(
            reel_id=f"r{i}",
            module_id="m1",
            title=f"t{i}",
            script_text=f"نفس الافتتاح بالظبط.{body}",
            self_check_status="pass",
        )
        for i in range(3)
    ]
    assert flat_machine_script_flagged(reels) is True


def test_flow_reference_not_converted_into_creator_template():
    catchphrase = "يا نجم السوشيال المدفع"
    source = SourceForCompiler(
        source_id=1,
        category="flow_reference",
        priority="medium",
        text=(f"{catchphrase}! يلا نبدأ. بعدين نعلّي الشدة. بعدين نهدى. ") * 20,
        summary=None,
        chunks=None,
    )
    excerpts = compile_source_context([source], query_text="opening energy")
    assert catchphrase not in excerpts[0].text
    assert "template" not in excerpts[0].text.lower() or "never" in excerpts[0].text.lower()
    leak = check_creator_persona_script(
        "Following the creator template from flow_reference now.",
        reel_id="r1",
    )
    assert any(i.reason_code == "flow_template_leak" for i in leak)


def test_final_docx_does_not_expose_persona_planning_labels():
    final = FinalCourse(
        title="Clean Course",
        full_text="# Module One\n## Lesson One\nعلم واضح.",
        modules=[
            FinalModule(
                module_id="m1",
                title="Module One",
                reels=[
                    FinalReel(
                        reel_id="m1-r1",
                        title="Lesson One",
                        script_text="علم واضح من غير مبالغة.",
                    )
                ],
            )
        ],
    )
    text = extract_plain_text(render_final_course_docx(final)).lower()
    assert find_forbidden_substrings(text) == []
    for leak in (
        "course_creator_persona",
        "module_persona_adjustment",
        "lesson_persona_state",
        "viral_intent",
        "confidence_heat",
    ):
        assert leak not in text


def test_prompt_payload_includes_compact_persona_layers():
    course = plan_course_creator_persona(
        title="Excel", audience="staff", outcome="budget sheet"
    )
    module = _module_with_reels()
    adj = plan_module_persona_adjustment(
        module=module,
        module_index=0,
        total_modules=1,
        course_persona=course,
        module_role="foundation",
    )
    state = plan_lesson_persona_state(
        reel=module.reels[0],
        reel_index=0,
        reels_in_module=2,
        module_adjustment=adj,
    )
    payload = format_persona_for_prompt(course, adj, state)
    assert "domain_identity" in payload["course_creator_persona"]
    assert "module_feel" in payload["module_persona_adjustment"]
    assert "viral_intent" in payload["lesson_persona_state"]
    assert "imitate" in payload["course_creator_persona"]["things_this_persona_would_never_do"].lower()
