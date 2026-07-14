"""ROKN Educational Creator Standard — Admin Knowledge + prompt + script checks."""

from app.generation.knowledge_packs import (
    build_stage_rules_pack,
    stage_educational_creator_standard,
)
from app.generation.prompt_compiler import select_packed_rules_for_stage, select_rules_for_stage
from app.generation.teleprompter_checks import find_forbidden_substrings
from app.prompts.prompt_registry import PipelineStage
from app.schemas.generation import FinalCourse, FinalModule, FinalReel
from app.seed_admin_knowledge import (
    EDUCATIONAL_CREATOR_STANDARD,
    REQUIRED_KEYS,
    SEED_ITEMS,
)
from app.services.docx_export import extract_plain_text, render_final_course_docx
from app.validators.creator_persona_checker import (
    check_creator_persona_script,
    script_has_field_aware_practical_tone,
    script_passes_educational_creator_warmth,
)

GOOD_PRACTITIONER_SCRIPT = """\
خليني أوضح لك الحتة دي بسرعة.

الغلط هنا إن ناس كتير بتفهم الموضوع بالعكس لما الميزانية صغيرة والعميل مش واضح.

اللي يفرق معاك عمليًا في الشغل الحقيقي هو إنك تحدد هدف الإعلان قبل ما تختار التنسيق.

مش كل الحالات ينفع معها نفس الحل — واتساب وفيسبوك بيختلفوا في سرعة الرد والمتابعة.

هنا بقى لازم ناخد بالنا من قرار بسيط: لو العميل بيبعت أصول ناقصة، اشتغل على نسخة أوضح مش نسخة أجمل.
"""

GENERIC_AI_SCRIPT = """\
Furthermore, it is important to note that marketing requires strategy.

Moreover, in conclusion we can say that ads are useful for business growth.
"""

COURSE_SELLER_SCRIPT = """\
سجل دلوقتي واحجز مقعدك في الكورس قبل ما العرض محدود يخلص.

هتتعلم أسرار الإعلانات في دقائق.
"""

FAKE_BIO_SCRIPT = """\
لما كنت بشتغل في شركة كبيرة، أنا شخصياً عملت حملات لعميل كنت بخدمه كل يوم.

من تجربتي الشخصية ده أهم درس.
"""


def test_educational_creator_standard_in_seed_and_required_keys():
    assert "rukn_educational_creator_standard" in REQUIRED_KEYS
    keys = {item["key"] for item in SEED_ITEMS}
    assert "rukn_educational_creator_standard" in keys
    item = next(i for i in SEED_ITEMS if i["key"] == "rukn_educational_creator_standard")
    assert item["title"] == "ROKN Educational Creator Standard"
    assert item["content_text"] == EDUCATIONAL_CREATOR_STANDARD


def test_standard_covers_practitioner_not_seller_identity():
    text = EDUCATIONAL_CREATOR_STANDARD.lower()
    assert "practitioner" in text
    assert "course seller" in text
    assert "generic ai" in text
    assert "teleprompter docx only" in text
    assert "do not invent" in text or "fake biography" in text


def test_prompt_compiler_includes_creator_standard_in_relevant_stages():
    rules = {"rukn_educational_creator_standard": EDUCATIONAL_CREATOR_STANDARD}
    for stage in (
        PipelineStage.BUILD_COURSE_MAP,
        PipelineStage.WRITE_SINGLE_REEL,
        PipelineStage.REVIEW_SINGLE_REEL,
        PipelineStage.REVIEW_MODULE,
        PipelineStage.FINAL_REVIEW,
        PipelineStage.REBUILD_FINAL_COURSE,
    ):
        selected = select_rules_for_stage(rules, stage)
        assert "rukn_educational_creator_standard" in selected


