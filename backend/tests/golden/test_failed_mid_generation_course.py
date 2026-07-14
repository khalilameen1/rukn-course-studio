"""Golden test course: a provider failure injected partway through reel
generation.

Regression-relevant fact pinned down here: partial-save behavior - a
mid-pipeline failure ends the job `PARTIAL` (never a raw exception, never
silently discarding already-completed reels), the completed reels survive
on the job row, and a partial DOCX is still exportable from them. Reuses
the `FailAfterNReelsProvider`-style pattern already established in
test_orchestrator.py's resumable-generation tests rather than inventing a
new failure-injection mechanism. See tests/golden/conftest.py for the
"golden" convention and the exact `pytest tests/golden` run command.
"""

from docx import Document

from app.ai.fake_provider import FakeProvider
from app.generation.orchestrator import run_generation
from app.models.enums import JobStatus

from .conftest import make_course


class FailAfterNReelsProvider(FakeProvider):
    """Raises once `fail_after` distinct reels have already completed
    successfully. Mirrors test_orchestrator.py's provider of the same
    name/behavior exactly (kept as its own small copy here, rather than an
    import, so this golden fixture stays self-contained and independently
    runnable)."""

    def __init__(self, fail_after: int):
        super().__init__()
        self.fail_after = fail_after
        self._seen_reel_ids: set[str] = set()

    def write_single_reel(self, input):  # noqa: A002 - matches AIProvider's signature
        if (
            input.reel.reel_id not in self._seen_reel_ids
            and len(self._seen_reel_ids) >= self.fail_after
        ):
            raise RuntimeError("simulated provider failure (golden fixture)")
        self._seen_reel_ids.add(input.reel.reel_id)
        return super().write_single_reel(input)


def test_mid_generation_failure_preserves_partial_output(session):
    course = make_course(session)
    provider = FailAfterNReelsProvider(fail_after=2)

    job = run_generation(session, course.id, provider=provider)

    assert job.status == JobStatus.PARTIAL
    assert job.error_message
    assert job.completed_reels_count == 2
    assert len(job.completed_reels_json) == 2
    assert job.course_map_json is not None

    assert job.partial_docx_path
    document = Document(job.partial_docx_path)
    texts = [p.text for p in document.paragraphs]
    assert "Partial draft" in texts[0]
    # Only the two reels that actually completed made it into the partial
    # DOCX - the third (never written) must not appear.
    completed_titles = {r["title"] for r in job.completed_reels_json}
    assert len(completed_titles) == 2
    body_text = "\n".join(texts)
    for title in completed_titles:
        assert title in body_text

    # Output scoring (§4) still runs against whatever partial content made
    # it out, even though the run itself failed.
    assert job.output_score_json is not None
    assert job.output_score_json["module_lesson_structure_present"] is True
