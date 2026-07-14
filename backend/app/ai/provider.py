"""AI provider abstraction for the generation pipeline (docs/ARCHITECTURE.md).

`AIProvider` is the interface every pipeline stage calls through. Nothing in
this file calls a real AI/LLM API - see app/ai/fake_provider.py for the
deterministic stand-in used while the pipeline itself is being built and
tested. The future orchestrator should depend only on `AIProvider`, never on
a concrete implementation, so swapping in a real provider later is a
one-line change at the call site (not a pipeline rewrite).

Input models here are intentionally decoupled from the DB layer (no
SQLModel/DB session involved) - callers pass plain values, so this module
has no dependency on app.db or app.crud.
"""

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from app.models.enums import (
    ExplanationLevel,
    GenerationPreset,
    StructureMode,
    TargetMarket,
)
from app.schemas.generation import (
    CourseMap,
    FinalCourse,
    GeneratedReel,
    ModulePlan,
    ReelPlan,
    ReviewResult,
)


class CourseBrief(BaseModel):
    """The subset of a Course's fields the pipeline needs to build a map."""

    title: str
    audience: str
    outcome: str
    special_notes: str | None = None
    structure_mode: StructureMode
    explanation_level: ExplanationLevel
    generation_preset: GenerationPreset = GenerationPreset.BALANCED
    manual_map_text: str | None = None
    target_market: TargetMarket = TargetMarket.EGYPT
    course_domain: str | None = None


class SourceExcerpt(BaseModel):
    """One usable piece of source material (see CourseSource.extracted_text).

    Only sources with status `ready`/`poor_extraction` should ever be
    turned into a SourceExcerpt - see app/services/extraction.py.

    `text` is the compact content field - extracted-knowledge
    summary/chunks for `scientific_reference`/`old_course`/`raw_material`,
    a serialized flow profile for `flow_reference`, full text for
    `user_notes`. `allowed_use`/`disallowed_use`/`style_contamination_warning`
    are the "Source Authority Firewall" metadata (see
    app/generation/prompt_compiler.py): they label exactly what a source
    may and may never be used for, so no uploaded source can ever define
    Rukn's language, format, or structure - that authority comes only from
    Admin Knowledge and explicit user instructions. All three default to
    "nothing set" so existing callers/tests that build a `SourceExcerpt`
    directly (without going through `compile_source_context`) keep working
    unchanged.
    """

    source_id: int
    category: str
    priority: str
    text: str
    allowed_use: list[str] = Field(default_factory=list)
    disallowed_use: list[str] = Field(default_factory=list)
    style_contamination_warning: str | None = None


class PriorReelSummary(BaseModel):
    """Compact context about an already-generated reel.

    Deliberately NOT the full script - docs/ARCHITECTURE.md Stage 2 passes
    a bounded summary of prior reels (not their full text) so cost/quality
    stay stable regardless of course length.
    """

    reel_id: str
    title: str
    used_ideas: list[str] = Field(default_factory=list)
    used_examples: list[str] = Field(default_factory=list)


class ModuleWithReels(BaseModel):
    """A module plan paired with the reels generated for it so far."""

    module: ModulePlan
    reels: list[GeneratedReel] = Field(default_factory=list)


class BuildCourseMapInput(BaseModel):
    brief: CourseBrief
    sources: list[SourceExcerpt] = Field(default_factory=list)
    rules_context: dict[str, str] = Field(default_factory=dict)
    # Compact synthetic creator persona (internal). Guides map planning tone/
    # variety; never appears in DOCX.
    course_creator_persona: dict[str, str] = Field(default_factory=dict)
    # Two-pass map: first_draft then final_master after student/critic/mentor.
    map_phase: str = "first_draft"
    previous_map_feedback: list[str] = Field(default_factory=list)
    # Quality mode hint for duration floor (premium vs preview/mini).
    generation_quality_mode: str = "premium"


