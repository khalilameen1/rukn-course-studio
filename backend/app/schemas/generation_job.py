from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_serializer,
    field_validator,
    model_validator,
)

from app.generation.public_progress import sanitize_progress_message
from app.models.enums import GenerationQualityMode, JobStatus, WebResearchMode
from app.schemas.validators import (
    GenerationQualityModeLoose,
    JobStatusLoose,
    WebResearchModeLoose,
)
from app.services.enum_coerce import coerce_str_enum


def _public_storage_name(value: object) -> str | None:
    """Return basename only — never absolute server paths in API responses."""
    if value is None or value == "":
        return None
    name = Path(str(value)).name
    return name or None


def _sanitize_public_error(message: object, category: object) -> str | None:
    """Coarse user-facing error — never raw exception / stack text."""
    if message is None or message == "":
        if category:
            return f"Generation stopped ({category})."
        return None
    text = str(message).strip()
    if len(text) > 240:
        text = text[:237] + "..."
    # Drop paths / secrets-looking fragments.
    if "Traceback" in text or "File \"" in text:
        return f"Generation stopped ({category or 'error'})."
    return text


class GenerateCourseRequest(BaseModel):
    """Optional body for POST /courses/{id}/generate.

    Never accepts raw temperature, agent knobs, or research confirmation UX.
    """

    generation_quality_mode: GenerationQualityModeLoose = GenerationQualityMode.PREMIUM
    web_research_mode: WebResearchModeLoose = WebResearchMode.AUTONOMOUS_GAP_FILL
    # When true, client confirmed the map preview and hard-limit warnings.
    map_preview_confirmed: bool = False
    human_override_hard_limits: bool = False
    address_form: str = "masculine"
    presenter_language: str = "ar"
    presenter_dialect: str = "egyptian"
    delivery_pattern: str = "teleprompter_standard"
    approved_snapshot_fingerprint: str | None = None


class WriterTestTopicIn(BaseModel):
    title: str
    purpose: str = ""


class WriterTest3ReelsRequest(BaseModel):
    """Exactly three topics for the production writer-test path."""

    topics: list[WriterTestTopicIn]
    series_linked: bool = False
    series_context: str = ""
    idempotency_key: str | None = None
    generation_quality_mode: GenerationQualityModeLoose = GenerationQualityMode.PREMIUM
    retry_reel_id: str | None = None
    existing_job_id: int | None = None


class MapPreviewRequest(BaseModel):
    generation_quality_mode: GenerationQualityModeLoose = GenerationQualityMode.PREMIUM
    human_override_hard_limits: bool = False
    web_research_mode: WebResearchModeLoose = WebResearchMode.DISABLED
    address_form: str = "masculine"
    presenter_language: str = "ar"
    presenter_dialect: str = "egyptian"
    delivery_pattern: str = "teleprompter_standard"

