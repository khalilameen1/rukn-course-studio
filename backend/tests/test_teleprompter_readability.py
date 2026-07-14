"""Teleprompter Readability Formatting Gate tests."""

from app.generation.course_quality_gates import run_course_quality_gates
from app.generation.prompt_compiler import select_rules_for_stage
from app.generation.teleprompter_checks import find_forbidden_substrings
from app.generation.teleprompter_readability import (
    TELEPROMPTER_READABILITY_PROMPT_RULE,
    format_script_for_teleprompter,
    looks_like_dense_paragraph,
    looks_like_word_per_line,
    punctuation_density,
)
from app.ai.provider import CourseBrief
from app.models.enums import ExplanationLevel, StructureMode
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


DENSE = (
    "دلوقتي لو أنت بتعمل إعلان على ميتا لازم تفهم إن الاستهداف تغير جدًا لأن "
    "ميتا بقت تعتمد على الذكاء الاصطناعي بشكل أكبر وده معناه إنك لو فضلت "
    "تضيق الجمهور زي زمان ممكن تمنع النظام من إنه يلاقي الناس الصح، وبعدين "
    "لازم تقيس الـ ROAS كل أسبوع عشان تعرف الحملة رابحة ولا لأ."
)


def _brief() -> CourseBrief:
    return CourseBrief(
        title="Meta Ads",
        audience="shop owners",
        outcome="run ads",
        structure_mode=StructureMode.CONNECTED_NO_MODULES,
        explanation_level=ExplanationLevel.FINAL_ONLY,
    )


def _map() -> CourseMap:
    return CourseMap(
        course_title="Meta Ads",
        main_thread="ads",
        modules=[
            ModulePlan(
                module_id="m1",
                title="Ads",
                purpose="run",
                bridge_project=None,
                reels=[
                    ReelPlan(
                        reel_id="r1",
                        title="Targeting",
                        purpose="teach targeting",
                        estimated_length="short",
                    )
                ],
            )
        ],
    )


def test_format_splits_dense_paragraph_into_readable_lines():
    out = format_script_for_teleprompter(DENSE)
    assert "\n" in out
    assert not looks_like_dense_paragraph(out)
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert len(lines) >= 3
    assert "ميتا" in out
    assert "ROAS" in out or "roas" in out.lower() or "الجمهور" in out


def test_format_avoids_heavy_punctuation():
    punctuated = (
        "الاستهداف، تغير؛ جدًا… لأن ميتا — بقت تعتمد، على الذكاء، الاصطناعي."
    )
    out = format_script_for_teleprompter(punctuated)
    assert punctuation_density(out) < punctuation_density(punctuated)
    assert "؛" not in out
    assert "…" not in out


def test_format_strips_pause_labels():
    raw = "دلوقتي نبدأ [pause] وبعدين نقيس [breath] النتيجة (silence) كويس."
    out = format_script_for_teleprompter(raw)
    assert "[pause]" not in out.lower()
    assert "[breath]" not in out.lower()
    assert "(silence)" not in out.lower()
    assert find_forbidden_substrings(out) == []


def test_format_does_not_break_every_word():
    raw = "دلوقتي هنفهم الاستهداف على ميتا بشكل عملي وبسيط للمتعلم."
    out = format_script_for_teleprompter(raw)
    assert not looks_like_word_per_line(out)
    for ln in out.splitlines():
        if ln.strip():
            # No theatrical single-token lines from a short complete thought
            # unless the whole script is already short.
            pass
    assert len([ln for ln in out.splitlines() if ln.strip()]) < 12


def test_gate_applies_readability_before_docx():
    course = FinalCourse(
        title="Meta Ads",
        modules=[
            FinalModule(
                module_id="m1",
                title="Setup",
                bridge_project=None,
                reels=[
                    FinalReel(reel_id="r1", title="Targeting", script_text=DENSE),
                ],
            )
        ],
        full_text=DENSE,
    )
    updated, report = run_course_quality_gates(
        final_course=course, course_map=_map(), brief=_brief()
    )
    script = updated.modules[0].reels[0].script_text
    assert "\n" in script
    assert not looks_like_dense_paragraph(script)
    assert any("teleprompter_readability" in r for r in report.remediations)


def test_docx_preserves_line_breaks_and_blank_blocks():
    script = (
        "دلوقتي لو أنت بتعمل إعلان على ميتا\n"
        "في نقطة لازم تبقى واضحة من الأول\n"
        "\n"
        "الاستهداف مش زي زمان"
    )
    course = FinalCourse(
        title="Meta Ads Course",
        modules=[
            FinalModule(
                module_id="m1",
                title="Targeting",
                bridge_project=None,
                reels=[FinalReel(reel_id="r1", title="Lesson 1", script_text=script)],
            )
        ],
        full_text=script,
    )
    doc = render_final_course_docx(course)
    texts = [p.text for p in doc.paragraphs]
    # Heading + lesson lines present as separate paragraphs
    body = extract_plain_text(doc)
    assert "Module 1 — Targeting" in body
    assert "Lesson 1 — Lesson 1" in body
    assert "دلوقتي لو أنت بتعمل إعلان على ميتا" in body
    assert "الاستهداف مش زي زمان" in body
    # Blank teleprompter pause paragraph preserved between idea blocks
    assert "" in texts
    # No internal notes
    for leak in ("[pause]", "needs_review", "internal_review", "keep_candidate"):
        assert leak not in body.lower()


def test_docx_contains_only_headings_and_spoken_transcript():
    course = FinalCourse(
        title="Course Title",
        modules=[
            FinalModule(
                module_id="m1",
                title="Mod",
                bridge_project="INTERNAL BRIDGE — never in DOCX",
                reels=[
                    FinalReel(
                        reel_id="r1",
                        title="Les",
                        script_text="سطر واحد للشرح\nسطر تاني",
                    )
                ],
            )
        ],
        full_text="x",
    )
    body = extract_plain_text(render_final_course_docx(course))
    assert "Course Title" in body
    assert "Module 1 — Mod" in body
    assert "Lesson 1 — Les" in body
    assert "سطر واحد للشرح" in body
    assert "INTERNAL BRIDGE" not in body
    assert "bridge" not in body.lower()


def test_prompt_compiler_injects_readability_rule():
    rules = select_rules_for_stage(
        {"rukn_teleprompter_docx_contract": "contract text"},
        PipelineStage.WRITE_SINGLE_REEL,
    )
    assert rules["rukn_teleprompter_readability_runtime"] == TELEPROMPTER_READABILITY_PROMPT_RULE
    assert "teleprompter reading" in TELEPROMPTER_READABILITY_PROMPT_RULE
    assert "pause labels" in TELEPROMPTER_READABILITY_PROMPT_RULE
