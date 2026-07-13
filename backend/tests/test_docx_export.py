"""Tests for app/services/docx_export.py."""

from docx import Document

from app.schemas.generation import FinalCourse, FinalModule, FinalReel
from app.services.docx_export import (
    export_final_course_to_docx,
    next_version_number,
    render_final_course_docx,
)


def _sample_final_course() -> FinalCourse:
    return FinalCourse(
        title="Intro to Excel Formulas",
        modules=[
            FinalModule(
                module_id="m1",
                title="Module 1: Getting Started",
                bridge_project="Build a starter budget sheet",
                reels=[
                    FinalReel(reel_id="m1-r1", title="Reel 1: Opening Excel", script_text="Line one.\nLine two."),
                    FinalReel(reel_id="m1-r2", title="Reel 2: Basic Formulas", script_text="Type an equals sign."),
                ],
            ),
            FinalModule(
                module_id="m2",
                title="Module 2: Budgets",
                bridge_project=None,
                reels=[
                    FinalReel(reel_id="m2-r1", title="Reel 3: Totals", script_text="Use SUM to add a column."),
                ],
            ),
        ],
        full_text="irrelevant - the exporter renders from `modules`, not this",
    )


def _headings(document) -> list[tuple[str, str]]:
    """[(style_name, text), ...] for every heading paragraph in the doc."""
    return [
        (p.style.name, p.text)
        for p in document.paragraphs
        if p.style.name.startswith("Heading") or p.style.name == "Title"
    ]


def test_render_includes_course_title_as_top_level_heading():
    document = render_final_course_docx(_sample_final_course())

    headings = _headings(document)
    assert headings[0] == ("Title", "Intro to Excel Formulas")


def test_render_includes_each_module_and_reel_as_headings_in_order():
    document = render_final_course_docx(_sample_final_course())

    headings = [text for style, text in _headings(document) if style != "Title"]
    assert headings == [
        "Module 1: Getting Started",
        "Reel 1: Opening Excel",
        "Reel 2: Basic Formulas",
        "Module 2: Budgets",
        "Reel 3: Totals",
    ]


def test_render_includes_script_text_under_each_reel():
    document = render_final_course_docx(_sample_final_course())

    body_texts = [p.text for p in document.paragraphs if not p.style.name.startswith("Heading")]
    assert "Line one." in body_texts
    assert "Line two." in body_texts
    assert "Type an equals sign." in body_texts
    assert "Use SUM to add a column." in body_texts


def test_render_adds_bridge_project_after_module_when_present():
    document = render_final_course_docx(_sample_final_course())

    bridge_paragraphs = [p for p in document.paragraphs if "Bridge project:" in p.text]
    assert len(bridge_paragraphs) == 1
    assert "Build a starter budget sheet" in bridge_paragraphs[0].text
    # Module 2 has no bridge_project, so there must be exactly one overall.


def test_next_version_number():
    assert next_version_number([]) == 1
    assert next_version_number([1]) == 2
    assert next_version_number([1, 2, 3]) == 4
    assert next_version_number([5, 1, 3]) == 6


def test_export_final_course_to_docx_writes_real_openable_file(tmp_path, monkeypatch):
    import app.services.docx_export as docx_export_module

    monkeypatch.setattr(docx_export_module.settings, "storage_outputs_dir", tmp_path)

    path = export_final_course_to_docx(_sample_final_course(), course_id=42, version_number=3)

    assert path == tmp_path / "42" / "course_v3.docx"
    assert path.exists()

    reopened = Document(str(path))
    texts = [p.text for p in reopened.paragraphs]
    assert "Intro to Excel Formulas" in texts
    assert "Module 1: Getting Started" in texts
