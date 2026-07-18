"""Multi-agent review labels — Creator does not self-criticize.

Internal order per lesson (and map):
1. Creator Agent — full first draft
2. Student Agent — completed-draft learner confusion
3. Specialist Critic Agent — accuracy / weakness / filler / realism / domain
4. Master Mentor Agent — hook / loop / pacing / creator instinct / academic gaps
5. Creator Agent — Final Master Version (absorb feedback; never paste reviews)

Only Final Master is `script_text` / Teleprompter DOCX. Critic output is
compact, internal-only, and must never appear in the export.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SpecialistCriticReport(BaseModel):
    """Compact internal critic attack (never user-facing / never DOCX)."""

    fatal_issues: list[str] = Field(default_factory=list)
    accuracy_risks: list[str] = Field(default_factory=list)
    realism_risks: list[str] = Field(default_factory=list)
    weak_value: list[str] = Field(default_factory=list)
    filler_to_remove: list[str] = Field(default_factory=list)
    style_risks: list[str] = Field(default_factory=list)
    missing_depth: list[str] = Field(default_factory=list)
    overperformance: list[str] = Field(default_factory=list)
    what_to_keep: list[str] = Field(default_factory=list)
    rebuild_direction: str = ""


# Short labels for orchestrator heartbeats / UI progress messages.
# V1 user-facing vocabulary (keep aligned with product lock).
PROGRESS_PLANNING_MAP = "Building course map"
PROGRESS_MAP_FIRST_DRAFT = "Building course map"
PROGRESS_MAP_STUDENT = "Building course map"
PROGRESS_MAP_CRITIC = "Building course map"
PROGRESS_MAP_MENTOR = "Building course map"
PROGRESS_MAP_MASTER = "Rebuilding final course map"
PROGRESS_START_LESSONS = "Writing lessons"
PROGRESS_CREATOR_DRAFT = "Writing first draft"
PROGRESS_STUDENT_CLARITY = "Checking student clarity"
PROGRESS_SPECIALIST_CRITIC = "Running specialist critic"
PROGRESS_MASTER_MENTOR = "Consulting master mentor"
PROGRESS_REBUILD_MASTER = "Rewriting final master version"
PROGRESS_SAVING_LESSON = "Saving lesson"
PROGRESS_EXPORTING = "Exporting Teleprompter DOCX"
PROGRESS_PAUSED = "Generation paused after saving completed work"

# Forbidden DOCX / API-leak substrings specific to the critic loop.
CRITIC_LEAK_SUBSTRINGS: tuple[str, ...] = (
    "specialist_critic_report",
    "fatal_issues",
    "rebuild_direction",
    "filler_to_remove",
    "accuracy_risks",
    "creator draft a",
    "draft b critic",
    "adversarial critic notes",
    "student_review",
    "missing_prerequisites",
    "unclear_terms",
    "likely_student_questions",
    "mentor_review",
    "strongest_hidden_angle",
    "hook_advice",
    "rebuild_instruction",
)
