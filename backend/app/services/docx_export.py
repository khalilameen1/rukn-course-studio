"""DOCX export for a finished, reviewed course (docs/ARCHITECTURE.md Stage 8).

Renders a `FinalCourse` (see app/schemas/generation.py) into a real .docx
following the teleprompter contract (see the `rukn_teleprompter_docx_contract`
admin knowledge item, app/seed_admin_knowledge.py): the DOCX is a
teleprompter-ready lecturer script, not a book/handout/report. V1 contains
ONLY the course title, numbered "Module N — title" / "Lesson N — title"
headings, and the spoken script under each lesson — nothing else.

Bridge projects, production notes, asset briefs, reviews, scores, sources,
citations, and planning labels must never appear in the export. Bridge
projects may still exist on the internal course map for teaching structure;
they are not rendered into the DOCX.

If an admin has an active `docx_template` knowledge item (see
app/models/admin_knowledge.py), that should eventually drive
branding/formatting here instead of the defaults below. Not implemented
yet - out of scope for now ("create clean default formatting").

No DB access here (mirrors app/services/extraction.py): version numbering
and CourseVersion creation are the caller's (app/generation/orchestrator.py)
responsibility, this module only renders and saves a file.
"""

from pathlib import Path

from docx import Document
from docx.document import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt
from docx.text.paragraph import Paragraph

from app.config import settings
from app.schemas.generation import CourseMap, FinalCourse, FinalModule, FinalReel, GeneratedReel

# A widely-available, Arabic-friendly font (script content is primarily
# Egyptian Arabic - see rukn_writing_style). Large size + generous line
# spacing so the script is comfortably readable at arm's length on camera.
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
    """Set both the ascii and complex-script ("cs") font on a style.

    python-docx's `style.font.name` only sets the ascii/hAnsi font slot.
    Word renders Arabic text using the separate "cs" slot, which silently
    stays at Word's default font unless set explicitly here too - so
    without this, `TELEPROMPTER_FONT` would only apply to Latin text.
    """
    style.font.name = TELEPROMPTER_FONT
    style.font.size = size
    r_pr = style.element.get_or_add_rPr()
    r_fonts = r_pr.find(qn("w:rFonts"))
    if r_fonts is None:
        r_fonts = r_pr.makeelement(qn("w:rFonts"), {})
        r_pr.append(r_fonts)
    r_fonts.set(qn("w:cs"), TELEPROMPTER_FONT)


def _set_rtl(paragraph: Paragraph) -> Paragraph:
    """Right-to-left paragraph direction + right alignment - this script is
    read on camera, almost always in Arabic. Returns the paragraph so this
    can wrap a `document.add_...` call inline."""
    p_pr = paragraph._p.get_or_add_pPr()  # noqa: SLF001 - python-docx has no public API for bidi
    if p_pr.find(qn("w:bidi")) is None:
        p_pr.append(p_pr.makeelement(qn("w:bidi"), {}))
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    return paragraph


def _apply_teleprompter_formatting(document: DocxDocument) -> None:
    """Large, Arabic-friendly font and comfortable spacing throughout - no
    decorative design, just readable-on-camera defaults (see the
    "Formatting" section of the teleprompter contract)."""
    styles = document.styles
    _set_style_font(styles["Normal"], BODY_FONT_SIZE)
    styles["Normal"].paragraph_format.line_spacing = BODY_LINE_SPACING
    styles["Normal"].paragraph_format.space_after = Pt(8)
    for style_name, size in _HEADING_STYLE_SIZES.items():
        _set_style_font(styles[style_name], size)


def _add_script_lines(document: DocxDocument, script_text: str) -> None:
    """Write spoken transcript lines; preserve blank lines as pause spacing."""
    for line in (script_text or "").splitlines():
        if line.strip():
            _set_rtl(document.add_paragraph(line.strip()))
        else:
            _set_rtl(document.add_paragraph(""))


def render_final_course_docx(final_course: FinalCourse) -> DocxDocument:
    """Build the in-memory python-docx Document. Split out from saving so
    the rendering logic is testable without touching the filesystem."""
    document = Document()
    _apply_teleprompter_formatting(document)

    _set_rtl(document.add_heading(final_course.title or "Untitled Course", level=0))

    for module_index, module in enumerate(final_course.modules, start=1):
        if module_index > 1:
            document.add_page_break()

        _set_rtl(document.add_heading(f"Module {module_index} — {module.title}", level=1))

        for lesson_index, reel in enumerate(module.reels, start=1):
            _set_rtl(document.add_heading(f"Lesson {lesson_index} — {reel.title}", level=2))
            _add_script_lines(document, reel.script_text or "")
        # V1: never render bridge_project / Project blocks into the DOCX.

    return document