def test_packed_creator_standard_is_stage_relevant_not_full_dump():
    full_len = len(EDUCATIONAL_CREATOR_STANDARD)
    assert full_len > 2000

    map_slice = stage_educational_creator_standard(
        EDUCATIONAL_CREATOR_STANDARD, PipelineStage.BUILD_COURSE_MAP
    )
    write_slice = stage_educational_creator_standard(
        EDUCATIONAL_CREATOR_STANDARD, PipelineStage.WRITE_SINGLE_REEL
    )
    review_slice = stage_educational_creator_standard(
        EDUCATIONAL_CREATOR_STANDARD, PipelineStage.REVIEW_SINGLE_REEL
    )
    final_slice = stage_educational_creator_standard(
        EDUCATIONAL_CREATOR_STANDARD, PipelineStage.FINAL_REVIEW
    )

    for slice_text in (map_slice, write_slice, review_slice, final_slice):
        assert slice_text
        assert len(slice_text) < full_len // 2
        assert EDUCATIONAL_CREATOR_STANDARD not in slice_text

    assert "Core identity" in map_slice or "Core identity" in write_slice
    assert "Student Agent" not in map_slice
    assert "Speech qualities" in write_slice or "Generosity" in write_slice
    assert "must avoid" in review_slice.lower() or "What the script must avoid" in review_slice or "Human warmth" in review_slice
    assert (
        "Speech qualities" in final_slice
        or "must avoid" in final_slice.lower()
        or "Clarity without flattening" in final_slice
    )

    packed = select_packed_rules_for_stage(
        {"rukn_educational_creator_standard": EDUCATIONAL_CREATOR_STANDARD},
        PipelineStage.WRITE_SINGLE_REEL,
    )
    body = " ".join(packed.values())
    assert EDUCATIONAL_CREATOR_STANDARD not in body
    assert "stage-relevant" in body.lower()


def test_build_stage_rules_pack_slices_creator_standard():
    selected = {"rukn_educational_creator_standard": EDUCATIONAL_CREATOR_STANDARD}
    packed = build_stage_rules_pack(selected, PipelineStage.FINAL_REVIEW)
    body = packed.get("final_export_rules_pack", "")
    assert EDUCATIONAL_CREATOR_STANDARD not in body
    assert "educational_creator_standard" in body


def test_final_script_avoids_generic_ai_teacher_tone():
    issues = check_creator_persona_script(GENERIC_AI_SCRIPT, reel_id="r1")
    assert any(i.reason_code == "generic_ai_teacher_tone" for i in issues)
    assert not script_passes_educational_creator_warmth(GENERIC_AI_SCRIPT)


def test_final_script_avoids_course_seller_tone():
    issues = check_creator_persona_script(COURSE_SELLER_SCRIPT, reel_id="r1")
    assert any(i.reason_code == "course_seller_tone" for i in issues)


def test_final_script_favors_practical_field_aware_explanation():
    assert script_has_field_aware_practical_tone(GOOD_PRACTITIONER_SCRIPT)
    issues = check_creator_persona_script(GOOD_PRACTITIONER_SCRIPT, reel_id="r1")
    assert not any(
        i.reason_code in ("generic_ai_teacher_tone", "course_seller_tone")
        for i in issues
    )


def test_final_script_does_not_invent_fake_personal_experience():
    issues = check_creator_persona_script(FAKE_BIO_SCRIPT, reel_id="r1")
    assert any(i.reason_code == "fake_personal_experience" for i in issues)


def test_final_script_preserves_warmth_without_slangy_costume():
    assert script_passes_educational_creator_warmth(GOOD_PRACTITIONER_SCRIPT)
    slangy = check_creator_persona_script("يا نجم السوشيال المدفع هتنجح فوراً", reel_id="r1")
    assert any(i.reason_code == "fake_egyptian_ai_tone" for i in slangy)


def test_final_docx_remains_clean_teleprompter_script_only():
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
                        script_text=GOOD_PRACTITIONER_SCRIPT,
                    )
                ],
            )
        ],
    )
    docx_bytes = render_final_course_docx(course)
    plain = extract_plain_text(docx_bytes)
    assert "Module 1" in plain
    assert "Lesson 1" in plain
    assert "خليني أوضح" in plain
    assert not find_forbidden_substrings(plain)
    assert "course_creator_persona" not in plain.lower()
    assert "admin knowledge" not in plain.lower()
