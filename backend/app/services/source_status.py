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
        "This PDF is password-protected. Re-upload it with the correct "
        "password to extract its text."
    ),
    EXTRACTION_BLOCKED: (
        "No text could be extracted from this file. It may be corrupted or "
        "in a format we can't read."
    ),
    SCANNED_NO_TEXT: (
        "This PDF appears to be scanned or image-only, with no selectable "
        "text. OCR isn't supported yet, so this source can't be used for "
        "generation."
    ),
    POOR_EXTRACTION: (
        "The extracted text looks too short or garbled to be reliable. "
        "Consider replacing this source with a cleaner file."
    ),
    FAILED: "Something went wrong while processing this file.",
    PROCESSING_FAILED: (
        "The file was uploaded, but text extraction or analysis failed. "
        "You can retry processing without re-uploading."
    ),
}
