"""GENSPARK-style mission / roster / synthesis / public job signals."""

from app.generation.agent_roster import build_agent_roster
from app.generation.mission_brief import build_mission_brief, suggest_tighten_brief
from app.generation.public_progress import estimate_live_eta
from app.generation.research_synthesis import (
    format_architecture_summary,
    grounding_confidence_label,
    improve_next_run_tip,
    merge_specialist_excerpts,
    synthesize_research_for_write,
)
from app.generation.web_research import EvidenceEntry, EvidenceLedger, SourceMemory, SourceMemoryItem
from app.schemas.generation_job import GenerationJobRead


def test_mission_brief_card_shape():
    clarity = {
        "clarity_score": 40,
        "premium_recommended": False,
        "warnings": ["thin"],
        "blockers": [],
    }
    mission = build_mission_brief(
        title="Meta Ads for shops",
        audience="shop owners",
        outcome="learn ads",
        clarity=clarity,
        included_source_count=0,
    )
    assert "Build" in mission["headline"]
    assert mission["confidence"] == "needs_sharpening"
    assert mission["tighten_brief_suggestion"]
    assert "Admin Knowledge" in mission["grounding"]


def test_tighten_brief_suggestion():
    tip = suggest_tighten_brief(audience="beginners", outcome="learn Canva")
    assert "sharper" in tip.lower() or "Add who" in tip


def test_agent_roster_transitions():
    running = build_agent_roster(current_stage="generating", status="running")
    assert {a["id"] for a in running} == {"research", "map", "lessons", "quality", "export"}
    assert next(a for a in running if a["id"] == "lessons")["state"] == "running"
    assert next(a for a in running if a["id"] == "research")["state"] == "done"

    done = build_agent_roster(current_stage="done", status="completed")
    assert all(a["state"] == "done" for a in done)


def test_synthesis_and_architecture_and_confidence():
    ledger = EvidenceLedger(
        entries=[
            EvidenceEntry(
                claim_or_gap="a",
                support_status="supported",
                source_title="t",
                note="",
                used_in_script=True,
            ),
            EvidenceEntry(
                claim_or_gap="b",
                support_status="omitted",
                source_title="t2",
                note="",
            ),
        ]
    )
    synth = synthesize_research_for_write(
        ledger=ledger,
        web_excerpts=[("Official Ads", "workflow steps for beginners")],
        upload_memory=SourceMemory(
            items=[SourceMemoryItem(title="n", kind="upload", summary="notes", authority="standard")]
        ),
    )
    assert "synthesized" in synth["public_note"].lower() or "Research" in synth["public_note"]
    assert "SYNTHESIS" in synth["internal_brief"]

    arch = format_architecture_summary(module_count=2, lesson_count=6)
    assert "6 lesson" in arch and "2 module" in arch

    assert grounding_confidence_label(ledger) in {"strong", "mixed", "weak"}
    tip = improve_next_run_tip(grounding_confidence="weak", clarity_score=80)
    assert "source" in tip.lower() or "upload" in tip.lower()


def test_merge_specialist_excerpts_prefers_toolish():
    merged = merge_specialist_excerpts(
        [
            ("Market", "local market notes for egypt shops"),
            ("Docs", "official help center workflow for Ads Manager"),
            ("Practice", "step checklist for beginners"),
        ],
        max_items=3,
    )
    assert merged[0][0] == "Docs"


def test_live_eta_and_job_read_genspark_fields():
    assert "min" in estimate_live_eta(progress_percent=20, quality_mode="premium", total_lessons=8)
    read = GenerationJobRead.model_validate(
        {
            "id": 1,
            "course_id": 1,
            "status": "running",
            "cancel_requested": False,
            "current_stage": "generating",
            "progress_percent": 40,
            "output_docx_path": None,
            "error_category": None,
            "error_message": None,
            "completed_modules_count": 0,
            "completed_reels_count": 2,
            "total_lessons_count": 8,
            "partial_docx_path": None,
            "last_progress_message": "Writing lessons",
            "last_saved_at": None,
            "estimated_usage_summary": None,
            "estimated_duration_summary": None,
            "sources_run_summary": None,
            "provenance_summary": None,
            "architecture_summary": "8 lesson(s) · 2 module(s) · practical path",
            "grounding_confidence": "mixed",
            "research_synthesis_summary": "Research synthesized for writing",
            "improve_next_tip": "Add notes",
            "generation_quality_mode": "premium",
            "web_research_mode": "autonomous_gap_fill",
            "budget_warning": None,
            "web_searches_count": 2,
            "research_memory_reuse_count": 1,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
    )
    dumped = read.model_dump()
    assert dumped["architecture_summary"]
    assert dumped["grounding_confidence"] == "mixed"
    assert dumped["agent_roster"]
    assert dumped["live_eta_summary"]
    assert "evidence_ledger_json" not in dumped
