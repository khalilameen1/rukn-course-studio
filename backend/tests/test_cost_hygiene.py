"""Cost Hygiene + Trusted Knowledge Gate tests."""

from datetime import datetime, timedelta, timezone

from app.generation.cost_hygiene import IdenticalRetryGuard, build_usage_panel
from app.generation.knowledge_packs import (
    build_stage_rules_pack,
    pack_is_compact,
)
from app.generation.prompt_compiler import (
    SourceForCompiler,
    compile_source_context,
    select_packed_rules_for_stage,
    select_rules_for_stage,
)
from app.generation.research_memory import (
    ResearchMemoryEntry,
    ResearchMemoryStore,
    build_research_need,
    entry_from_web_facts,
    should_reuse_research,
    upsert_research_entry,
)
from app.generation.source_memory_store import (
    build_source_memory_payload,
    compute_source_hash,
    memory_matches_hash,
)
from app.generation.trusted_sources import classify_source
from app.generation.web_research import (
    FakeResearchBackend,
    WebFact,
    WebSourceMemory,
    run_autonomous_gap_fill,
)
from app.models.enums import WebResearchMode
from app.prompts.prompt_registry import PipelineStage
from app.services.docx_export import extract_plain_text, render_final_course_docx
from app.schemas.generation import FinalCourse, FinalModule, FinalReel


LONG_PDF = ("Chapter about attribution windows and ROAS for brands. " * 100)


def test_unchanged_pdf_hash_skips_reextract():
    memory = build_source_memory_payload(
        title="ads.pdf",
        category="scientific_reference",
        extracted_text=LONG_PDF,
        priority="high",
    )
    assert memory["source_hash"] == compute_source_hash(LONG_PDF)
    assert memory_matches_hash(memory, LONG_PDF)
    assert not memory_matches_hash(memory, LONG_PDF + " changed")
    assert memory["extracted_facts"]
    assert "extraction_version" in memory
    assert "extracted_at" in memory
    assert memory["tokens_used"] > 0


def test_same_research_question_reuses_memory():
    store = ResearchMemoryStore()
    for q in ("Meta", "shops", "profitable"):
        need = build_research_need(
            question=q,
            why_needed="missing_practical_or_factual_coverage",
            course_id=1,
        )
        entry = entry_from_web_facts(
            need=need,
            facts=[
                WebFact(
                    title=f"Trusted overview: {q}",
                    summary=f"Practical facts about {q}.",
                    url="https://www.facebook.com/business/help",
                )
            ],
        )
        store = upsert_research_entry(store, entry)

    reuse, found, reason = should_reuse_research(store, "Meta")
    assert reuse is True
    assert found is not None
    assert reason == "reuse"

    class CountingBackend(FakeResearchBackend):
        def __init__(self):
            self.calls = 0

        def fetch_facts(self, query: str, *, sensitive: bool):
            self.calls += 1
            return super().fetch_facts(query, sensitive=sensitive)

    cached = WebSourceMemory(
        research_entries=[e.model_dump(mode="json") for e in store.entries],
        gaps_researched=["Meta", "shops", "profitable"],
    )
    backend = CountingBackend()
    result = run_autonomous_gap_fill(
        course_title="Meta Ads",
        audience="shops",
        outcome="profitable ads",
        special_notes=None,
        memory_items=[],
        mode=WebResearchMode.AUTONOMOUS_GAP_FILL,
        backend=backend,
        cached_web_memory=cached,
        course_id=1,
    )
    assert backend.calls == 0
    assert result.web_searches_count == 0
    assert result.web_cache_hits >= 1


def test_new_distinct_question_can_search():
    class CountingBackend(FakeResearchBackend):
        def __init__(self):
            self.calls = 0

        def fetch_facts(self, query: str, *, sensitive: bool):
            self.calls += 1
            return super().fetch_facts(query, sensitive=sensitive)

    backend = CountingBackend()
    result = run_autonomous_gap_fill(
        course_title="Completely Unique Topic XYZABC",
        audience="learners",
        outcome="master unique skillset FOOBAR",
        special_notes=None,
        memory_items=[],
        mode=WebResearchMode.AUTONOMOUS_GAP_FILL,
        backend=backend,
        cached_web_memory=WebSourceMemory(),
    )
    assert backend.calls >= 1
    assert result.web_searches_count >= 1


def test_stale_platform_question_can_refresh():
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    entry = ResearchMemoryEntry(
        normalized_question="meta ads algorithm",
        extracted_answer="old answer",
        retrieved_at=old,
        freshness_policy="platform_current",
        source_quality="conditional",
        low_confidence=False,
    )
    store = ResearchMemoryStore(entries=[entry])
    reuse, _, reason = should_reuse_research(store, "meta ads algorithm")
    assert reuse is False
    assert reason == "stale_or_low_confidence"


