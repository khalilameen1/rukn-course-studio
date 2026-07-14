"""Tests for the Student Confusion Layer (80% serious learner)."""

from app.generation.student_confusion import (
    STUDENT_LEAK_SUBSTRINGS,
    StudentReview,
    filter_student_review_to_80_percent,
    should_ignore_student_feedback,
    student_clarity_hints_for_script,
)
from app.generation.specialist_critic import (
    CRITIC_LEAK_SUBSTRINGS,
    PROGRESS_STUDENT_CLARITY,
)
from app.generation.teleprompter_checks import find_forbidden_substrings
from app.prompts.prompt_registry import PipelineStage, load_prompt
from app.schemas.generation import FinalCourse, FinalModule, FinalReel
from app.services.docx_export import extract_plain_text, render_final_course_docx


def test_write_prompt_includes_student_layer_before_specialist_and_master():
    write = load_prompt(PipelineStage.WRITE_SINGLE_REEL).lower()
    review = load_prompt(PipelineStage.REVIEW_SINGLE_REEL).lower()
    assert "first_draft" in write
    assert "final_master" in write
    assert "student confusion" in review
    assert "80%" in review or "80 percent" in review or "~80%" in review
    assert "student_" in review or "student confusion" in review
    assert text_index_student_before_specialist(review)
    assert "ignore" in review and "edge" in review
    assert "master version" in write or "final master" in write


def text_index_student_before_specialist(text: str) -> bool:
    return text.index("student") < text.index("specialist")


def test_map_prompt_includes_student_learnability_check():
    text = load_prompt(PipelineStage.BUILD_COURSE_MAP).lower()
    assert "student" in text
    assert "prerequisite" in text or "learnable" in text


def test_student_review_schema_is_compact():
    review = StudentReview(
        unclear_terms=["CTR"],
        skipped_steps=["how to open the ads manager"],
        what_to_clarify_without_padding=["one-breath gloss for CTR"],
        what_to_keep_unexplained_because_80_percent_do_not_need_it=[
            "full history of attribution theory"
        ],
    )
    keys = set(review.model_dump())
    assert "unclear_terms" in keys
    assert "skipped_steps" in keys
    assert "likely_student_questions" in keys


def test_missing_term_triggers_local_clarity_hint():
    issues = student_clarity_hints_for_script(
        "خلي الـ CTR عالي وقول الحملة نجحت."
    )
    assert any(i.reason_code == "unclear_term" for i in issues)


def test_skipped_practical_step_triggers_local_clarity_hint():
    issues = student_clarity_hints_for_script(
        "Just obviously open it then after that publish the campaign."
    )
    assert any(i.reason_code == "skipped_step" for i in issues)


def test_rare_edge_case_is_ignored_by_80_percent_filter():
    assert should_ignore_student_feedback(
        "Also cover this rare philosophical edge-case objection for genius students."
    )
    raw = StudentReview(
        unclear_terms=["CTR"],
        likely_student_questions=[
            "يعني إيه CTR؟",
            "Rewrite the whole course as a textbook for every possible objection.",
        ],
        what_to_clarify_without_padding=["CTR gloss"],
    )
    filtered = filter_student_review_to_80_percent(raw)
    assert "CTR" in filtered.unclear_terms
    assert not any("textbook" in q.lower() for q in filtered.likely_student_questions)
    assert not any("philosophical" in q.lower() for q in filtered.likely_student_questions)


def test_over_explanation_not_required_for_kept_unexplained():
    review = StudentReview(
        what_to_keep_unexplained_because_80_percent_do_not_need_it=[
            "full Bayesian attribution derivation"
        ]
    )
    filtered = filter_student_review_to_80_percent(review)
    assert filtered.what_to_keep_unexplained_because_80_percent_do_not_need_it
    # Master guidance: keep unexplained list means do NOT pad script for these.
    assert not filtered.what_to_clarify_without_padding


def test_final_docx_does_not_expose_student_review():
    final = FinalCourse(
        title="Course",
        full_text="# M\n## L\nSpoken only.",
        modules=[
            FinalModule(
                module_id="m1",
                title="Module",
                reels=[
                    FinalReel(
                        reel_id="m1-r1",
                        title="Lesson",
                        script_text="النقطة واضحة: جرّب الاستهداف الضيّق على الحي.",
                    )
                ],
            )
        ],
    )
    text = extract_plain_text(render_final_course_docx(final)).lower()
    assert find_forbidden_substrings(text) == []
    for leak in STUDENT_LEAK_SUBSTRINGS + CRITIC_LEAK_SUBSTRINGS:
        assert leak not in text
    assert "student_review" not in text
    assert "creator draft" not in text


def test_progress_label_checking_student_clarity_exists():
    assert PROGRESS_STUDENT_CLARITY == "Checking student clarity"
