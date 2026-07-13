"""Tests for app/services/extraction.py.

Covers the scenarios called out when this was implemented: txt, md, docx,
normal PDF, encrypted PDF (no/wrong/correct password), scanned/image-only
PDF, a fully blank PDF, and the poor_extraction ("too short") heuristic.
"""

import fitz
import pytest
from docx import Document as DocxDocument

from app.services.extraction import extract_text
from app.services.source_status import (
    EXTRACTION_BLOCKED,
    PASSWORD_REQUIRED,
    POOR_EXTRACTION,
    READY,
    SCANNED_NO_TEXT,
)

SAMPLE_TEXT = (
    "This is a reasonably long sample paragraph of real text used to "
    "validate extraction across the file formats supported by the Rukn "
    "Course Studio ingestion pipeline."
)


def _make_pdf(path, text: str | None = None, image: bool = False) -> None:
    doc = fitz.open()
    page = doc.new_page()
    if text:
        page.insert_textbox(fitz.Rect(36, 36, 560, 750), text)
    if image:
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 100))
        pix.set_rect(pix.irect, (200, 200, 200))
        page.insert_image(fitz.Rect(0, 0, 200, 200), pixmap=pix)
    doc.save(path)
    doc.close()


def _make_encrypted_pdf(path, text: str, user_password: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(36, 36, 560, 750), text)
    doc.save(
        path,
        encryption=fitz.PDF_ENCRYPT_AES_256,
        user_pw=user_password,
        owner_pw=user_password,
    )
    doc.close()


def test_txt_extraction(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_text(SAMPLE_TEXT, encoding="utf-8")

    result = extract_text(path, ".txt")

    assert result.status == READY
    assert result.text == SAMPLE_TEXT


def test_md_extraction(tmp_path):
    path = tmp_path / "sample.md"
    path.write_text(f"# Heading\n\n{SAMPLE_TEXT}", encoding="utf-8")

    result = extract_text(path, ".md")

    assert result.status == READY
    assert "Heading" in result.text
    assert SAMPLE_TEXT in result.text


def test_docx_extraction(tmp_path):
    path = tmp_path / "sample.docx"
    document = DocxDocument()
    document.add_paragraph(SAMPLE_TEXT)
    document.save(path)

    result = extract_text(path, ".docx")

    assert result.status == READY
    assert SAMPLE_TEXT in result.text


def test_normal_pdf_extraction(tmp_path):
    path = tmp_path / "normal.pdf"
    _make_pdf(path, text=SAMPLE_TEXT)

    result = extract_text(path, ".pdf")

    assert result.status == READY
    assert result.text
    assert len(result.text) > 20


def test_encrypted_pdf_without_password_needs_password(tmp_path):
    path = tmp_path / "encrypted.pdf"
    _make_encrypted_pdf(path, SAMPLE_TEXT, user_password="secret123")

    result = extract_text(path, ".pdf")

    assert result.status == PASSWORD_REQUIRED
    assert result.text is None


def test_encrypted_pdf_with_wrong_password_still_needs_password(tmp_path):
    path = tmp_path / "encrypted.pdf"
    _make_encrypted_pdf(path, SAMPLE_TEXT, user_password="secret123")

    result = extract_text(path, ".pdf", password="not-the-password")

    assert result.status == PASSWORD_REQUIRED
    assert result.text is None


def test_encrypted_pdf_with_correct_password_extracts_text(tmp_path):
    path = tmp_path / "encrypted.pdf"
    _make_encrypted_pdf(path, SAMPLE_TEXT, user_password="secret123")

    result = extract_text(path, ".pdf", password="secret123")

    assert result.status == READY
    # PDF text boxes wrap lines, so compare with whitespace normalized
    # rather than requiring an exact substring match.
    assert " ".join(result.text.split()) == SAMPLE_TEXT


def test_scanned_pdf_with_image_and_no_text(tmp_path):
    path = tmp_path / "scanned.pdf"
    _make_pdf(path, text=None, image=True)

    result = extract_text(path, ".pdf")

    assert result.status == SCANNED_NO_TEXT
    assert result.text is None


def test_blank_pdf_with_no_text_and_no_image(tmp_path):
    path = tmp_path / "blank.pdf"
    _make_pdf(path, text=None, image=False)

    result = extract_text(path, ".pdf")

    assert result.status == EXTRACTION_BLOCKED
    assert result.text is None


def test_poor_extraction_for_very_short_text(tmp_path):
    path = tmp_path / "short.txt"
    path.write_text("Hi", encoding="utf-8")

    result = extract_text(path, ".txt")

    assert result.status == POOR_EXTRACTION


@pytest.mark.parametrize("suffix", [".txt", ".md", ".docx", ".pdf"])
def test_never_raises_on_missing_file(tmp_path, suffix):
    missing = tmp_path / f"does-not-exist{suffix}"

    result = extract_text(missing, suffix)

    assert result.status == "failed"
    assert result.error
