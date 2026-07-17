"""User-facing status values for CourseSource.

CourseSource.status is a plain string column (not a DB-level enum - see
app/models/course_source.py), so these are defined as constants here rather
than in app/models/enums.py. The message mapping is the single source of
truth the API uses to explain a status to the user (see
app/schemas/course_source.py status_message).
"""

UPLOADED = "uploaded"
PROCESSING = "processing"
READY = "ready"
PASSWORD_REQUIRED = "password_required"
EXTRACTION_BLOCKED = "extraction_blocked"
SCANNED_NO_TEXT = "scanned_no_text"
POOR_EXTRACTION = "poor_extraction"
FAILED = "failed"
PROCESSING_FAILED = "processing_failed"

SOURCE_STATUS_MESSAGES: dict[str, str] = {
    UPLOADED: "Uploaded - not yet processed.",
    PROCESSING: "Processing the uploaded file.",
    READY: "Text extracted successfully. Ready to use for generation.",
    PASSWORD_REQUIRED: (
        "This PDF is password-protected. Use Unlock with the correct password "
        "(no need to re-upload), or replace the file."
    ),
    EXTRACTION_BLOCKED: (
        "No text could be extracted from this file. It may be corrupted or "
        "in a format we can't read. Try Retry, or upload a cleaner copy."
    ),
    SCANNED_NO_TEXT: (
        "This PDF appears to be scanned or image-only (no selectable text). "
        "OCR is not supported in V1 — export a text PDF from your scanner/app, "
        "or paste the text as notes, then upload again."
    ),
    POOR_EXTRACTION: (
        "The extracted text looks too short or garbled to be reliable. "
        "It is excluded from generation until you explicitly include it. "
        "Prefer replacing with a cleaner file."
    ),
    FAILED: "Something went wrong while processing this file. Try Retry.",
    PROCESSING_FAILED: (
        "The file was uploaded, but text extraction or analysis failed. "
        "You can Retry processing without re-uploading."
    ),
}
