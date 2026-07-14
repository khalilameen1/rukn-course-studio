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
    """What kind of material one uploaded/pasted source is - drives how the
    prompt compiler treats it (see app/generation/prompt_compiler.py).

    - SCIENTIFIC_REFERENCE: factual/technical/educational material to
      extract, summarize, and rephrase into Rukn's style. Preserve factual
      accuracy; never copy long passages verbatim. Replaces the old
      MAIN_CONTENT and SUPPORTING categories (the "what" of a course).
    - FLOW_REFERENCE: a style/flow/speaking reference - it's about HOW
      something is said, not WHAT is said (hook pattern, pacing,
      transitions, escalation, ending style, human-naturalness). Never
      treated as a factual source; never copied verbatim, including
      catchphrases/signature lines. Replaces the old SPOKEN_STYLE category.
    - OLD_COURSE: a previous course, to understand its structure/strengths/
      weaknesses. Reuse what's useful, avoid its weak parts; don't blindly
      summarize it. Prep for future fusion logic, but no fusion logic
      exists yet.
    - USER_NOTES: direct user instructions - highest priority. Adjusts
      scope/audience/tone/constraints; never dropped or truncated by any
      budget-compression step. Replaces the old NOTES category.
    - RAW_MATERIAL: mixed/unclear material. Classify and extract only the
      useful parts; if unclear, mark it as mixed/uncertain rather than
      inventing structure it doesn't have.
    """

    SCIENTIFIC_REFERENCE = "scientific_reference"
    FLOW_REFERENCE = "flow_reference"
    OLD_COURSE = "old_course"
    USER_NOTES = "user_notes"
    RAW_MATERIAL = "raw_material"


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class JobStatus(str, Enum):
    """`PARTIAL` sits between `RUNNING` and `FAILED`/`COMPLETED`: the run
    stopped early but has usable saved work (a course map and/or at least
    one completed reel) - see app/generation/orchestrator.py's error
    handling for exactly how that's decided. `FAILED` means nothing usable
    was saved yet (e.g. the run failed before the course map even
    finished)."""

    PENDING = "pending"
    RUNNING = "running"
    PARTIAL = "partial"
    FAILED = "failed"
    COMPLETED = "completed"


class GenerationPreset(str, Enum):
    """Named intents for how an AI provider should approach a generation
    task - see app/generation/presets.py for descriptions/temperatures.
    Lives here (not in app/generation/) so it can be a proper SQLModel
    column type on `Course` (app/models/course.py)."""

    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    CREATIVE = "creative"
    FUSION = "fusion"
    STRICT_TELEPROMPTER = "strict_teleprompter"
