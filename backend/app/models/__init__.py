"""SQLModel table models.

Importing this package registers every table on `SQLModel.metadata`, which
is what `app.db.init_db()` relies on to create all tables on startup.
"""

from app.models.admin_knowledge import AdminKnowledgeItem
from app.models.ai_usage_event import AIUsageEvent
from app.models.audit_log import AuditLog
from app.models.course import Course
from app.models.course_source import CourseSource
from app.models.course_version import CourseVersion
from app.models.enums import (
    ExplanationLevel,
    ItemType,
    JobStatus,
    Priority,
    SourceCategory,
    StructureMode,
)
from app.models.generation_job import GenerationJob
from app.models.source_analysis import SourceAnalysis

# Side-effect imports: register auth / lock tables on SQLModel.metadata.
from app.auth.login_throttle import LoginThrottleEvent  # noqa: F401
from app.auth.token_denylist import RevokedToken  # noqa: F401
from app.generation.map_lock import CourseMapLock  # noqa: F401

__all__ = [
    "AdminKnowledgeItem",
    "AIUsageEvent",
    "AuditLog",
    "Course",
    "CourseSource",
    "CourseVersion",
    "GenerationJob",
    "SourceAnalysis",
    "ItemType",
    "StructureMode",
    "ExplanationLevel",
    "SourceCategory",
    "Priority",
    "JobStatus",
]
