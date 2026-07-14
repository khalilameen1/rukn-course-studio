"""ROKN Anti-Patterns and Quality Checks — rejection layer, no golden samples."""

from app.generation.knowledge_packs import (
    build_stage_rules_pack,
    stage_anti_patterns_quality_checks,
)
from app.generation.prompt_compiler import select_packed_rules_for_stage, select_rules_for_stage
from app.generation.teleprompter_checks import find_forbidden_substrings
from app.prompts.prompt_registry import PipelineStage
from app.schemas.generation import FinalCourse, FinalModule, FinalReel, GeneratedReel
from app.seed_admin_knowledge import (
    ANTI_PATTERNS_QUALITY_CHECKS,
    REQUIRED_KEYS,
    SEED_ITEMS,
)
from app.services.docx_export import extract_plain_text, render_final_course_docx
from app.validators.anti_patterns_checker import (
    article_has_no_positive_golden_samples,
    check_anti_patterns_script,
    find_admin_knowledge_leaks,
    scripts_avoid_template_writing,
)
from app.validators.anti_template_checker import check_anti_template

FLEXIBLE_SCRIPT_A = """\
قبل ما تختار نوع الإعلان، حدد هدف واضح من الحملة.

لو الميزانية صغيرة، ابدأ بتنسيق واحد وقياسه أسبوع قبل ما تضيف تعقيد.

الغلط الشائع إن الناس بتنسخ إعدادات حملة قديمة من غير ما تراجع الهدف الحالي.
"""

FLEXIBLE_SCRIPT_B = """\
لما العميل يبعت أصول ناقصة، اطلب نسخة أوضح مش أجمل.

واتساب بيحتاج رد سريع أكتر من إنستجرام في أغلب الحالات.

مش كل عميل محتاج نفس عدد التعديلات — ده قرار ميزانية ووقت.
"""

TEMPLATE_HOOK_SCRIPT = "محدش قالك السر اللي هتتصدم منه في الإعلانات."

WORD_PER_LINE_SCRIPT = "لو\nجربت\nكده\nقبل\nكده\nهتعرف\nالفرق\nفوراً."

DOCX_SCRIPT = """\
حدد هدف الإعلان قبل التنسيق.

لو الميزانية محدودة، ابدأ باختبار واحد واضح.
"""


def test_anti_patterns_in_seed_and_required_keys():
    assert "rukn_anti_patterns_quality_checks" in REQUIRED_KEYS
    keys = {item["key"] for item in SEED_ITEMS}
    assert "rukn_anti_patterns_quality_checks" in keys
    item = next(i for i in SEED_ITEMS if i["key"] == "rukn_anti_patterns_quality_checks")
    assert item["title"] == "ROKN Anti-Patterns and Quality Checks"
    assert item["content_text"] == ANTI_PATTERNS_QUALITY_CHECKS


def test_no_fixed_positive_examples_in_anti_patterns_article():
    assert article_has_no_positive_golden_samples(ANTI_PATTERNS_QUALITY_CHECKS)
    lower = ANTI_PATTERNS_QUALITY_CHECKS.lower()
    assert "rejected patterns" in lower
    assert "must not contain" in lower
    assert "fixed good examples" in lower or "examples to imitate" in lower
    # Retired spoken-style bank must not ship positive golden lines.
    style_bank = next(i for i in SEED_ITEMS if i["key"] == "rukn-spoken-style-bank")
    assert "retired" in style_bank["content_text"].lower()
    assert "example spoken-style lines" not in style_bank["content_text"].lower()
    assert "rukn_anti_patterns_quality_checks" in style_bank["content_text"]


def test_prompt_compiler_uses_anti_patterns_in_review_and_final_only():
    rules = {"rukn_anti_patterns_quality_checks": ANTI_PATTERNS_QUALITY_CHECKS}
    review_stages = (
        PipelineStage.REVIEW_SINGLE_REEL,
        PipelineStage.REVIEW_FIVE_REELS,
        PipelineStage.REVIEW_MODULE,
        PipelineStage.REVIEW_TWO_MODULES,
        PipelineStage.FINAL_REVIEW,
        PipelineStage.REBUILD_FINAL_COURSE,
    )
    for stage in review_stages:
        selected = select_rules_for_stage(rules, stage)
        assert "rukn_anti_patterns_quality_checks" in selected

    for stage in (PipelineStage.BUILD_COURSE_MAP, PipelineStage.WRITE_SINGLE_REEL):
        selected = select_rules_for_stage(rules, stage)
        assert "rukn_anti_patterns_quality_checks" not in selected