class GenerationJobRead(BaseModel):
    """User-facing job status (Copilot-scale public DTO).

    Excludes internal pipeline state, waste codes, lesson indices, and
    research telemetry. Critic/student/mentor content is never exposed.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    status: JobStatusLoose
    cancel_requested: bool = False
    current_stage: Optional[str]
    progress_percent: int = 0
    output_docx_path: Optional[str]
    error_category: Optional[str] = None
    # Sanitized in validator; raw DB value never returned as-is if stack-like.
    error_message: Optional[str] = None
    completed_modules_count: int = 0
    completed_reels_count: int = 0
    total_lessons_count: int = 0
    partial_docx_path: Optional[str]
    last_progress_message: Optional[str] = None
    last_saved_at: Optional[datetime] = None
    estimated_usage_summary: Optional[str] = None
    estimated_duration_summary: Optional[str] = None
    sources_run_summary: Optional[str] = None
    provenance_summary: Optional[str] = None
    architecture_summary: Optional[str] = None
    grounding_confidence: Optional[str] = None
    research_synthesis_summary: Optional[str] = None
    improve_next_tip: Optional[str] = None
    generation_quality_mode: GenerationQualityModeLoose = GenerationQualityMode.PREMIUM
    web_research_mode: WebResearchModeLoose = WebResearchMode.AUTONOMOUS_GAP_FILL
    budget_warning: Optional[str] = None
    # Safe research cost hygiene (no ledger / no URLs).
    web_searches_count: int = 0
    research_memory_reuse_count: int = 0
    created_at: datetime
    updated_at: datetime
    config_fingerprint: Optional[str] = None
    snapshot_version: Optional[str] = None

    # Loaded for sanitizers / aliases only — never serialized.
    needs_review_count: int = Field(default=0, exclude=True)
    current_module_index: Optional[int] = Field(default=None, exclude=True)
    current_lesson_index: Optional[int] = Field(default=None, exclude=True)
    last_completed_step: Optional[str] = Field(default=None, exclude=True)
    waste_warnings_json: list[str] = Field(default_factory=list, exclude=True)
    reused_source_memory_count: int = Field(default=0, exclude=True)

    @model_validator(mode="before")
    @classmethod
    def _derive_safe_snapshot_metadata(cls, value: object) -> object:
        if isinstance(value, dict):
            data = dict(value)
            snapshot = data.get("run_snapshot_json")
        else:
            data = {
                name: getattr(value, name, None)
                for name in cls.model_fields
                if name not in {"config_fingerprint", "snapshot_version"}
            }
            snapshot = getattr(value, "run_snapshot_json", None)
        if isinstance(snapshot, dict):
            data["config_fingerprint"] = snapshot.get("CONFIG_FINGERPRINT")
            data["snapshot_version"] = snapshot.get("version")
        return data

    @field_serializer("output_docx_path", "partial_docx_path")
    @classmethod
    def _serialize_storage_paths(cls, value: object) -> str | None:
        return _public_storage_name(value)

    @field_validator("waste_warnings_json", mode="before")
    @classmethod
    def _coerce_waste(cls, value: object) -> object:
        from app.services.json_coerce import coerce_json_list

        return coerce_json_list(value) or []

    @field_validator("last_progress_message", mode="before")
    @classmethod
    def _sanitize_progress(cls, value: object, info) -> object:
        stage = None
        if info.data and isinstance(info.data, dict):
            stage = info.data.get("current_stage")
        if value is None:
            return value
        return sanitize_progress_message(
            str(value), stage=stage if isinstance(stage, str) else None
        )

    @field_validator("error_message", mode="before")
    @classmethod
    def _sanitize_error(cls, value: object, info) -> object:
        category = None
        if info.data and isinstance(info.data, dict):
            category = info.data.get("error_category")
        return _sanitize_public_error(value, category)

    @field_validator("cancel_requested", mode="before")
    @classmethod
    def _coerce_cancel_requested(cls, value: object) -> object:
        return False if value is None else value

    @field_validator(
        "progress_percent",
        "completed_modules_count",
        "completed_reels_count",
        "total_lessons_count",
        "web_searches_count",
        "research_memory_reuse_count",
        mode="before",
    )
    @classmethod
    def _coerce_null_ints(cls, value: object) -> object:
        return 0 if value is None else value

    @field_validator("status", "generation_quality_mode", "web_research_mode", mode="before")
    @classmethod
    def _coerce_enum_name_or_value(cls, value: object) -> object:
        """Accept legacy NAME strings (`RUNNING`) as well as values (`running`)."""
        if value is None or isinstance(
            value, (JobStatus, GenerationQualityMode, WebResearchMode)
        ):
            return value
        for enum_cls in (JobStatus, GenerationQualityMode, WebResearchMode):
            coerced = coerce_str_enum(enum_cls, value)
            if isinstance(coerced, enum_cls):
                return coerced
        return value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def research_tips(self) -> list[str]:
        """Human tips from waste codes — never raw agent telemetry."""
        mapping = {
            "identical_retry_blocked": "Repeated identical repair was blocked (cost hygiene).",
            "research_cache_hit": "Research memory cache reused for matching needs.",
            "thick_library_skipped_gaps": "Thick uploads — limited web gap fill.",
        }
        tips: list[str] = []
        for code in self.waste_warnings_json or []:
            tip = mapping.get(str(code))
            if tip and tip not in tips:
                tips.append(tip)
            elif code and str(code) not in tips and len(tips) < 6:
                tips.append(str(code).replace("_", " "))
        if self.web_searches_count:
            tips.insert(0, f"Web searches this run: {self.web_searches_count}")
        if self.research_memory_reuse_count:
            tips.insert(
                0 if not self.web_searches_count else 1,
                f"Research cache hits: {self.research_memory_reuse_count}",
            )
        return tips[:8]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def agent_roster(self) -> list[dict[str, str]]:
        from app.generation.agent_roster import build_agent_roster

        status_val = self.status.value if hasattr(self.status, "value") else str(self.status)
        return build_agent_roster(
            current_stage=self.current_stage,
            status=status_val,
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def live_eta_summary(self) -> str | None:
        """Coarse remaining-time hint from progress % (Spark-speed honesty)."""
        from app.generation.public_progress import estimate_live_eta

        status_val = (
            self.status.value if hasattr(self.status, "value") else str(self.status or "")
        ).lower()
        if status_val in {"completed", "failed", "partial", "canceled", "paused"}:
            return None
        stage = (self.current_stage or "").lower()
        if stage in {"done", "failed", "partial", "canceled"}:
            return None
        return estimate_live_eta(
            progress_percent=self.progress_percent,
            quality_mode=str(
                self.generation_quality_mode.value
                if hasattr(self.generation_quality_mode, "value")
                else self.generation_quality_mode
            ),
            total_lessons=self.total_lessons_count,
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def run_status(self) -> JobStatus:
        """Alias for `status` — persisted operational run state."""
        return self.status

    @computed_field  # type: ignore[prop-decorator]
    @property
    def completed_lessons_count(self) -> int:
        """Alias for `completed_reels_count` (lessons == reels)."""
        return self.completed_reels_count

    @computed_field  # type: ignore[prop-decorator]
    @property
    def stopped_after_label(self) -> str | None:
        from app.services.finalize_saved_job import format_stopped_after_label

        return format_stopped_after_label(self.last_completed_step)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def can_finalize_from_saved(self) -> bool:
        """UI hint: Finish/Retry may assemble Teleprompter without AI tokens.

        Counter-based (map/reels JSON are internal). The finalize endpoint
        re-checks full integrity before writing.
        """
        if self.output_docx_path:
            return False
        status_val = (
            self.status.value if hasattr(self.status, "value") else str(self.status or "")
        ).lower()
        if status_val == "completed":
            return False
        total = int(self.total_lessons_count or 0)
        done = int(self.completed_reels_count or 0)
        return total > 0 and done >= total

    @computed_field  # type: ignore[prop-decorator]
    @property
    def can_download_completed(self) -> bool:
        """Partial draft or final Teleprompter is available for download."""
        return bool(self.partial_docx_path or self.output_docx_path)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def partial_docx_available(self) -> bool:
        return bool(self.partial_docx_path)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def public_stage_label(self) -> str | None:
        from app.generation.public_progress import public_stage_label

        return public_stage_label(self.current_stage)


class WriterTestReelPublic(BaseModel):
    reel_id: str
    title: str
    script_text: str = ""
    word_count: int = 0
    estimated_seconds: float = 0.0
    quality_status: str = "pass"
    quality_summary: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    is_final_master: bool = False


class WriterTestJobRead(BaseModel):
    job: GenerationJobRead
    job_kind: str = "writer_test_3_reels"
    config_fingerprint: str | None = None
    series_linked: bool = False
    reels: list[WriterTestReelPublic] = Field(default_factory=list)
