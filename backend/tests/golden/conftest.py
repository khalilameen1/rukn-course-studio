"""Shared fixtures/helpers for the golden test courses (see the module
docstring in `test_no_sources_basic_course.py` for what "golden" means
here).

Deliberately mirrors `backend/tests/test_orchestrator.py`'s conventions
(the `session`/`isolated_storage` fixtures, `_make_course`,
`_make_source_with_analysis`) rather than inventing new ones - this
directory is not a different testing style, just a curated, individually
runnable subset.
"""

from dataclasses import asdict

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.crud import course_sources, courses, source_analyses
from app.models.enums import ExplanationLevel, Priority, SourceCategory, StructureMode
from app.services.source_analysis import analyze_source_text


@pytest.fixture()
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'golden_test.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    """Redirect saved internal JSON / exported DOCX to a temp dir instead
    of real storage/ - same reasoning as test_orchestrator.py."""
    import app.generation.orchestrator as orchestrator_module
    import app.services.docx_export as docx_export_module

    monkeypatch.setattr(orchestrator_module.settings, "storage_outputs_dir", tmp_path)
    monkeypatch.setattr(docx_export_module.settings, "storage_outputs_dir", tmp_path)


def make_course(session, **overrides):
    fields = dict(
        title="Intro to Household Budgeting",
        audience="young adults living independently for the first time",
        outcome="build and stick to a simple monthly budget",
        structure_mode=StructureMode.CONNECTED_NO_MODULES,
        explanation_level=ExplanationLevel.FINAL_ONLY,
    )
    fields.update(overrides)
    return courses.create(session, **fields)


def make_source_with_analysis(
    session,
    course_id,
    text,
    category=SourceCategory.SCIENTIFIC_REFERENCE,
    priority=Priority.MEDIUM,
):
    """Mirrors app/routers/sources.py's real upload/notes-creation path
    (extraction -> analysis), so these golden fixtures compile sources
    exactly the way a real upload would."""
    source = course_sources.create(
        session,
        course_id=course_id,
        source_category=category,
        priority=priority,
        status="ready",
        extracted_text=text,
    )
    analysis = analyze_source_text(text, category.value)
    source_analyses.create(
        session,
        source_id=source.id,
        chunks_json=[asdict(chunk) for chunk in analysis.chunks],
        source_summary=analysis.source_summary,
        key_points_json=analysis.key_points,
        avoid_points_json=analysis.avoid_points,
    )
    return source
