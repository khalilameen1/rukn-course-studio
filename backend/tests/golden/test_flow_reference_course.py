"""Golden test course: one small `flow_reference` source with a planted
catchphrase.

Regression-relevant fact pinned down here: a `flow_reference` source is
always reduced to a `human_flow_profile`-shaped qualitative description
(see `app/generation/prompt_compiler.py` `build_flow_profile`/
`_serialize_flow_profile`) - never the source's actual wording, and
*especially* never its planted catchphrase/signature line, which is the
one thing the Source Authority Firewall explicitly forbids copying for
this category. See tests/golden/conftest.py for the "golden" convention
and the exact `pytest tests/golden` run command.
"""

from app.ai.fake_provider import FakeProvider
from app.generation.orchestrator import run_generation
from app.models.enums import JobStatus, Priority, SourceCategory

from .conftest import make_course, make_source_with_analysis

# A deliberately distinctive, never-legitimately-generated phrase - if this
# ever shows up anywhere in a compiled excerpt (or, transitively, the final
# DOCX), the Source Authority Firewall has been violated.
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

    def build_course_map(self, input):  # noqa: A002 - matches AIProvider's signature
        self.map_calls.append(input)
        return super().build_course_map(input)


def test_flow_reference_becomes_a_profile_never_the_catchphrase(session):
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
    excerpt = provider.map_calls[0].sources[0]

    assert excerpt.category == SourceCategory.FLOW_REFERENCE.value
    # Never the catchphrase, never the raw text verbatim.
    assert PLANTED_CATCHPHRASE not in excerpt.text
    assert FLOW_SOURCE_TEXT not in excerpt.text
    # Must actually be the profile shape, not just "happens not to contain
    # the catchphrase" - `_serialize_flow_profile` always starts with this
    # literal marker.
    assert excerpt.text.startswith("Flow/style reference (heuristic profile")
    assert "pacing:" in excerpt.text
    assert "Things not to copy from this source" in excerpt.text

    # Never allowed to be treated as course knowledge/format for this
    # category (Source Authority Firewall).
    assert "copy_catchphrases_or_signature_lines" in excerpt.disallowed_use
    assert "use_as_course_knowledge" in excerpt.disallowed_use

    # And the catchphrase must never leak all the way through to the final
    # exported DOCX either.
    from docx import Document

    document = Document(job.output_docx_path)
    full_text = "\n".join(p.text for p in document.paragraphs)
    assert PLANTED_CATCHPHRASE not in full_text
