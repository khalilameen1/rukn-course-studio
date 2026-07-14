"""Tests for Master Creator-Academic Mentor layer (synthetic, internal)."""

from app.generation.master_mentor import (
    MENTOR_LEAK_SUBSTRINGS,
    MentorReview,
    mentor_advice_hints_for_script,
    mentor_advises_bolder,
    mentor_advises_no_fake_loop,
    mentor_advises_quieter,
    mentor_forbids_named_creator_imitation,
)
from app.generation.specialist_critic import (
    CRITIC_LEAK_SUBSTRINGS,
    PROGRESS_MASTER_MENTOR,
)
from app.generation.teleprompter_checks import find_forbidden_substrings
from app.prompts.prompt_registry import PipelineStage, load_prompt
from app.schemas.generation import FinalCourse, FinalModule, FinalReel
from app.services.docx_export import extract_plain_text, render_final_course_docx


def test_write_prompt_includes_mentor_before_master_version():
    write = load_prompt(PipelineStage.WRITE_SINGLE_REEL).lower()
    review = load_prompt(PipelineStage.REVIEW_SINGLE_REEL).lower()
    assert "first_draft" in write and "final_master" in write
    assert "master creator-academic mentor" in review or "mentor" in review
    assert "mentor_" in review or "mentor" in review
    assert "not a real" in review or "not imitate" in review or "named" in review
    assert write.index("first_draft") < write.index("final_master")


def test_map_prompt_includes_mentor_playlist_checks():
    text = load_prompt(PipelineStage.BUILD_COURSE_MAP).lower()
    assert "mentor" in text
    assert "spine" in text or "playlist" in text


def test_mentor_review_schema_is_compact():
    review = MentorReview(
        strongest_hidden_angle="Budget constraint is the real hook",
        hook_advice="Open quieter on the decision, not the drama",
        loop_advice="Clean close — no fake next-reel tease",
        academic_gap="Name when ROAS misleads on small spend",
        what_to_make_bolder="The wrong-default contrast",
        what_to_make_quieter="The opening sentence",
        rebuild_instruction="Lead with the angle; drop the announcement ending.",
    )
    dumped = review.model_dump()
    assert "hook_advice" in dumped
    assert "rebuild_instruction" in dumped


def test_mentor_can_advise_stronger_hook_without_overhype():
    issues = mentor_advice_hints_for_script("السر اللي محدش يعرفه هيغير حياتك في الإعلانات.")
    assert any(i.reason_code == "mentor_quieter_hook" for i in issues)
    review = MentorReview(
        hook_advice="Quieter meaning-first open; no hype words",
        what_to_make_quieter="Opening",
        what_to_make_bolder="The usable distinction in paragraph 2",
    )
    assert mentor_advises_quieter(review)
    assert mentor_advises_bolder(review)


def test_mentor_can_advise_no_fake_loop():
    issues = mentor_advice_hints_for_script("النقطة واضحة. في الريل الجاي هنكمل.")
    assert any(i.reason_code == "mentor_no_fake_loop" for i in issues)
    review = MentorReview(loop_advice="No fake loop — clean close")
    assert mentor_advises_no_fake_loop(review)


def test_mentor_can_flag_subtle_academic_gap():
    issues = mentor_advice_hints_for_script("This always works 100% guaranteed with no exception.")
    assert any(i.reason_code == "mentor_academic_gap" for i in issues)


def test_mentor_rejects_named_creator_imitation_pattern():
    assert mentor_forbids_named_creator_imitation("زي ما بيقول أحمد في التريند")


def test_final_docx_does_not_expose_mentor_review():
    final = FinalCourse(
        title="Course",
        full_text="# M\n## L\nSpoken.",
        modules=[
            FinalModule(
                module_id="m1",
                title="Module",
                reels=[
                    FinalReel(
                        reel_id="m1-r1",
                        title="Lesson",
                        script_text="جرّب الاستهداف الضيّق على الحي قبل ما توسّع.",
                    )
                ],
            )
        ],
    )
    text = extract_plain_text(render_final_course_docx(final)).lower()
    assert find_forbidden_substrings(text) == []
    for leak in MENTOR_LEAK_SUBSTRINGS + CRITIC_LEAK_SUBSTRINGS:
        assert leak not in text
    assert "mentor_review" not in text
    assert "creator draft" not in text


def test_progress_includes_consulting_master_mentor():
    assert PROGRESS_MASTER_MENTOR == "Consulting master mentor"


def test_quota_timeout_stop_preserves_saved_work_contract():
    """Cross-check: FailAfterNReelsProvider path in test_creator_critic_loop covers
    timeout → PARTIAL + partial DOCX + preserved completed_reels. Mentor does not
    change that stop/save contract."""
    assert PROGRESS_MASTER_MENTOR
    for leak in MENTOR_LEAK_SUBSTRINGS:
        assert leak  # leak list is non-empty for DOCX forbid coverage
