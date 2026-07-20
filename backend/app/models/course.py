from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column
from sqlmodel import Field, SQLModel

from app.db_enums import sa_str_enum
from app.db_json import sa_json_array, sa_json_object
from app.models.enums import (
    AddressForm,
    CourseFamily,
    ExplanationLevel,
    GenerationPreset,
    GenerationQualityMode,
    StructureMode,
    TargetMarket,
    WebResearchMode,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Course(SQLModel, table=True):
    """A course brief plus its generation configuration and current status.

    `active_rules_snapshot_json` (deprecated, unused): the docstring below
    originally described intended behavior that was never actually wired
    up anywhere in the codebase (confirmed by grep - nothing ever writes to
    this field). It's also the wrong model for a per-run snapshot: `Course`
    is one mutable row reused across every run for that course, so writing
    a snapshot here on each run would silently overwrite the previous
    run's snapshot the next time generation runs - exactly what "old
    generation runs should still show which snapshot they used" rules out.
    The real, immutable, per-run snapshot lives on
    `GenerationJob.run_snapshot_json` instead - see
    app/generation/run_snapshot.py. This field is left in place (nothing
    references it, so removing it isn't necessary) but should be
    considered dead/reserved, not a source of truth for anything.
    """

    __tablename__ = "courses"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    audience: str
    outcome: str
    special_notes: Optional[str] = None
    course_type: str = Field(default="practical_skill")
    # Optional domain label (e.g. "meta_ads", "excel") — course-specific.
    course_domain: Optional[str] = Field(default=None)
    course_specialty: Optional[str] = Field(default=None)
    primary_course_family: CourseFamily = Field(
        default=CourseFamily.GENERAL_SKILL,
        sa_column=Column(
            sa_str_enum(CourseFamily),
            nullable=False,
            server_default=CourseFamily.GENERAL_SKILL.value,
        ),
    )
    secondary_course_families: list[str] = Field(
        default_factory=list,
        sa_column=Column(
            "secondary_course_families_json",
            sa_json_array(),
            nullable=False,
            server_default="[]",
        ),
    )
    structure_mode: StructureMode = Field(
        sa_column=Column(sa_str_enum(StructureMode), nullable=False)
    )
    # User-provided or Generate-Course-Map result — course-specific plan only.
    manual_map_text: Optional[str] = Field(default=None)
    explanation_level: ExplanationLevel = Field(
        default=ExplanationLevel.FINAL_ONLY,
        sa_column=Column(
            sa_str_enum(ExplanationLevel),
            nullable=False,
            server_default=ExplanationLevel.FINAL_ONLY.value,
        ),
    )
    generation_preset: GenerationPreset = Field(
        default=GenerationPreset.BALANCED,
        sa_column=Column(
            sa_str_enum(GenerationPreset),
            nullable=False,
            server_default=GenerationPreset.BALANCED.value,
        ),
    )
    # Preview = cheaper direction test; Premium = full locked pipeline (default).
    generation_quality_mode: GenerationQualityMode = Field(
        default=GenerationQualityMode.PREMIUM,
        sa_column=Column(
            sa_str_enum(GenerationQualityMode),
            nullable=False,
            server_default=GenerationQualityMode.PREMIUM.value,
        ),
    )
    # Autonomous gap fill by default — research missing facts without asking.
    web_research_mode: WebResearchMode = Field(
        default=WebResearchMode.AUTONOMOUS_GAP_FILL,
        sa_column=Column(
            sa_str_enum(WebResearchMode),
            nullable=False,
            server_default=WebResearchMode.AUTONOMOUS_GAP_FILL.value,
        ),
    )
    # Default Egypt: local market realism for practical courses.
    target_market: TargetMarket = Field(
        default=TargetMarket.EGYPT,
        sa_column=Column(
            sa_str_enum(TargetMarket),
            nullable=False,
            server_default=TargetMarket.EGYPT.value,
        ),
    )
    student_language: str = Field(
        default="ar", sa_column_kwargs={"nullable": False, "server_default": "ar"}
    )
    spoken_variety: str = Field(
        default="egyptian_colloquial",
        sa_column_kwargs={
            "nullable": False,
            "server_default": "egyptian_colloquial",
        },
    )
    address_form: AddressForm = Field(
        default=AddressForm.MASCULINE,
        sa_column=Column(
            sa_str_enum(AddressForm),
            nullable=False,
            server_default=AddressForm.MASCULINE.value,
        ),
    )
    learner_starting_state: str = Field(
        default="", sa_column_kwargs={"nullable": False, "server_default": ""}
    )
    required_final_performance: str = Field(
        default="", sa_column_kwargs={"nullable": False, "server_default": ""}
    )
    required_independence_level: str = Field(
        default="independent_with_checklist",
        sa_column_kwargs={
            "nullable": False,
            "server_default": "independent_with_checklist",
        },
    )
    instructor_responsibility_boundaries: list[str] = Field(
        default_factory=list,
        sa_column=Column(
            "instructor_responsibility_boundaries_json",
            sa_json_array(),
            nullable=False,
            server_default="[]",
        ),
    )
    verified_instructor_experience: list[str] = Field(
        default_factory=list,
        sa_column=Column(
            "verified_instructor_experience_json",
            sa_json_array(),
            nullable=False,
            server_default="[]",
        ),
    )
    forbidden_first_person_claims: list[str] = Field(
        default_factory=list,
        sa_column=Column(
            "forbidden_first_person_claims_json",
            sa_json_array(),
            nullable=False,
            server_default="[]",
        ),
    )
    realistic_student_budget: Optional[str] = Field(default=None)
    available_tools: list[str] = Field(
        default_factory=list,
        sa_column=Column(
            "available_tools_json", sa_json_array(), nullable=False, server_default="[]"
        ),
    )
    professional_constraints: list[str] = Field(
        default_factory=list,
        sa_column=Column(
            "professional_constraints_json",
            sa_json_array(),
            nullable=False,
            server_default="[]",
        ),
    )
    high_stakes_constraints: list[str] = Field(
        default_factory=list,
        sa_column=Column(
            "high_stakes_constraints_json",
            sa_json_array(),
            nullable=False,
            server_default="[]",
        ),
    )
    # Persistent Web Source Memory cache across generation jobs (internal).
    web_source_memory_json: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(sa_json_object(), nullable=True)
    )
    # Official Tool Documentation Gate memory (internal) — tools + docs notes.
    official_tool_memory_json: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(sa_json_object(), nullable=True)
    )
    status: str = Field(default="draft")
    active_rules_snapshot_json: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(sa_json_object(), nullable=True)
    )
    # Approved map-preview GenerationContextSnapshot (additive; nullable).
    generation_context_snapshot_json: Optional[dict[str, Any]] = Field(
        default=None, sa_column=Column(sa_json_object(), nullable=True)
    )
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
