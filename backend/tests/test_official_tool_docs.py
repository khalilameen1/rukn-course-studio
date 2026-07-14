"""Official Tool Documentation Gate tests."""

from __future__ import annotations

from app.generation.official_tool_docs import (
    OFFICIAL_TOOL_DOCX_LEAKS,
    OfficialToolMemoryStore,
    annotate_dependencies_from_map,
    compile_official_tool_guidance,
    detect_tool_dependencies,
    map_official_tool_feedback,
    rewrite_script_official_tool,
    run_official_tool_docs_pass,
    should_reuse_tool_memory,
)
from app.generation.teleprompter_checks import find_forbidden_substrings
from app.generation.web_research import FakeResearchBackend
from app.schemas.generation import CourseMap, FinalCourse, FinalModule, FinalReel, ModulePlan, ReelPlan
from app.services.docx_export import extract_plain_text, render_final_course_docx


def test_tool_dependency_detected_from_brief():
    deps = detect_tool_dependencies(
        title="Meta Ads for shops",
        audience="egypt shops",
        outcome="run profitable ads",
        special_notes="Facebook Ads Manager",
        course_domain="meta_ads",
    )
    names = {d.tool_name for d in deps}
    assert "Meta Ads" in names
    assert all(d.official_docs_needed for d in deps)


def test_official_docs_research_triggered_and_memory_stored():
    store = run_official_tool_docs_pass(
        title="Shopify store course",
        audience="beginners",
        outcome="launch store",
        course_domain="shopify",
        prefer_fake=True,
        allow_fetch=True,
        research_backend=FakeResearchBackend(),
        course_id=7,
    )
    assert any(d.tool_name == "Shopify" for d in store.tool_dependencies)
    assert store.needs_logged
    assert store.entries
    assert "Shopify" in store.entries[0].tool_name or store.entries[0].tool_name == "Shopify"
    assert store.entries[0].relevant_current_behaviors


def test_official_tool_memory_reused_no_repeat_lookup():
    first = run_official_tool_docs_pass(
        title="Canva design basics",
        audience="a",
        outcome="o",
        prefer_fake=True,
        allow_fetch=True,
        research_backend=FakeResearchBackend(),
        course_id=1,
    )
    assert first.entries
    reuse_ok, entry, reason = should_reuse_tool_memory(first, first.tool_dependencies[0])
    assert reuse_ok and entry is not None and reason == "hit"

    second = run_official_tool_docs_pass(
        title="Canva design basics",
        audience="a",
        outcome="o",
        prefer_fake=True,
        allow_fetch=True,
        research_backend=FakeResearchBackend(),
        course_id=2,
        cached=first,
    )
    # Same research_need_key should not duplicate entries.
    keys = [e.research_need_key for e in second.entries]
    assert len(keys) == len(set(keys))


def test_old_course_source_flagged_when_fragile_ui_conflicts():
    store = run_official_tool_docs_pass(
        title="Meta Ads",
        audience="a",
        outcome="o",
        source_texts_for_conflict=[
            "In this old course, click the blue button at the top left in Ads Manager."
        ],
        prefer_fake=True,
        allow_fetch=True,
        research_backend=FakeResearchBackend(),
    )
    assert store.outdated_source_flags
    assert store.outdated_source_flags[0]["action"] == "prefer_official_docs_principles_only"


def test_course_map_feedback_reframes_fragile_tool_lesson():
    store = OfficialToolMemoryStore(
        tool_dependencies=detect_tool_dependencies(title="Meta Ads course")
    )
    cmap = CourseMap(
        course_title="Ads",
        main_thread="profit",
        modules=[
            ModulePlan(
                module_id="m1",
                title="Meta Ads UI",
                purpose="buttons",
                reels=[
                    ReelPlan(
                        reel_id="m1-r1",
                        title="Click the top left blue button",
                        purpose="legacy path",
                        must_cover=["top left button", "settings → ads"],
                        estimated_length="short",
                    )
                ],
            )
        ],
    )
    fb = map_official_tool_feedback(cmap, store)
    assert fb
    annotated = annotate_dependencies_from_map(store.tool_dependencies, cmap)
    assert annotated[0].affected_modules


def test_fragile_ui_rewritten_and_docx_clean():
    dirty = (
        "Click the blue button at the top left to create. "
        "According to official docs https://example.com/help you must."
    )
    clean = rewrite_script_official_tool(dirty)
    assert "top left" not in clean.lower()
    assert "according to official" not in clean.lower()
    assert "https://" not in clean.lower()
    final = FinalCourse(
        title="T",
        full_text=f"# M\n## L\n{clean}",
        modules=[
            FinalModule(
                module_id="m1",
                title="M",
                reels=[FinalReel(reel_id="r1", title="L", script_text=clean)],
            )
        ],
    )
    text = extract_plain_text(render_final_course_docx(final)).lower()
    for leak in OFFICIAL_TOOL_DOCX_LEAKS:
        assert leak.lower() not in text
    assert find_forbidden_substrings(text) == [] or "http" not in text


def test_prompt_guidance_mentions_official_authority():
    store = run_official_tool_docs_pass(
        title="WordPress sites",
        audience="a",
        outcome="o",
        allow_fetch=False,
    )
    guide = compile_official_tool_guidance(store)
    assert "Official" in guide
    assert "WordPress" in guide
