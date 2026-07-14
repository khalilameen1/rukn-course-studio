"""Golden test course: verifies the final DOCX contains only spoken
script + module/lesson headings, no internal-pipeline notes.

Regression-relevant fact pinned down here: DOCX cleanliness end to end -
reuses the same `TELEPROMPTER_FORBIDDEN_SUBSTRINGS` constant already
established (and, since this pass, centralized in
app/generation/teleprompter_checks.py) for `test_docx_export.py`, so this
fixture and that unit-level test can never silently drift apart on what
"clean" means. Also exercises the Output Scoring Gates (§4) end to end
against the exact same exported document. See tests/golden/conftest.py
for the "golden" convention and the exact `pytest tests/golden` run
command.
"""

from docx import Document

from app.generation.orchestrator import run_generation
from app.generation.teleprompter_checks import (
    TELEPROMPTER_FORBIDDEN_SUBSTRINGS,
    module_lesson_structure_present,
)
from app.models.enums import JobStatus
from app.services.docx_export import extract_plain_text

from .conftest import make_course


def test_final_docx_is_clean_and_scores_as_such(session):
    course = make_course(session)

    job = run_generation(session, course.id)

    assert job.status == JobStatus.COMPLETED
    document = Document(job.output_docx_path)
    text = extract_plain_text(document)
    lowered = text.lower()

    for forbidden in TELEPROMPTER_FORBIDDEN_SUBSTRINGS:
        assert forbidden not in lowered

    assert module_lesson_structure_present(text)

    # The same cleanliness must be reflected in the stored output score
    # (§4) for this run - not just true "by inspection" here, but actually
    # recorded on the job for the frontend's quality warnings panel.
    score = job.output_score_json
    assert score["teleprompter_clean"] is True
    assert score["internal_notes_absent"] is True
    assert score["forbidden_substrings_found"] == []
    assert score["module_lesson_structure_present"] is True
