"""Egyptian market reality + evergreen course gates."""

from app.ai.provider import CourseBrief
from app.generation.course_map_quality import local_map_review_feedback
from app.generation.course_quality_gates import run_course_quality_gates
from app.generation.market_evergreen import (
    MARKET_EVERGREEN_DOCX_LEAKS,
    compile_market_guidance,
    map_market_evergreen_feedback,
    rewrite_script_market_evergreen,
    scan_script_market_evergreen,
)
from app.generation.prompt_compiler import (
    PROMPT_COMPILER_VERSION,
    select_rules_for_stage,
)
from app.generation.teleprompter_checks import find_forbidden_substrings
from app.models.enums import (
    ExplanationLevel,
    GenerationQualityMode,
    StructureMode,
    TargetMarket,
)
from app.prompts.prompt_registry import PipelineStage
from app.schemas.generation import (
    CourseMap,
    FinalCourse,
    FinalModule,
    FinalReel,
    ModulePlan,
    ReelPlan,
)
from app.services.docx_export import extract_plain_text, render_final_course_docx


def _brief(**kw) -> CourseBrief:
    base = dict(
        title="Meta Ads for Egyptian shops",
        audience="shop owners",
        outcome="run profitable ads",
        special_notes=None,
        structure_mode=StructureMode.CONNECTED_MODULES_WITH_BRIDGE_PROJECTS,
        explanation_level=ExplanationLevel.FINAL_ONLY,
        target_market=TargetMarket.EGYPT,
    )
    base.update(kw)
    return CourseBrief(**base)


def _map_fragile_ui() -> CourseMap:
    return CourseMap(
        course_title="Ads",
        main_thread="ads",
        modules=[
            ModulePlan(
                module_id="m1",
                title="UI clicks",
                purpose="Click the blue button at the top left in Ads Manager",
                bridge_project=None,
                reels=[
                    ReelPlan(
                        reel_id="m1-r1",
                        title="Button path",
                        purpose="Go to Settings, then Advanced, then this exact tab",
                        estimated_length="20 minutes",
                        must_cover=["click the blue button top left"],
                    )
                ],
            )
        ],
    )


def test_translated_us_market_content_is_flagged_and_rebuilt():
    dirty = (
        "Furthermore it is worth noting that Silicon Valley Series A startups "
        "need a $10,000 ad budget and HubSpot Enterprise."
    )
    findings = scan_script_market_evergreen(dirty, target_market=TargetMarket.EGYPT)
    codes = {f.code for f in findings}
    assert "translated_tone" in codes or "foreign_market_assumption" in codes
    cleaned = rewrite_script_market_evergreen(dirty, target_market=TargetMarket.EGYPT)
    assert "silicon valley" not in cleaned.lower()
    assert "whatsapp" in cleaned.lower() or "واتساب" in cleaned or "محل" in cleaned


def test_egypt_target_market_guidance_and_local_examples():
    guide = compile_market_guidance(TargetMarket.EGYPT)
    assert "TARGET_MARKET=egypt" in guide
    assert "WhatsApp" in guide or "whatsapp" in guide.lower()
    out = rewrite_script_market_evergreen(
        "Leverage synergies with American clients in Silicon Valley.",
        target_market=TargetMarket.EGYPT,
    )
    assert "محل" in out or "عيادة" in out or "واتساب" in out or "whatsapp" in out.lower()


def test_expensive_foreign_tool_assumption_flagged():
    text = "You must buy Salesforce Enterprise before you can start."
    codes = {f.code for f in scan_script_market_evergreen(text)}
    assert "expensive_tool_assumption" in codes


def test_fragile_ui_button_location_rephrased():
    text = "Click the blue button at the top left to create the campaign."
    out = rewrite_script_market_evergreen(text, target_market=TargetMarket.EGYPT)
    assert "top left" not in out.lower()
    assert "دور على" in out or "المكان" in out


def test_short_lived_salary_price_date_flagged():
    text = "In 2026 the average salary is $5000 and currently the price is $99."
    codes = {f.code for f in scan_script_market_evergreen(text)}
    assert "short_lived_fact" in codes
    out = rewrite_script_market_evergreen(text)
    assert "in 2026" not in out.lower()
    assert "راجع السعر" in out or "السعر" not in out  # softened


def test_software_lesson_principle_not_only_clicks():
    text = (
        "Click the create button. Then press the next tab. "
        "Then tap the save menu. Done."
    )
    codes = {f.code for f in scan_script_market_evergreen(text)}
    assert "button_click_tutorial" in codes
    out = rewrite_script_market_evergreen(text)
    assert "القاعدة" in out or "الواجهة" in out


def test_evergreen_rewrite_stays_natural_without_disclaimer_spam():
    text = "Click the blue button at the top left once."
    out = rewrite_script_market_evergreen(text)
    # One principle beat is fine; not a wall of warnings.
    assert out.count("راجع السعر") <= 1
    assert "egyptian market gate" not in out.lower()
    assert "evergreen review" not in out.lower()


def test_final_docx_hides_market_evergreen_notes():
    course = FinalCourse(
        title="Course",
        full_text="",
        modules=[
            FinalModule(
                module_id="m1",
                title="Module",
                reels=[
                    FinalReel(
                        reel_id="m1-r1",
                        title="Lesson",
                        script_text=(
                            "علّم العميل المحلي على واتساب. "
                            "market analysis note: ignore. evergreen review: ignore."
                        ),
                    )
                ],
            )
        ],
    )
    out, _ = run_course_quality_gates(
        final_course=course, course_map=_map_fragile_ui(), brief=_brief()
    )
    plain = extract_plain_text(render_final_course_docx(out)).lower()
    assert find_forbidden_substrings(plain) == []
    for leak in MARKET_EVERGREEN_DOCX_LEAKS:
        assert leak not in plain


def test_course_map_fragile_ui_triggers_rebuild_feedback():
    fb = map_market_evergreen_feedback(
        _map_fragile_ui(), target_market=TargetMarket.EGYPT
    )
    assert any("Evergreen" in line or "UI" in line or "brittle" in line for line in fb)
    full = local_map_review_feedback(
        _map_fragile_ui(),
        quality_mode=GenerationQualityMode.PREMIUM,
        relax_floor=True,
        target_market=TargetMarket.EGYPT,
    )
    assert any("Evergreen" in line or "brittle" in line for line in full)


def test_target_market_passed_to_prompt_compiler_runtime():
    from app.data.course_standard import STANDARD_FILE_NAMES, load_standard_files

    assert PROMPT_COMPILER_VERSION == "3.0-rukn-standard-v1.3"
    guide = compile_market_guidance(TargetMarket.GLOBAL)
    assert "TARGET_MARKET=global" in guide
    selected = select_rules_for_stage(load_standard_files(), PipelineStage.WRITE_SINGLE_REEL)
    assert tuple(selected) == STANDARD_FILE_NAMES
    brief = _brief(target_market=TargetMarket.ARAB_MARKET)
    assert brief.target_market == TargetMarket.ARAB_MARKET
