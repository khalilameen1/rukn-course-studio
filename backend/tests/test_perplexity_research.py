"""Perplexity-scale research UX: structured needs, clarity, provenance, cost hygiene."""

from app.generation.brief_clarity import score_brief_clarity
from app.generation.claim_dedup import dedupe_excerpt_pairs
from app.generation.evidence_provenance import (
    format_provenance_summary,
    ledger_support_rollup,
    mark_evidence_used_in_scripts,
)
from app.generation.output_scoring import score_final_course
from app.generation.research_needs import build_structured_research_needs
from app.generation.web_research import (
    MAX_WEB_SEARCHES_PER_RUN,
    EvidenceEntry,
    EvidenceLedger,
    FakeResearchBackend,
    identify_factual_gaps,
    run_autonomous_gap_fill,
    strip_research_leaks_from_script,
)
from app.models.enums import WebResearchMode
from app.schemas.generation import FinalCourse, FinalModule, FinalReel
from app.schemas.generation_job import GenerationJobRead
from app.services.docx_export import extract_plain_text, render_final_course_docx


def test_structured_research_needs_not_token_soup():
    needs = build_structured_research_needs(
        course_title="Meta Ads for Egyptian shops",
        audience="shop owners who never ran ads",
        outcome="launch a profitable Meta Ads campaign this month",
        special_notes="Focus on Ads Manager and catalog",
        upload_summaries=[],
        max_needs=5,
    )
    assert needs
    kinds = {n.kind for n in needs}
    assert kinds & {"definition", "tool", "practice", "market"}
    for n in needs:
        assert len(n.question.split()) >= 3
        assert n.why_needed


def test_identify_factual_gaps_uses_structured_needs():
    from app.generation.web_research import SourceMemory, SourceMemoryItem

    gaps = identify_factual_gaps(
        course_title="Canva for social posts",
        audience="beginners",
        outcome="design 10 posts with brand kit",
        special_notes=None,
        upload_memory=SourceMemory(
            items=[
                SourceMemoryItem(
                    title="notes",
                    kind="upload",
                    summary="short",
                    authority="standard",
                )
            ]
        ),
        max_gaps=4,
    )
    assert gaps
    assert all(g.topic and g.reason for g in gaps)


def test_brief_clarity_scores_and_premium_gate():
    weak = score_brief_clarity(
        title="Ads",
        audience="ppl",
        outcome="learn",
    )
    assert weak["clarity_score"] < 55
    assert weak["premium_recommended"] is False
    assert weak["warnings"]

    strong = score_brief_clarity(
        title="Meta Ads for local shops",
        audience="Egyptian shop owners with no ads experience",
        outcome="Launch and optimize a Meta Ads campaign that gets sales within 30 days",
        special_notes="Use Ads Manager, catalog, and pixel basics",
    )
    assert strong["clarity_score"] >= 55
    assert strong["premium_recommended"] is True


def test_claim_dedup_keeps_longer_summary():
    pairs = [
        ("A", "Meta Ads auction favors relevance and bid"),
        ("B", "Meta Ads auction favors relevance and bid strength overall"),
        ("C", "Completely different claim about Canva templates"),
    ]
    out = dedupe_excerpt_pairs(pairs)
    assert len(out) == 2
    assert out[0][1].startswith("Meta Ads auction favors relevance and bid strength")


def test_provenance_marks_used_and_formats_summary():
    ledger = EvidenceLedger(
        entries=[
            EvidenceEntry(
                claim_or_gap="Meta Ads auction uses relevance",
                support_status="supported",
                source_title="Wiki",
                note="relevance score matters",
            ),
            EvidenceEntry(
                claim_or_gap="Guaranteed ROI forever",
                support_status="omitted",
                source_title="spam",
                note="",
            ),
        ]
    )
    scripts = [
        "في Meta Ads المزاد يعتمد على الـ relevance مع الـ bid عشان توصّل للناس الصح."
    ]
    marked = mark_evidence_used_in_scripts(ledger, scripts)
    assert any(e.used_in_script for e in marked.entries)
    summary = format_provenance_summary(
        upload_count=2,
        web_gap_count=1,
        ledger=marked,
        web_searches=3,
        cache_hits=1,
    )
    assert "upload" in summary.lower()
    assert "http" not in summary.lower()
    assert "example.com" not in summary.lower()


