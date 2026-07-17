"""DOCX export for a finished, reviewed course (docs/ARCHITECTURE.md Stage 8).

Renders a `FinalCourse` (see app/schemas/generation.py) into a real .docx
following the teleprompter contract: course title, module headings, lesson
headings, spoken beats (no punctuation in body), module projects between
modules, and graduation project. Never production notes, sources, reviews,
Hook/Loop labels, or critic metadata.
"""

from pathlib import Path

from docx import Document
from docx.document import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt
from docx.text.paragraph import Paragraph

from app.config import settings
from app.generation.contracts.spoken_final_master import (
    beats_to_plain_script,
    strip_punctuation_from_spoken_body,
    text_to_spoken_beats,
)
from app.schemas.generation import (
    CourseMap,
    FinalCourse,
    FinalModule,
    FinalReel,
    GeneratedReel,
    ModuleProject,
)

TELEPROMPTER_FONT = "Arial"
BODY_FONT_SIZE = Pt(14)
BODY_LINE_SPACING = 1.5
_HEADING_STYLE_SIZES = {
    "Title": Pt(28),
    "Heading 1": Pt(20),
    "Heading 2": Pt(16),
    "Heading 3": Pt(14),
}


def _set_style_font(style, size: Pt) -> None:
    style.font.name = TELEPROMPTER_FONT
    style.font.size = size
    r_pr = style.element.get_or_add_rPr()
    r_fonts = r_pr.find(qn("w:rFonts"))
    if r_fonts is None:
        r_fonts = r_pr.makeelement(qn("w:rFonts"), {})
        r_pr.append(r_fonts)
    r_fonts.set(qn("w:cs"), TELEPROMPTER_FONT)


def _set_rtl(paragraph: Paragraph) -> Paragraph:
    p_pr = paragraph._p.get_or_add_pPr()  # noqa: SLF001
    if p_pr.find(qn("w:bidi")) is None:
        p_pr.append(p_pr.makeelement(qn("w:bidi"), {}))
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    return paragraph


def _apply_teleprompter_formatting(document: DocxDocument) -> None:
    styles = document.styles
    _set_style_font(styles["Normal"], BODY_FONT_SIZE)
    styles["Normal"].paragraph_format.line_spacing = BODY_LINE_SPACING
    styles["Normal"].paragraph_format.space_after = Pt(8)
    for style_name, size in _HEADING_STYLE_SIZES.items():
        _set_style_font(styles[style_name], size)


def _spoken_body_lines(reel: FinalReel) -> list[str]:
    """Spoken lines for DOCX. Keeps intentional blank pause paragraphs."""
    beats = list(reel.spoken_beats or [])
    if beats:
        plain = beats_to_plain_script(beats)
    else:
        plain = reel.script_text or ""
    cleaned = strip_punctuation_from_spoken_body(plain)
    from app.generation.web_research import strip_research_leaks_from_script

    cleaned = strip_research_leaks_from_script(cleaned)
    # Preserve blank lines (teleprompter pauses); drop only trailing empties later.
    return [ln.strip() if ln.strip() else "" for ln in cleaned.splitlines()]


def _add_script_lines(document: DocxDocument, script_text: str) -> None:
    """Legacy helper — prefer reel-aware path; strips punctuation."""
    from app.generation.web_research import strip_research_leaks_from_script

    cleaned = strip_research_leaks_from_script(script_text or "")
    cleaned = strip_punctuation_from_spoken_body(cleaned)
    for line in cleaned.splitlines():
        if line.strip():
            _set_rtl(document.add_paragraph(line.strip()))
        else:
            _set_rtl(document.add_paragraph(""))


def _add_reel_script(document: DocxDocument, reel: FinalReel) -> None:
    lines = _spoken_body_lines(reel)
    # Trim leading/trailing blank pause lines only.
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    if not lines:
        return
    for line in lines:
        _set_rtl(document.add_paragraph(line))


def _add_module_project(document: DocxDocument, project: ModuleProject) -> None:
    """Render a module/graduation project — not a numbered lesson."""
    _set_rtl(document.add_heading(project.name or "مشروع الموديول", level=2))
    if project.brief:
        _set_rtl(document.add_paragraph(project.brief))
    if project.inputs_or_files:
        _set_rtl(document.add_paragraph("المدخلات: " + "، ".join(project.inputs_or_files)))
    if project.deliverable_shape:
        _set_rtl(document.add_paragraph("شكل التسليم: " + project.deliverable_shape))
    if project.pass_criteria:
        _set_rtl(document.add_paragraph("شروط الاجتياز: " + "؛ ".join(project.pass_criteria)))
    if project.skills_tested:
        _set_rtl(document.add_paragraph("المهارات: " + "؛ ".join(project.skills_tested)))


