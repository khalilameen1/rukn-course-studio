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

from pydantic import BaseModel, Field, model_validator

from app.models.enums import AddressForm, CourseFamily, CourseMixType, LessonDeliveryMode


class ReviewScope(str, Enum):
    """Scopes whose findings can change acceptance or trigger a rewrite."""

    REEL = "reel"
    MODULE = "module"
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


class CourseThesis(BaseModel):
    """Internal course thesis — required before Course Map generation.

    Hard limits cannot be exceeded by the AI alone; human_override_hard_limits
    must be an explicit human choice (with UI warning).
    """

    final_student_outcome: str
    audience_and_starting_level: str
    practical_deliverable: str
    in_scope: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    course_type: str = "practical_skill"
    course_domain: str = ""
    course_specialty: str = ""
    primary_course_family: CourseFamily = CourseFamily.GENERAL_SKILL
    secondary_course_families: list[CourseFamily] = Field(default_factory=list)
    target_market: str = "egypt"
    student_language: str = "ar"
    spoken_variety: str = "egyptian_colloquial"
    learner_starting_state: str = ""
    required_final_performance: str = ""
    required_independence_level: str = "independent_with_checklist"
    instructor_responsibility_boundaries: list[str] = Field(default_factory=list)
    verified_instructor_experience: list[str] = Field(default_factory=list)
    forbidden_first_person_claims: list[str] = Field(default_factory=list)
    realistic_student_budget: str = ""
    available_tools: list[str] = Field(default_factory=list)
    professional_constraints: list[str] = Field(default_factory=list)
    high_stakes_constraints: list[str] = Field(default_factory=list)
    beginner_assumption_policy: str = "no_undeclared_prerequisites"
    experienced_learner_policy: str = "respect_existing_competence"
    mix_type: CourseMixType = CourseMixType.PRACTICAL
    target_theory_ratio: float = 0.25
    target_practice_ratio: float = 0.60
    target_minutes_min: int = 150
    target_minutes_max: int = 210
    hard_max_minutes: int = 240
    target_lessons_min: int = 35
    target_lessons_max: int = 55
    hard_max_lessons: int = 60
    size_basis_capabilities: list[str] = Field(default_factory=list)
    size_derivation: str = "capability_based"
    required_tools: list[str] = Field(default_factory=list)
    final_project: str = ""
    address_form: AddressForm = AddressForm.MASCULINE
    human_override_hard_limits: bool = False


class ModuleProject(BaseModel):
    """Practical project after a module — not a numbered lesson."""

    name: str
    brief: str
    inputs_or_files: list[str] = Field(default_factory=list)
    deliverable_shape: str = ""
    pass_criteria: list[str] = Field(default_factory=list)
    skills_tested: list[str] = Field(default_factory=list)

    @classmethod
    def from_bridge_text(cls, text: str | None, *, module_title: str = "") -> "ModuleProject | None":
        raw = (text or "").strip()
        if not raw:
            return None
        return cls(
            name=f"مشروع: {module_title}".strip(": ") if module_title else "مشروع الموديول",
            brief=raw,
            deliverable_shape="تسليم عملي قصير",
            pass_criteria=["ينفّذ المطلوب بوضوح", "يستخدم مهارات الموديول"],
            skills_tested=[],
        )


class LessonSemanticContract(BaseModel):
    """Meaning that must exist before prose is written for one lesson."""

    learner_before: str
    learner_after: str
    exact_capability_change: str
    strongest_non_obvious_meaning: str
    misconception_or_failure: str
    causal_explanation: str
    proof_example_or_demonstration: str
    learner_test_or_action: str
    boundary_or_exception: str
    real_tension: str
    complete_payoff: str
    earned_next_need: str
    escalation_role: str
    sequence_dependency: str


class ReelPlan(BaseModel):
    """One reel's plan, produced while building the CourseMap (Stage 1).

    Includes Lesson Blueprint fields (internal). No script text yet.
    """

    reel_id: str
    title: str
    purpose: str
    must_cover: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)
    source_hints: list[str] = Field(default_factory=list)
    # Free-form legacy estimate; also derived from delivery_mode ranges.
    estimated_length: str = ""

    # --- Lesson Blueprint (internal) ------------------------------------
    distinct_teaching_outcome: str = ""
    new_skill_or_decision: str = ""
    why_standalone: str = ""
    student_can_do_after: str = ""
    delivery_mode: LessonDeliveryMode | None = None
    target_spoken_words_min: int | None = None
    target_spoken_words_max: int | None = None
    needs_screen_or_visual: bool = False
    internal_visual_plan: str = ""
    required_assets: list[str] = Field(default_factory=list)
    source_references: list[str] = Field(default_factory=list)
    prerequisite_lesson_ids: list[str] = Field(default_factory=list)
    project_contribution: str = ""
    already_taught_forbid_repeat: list[str] = Field(default_factory=list)
    # True → may open a natural need for the next lesson; False → clean close.
    needs_natural_bridge: bool = False
    lesson_semantic_contract: LessonSemanticContract | None = None


