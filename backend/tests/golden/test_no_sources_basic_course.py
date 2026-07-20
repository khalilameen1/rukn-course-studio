"""Golden test course: brief only, no sources at all.

"Golden" here means: a small, fixed fixture run entirely against
`FakeProvider` (no network calls, no randomness) that pins down one or
more regression-relevant facts about the pipeline. Run just this
directory with:

    pytest tests/golden

(see README.md "Golden test courses" for the full write-up).

This fixture's regression-relevant facts: (1) a course with zero sources
still produces a coherent, COMPLETED teleprompter DOCX end to end, and (2)
a non-default `generation_preset` set on the course is honored end to end
and shows up verbatim in the run snapshot (§2/§3) - preset handling,
spread here rather than duplicated across every fixture.
"""

from docx import Document

from app.generation.orchestrator import run_generation
from app.models.enums import GenerationPreset, JobStatus

from .conftest import make_course


def test_no_sources_produces_a_complete_coherent_docx(session):
    course = make_course(session, generation_preset=GenerationPreset.CREATIVE)

    job = run_generation(session, course.id)

    assert job.status == JobStatus.COMPLETED
    assert job.output_docx_path

    document = Document(job.output_docx_path)
    texts = [p.text for p in document.paragraphs]
    assert course.title in texts
    assert any(t.startswith("Module 1") for t in texts)
    assert any(t.startswith("Lesson 1") for t in texts)

    # Preset handling: the course's own (non-default) preset choice must
    # reach the pipeline and be recorded, not silently fall back to the
    # global default.
    assert (
        job.run_snapshot_json["CONFIG_INPUTS"]["GENERATION_SETTINGS"]["generation_preset"]
        == GenerationPreset.CREATIVE.value
    )
    # No sources at all -> the run snapshot's source list must be empty,
    # not just "not present".
    assert job.run_snapshot_json["SOURCE_LEDGER"] == []