def extract_plain_text(document: DocxDocument) -> str:
    """Flatten every paragraph's text into one newline-joined string, in
    document order.

    Read-only: used solely by app/generation/output_scoring.py to run
    observational checks against exactly what the DOCX actually contains -
    never written back into the document, never changes export behavior.
    """
    return "\n".join(p.text for p in document.paragraphs)


def next_version_number(existing_version_numbers: list[int]) -> int:
    """Pure helper: the caller supplies whatever version numbers already
    exist for the course (from CourseVersion rows) and gets the next one."""
    return max(existing_version_numbers, default=0) + 1


def export_final_course_to_docx(
    final_course: FinalCourse, course_id: int, version_number: int
) -> Path:
    """Render and save to storage/outputs/{course_id}/course_v{n}.docx."""
    document = render_final_course_docx(final_course)

    course_dir = settings.storage_outputs_dir / str(course_id)
    course_dir.mkdir(parents=True, exist_ok=True)
    output_path = course_dir / f"course_v{version_number}.docx"
    document.save(output_path)
    return output_path


# --- Partial export (used only when a run stops early - see -----------------
# app/generation/orchestrator.py's error handling) -------------------------
#
# Deliberately separate functions from `render_final_course_docx` /
# `export_final_course_to_docx` above: the completed-DOCX contract and its
# tests must stay byte-for-byte unaffected by this. Everything below
# reuses the same internal formatting helpers so a partial draft looks
# like the same teleprompter document, just visibly marked as partial.
PARTIAL_DRAFT_NOTE = "Partial draft — generation stopped before completion."


def _assemble_partial_course(course_map: CourseMap, reels: list[GeneratedReel]) -> FinalCourse:
    """Adapted from app/generation/orchestrator.py `_assemble_final_course`:
    groups completed reels under their module in map order, but - unlike
    that function - skips any module with zero completed reels instead of
    erroring, since a partial run may have stopped mid-module."""
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
                FinalReel(reel_id=reel.reel_id, title=reel.title, script_text=reel.script_text)
            )

        if module.bridge_project:
            sections.append(f"[Bridge project] {module.bridge_project}")

        final_modules.append(
            FinalModule(
                module_id=module.module_id,
                title=module.title,
                bridge_project=module.bridge_project,
                reels=final_reels,
            )
        )

    return FinalCourse(
        title=course_map.course_title,
        modules=final_modules,
        full_text="\n\n".join(sections),
    )


def build_partial_course_from_job(
    course_map_json: dict | str | None, completed_reels_json: list | str | None
) -> FinalCourse:
    """Reconstruct a `FinalCourse`-shaped structure from a `GenerationJob`'s
    persisted `course_map_json` / `completed_reels_json` (see
    app/models/generation_job.py) - the only usable state a failed/partial
    run leaves behind."""
    from app.services.json_coerce import coerce_json_dict, coerce_json_list

    course_map = CourseMap.model_validate(coerce_json_dict(course_map_json) or {})
    reels = [
        GeneratedReel.model_validate(r)
        for r in coerce_json_list(completed_reels_json)
        if isinstance(r, dict)
    ]
    return _assemble_partial_course(course_map, reels)


def render_partial_course_docx(final_course: FinalCourse) -> DocxDocument:
    """Same module/lesson structure and Arabic-friendly formatting as
    `render_final_course_docx`, plus exactly one extra paragraph before the
    course title marking it as a partial draft - nothing else extra (no
    logs, no review notes, no error text)."""
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
            _add_script_lines(document, reel.script_text or "")
        # V1: never render bridge_project / Project blocks into the DOCX.

    return document


def export_partial_course_to_docx(final_course: FinalCourse, course_id: int, job_id: int) -> Path:
    """Save to storage/outputs/{course_id}/partial_job_{job_id}.docx - a
    naming pattern clearly distinct from a real `course_v{n}.docx` version
    so it can never be confused with a completed version or picked up by
    `next_version_number`/version listings (both only ever look at
    `CourseVersion` rows, never at files on disk)."""
    document = render_partial_course_docx(final_course)

    course_dir = settings.storage_outputs_dir / str(course_id)
    course_dir.mkdir(parents=True, exist_ok=True)
    output_path = course_dir / f"partial_job_{job_id}.docx"
    document.save(output_path)
    return output_path
