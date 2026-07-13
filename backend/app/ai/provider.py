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

from app.models.enums import ExplanationLevel, StructureMode
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
    manual_map_text: str | None = None


class SourceExcerpt(BaseModel):
    """One usable piece of source material (see CourseSource.extracted_text).

    Only sources with status `ready`/`poor_extraction` should ever be
    turned into a SourceExcerpt - see app/services/extraction.py.
    """

    source_id: int
    category: str
    priority: str
    text: str


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


class WriteSingleReelInput(BaseModel):
    course_title: str
    main_thread: str
    module: ModulePlan
    reel: ReelPlan
    prior_reels_in_module: list[PriorReelSummary] = Field(default_factory=list)
    sources: list[SourceExcerpt] = Field(default_factory=list)
    rules_context: dict[str, str] = Field(default_factory=dict)
    # Populated on a retry (see app/generation/orchestrator.py
    # `_write_and_review_reel`): the previous attempt's review instructions,
    # so the rewrite actually targets what was wrong last time instead of
    # blindly regenerating from scratch.
    previous_review_feedback: list[str] = Field(default_factory=list)


class ReviewSingleReelInput(BaseModel):
    reel_plan: ReelPlan
    generated_reel: GeneratedReel
    rules_context: dict[str, str] = Field(default_factory=dict)


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
