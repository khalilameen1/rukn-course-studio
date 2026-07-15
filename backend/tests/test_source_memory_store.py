"""Persistent Source Memory — no full PDF in generation prompts."""

from app.generation.prompt_compiler import SourceForCompiler, compile_source_context
from app.generation.source_distillation import DISTILLED_LABEL
from app.generation.source_memory_store import (
    build_source_memory_payload,
    compiler_text_from_memory,
    format_memory_snippet,
)
from app.generation.web_research import WebSourceMemory, run_autonomous_gap_fill
from app.models.enums import WebResearchMode


LONG_PDF = (
    "Chapter one about Meta ads attribution windows and ROAS for boutique brands. "
    * 80
    + "For example, a local shop burned budget testing cool blue headlines. "
    + "CTR CPA KPI ROAS LTV terminology section follows with more detail. " * 40
)


def test_source_memory_built_once_without_full_prompt_dump():
    memory = build_source_memory_payload(
        title="ads.pdf",
        category="scientific_reference",
        extracted_text=LONG_PDF,
    )
    assert memory["processed_once"] is True
    assert memory["original_chars"] == len(LONG_PDF)
    assert memory["facts"] or memory["summary"]
    snippet = format_memory_snippet(memory, query_text="ROAS attribution shop")
    assert len(snippet) < len(LONG_PDF) // 4
    assert DISTILLED_LABEL in snippet or "Summary" in snippet or "Useful concepts" in snippet
    assert LONG_PDF[:200] not in snippet or len(snippet) < 2000


def test_compile_context_uses_memory_not_full_pdf():
    memory = build_source_memory_payload(
        title="ads.pdf",
        category="scientific_reference",
        extracted_text=LONG_PDF,
    )
    compact = compiler_text_from_memory(
        memory=memory,
        summary=memory["summary"],
        chunks=None,
        fallback_text=LONG_PDF,
        query_text="ROAS Meta ads",
        category="scientific_reference",
    )
    assert len(compact) < 2000
    assert len(compact) < len(LONG_PDF) // 10

    excerpts = compile_source_context(
        [
            SourceForCompiler(
                source_id=1,
                category="scientific_reference",
                priority="high",
                text=compact,
                summary=memory["summary"],
                memory=memory,
            )
        ],
        query_text="ROAS attribution",
    )
    assert len(excerpts) == 1
    assert len(excerpts[0].text) < len(LONG_PDF) // 4
    assert "UNTRUSTED_REFERENCE_MATERIAL" in excerpts[0].text
    assert DISTILLED_LABEL in excerpts[0].text or "Useful concepts" in excerpts[0].text


def test_web_research_reuses_cached_memory_without_repeat_search():
    # Pre-seed the same gap topics identify_factual_gaps would emit for a thin brief.
    cached = WebSourceMemory(
        items=[],
        gaps_researched=["Meta", "shops", "profitable"],
    )

    class CountingBackend:
        def __init__(self) -> None:
            self.calls = 0

        def fetch_facts(self, query: str, *, sensitive: bool):
            self.calls += 1
            return []

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
    )
    assert backend.calls == 0
    assert result.web_searches_count == 0
    assert result.web_cache_hits >= 1


def test_user_notes_still_pass_full_short_text():
    notes = "Please keep lessons under 3 minutes and use WhatsApp examples."
    text = compiler_text_from_memory(
        memory=None,
        summary=None,
        chunks=None,
        fallback_text=notes,
        query_text="",
        category="user_notes",
    )
    assert text == notes
