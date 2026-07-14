"""Golden test course: one small `scientific_reference` source with an
invented factual snippet.

Regression-relevant facts pinned down here: the prompt compiler
(app/generation/prompt_compiler.py `compile_source_context`) never sends a
verbatim copy of a long `scientific_reference` source to the provider -
only an extract/summary - and every compiled excerpt still carries that
category's `allowed_use`/`disallowed_use` labels (the "Source Authority
Firewall"). See tests/golden/conftest.py for the "golden" convention and
the exact `pytest tests/golden` run command.
"""

from app.ai.fake_provider import FakeProvider
from app.generation.orchestrator import run_generation
from app.models.enums import JobStatus, Priority, SourceCategory
from app.services.source_analysis import SHORT_SOURCE_MAX_CHARS

from .conftest import make_course, make_source_with_analysis

# An invented fact, deliberately padded well past SHORT_SOURCE_MAX_CHARS so
# the compiler's "long source -> extract, not full text" path is actually
# exercised (a short source would legitimately pass through verbatim).
_INVENTED_FACT = (
    "According to the (fictional, test-only) Nabta Household Finance Survey, "
    "households that track every expense for at least six consecutive weeks "
    "report a median reduction of 14% in discretionary spending within the "
    "following three months. "
)
_PADDING = "This paragraph exists purely to pad the source past the short-source threshold. "
SCIENTIFIC_SOURCE_TEXT = _INVENTED_FACT + (_PADDING * 40)

assert len(SCIENTIFIC_SOURCE_TEXT) > SHORT_SOURCE_MAX_CHARS


class RecordingProvider(FakeProvider):
    """Records every `BuildCourseMapInput`/`WriteSingleReelInput` it
    receives, so this test can inspect exactly which `SourceExcerpt`s the
    prompt compiler produced for this run - same pattern as
    `test_orchestrator.py`'s `RecordingProvider`."""

    def __init__(self):
        super().__init__()
        self.map_calls = []
        self.reel_calls = []

    def build_course_map(self, input):  # noqa: A002 - matches AIProvider's signature
        self.map_calls.append(input)
        return super().build_course_map(input)

    def write_single_reel(self, input):  # noqa: A002
        self.reel_calls.append(input)
        return super().write_single_reel(input)


def test_scientific_reference_excerpt_is_extracted_not_copied_verbatim(session):
    course = make_course(session)
    make_source_with_analysis(
        session,
        course.id,
        SCIENTIFIC_SOURCE_TEXT,
        category=SourceCategory.SCIENTIFIC_REFERENCE,
        priority=Priority.HIGH,
    )

    provider = RecordingProvider()
    job = run_generation(session, course.id, provider=provider)

    assert job.status == JobStatus.COMPLETED
    assert provider.map_calls, "expected at least one build_course_map call"

    map_excerpts = provider.map_calls[0].sources
    assert len(map_excerpts) == 1
    excerpt = map_excerpts[0]

    assert excerpt.category == SourceCategory.SCIENTIFIC_REFERENCE.value
    # The compiled excerpt must be shorter than the source - i.e. an
    # extract/summary, never the full padded text verbatim.
    assert len(excerpt.text) < len(SCIENTIFIC_SOURCE_TEXT)
    # Source Authority Firewall: allowed/disallowed-use labels travel with
    # every compiled excerpt, independent of what the source itself says.
    assert "extract_factual_knowledge" in excerpt.allowed_use
    assert "imitate_source_tone" in excerpt.disallowed_use
    assert excerpt.style_contamination_warning

    # Reel writing gets the same treatment (its own query-scoped excerpt,
    # not the raw source either).
    assert provider.reel_calls, "expected at least one write_single_reel call"
    reel_excerpts = provider.reel_calls[0].sources
    assert len(reel_excerpts) == 1
    assert len(reel_excerpts[0].text) < len(SCIENTIFIC_SOURCE_TEXT)

    # The run snapshot (§2/§3) must record this source as actually used.
    used_source_ids = job.run_snapshot_json["source_ids_used"]
    assert len(used_source_ids) == 1