def test_low_quality_social_rejected_as_factual_authority():
    bad = classify_source(
        title="Top 10 tips from TikTok",
        url="https://www.tiktok.com/@coach/video/1",
        summary="Viral tips",
    )
    assert bad.allowed_as_fact is False
    reddit = classify_source(
        title="Reddit comment about ads",
        url="https://www.reddit.com/r/ads/comments/abc",
        summary="Forum comment",
    )
    assert reddit.allowed_as_fact is False


def test_university_and_official_sources_accepted():
    uni = classify_source(
        title="University lecture notes on marketing attribution",
        url="https://ocw.mit.edu/courses/marketing",
        summary="Academic course materials textbook excerpt",
    )
    assert uni.allowed_as_fact is True
    official = classify_source(
        title="Meta Ads Help Center",
        url="https://www.facebook.com/business/help",
        summary="Official documentation",
    )
    assert official.allowed_as_fact is True


def test_prompt_compiler_no_full_pdf_in_lesson_prompts():
    memory = build_source_memory_payload(
        title="ads.pdf",
        category="scientific_reference",
        extracted_text=LONG_PDF,
    )
    excerpts = compile_source_context(
        [
            SourceForCompiler(
                source_id=1,
                category="scientific_reference",
                priority="high",
                text="placeholder",
                summary=memory["summary"],
                memory=memory,
            )
        ],
        query_text="ROAS attribution",
    )
    assert len(excerpts[0].text) < len(LONG_PDF) // 5


def test_prompt_compiler_packs_admin_knowledge():
    big = "Rule line about quality.\n" + ("- bullet detail about writing\n" * 80)
    all_rules = {
        "rukn_core_rules": big,
        "rukn_practical_course_rules": big,
        "rukn_writing_style": big,
        "rukn_high_signal_reel_doctrine": big,
        "rukn_dynamic_teaching_curve": big,
        "rukn_creator_persona_engine": big,
        "rukn_creator_critic_loop": big,
        "rukn_student_confusion_layer": big,
        "rukn_master_mentor_engine": big,
        "rukn_teleprompter_docx_contract": big,
        "rukn_market_evergreen_gates": big,
        "rukn_originality_rights_gate": big,
    }
    selected = select_rules_for_stage(all_rules, PipelineStage.WRITE_SINGLE_REEL)
    packed = select_packed_rules_for_stage(all_rules, PipelineStage.WRITE_SINGLE_REEL)
    assert "lesson_writing_rules_pack" in packed
    assert pack_is_compact(packed, selected)
    assert sum(len(v) for v in packed.values()) < sum(len(v) for v in selected.values())


def test_identical_retry_blocked():
    guard = IdenticalRetryGuard()
    assert guard.allow(phase="final_master", feedback=["fix A"], script_text="draft")
    assert not guard.allow(phase="final_master", feedback=["fix A"], script_text="draft")
    assert guard.allow(phase="final_master", feedback=["fix B"], script_text="draft")


def test_premium_pipeline_still_two_writes_and_final_rewrite():
    """Premium loop stays: first draft + review bundle + final rewrite (≥2 writes)."""
    from app.generation.orchestrator import MAX_FINAL_REBUILD_ATTEMPTS, WRITES_PER_REEL

    assert MAX_FINAL_REBUILD_ATTEMPTS == 2
    assert WRITES_PER_REEL >= 2


def test_final_docx_has_no_sources_or_reviews():
    final = FinalCourse(
        title="Ads",
        full_text="# Module 1\n## Lesson 1\nخلّينا نثبت فرق عملي من غير حشو.",
        modules=[
            FinalModule(
                module_id="m1",
                title="Module 1",
                reels=[
                    FinalReel(
                        reel_id="m1-r1",
                        title="Lesson 1",
                        script_text="خلّينا نثبت فرق عملي من غير حشو.",
                    )
                ],
            )
        ],
    )
    text = extract_plain_text(render_final_course_docx(final)).lower()
    assert "source memory" not in text
    assert "needs confirmation" not in text
    assert "critic" not in text
    assert "mentor" not in text
    assert "citation" not in text


def test_usage_panel_and_waste_warning():
    panel = build_usage_panel(
        estimated_cost_usd=2.0,
        completed_lessons=2,
        web_searches_count=20,
        source_memories_reused=3,
        waste_warnings=["duplicate_source_extraction"],
        research_memory_reuses=4,
    )
    assert panel["cost_per_completed_lesson"] == 1.0
    assert "high_web_search_count" in panel["warnings"]
    assert "duplicate_source_extraction" in panel["warnings"]
    assert panel["source_memories_reused"] == 3


def test_stage_pack_builder_caps_size():
    selected = {
        "rukn_core_rules": "x" * 5000,
        "rukn_writing_style": "y" * 5000,
    }
    pack = build_stage_rules_pack(selected, PipelineStage.WRITE_SINGLE_REEL)
    assert sum(len(v) for v in pack.values()) <= 4200
