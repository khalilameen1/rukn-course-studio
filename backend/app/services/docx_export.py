"""DOCX export for a finished, reviewed course (docs/ARCHITECTURE.md Stage 8).

Renders a `FinalCourse` (see app/schemas/generation.py) into a real .docx
using python-docx, with clean default formatting: course title, each module
as a heading, each reel as a heading with its script text under it, and a
bridge project paragraph after a module if it has one.

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

from app.config import settings
from app.schemas.generation import FinalCourse


def render_final_course_docx(final_course: FinalCourse) -> DocxDocument:
    """Build the in-memory python-docx Document. Split out from saving so
    the rendering logic is testable without touching the filesystem."""
    document = Document()
    document.add_heading(final_course.title or "Untitled Course", level=0)

    for module in final_course.modules:
        document.add_heading(module.title, level=1)

        for reel in module.reels:
            document.add_heading(reel.title, level=2)
            for line in (reel.script_text or "").splitlines():
                if line.strip():
                    document.add_paragraph(line)

        if module.bridge_project:
            paragraph = document.add_paragraph()
            run = paragraph.add_run(f"Bridge project: {module.bridge_project}")
            run.italic = True

    return document


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