def test_packed_anti_patterns_are_rejection_layer_not_full_dump():
    full_len = len(ANTI_PATTERNS_QUALITY_CHECKS)
    review_slice = stage_anti_patterns_quality_checks(
        ANTI_PATTERNS_QUALITY_CHECKS, PipelineStage.REVIEW_SINGLE_REEL
    )
    final_slice = stage_anti_patterns_quality_checks(
        ANTI_PATTERNS_QUALITY_CHECKS, PipelineStage.FINAL_REVIEW
    )
    assert review_slice
    assert final_slice
    assert len(review_slice) < full_len // 2
    assert "rejection layer only" in review_slice.lower()
    assert "do not copy as a style template" in review_slice.lower()

    packed = select_packed_rules_for_stage(
        {"rukn_anti_patterns_quality_checks": ANTI_PATTERNS_QUALITY_CHECKS},
        PipelineStage.FINAL_REVIEW,
    )
    body = " ".join(packed.values())
    assert ANTI_PATTERNS_QUALITY_CHECKS not in body


def test_build_stage_rules_pack_slices_anti_patterns():
    selected = {"rukn_anti_patterns_quality_checks": ANTI_PATTERNS_QUALITY_CHECKS}
    packed = build_stage_rules_pack(selected, PipelineStage.REVIEW_SINGLE_REEL)
    body = packed.get("review_rules_pack", "")
    assert "anti_patterns_quality_checks" in body
    assert ANTI_PATTERNS_QUALITY_CHECKS not in body


def test_template_hooks_are_flagged():
    issues = check_anti_patterns_script(TEMPLATE_HOOK_SCRIPT, reel_id="r1")
    assert any(i.reason_code == "template_hook" for i in issues)


def test_teleprompter_over_formatting_is_flagged():
    issues = check_anti_patterns_script(WORD_PER_LINE_SCRIPT, reel_id="r1")
    assert any(i.reason_code == "teleprompter_over_formatting" for i in issues)

    pause_script = "النقطة واضحة.\n[pause]\nنكمل الخطوة."
    pause_issues = check_anti_patterns_script(pause_script, reel_id="r2")
    assert any(i.reason_code == "teleprompter_pause_labels" for i in pause_issues)


def test_final_docx_does_not_copy_admin_knowledge_phrases():
    course = FinalCourse(
        title="Ads",
        full_text="ignored",
        modules=[
            FinalModule(
                module_id="m1",
                title="Module 1",
                reels=[
                    FinalReel(
                        reel_id="m1-r1",
                        title="Lesson 1",
                        script_text=DOCX_SCRIPT,
                    )
                ],
            )
        ],
    )
    plain = extract_plain_text(render_final_course_docx(course))
    assert not find_admin_knowledge_leaks(plain)
    assert not find_forbidden_substrings(plain)
    assert "anti-patterns" not in plain.lower()


def test_repeated_template_hooks_flagged_across_reels():
    reels = [
        GeneratedReel(
            reel_id="r1",
            module_id="m1",
            title="a",
            script_text="خلّي بالك من الميزانية قبل ما تبدأ.\nتفاصيل.",
            self_check_status="pass",
        ),
        GeneratedReel(
            reel_id="r2",
            module_id="m1",
            title="b",
            script_text="خلّي بالك من الميزانية قبل ما تختار الجمهور.\nتفاصيل.",
            self_check_status="pass",
        ),
    ]
    issues = check_anti_template(reels)
    assert any(i.reason_code == "repeated_hook_family" for i in issues)


def test_flexible_scripts_not_flagged_as_template_machine():
    reels = [
        GeneratedReel(
            reel_id="r1",
            module_id="m1",
            title="a",
            script_text=FLEXIBLE_SCRIPT_A,
            self_check_status="pass",
        ),
        GeneratedReel(
            reel_id="r2",
            module_id="m1",
            title="b",
            script_text=FLEXIBLE_SCRIPT_B,
            self_check_status="pass",
        ),
        GeneratedReel(
            reel_id="r3",
            module_id="m1",
            title="c",
            script_text="قرار التوقيت مهم لما العميل بيتأخر في الرد.",
            self_check_status="pass",
        ),
    ]
    assert scripts_avoid_template_writing(reels)
    assert not check_anti_template(reels)
