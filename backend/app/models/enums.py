"""String enums shared by the database models.

Using `str, Enum` so values serialize as plain strings in both SQLite and
JSON API responses, instead of needing custom encoders.
"""

from enum import Enum


class ItemType(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"
    DOCX_TEMPLATE = "docx_template"


class StructureMode(str, Enum):
    CONNECTED_NO_MODULES = "connected_no_modules"
    CONNECTED_MODULES_WITH_BRIDGE_PROJECTS = "connected_modules_with_bridge_projects"


class ExplanationLevel(str, Enum):
    FINAL_ONLY = "final_only"
    SHORT_SUMMARY = "short_summary"
    FULL_REPORT = "full_report"


class SourceCategory(str, Enum):
    MAIN_CONTENT = "main_content"
    SUPPORTING = "supporting"
    SPOKEN_STYLE = "spoken_style"
    OLD_COURSE = "old_course"
    NOTES = "notes"


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