class ModulePlan(BaseModel):
    """One module's plan: its reels plus an optional module project.

    `bridge_project` is the legacy free-form string. Prefer `module_project`.
    `reels` may be empty in unit tests that inject a reel separately; the
    Anthropic map path rejects maps with zero lessons before save.
    """

    module_id: str
    title: str
    purpose: str
    bridge_project: str | None = None
    module_project: ModuleProject | None = None
    reels: list[ReelPlan] = Field(default_factory=list)
    # Running practical case used across lessons in this module (internal).
    continuous_case: str = ""

    @model_validator(mode="after")
    def _sync_project(self) -> "ModulePlan":
        # Legacy bridge_project string → structured module_project.
        # Do not force bridge_project from module_project (last modules may
        # have a project without a bridge-to-next string).
        if self.module_project is None and self.bridge_project:
            self.module_project = ModuleProject.from_bridge_text(
                self.bridge_project, module_title=self.title
            )
        return self


class CourseMap(BaseModel):
    """Stage 1 output: the full course skeleton before any reel is generated.

    ``modules`` must be non-empty so Anthropic tool schemas advertise
    ``minItems: 1`` and sparse title-only maps fail validation instead of
    surviving into a silent Unusable response after the two-pass map.
    """

    course_title: str
    main_thread: str
    modules: list[ModulePlan] = Field(min_length=1)
    thesis: CourseThesis | None = None
    graduation_project: ModuleProject | None = None


class GeneratedReel(BaseModel):
    """Stage 2 output for one reel, after generation and its Stage 3 self-check.

    Primary spoken source is `spoken_beats`. `script_text` is the plain
    derived teleprompter body (no metadata labels).
    """

    reel_id: str
    module_id: str
    title: str
    script_text: str
    spoken_beats: list[str] = Field(default_factory=list)
    used_ideas: list[str] = Field(default_factory=list)
    used_examples: list[str] = Field(default_factory=list)
    self_check_status: ReviewStatus
    delivery_mode: LessonDeliveryMode | None = None
    quality_status: str = "pass"  # pass | needs_review | fail (internal)
    quality_report: dict = Field(default_factory=dict)  # internal only


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
    # Structured editorial fields (optional; older callers omit them).
    violation_type: str = ""
    severity: str = ""  # fatal | serious | minor | note
    evidence: str = ""
    required_repair: str = ""
    requires_rewrite: bool = True
    affects_map_or_other_lessons: bool = False


class ReviewResult(BaseModel):
    """Actionable review output; findings must rewrite content or block it."""

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
    spoken_beats: list[str] = Field(default_factory=list)
    delivery_mode: LessonDeliveryMode | None = None
    quality_status: str = "pass"


class FinalModule(BaseModel):
    """One module's final structure: title, its final reels (in order), and
    an optional module project - everything DOCX export needs, already
    grouped and ordered."""

    module_id: str
    title: str
    bridge_project: str | None = None
    module_project: ModuleProject | None = None
    reels: list[FinalReel] = Field(default_factory=list)
    # Intentionally no bridge→module_project sync here: legacy bridge_project
    # stays internal. Only structured module_project is exported to DOCX.


class FinalCourse(BaseModel):
    """Stage 7 output, handed to Stage 8 (DOCX export).

    `modules` carries the final, approved reel scripts grouped by module
    (reflecting any Stage 7 rebuild) - this is the structured data DOCX
    export renders from. `full_text` is a flattened, human-skimmable
    rendering of the same content (module/reel headers as "#"/"##" lines)
    for quick internal review/logging - it is not what the exporter parses.
    """

    title: str
    modules: list[FinalModule] = Field(default_factory=list)
    full_text: str
    graduation_project: ModuleProject | None = None
    thesis: CourseThesis | None = None
