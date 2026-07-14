"""Golden-style regression checks for rukn_high_signal_reel_doctrine.

Pure local validators + prompt-compiler authority - no live Anthropic calls.
Run with: pytest tests/golden -q
"""

from app.generation.prompt_compiler import SourceForCompiler, compile_source_context
from app.schemas.generation import GeneratedReel
from app.validators.anti_template_checker import check_anti_template
from app.validators.high_signal_checker import check_high_signal


def test_overhyped_hook_is_flagged():
    issues = check_high_signal("السر اللي محدش يعرفه في الإعلانات...")
    assert any(i.reason_code == "overhyped_hook" for i in issues)


def test_forced_next_reel_loop_is_flagged():
    issues = check_high_signal("النقطة واضحة. في الريل الجاي هنكمل.")
    assert any(i.reason_code == "forced_loop" for i in issues)


def test_generic_advice_is_flagged():
    issues = check_high_signal("اسعى للنجاح وكل حاجة هتظبط.")
    assert any(i.reason_code == "generic_advice" for i in issues)


def test_academic_tone_leakage_is_flagged():
    issues = check_high_signal("في ضوء ما سبق يمكن القول إن الإعلان مهم.")
    assert any(i.reason_code == "academic_tone" for i in issues)


def test_unrealistic_big_company_example_is_flagged():
    issues = check_high_signal("زي ما بيعملوا في Silicon Valley بالمليارات.")
    assert any(i.reason_code == "unrealistic_example" for i in issues)


def test_removable_filler_sentences_are_flagged():
    script = "يلا.\nمهم.\nبكده.\nودي النقطة الحقيقية عن ميزانية الموبايل."
    issues = check_high_signal(script)
    assert any(i.reason_code == "removable_filler" for i in issues)


def test_repeated_hook_family_across_reels():
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
            script_text="خلّي بالك من الميزانية في الموبايل.\nتفاصيل تانية.",
            self_check_status="pass",
        ),
    ]
    issues = check_anti_template(reels)
    assert any(i.reason_code == "repeated_hook_family" for i in issues)


def test_equal_word_counts_across_many_reels_flagged():
    body = " كلمة" * 40
    reels = [
        GeneratedReel(
            reel_id=f"r{i}",
            module_id="m1",
            title=f"t{i}",
            script_text=f"افتتاح مختلف رقم {i}.{body}",
            self_check_status="pass",
        )
        for i in range(3)
    ]
    issues = check_anti_template(reels)
    assert any(i.reason_code == "equal_length_padding" for i in issues)


def test_flow_reference_catchphrase_not_copied_into_profile():
    catchphrase = "يا نجم السوشيال المدفع"
    source = SourceForCompiler(
        source_id=1,
        category="flow_reference",
        priority="medium",
        text=(
            f"{catchphrase}! يلا نبدأ. بعدين نعلّي الشدة. "
            "بعدين نهدى. في الآخر نقفل بهدوء."
        )
        * 20,
        summary=None,
        chunks=None,
    )
    excerpts = compile_source_context([source], query_text="opening energy")
    assert len(excerpts) == 1
    assert catchphrase not in excerpts[0].text
    assert "human_flow" in excerpts[0].text.lower() or "pacing" in excerpts[0].text.lower()


def test_clean_local_high_signal_script_passes():
    script = (
        "لو بتعلن لمحل ملابس على الموبايل، ميزانية خمسين جنيه "
        "محتاجة استهداف أضيق من الإعلان العريض.\n"
        "الغلط الشائع إنك تدخل على جمهور كبير عشان الرخص، "
        "وبعدين الزيارات بتيجي من ناس بره الحي."
    )
    assert check_high_signal(script) == []