def test_ledger_support_rollup_preferred_in_scoring():
    ledger = {
        "entries": [
            {
                "claim_or_gap": "Meta Ads auction relevance",
                "support_status": "supported",
                "source_title": "t",
                "note": "",
                "used_in_script": False,
            },
            {
                "claim_or_gap": "y",
                "support_status": "weak",
                "source_title": "t2",
                "note": "",
                "used_in_script": False,
            },
        ]
    }
    rollup = ledger_support_rollup(ledger)
    assert rollup
    report = score_final_course(
        "Spoken script about unrelated cooking tips only.",
        rules_context={},
        source_texts=["Meta Ads auction relevance score bid"],
        evidence_ledger=ledger,
    )
    assert report.source_grounding_warning == rollup


def test_gap_fill_respects_search_budget_and_progress():
    assert MAX_WEB_SEARCHES_PER_RUN == 5
    seen: list[str] = []

    result = run_autonomous_gap_fill(
        course_title="Shopify checkout for fashion",
        audience="store owners",
        outcome="reduce cart abandonment with Shopify tools",
        special_notes="Payments and shipping",
        uploaded_texts=[],
        mode=WebResearchMode.AUTONOMOUS_GAP_FILL,
        backend=FakeResearchBackend(),
        on_progress=seen.append,
    )
    assert result.web_searches_count <= MAX_WEB_SEARCHES_PER_RUN
    assert any("Filling knowledge gaps" in m or "Reading sources" in m for m in seen)


def test_generation_job_read_exposes_research_cost_not_ledger():
    read = GenerationJobRead.model_validate(
        {
            "id": 1,
            "course_id": 1,
            "status": "completed",
            "cancel_requested": False,
            "current_stage": "done",
            "progress_percent": 100,
            "output_docx_path": None,
            "error_category": None,
            "error_message": None,
            "completed_modules_count": 1,
            "completed_reels_count": 2,
            "total_lessons_count": 2,
            "partial_docx_path": None,
            "last_progress_message": "Done",
            "last_saved_at": None,
            "estimated_usage_summary": None,
            "estimated_duration_summary": None,
            "sources_run_summary": "Used 1 upload",
            "provenance_summary": "Grounded on 1 upload(s) · 0 web gap(s) filled",
            "generation_quality_mode": "premium",
            "web_research_mode": "autonomous_gap_fill",
            "budget_warning": None,
            "web_searches_count": 2,
            "research_memory_reuse_count": 1,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "waste_warnings_json": ["research_cache_hit"],
        }
    )
    dumped = read.model_dump()
    assert dumped["web_searches_count"] == 2
    assert dumped["research_memory_reuse_count"] == 1
    assert dumped["provenance_summary"]
    assert any("Web searches" in t for t in dumped["research_tips"])
    assert "evidence_ledger_json" not in dumped


def test_export_strips_urls_and_arabic_citation_cues():
    dirty = (
        "النقطة دي مهمة.\n"
        "شوف https://docs.meta.com/ads و حسب المصدر ويكيبيديا.\n"
        "كمل بالخطوة الجاية."
    )
    clean = strip_research_leaks_from_script(dirty)
    assert "https://" not in clean.lower()
    assert "حسب المصدر" not in clean

    final = FinalCourse(
        title="Course",
        full_text="x",
        modules=[
            FinalModule(
                module_id="m1",
                title="Module",
                reels=[
                    FinalReel(
                        reel_id="m1-r1",
                        title="Lesson",
                        # Pass dirty through export — last-chance strip must catch it.
                        script_text=dirty,
                    )
                ],
            )
        ],
    )
    text = extract_plain_text(render_final_course_docx(final)).lower()
    assert "https://" not in text
    assert "حسب المصدر" not in text
    assert "docs.meta.com" not in text
