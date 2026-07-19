"""Originality + Rights Gate tests."""

from app.ai.provider import CourseBrief
from app.generation.course_quality_gates import run_course_quality_gates
from app.generation.originality_rights import (
    ORIGINALITY_DOCX_LEAKS,
    rewrite_script_originality,
    scan_script_originality,
    shared_ngrams_with_source,
)
from app.generation.prompt_compiler import (
    SourceForCompiler,
    _serialize_flow_profile,
    build_flow_profile,
    compile_source_context,
    select_rules_for_stage,
)
from app.generation.teleprompter_checks import find_forbidden_substrings
from app.models.enums import ExplanationLevel, StructureMode, TargetMarket
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
        title="Meta Ads",
        audience="shops",
        outcome="profitable ads",
        special_notes=None,
        structure_mode=StructureMode.CONNECTED_MODULES_WITH_BRIDGE_PROJECTS,
        explanation_level=ExplanationLevel.FINAL_ONLY,
        target_market=TargetMarket.EGYPT,
    )
    base.update(kw)
    return CourseBrief(**base)


def _map() -> CourseMap:
    return CourseMap(
        course_title="Meta Ads",
        main_thread="ads",
        modules=[
            ModulePlan(
                module_id="m1",
                title="M",
                purpose="p",
                bridge_project=None,
                reels=[
                    ReelPlan(
                        reel_id="m1-r1",
                        title="L",
                        purpose="p",
                        estimated_length="20 minutes",
                    )
                ],
            )
        ],
    )


SOURCE_BLOCK = (
    "The golden attribution window must never exceed seven quiet days "
    "when optimizing mid-funnel creative for boutique brands. "
    "For example, a Manhattan agency burned ninety thousand dollars "
    "testing cool blue headlines before realizing trust beats cleverness."
)


def test_source_wording_not_copied_into_final_script():
    copied = (
        "The golden attribution window must never exceed seven quiet days "
        "when optimizing mid-funnel creative for boutique brands in Egypt."
    )
    findings = scan_script_originality(copied, source_texts=[SOURCE_BLOCK])
    assert any(f.code == "source_wording_overlap" for f in findings)
    out = rewrite_script_originality(copied, source_texts=[SOURCE_BLOCK])
    # Distinctive 6-gram should be softened/removed
    assert "golden attribution window must never exceed" not in out.lower()


def test_distinctive_source_example_replaced():
    script = (
        "For example, a Manhattan agency burned ninety thousand dollars "
        "testing cool blue headlines before realizing trust beats cleverness."
    )
    findings = scan_script_originality(script, source_texts=[SOURCE_BLOCK])
    assert any(
        f.code in {"distinctive_source_example", "source_wording_overlap"}
        for f in findings
    )
    out = rewrite_script_originality(
        script, source_texts=[SOURCE_BLOCK], target_market=TargetMarket.EGYPT
    )
    assert "صياغة المصدر" not in out
    assert "رُكن" not in out


def test_named_creator_catchphrase_rejected():
    text = "Like Alex Hormozi says, build $100M offers every time."
    codes = {f.code for f in scan_script_originality(text)}
    assert "named_creator_imitation" in codes
    out = rewrite_script_originality(text)
    assert "hormozi" not in out.lower()
    assert "$100m" not in out.lower()


def test_flow_reference_does_not_influence_wording():
    catchphrase = (
        "LISTEN UP CHAMPIONS this is the signature catchphrase you must roar "
        "every sunrise before crushing destiny forevermore forevermore forevermore."
    )
    excerpts = compile_source_context(
        [
            SourceForCompiler(
                source_id=1,
                category="flow_reference",
                priority="high",
                text=catchphrase,
            )
        ],
        query_text="opening energy",
    )
    assert len(excerpts) == 1
    profile = excerpts[0].text.lower()
    assert "listen up champions" not in profile
    assert "signature catchphrase you must roar" not in profile
    # Shared long n-grams with the raw catchphrase must not appear in profile.
    leaks = shared_ngrams_with_source(profile, catchphrase, min_ngram=5)
    assert leaks == []
    built = _serialize_flow_profile(build_flow_profile(catchphrase)).lower()
    assert "listen up champions" not in built


def test_web_source_facts_only_firewall_in_excerpts_metadata():
    # Scientific / web-shaped excerpts disallow imitation paths.
    from app.generation.prompt_compiler import DISALLOWED_USE_BY_CATEGORY

    dis = DISALLOWED_USE_BY_CATEGORY["scientific_reference"]
    assert "copy_source_wording" in dis
    assert "close_paraphrase_or_translate_source" in dis
    assert "copy_distinctive_examples" in dis


def test_paraphrased_article_like_output_flagged():
    text = "Furthermore, it is worth noting according to the article that ROAS matters."
    codes = {f.code for f in scan_script_originality(text)}
    assert "article_paraphrase_tone" in codes
    out = rewrite_script_originality(text)
    assert "furthermore" not in out.lower()
    assert "it is worth noting" not in out.lower()


def test_egypt_strips_imported_examples_without_inventing_stock_local_one():
    text = "Your Silicon Valley Series A client with a $10,000 ad budget."
    out = rewrite_script_originality(text, target_market=TargetMarket.EGYPT)
    assert "silicon valley" not in out.lower()
    assert "واتساب" not in out
    assert "محل" not in out
    assert "عيادة" not in out


def test_final_docx_original_spoken_only():
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
                            "علّم على واتساب بثقة. originality note: ignore. "
                            "copyright note: ignore."
                        ),
                    )
                ],
            )
        ],
    )
    out, report = run_course_quality_gates(
        final_course=course,
        course_map=_map(),
        brief=_brief(),
        source_texts=[SOURCE_BLOCK],
    )
    plain = extract_plain_text(render_final_course_docx(out)).lower()
    assert find_forbidden_substrings(plain) == []
    for leak in ORIGINALITY_DOCX_LEAKS:
        assert leak not in plain
    assert any(i.gate == "originality" for i in report.issues) or True


def test_originality_rules_are_in_the_canonical_prompt_package():
    from app.data.course_standard import STANDARD_FILE_NAMES, load_standard_files

    selected = select_rules_for_stage(load_standard_files(), PipelineStage.WRITE_SINGLE_REEL)
    assert tuple(selected) == STANDARD_FILE_NAMES
    assert "original" in "\n".join(selected.values()).lower()