class WriteSingleReelInput(BaseModel):
    course_title: str
    main_thread: str
    module: ModulePlan
    reel: ReelPlan
    prior_reels_in_module: list[PriorReelSummary] = Field(default_factory=list)
    sources: list[SourceExcerpt] = Field(default_factory=list)
    rules_context: dict[str, str] = Field(default_factory=dict)
    # `first_draft`: creator writes the full draft uninterrupted.
    # `final_master`: creator rewrites after the combined review bundle.
    # See orchestrator `_write_and_review_reel`. Never expose drafts in DOCX.
    write_phase: str = "first_draft"
    # For `final_master`: compact combined student + critic + mentor feedback
    # from the completed first draft. Empty when writing `first_draft`.
    previous_review_feedback: list[str] = Field(default_factory=list)
    # Dynamic Teaching Curve (internal planning only — never DOCX). Compact
    # label dicts from app/generation/teaching_curves.py; guide voice/length/
    # energy for this write. Omitted labels mean "provider may ignore".
    module_curve: dict[str, str] = Field(default_factory=dict)
    lesson_curve: dict[str, str] = Field(default_factory=dict)
    # Synthetic field-specific viral educator persona (internal — never DOCX).
    course_creator_persona: dict[str, str] = Field(default_factory=dict)
    module_persona_adjustment: dict[str, str] = Field(default_factory=dict)
    lesson_persona_state: dict[str, str] = Field(default_factory=dict)
    # Market realism for examples / client scenarios (prompt + local gates).
    target_market: TargetMarket = TargetMarket.EGYPT


class ReviewSingleReelInput(BaseModel):
    reel_plan: ReelPlan
    generated_reel: GeneratedReel
    rules_context: dict[str, str] = Field(default_factory=dict)
    # Compact lesson persona + review reminders (internal).
    lesson_persona_state: dict[str, str] = Field(default_factory=dict)
    persona_review_reminders: list[str] = Field(default_factory=list)
    # `draft_bundle`: Student Agent + Specialist Critic Agent + Master Mentor
    # Agent review of the completed first draft (Creator does not self-criticize).
    # `sanity_check`: optional compact post-final pass — prefer local validators.
    review_mode: str = "draft_bundle"


class ReviewFiveReelsInput(BaseModel):
    reels: list[GeneratedReel]
    rules_context: dict[str, str] = Field(default_factory=dict)


class ReviewModuleInput(BaseModel):
    module: ModulePlan
    reels: list[GeneratedReel]
    rules_context: dict[str, str] = Field(default_factory=dict)


class ReviewTwoModulesInput(BaseModel):
    first: ModuleWithReels
    second: ModuleWithReels
    rules_context: dict[str, str] = Field(default_factory=dict)


class FinalReviewInput(BaseModel):
    course_map: CourseMap
    all_reels: list[GeneratedReel]
    rules_context: dict[str, str] = Field(default_factory=dict)


class RebuildFinalCourseInput(BaseModel):
    course_map: CourseMap
    all_reels: list[GeneratedReel]
    final_review: ReviewResult
    rules_context: dict[str, str] = Field(default_factory=dict)


class AIProvider(ABC):
    """Every pipeline stage (docs/ARCHITECTURE.md §6, stages 1-2 and 3-7) calls through this."""

    @abstractmethod
    def build_course_map(self, input: BuildCourseMapInput) -> CourseMap: ...

    @abstractmethod
    def write_single_reel(self, input: WriteSingleReelInput) -> GeneratedReel: ...

    @abstractmethod
    def review_single_reel(self, input: ReviewSingleReelInput) -> ReviewResult: ...

    @abstractmethod
    def review_five_reels(self, input: ReviewFiveReelsInput) -> ReviewResult: ...

    @abstractmethod
    def review_module(self, input: ReviewModuleInput) -> ReviewResult: ...

    @abstractmethod
    def review_two_modules(self, input: ReviewTwoModulesInput) -> ReviewResult: ...

    @abstractmethod
    def final_review(self, input: FinalReviewInput) -> ReviewResult: ...

    @abstractmethod
    def rebuild_final_course(self, input: RebuildFinalCourseInput) -> FinalCourse: ...
