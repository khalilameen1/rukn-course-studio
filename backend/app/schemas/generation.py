"""Internal-only schemas for the generation pipeline (docs/ARCHITECTURE.md).

These model the handoff points between pipeline stages: course map -> reel
generation -> the 5 layered review stages -> final assembly for export.

They are NOT API request/response models. Nothing in app/routers should
import from this module, and nothing defined here should ever be returned
to the frontend or the end user - per the project rule, the user only ever
sees the final DOCX and an optional short, coarse status (see
app/schemas/generation_job.py), never this internal structure.
"""

from enum import Enum

from pydantic import BaseModel, Field


class ReviewScope(str, Enum):
    """Matches the 5 review stages in docs/ARCHITECTURE.md §6 (stages 3-7)."""

    REEL = "reel"
    FIVE_REELS = "five_reels"
    MODULE = "module"
    TWO_MODULES = "two_modules"
    FINAL = "final"


class ReviewStatus(str, Enum):
    PASS = "pass"
    NEEDS_REVISION = "needs_revision"


class ReviewActionType(str, Enum):
    KEEP = "keep"
    REWRITE = "rewrite"
    MERGE = "merge"
    DELETE = "delete"
    MOVE = "move"
    ADD_MISSING_CONTEXT = "add_missing_context"


class ReelPlan(BaseModel):
    """One reel's plan, produced while building the CourseMap (Stage 1).

    No script text yet - that only exists once Stage 2 generates a
    `GeneratedReel` from this plan.
    """

    reel_id: str
    title: str
    purpose: str
    must_cover: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)
    source_hints: list[str] = Field(default_factory=list)
    # Free-form for now (e.g. "45-60 seconds", "short") - not yet locked to
    # a strict unit; tighten once the real pipeline needs one.
    estimated_length: str


class ModulePlan(BaseModel):
    """One module's plan: its reels plus an optional bridge project.

    `bridge_project` connects this module to the next one (see the
    `rukn_practical_course_rules` admin knowledge rule) and is null for modules
    that don't end in one.

    `reels` may be empty in unit tests that inject a reel separately; the
    Anthropic map path rejects maps with zero lessons before save.
    """

    module_id: str
    title: str
    purpose: str
    bridge_project: str | None = None
    reels: list[ReelPlan] = Field(default_factory=list)


class CourseMap(BaseModel):
    """Stage 1 output: the full course skeleton before any reel is generated.

    ``modules`` must be non-empty so Anthropic tool schemas advertise
    ``minItems: 1`` and sparse title-only maps fail validation instead of
    surviving into a silent Unusable response after the two-pass map.
    """

    course_title: str
    main_thread: str
    modules: list[ModulePlan] = Field(min_length=1)


class GeneratedReel(BaseModel):
    """Stage 2 output for one reel, after generation and its Stage 3 self-check.

    `used_ideas` / `used_examples` are tracked explicitly so later stages
    (five-reel window, module, course-wide review) can detect repetition
    without re-reading every prior reel's full `script_text`.
    """

    reel_id: str
    module_id: str
    title: str
    script_text: str
    used_ideas: list[str] = Field(default_factory=list)
    used_examples: list[str] = Field(default_factory=list)
    self_check_status: ReviewStatus


class ReviewAction(BaseModel):
    """One concrete correction requested by a review stage.

    `reason_code` is a short machine-readable code (e.g. "repetition",
    "hallucination", "laziness", "style_violation", "structure_violation" -
    see the Review Log finding types in docs/ARCHITECTURE.md §4.7);
    `instruction` is the actual human-readable direction fed back into
    regeneration.
    """

    action: ReviewActionType
    target_id: str
    reason_code: str
    instruction: str


class ReviewResult(BaseModel):
    """Output of any of the 5 review stages (Stage 3 through Stage 7)."""

    scope: ReviewScope
    status: ReviewStatus
    actions: list[ReviewAction] = Field(default_factory=list)


class FinalReel(BaseModel):
    """One reel's final, approved script - the unit DOCX export renders as
    a heading + body. Deliberately smaller than GeneratedReel: FinalCourse
    is the export-ready handoff, so it drops fields (used_ideas,
    self_check_status, ...) that are only relevant during generation/review."""

    reel_id: str
    title: str
    script_text: str


class FinalModule(BaseModel):
    """One module's final structure: title, its final reels (in order), and
    an optional bridge project - everything DOCX export needs, already
    grouped and ordered."""

    module_id: str
    title: str
    bridge_project: str | None = None
    reels: list[FinalReel] = Field(default_factory=list)


class FinalCourse(BaseModel):
    """Stage 7 output, handed to Stage 8 (DOCX export).

    `modules` carries the final, approved reel scripts grouped by module
    (reflecting any Stage 7 rebuild) - this is the structured data DOCX
    export renders from. `full_text` is a flattened, human-skimmable
    rendering of the same content (module/reel headers as "#"/"##" lines,
    bridge project as a "[Bridge project] ..." line) for quick internal
    review/logging - it is not what the exporter parses.
    """

    title: str
    modules: list[FinalModule] = Field(default_factory=list)
    full_text: str
