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
    - FLOW_REFERENCE: Natural Colloquial Calibration (storage key stays
      `flow_reference`). Off-topic / unrelated spoken samples used only to
      calibrate natural Egyptian/Arabic speech so scripts do not sound
      translated, stiff, robotic, or artificial. NOT a professional speaking
      reference, flow/structure reference, teaching ideal, hook/pacing model,
      or course-planning input. Never facts/claims/examples/terminology;
      never assume the speaker is good; never copy messy structure.
      Replaces the old SPOKEN_STYLE category.
    - MIXED_QUALITY_AI_COURSE_DRAFT: previous AI-generated course draft that
      may contain useful candidates AND defects. Segment-evaluate; extract
      candidates only; never copy wording/hooks/loops; never treat as quality
      reference or automatic truth. Not worthless.
    - OLD_COURSE: legacy alias for previous course/attempt. Processed with the
      same Mixed Draft Memory pipeline as MIXED_QUALITY_AI_COURSE_DRAFT so
      existing rows keep working (TEXT storage; no rename migration required).
    - USER_NOTES: direct user instructions - highest priority. Adjusts
      scope/audience/tone/constraints; never dropped or truncated by any
      budget-compression step. Replaces the old NOTES category.
    - RAW_MATERIAL: mixed/unclear material. Classify and extract only the
      useful parts; if unclear, mark it as mixed/uncertain rather than
      inventing structure it doesn't have.
    """

    SCIENTIFIC_REFERENCE = "scientific_reference"
    FLOW_REFERENCE = "flow_reference"
    MIXED_QUALITY_AI_COURSE_DRAFT = "mixed_quality_ai_course_draft"
    OLD_COURSE = "old_course"
    USER_NOTES = "user_notes"
    RAW_MATERIAL = "raw_material"
    # Spoken/pasted lesson transcript for this course (never the canonical standard).
    TRANSCRIPT = "transcript"


class SourceOrigin(str, Enum):
    """How the source was produced — separate from file format and user intent.

    A .txt/.docx/.pdf may be a transcript, book extract, OCR scan, or notes;
    extension is not authority. Stored on Source Memory and optionally declared.
    """

    WRITTEN_DOCUMENT = "written_document"
    ACADEMIC_BOOK = "academic_book"
    PRACTICAL_BOOK = "practical_book"
    ARTICLE = "article"
    OLD_COURSE_MATERIAL = "old_course_material"
    COURSE_TRANSCRIPT = "course_transcript"
    AI_GENERATED_TRANSCRIPT = "ai_generated_transcript"
    HUMAN_TRANSCRIPT = "human_transcript"
    OLD_COURSE_TRANSCRIPT = "old_course_transcript"
    MEETING_OR_WEBINAR_TRANSCRIPT = "meeting_or_webinar_transcript"
    SCANNED_PDF = "scanned_pdf"
    OCR_TEXT = "ocr_text"
    SCREENSHOT_OR_IMAGE = "screenshot_or_image"
    TRANSLATED_MATERIAL = "translated_material"
    USER_NOTES = "user_notes"
    UNKNOWN = "unknown"


class ExtractionMethod(str, Enum):
    """How text was obtained from the file/paste — not reliability."""

    DIRECT_TEXT = "direct_text"
    PDF_TEXT = "pdf_text"
    DOCX_TEXT = "docx_text"
    DOC_TEXT = "doc_text"
    OCR = "ocr"
    PASTED_TEXT = "pasted_text"
    MANUAL = "manual"
    UNKNOWN = "unknown"


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
    finished). `PAUSED` / `CANCELED` support cooperative stop without
    starting a duplicate run.
    """

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    PARTIAL = "partial"
    FAILED = "failed"
    COMPLETED = "completed"
    CANCELED = "canceled"


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


class GenerationQualityMode(str, Enum):
    """Operational depth of the multi-agent draft → review → Final Master pipeline.

    Creator Agent writes; Student / Specialist Critic / Master Mentor review
    the completed draft; Creator writes Final Master. Creator never
    self-criticizes.

    - PREMIUM: full draft + Student/Critic/Mentor AI review bundle + final rewrite
      (default for real course generation).
    - PREVIEW: cheaper/faster; simplified local review; still teleprompter-ready.

    Never expose raw temperature or internal agent details in the UI.
    """

    PREVIEW = "preview"
    PREMIUM = "premium"


class WebResearchMode(str, Enum):
    """How missing factual/practical gaps are filled after uploaded sources.

    - DISABLED: use uploaded/pasted sources only.
    - AUTONOMOUS_GAP_FILL (default): research missing facts from trusted web
      sources without asking the user. Never ask for routine confirmations.
    """

    DISABLED = "disabled"
    AUTONOMOUS_GAP_FILL = "autonomous_gap_fill"


class TargetMarket(str, Enum):
    """Course-level learner market context for examples and practical advice.

    Default EGYPT: Egyptian/Arab practical market realism (not US/EU translation).
    GLOBAL: avoid over-localizing; still ban literal-translation tone.
    CUSTOM: respect special_notes / brief for market; still evergreen + clean Arabic.
    """

    EGYPT = "egypt"
    ARAB_MARKET = "arab_market"
    GLOBAL = "global"
    CUSTOM = "custom"


class LessonDeliveryMode(str, Enum):
    """How a lesson is delivered on camera / screen (internal blueprint).

    Content type drives structure and length — not a mechanical reel index.
    """

    CAMERA_EXPLAINER = "camera_explainer"
    MICRO_CONCEPT = "micro_concept"
    SCREEN_DEMO = "screen_demo"
    DESIGN_CRITIQUE = "design_critique"
    CRITIQUE = "critique"
    BEFORE_AFTER = "before_after"
    ERROR_FIX = "error_fix"
    CASE_STUDY = "case_study"
    PROJECT_BUILD = "project_build"


class AddressForm(str, Enum):
    """Stable second-person address form for the whole course."""

    MASCULINE = "masculine"
    FEMININE = "feminine"
    NEUTRAL = "neutral"


class CourseMixType(str, Enum):
    """Theory vs practice mix declared on Course Thesis."""

    PRACTICAL = "practical"
    THEORETICAL = "theoretical"
    MIXED = "mixed"


class GenerationJobKind(str, Enum):
    """What a GenerationJob is producing."""

    FULL_COURSE = "full_course"
    MAP_PREVIEW = "map_preview"
    WRITER_TEST_3_REELS = "writer_test_3_reels"