def render_final_course_docx(final_course: FinalCourse) -> DocxDocument:
    """Build the in-memory python-docx Document."""
    document = Document()
    _apply_teleprompter_formatting(document)

    _set_rtl(document.add_heading(final_course.title or "Untitled Course", level=0))

    for module_index, module in enumerate(final_course.modules, start=1):
        if module_index > 1:
            document.add_page_break()

        _set_rtl(document.add_heading(f"Module {module_index} — {module.title}", level=1))

        for lesson_index, reel in enumerate(module.reels, start=1):
            _set_rtl(document.add_heading(f"Lesson {lesson_index} — {reel.title}", level=2))
            _add_reel_script(document, reel)

        # Only structured module_project is exported. Legacy bridge_project stays internal.
        if module.module_project is not None:
            _add_module_project(document, module.module_project)

    if final_course.graduation_project is not None:
        document.add_page_break()
        _set_rtl(document.add_heading("مشروع التخرج", level=1))
        _add_module_project(document, final_course.graduation_project)

    return document


def extract_plain_text(document: DocxDocument) -> str:
    return "\n".join(p.text for p in document.paragraphs)


def next_version_number(existing_version_numbers: list[int]) -> int:
    return max(existing_version_numbers, default=0) + 1


def export_final_course_to_docx(
    final_course: FinalCourse, course_id: int, version_number: int
) -> Path:
    document = render_final_course_docx(final_course)

    course_dir = settings.storage_outputs_dir / str(course_id)
    course_dir.mkdir(parents=True, exist_ok=True)
    output_path = course_dir / f"course_v{version_number}.docx"
    document.save(output_path)
    return output_path


PARTIAL_DRAFT_NOTE = "Partial draft — generation stopped before completion."


def _assemble_partial_course(course_map: CourseMap, reels: list[GeneratedReel]) -> FinalCourse:
    sections: list[str] = []
    final_modules: list[FinalModule] = []

    for module in course_map.modules:
        module_reels = [r for r in reels if r.module_id == module.module_id]
        if not module_reels:
            continue

        sections.append(f"# {module.title}")
        final_reels: list[FinalReel] = []
        for reel in module_reels:
            sections.append(f"## {reel.title}")
            sections.append(reel.script_text)
            final_reels.append(
                FinalReel(
                    reel_id=reel.reel_id,
                    title=reel.title,
                    script_text=reel.script_text,
                    spoken_beats=list(reel.spoken_beats or []),
                    delivery_mode=reel.delivery_mode,
                    quality_status=reel.quality_status,
                )
            )

        final_modules.append(
            FinalModule(
                module_id=module.module_id,
                title=module.title,
                bridge_project=module.bridge_project,
                module_project=module.module_project,
                reels=final_reels,
            )
        )

    return FinalCourse(
        title=course_map.course_title,
        modules=final_modules,
        full_text="\n\n".join(sections),
        graduation_project=course_map.graduation_project,
        thesis=course_map.thesis,
    )


def build_partial_course_from_job(
    course_map_json: dict | str | None, completed_reels_json: list | str | None
) -> FinalCourse:
    from app.services.json_coerce import coerce_json_dict, coerce_json_list

    course_map = CourseMap.model_validate(coerce_json_dict(course_map_json) or {})
    reels = [
        GeneratedReel.model_validate(r)
        for r in coerce_json_list(completed_reels_json)
        if isinstance(r, dict)
    ]
    return _assemble_partial_course(course_map, reels)


def render_partial_course_docx(final_course: FinalCourse) -> DocxDocument:
    document = Document()
    _apply_teleprompter_formatting(document)

    _set_rtl(document.add_paragraph(PARTIAL_DRAFT_NOTE))
    _set_rtl(document.add_heading(final_course.title or "Untitled Course", level=0))

    for module_index, module in enumerate(final_course.modules, start=1):
        if module_index > 1:
            document.add_page_break()

        _set_rtl(document.add_heading(f"Module {module_index} — {module.title}", level=1))

        for lesson_index, reel in enumerate(module.reels, start=1):
            _set_rtl(document.add_heading(f"Lesson {lesson_index} — {reel.title}", level=2))
            _add_reel_script(document, reel)

        # Only structured module_project is exported. Legacy bridge_project stays internal.
        if module.module_project is not None:
            _add_module_project(document, module.module_project)

    return document


def export_partial_course_to_docx(final_course: FinalCourse, course_id: int, job_id: int) -> Path:
    document = render_partial_course_docx(final_course)

    course_dir = settings.storage_outputs_dir / str(course_id)
    course_dir.mkdir(parents=True, exist_ok=True)
    output_path = course_dir / f"partial_job_{job_id}.docx"
    document.save(output_path)
    return output_path
