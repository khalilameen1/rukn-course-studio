"""Golden test: Natural Colloquial Calibration (`flow_reference`).

Regression facts:
1. Map stage must NOT receive flow_reference (no map/lesson-structure influence).
2. Compiled reel-stage excerpts are Natural Colloquial Calibration only —
   never the planted catchphrase, never hook/pacing/teaching fields.
"""

from app.ai.fake_provider import FakeProvider
from app.generation.orchestrator import run_generation
from app.generation.prompt_compiler import SourceForCompiler, compile_source_context
from app.models.enums import JobStatus, Priority, SourceCategory

from .conftest import make_course, make_source_with_analysis

PLANTED_CATCHPHRASE = "Zoom in, zoom out, and let's gooo!"
FLOW_SOURCE_TEXT = (
    f"{PLANTED_CATCHPHRASE} That's how every single one of my videos starts, no matter "
    f"the topic. Then I ask a quick question to hook you in. Then I move fast through three "
    f"short examples, back to back, no fluff. Then right at the end I say it again: "
    f"{PLANTED_CATCHPHRASE} See you in the next one!"
)


class RecordingProvider(FakeProvider):
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


def test_flow_reference_excluded_from_map_and_profile_never_leaks_catchphrase(session):
    course = make_course(session)
    make_source_with_analysis(
        session,
        course.id,
        FLOW_SOURCE_TEXT,
        category=SourceCategory.FLOW_REFERENCE,
        priority=Priority.MEDIUM,
    )

    provider = RecordingProvider()
    job = run_generation(session, course.id, provider=provider)

    assert job.status == JobStatus.COMPLETED

    for call in provider.map_calls:
        assert all(ex.category != SourceCategory.FLOW_REFERENCE.value for ex in call.sources)

    assert provider.reel_calls
    flow_excerpts = [
        ex
        for call in provider.reel_calls
        for ex in call.sources
        if ex.category == SourceCategory.FLOW_REFERENCE.value
    ]
    assert flow_excerpts
    excerpt = flow_excerpts[0]
    assert PLANTED_CATCHPHRASE not in excerpt.text
    assert FLOW_SOURCE_TEXT not in excerpt.text
    assert "Natural Colloquial Calibration" in excerpt.text
    assert "only for natural colloquial calibration" in excerpt.text
    assert "spoken_sentence_length_feel:" in excerpt.text
    assert "messy_transcript_quality_guard:" in excerpt.text
    assert "Things not to copy from this source" in excerpt.text
    assert "learn_hooks_from_transcript" in excerpt.disallowed_use
    assert "learn_pacing_model" in excerpt.disallowed_use
    assert "support_factual_claims" in excerpt.disallowed_use
    assert excerpt.authority_type == "natural_colloquial_calibration"

    from docx import Document

    document = Document(job.output_docx_path)
    full_text = "\n".join(p.text for p in document.paragraphs)
    assert PLANTED_CATCHPHRASE not in full_text
    assert "Natural Colloquial Calibration" not in full_text
    assert "colloquial calibration" not in full_text.lower()


def test_compile_colloquial_calibration_profile_shape_without_pipeline():
    excerpts = compile_source_context(
        [
            SourceForCompiler(
                source_id=1,
                category="flow_reference",
                priority="medium",
                text=FLOW_SOURCE_TEXT,
            )
        ],
        query_text="",
    )
    assert "Natural Colloquial Calibration" in excerpts[0].text
    assert PLANTED_CATCHPHRASE not in excerpts[0].text
    assert "only for natural colloquial calibration" in excerpts[0].text
