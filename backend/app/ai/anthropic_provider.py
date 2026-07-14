"""Real AIProvider backed by the Anthropic API (Claude).

Uses tool-calling (forced tool_choice) to get structured JSON output, then
validates that output against our own Pydantic schemas - never trusting
the model's JSON as-is. If validation fails, retries exactly once with a
note about what went wrong; if it still fails, raises `AnthropicProviderError`
(the orchestrator already treats any exception as a FAILED job).

Configuration: reads `ANTHROPIC_API_KEY` and `AI_MODEL_NAME` from
app.config.settings (see backend/.env.example). `settings.ai_model_name` is
the ONLY place a model name should ever be set - this file never hardcodes
one. Requests use `settings.anthropic_request_timeout_seconds` (default
120s) so a hung request fails clearly instead of hanging forever, and a
`temperature` resolved from `app/generation/presets.py` for the course's
`generation_preset` - see `configure_for_run` below.

Prompt templates live in backend/app/prompts/*.md; which file each stage uses
is defined in app/prompts/prompt_registry.py (never hardcoded here). Each
call appends the stage's actual input (already scoped to only what that stage
needs - see app/ai/provider.py's Input models) as a JSON block, so the model
always sees the active Rukn admin knowledge (`rules_context`), the relevant
brief/plan data, and only relevant source excerpts - never the whole course.
"""

import json
from typing import TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from app.ai.provider import (
    AIProvider,
    BuildCourseMapInput,
    FinalReviewInput,
    RebuildFinalCourseInput,
    ReviewFiveReelsInput,
    ReviewModuleInput,
    ReviewSingleReelInput,
    ReviewTwoModulesInput,
    WriteSingleReelInput,
)
from app.config import settings
from app.generation.model_routing import resolve_stage_overrides
from app.generation.presets import (
    DEFAULT_GENERATION_PRESET,
    GenerationPreset,
    resolve_generation_settings,
)
from app.prompts.prompt_registry import PipelineStage, get_prompt_spec, load_prompt
from app.schemas.generation import CourseMap, FinalCourse, GeneratedReel, ReviewResult

# "Retry once if JSON validation fails" -> 1 initial attempt + 1 retry.
MAX_ATTEMPTS = 2

ModelT = TypeVar("ModelT", bound=BaseModel)


class AnthropicProviderError(RuntimeError):
    """Raised when the model's output still fails schema validation after a retry."""


def _tool_for_schema(schema: type[BaseModel], name: str) -> dict:
    return {
        "name": name,
        "description": f"Return data matching the {schema.__name__} schema.",
        "input_schema": schema.model_json_schema(),
    }


class AnthropicProvider(AIProvider):
    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        max_tokens: int = 4096,
        preset: GenerationPreset | None = None,
        request_timeout_seconds: float | None = None,
    ) -> None:
        self._client = anthropic.Anthropic(
            api_key=api_key or settings.anthropic_api_key,
            timeout=(
                request_timeout_seconds
                if request_timeout_seconds is not None
                else settings.anthropic_request_timeout_seconds
            ),
        )
        # Single source of truth for the model name: settings.ai_model_name
        # (AI_MODEL_NAME env var), unless explicitly overridden by a caller
        # (e.g. tests). Never hardcode a model string anywhere else.
        self._model_name = model_name or settings.ai_model_name
        self._max_tokens = max_tokens
        # Starts at the given (or default) preset's temperature; the
        # orchestrator calls `configure_for_run` once per generation run
        # with the course's actual preset (see that method below) - this
        # constructor default only matters for callers that never do that
        # (e.g. tests constructing a provider directly).
        self._temperature = resolve_generation_settings(preset or DEFAULT_GENERATION_PRESET)[
            "temperature"
        ]
        # Set after every successful `_call_structured` call (see below) -
        # the AI Usage Center (§5) reads this via `hasattr`/`getattr` from
        # app/generation/orchestrator.py, the same decoupling pattern as
        # `configure_for_run`: this class stays entirely DB-independent,
        # the orchestrator (which has the session) does the persisting.
        # `None` until the first call completes.
        self.last_usage: dict | None = None

    def configure_for_run(self, generation_preset: GenerationPreset) -> None:
        """Re-resolve and apply `generation_preset`'s temperature for every
        call this provider instance makes from now on.

        Called once per run by app/generation/orchestrator.py right after
        the course brief is loaded, so every stage's call below uses the
        course's actual preset without each stage's own Input model needing
        to carry it individually. Deliberately not part of the `AIProvider`
        ABC (see app/ai/provider.py) - it's `hasattr`-guarded at the call
        site so `FakeProvider` needs zero changes.
        """
        self._temperature = resolve_generation_settings(generation_preset)["temperature"]

    def build_course_map(self, input: BuildCourseMapInput) -> CourseMap:
        return self._run(PipelineStage.BUILD_COURSE_MAP, input, CourseMap)

    def write_single_reel(self, input: WriteSingleReelInput) -> GeneratedReel:
        return self._run(PipelineStage.WRITE_SINGLE_REEL, input, GeneratedReel)

    def review_single_reel(self, input: ReviewSingleReelInput) -> ReviewResult:
        return self._run(PipelineStage.REVIEW_SINGLE_REEL, input, ReviewResult)

    def review_five_reels(self, input: ReviewFiveReelsInput) -> ReviewResult:
        return self._run(PipelineStage.REVIEW_FIVE_REELS, input, ReviewResult)

    def review_module(self, input: ReviewModuleInput) -> ReviewResult:
        return self._run(PipelineStage.REVIEW_MODULE, input, ReviewResult)

    def review_two_modules(self, input: ReviewTwoModulesInput) -> ReviewResult:
        return self._run(PipelineStage.REVIEW_TWO_MODULES, input, ReviewResult)

    def final_review(self, input: FinalReviewInput) -> ReviewResult:
        return self._run(PipelineStage.FINAL_REVIEW, input, ReviewResult)

    def rebuild_final_course(self, input: RebuildFinalCourseInput) -> FinalCourse:
        return self._run(PipelineStage.REBUILD_FINAL_COURSE, input, FinalCourse)

    # -- internals ---------------------------------------------------------

    def _run(
        self,
        stage: PipelineStage,
        input_model: BaseModel,
        schema: type[ModelT],
    ) -> ModelT:
        spec = get_prompt_spec(stage)
        prompt = self._build_prompt(stage, input_model)
        overrides = resolve_stage_overrides(stage)
        return self._call_structured(prompt, schema, spec.tool_name, overrides=overrides)

    def _build_prompt(self, stage: PipelineStage, input_model: BaseModel) -> str:
        template = load_prompt(stage)
        # `mode="json"` serializes enums to their plain string values, so
        # the model sees clean JSON, not Python repr internals.
        context_json = json.dumps(
            input_model.model_dump(mode="json"), indent=2, ensure_ascii=False
        )
        return f"{template}\n\n## Context (JSON)\n```json\n{context_json}\n```"

    def _call_structured(
        self,
        prompt: str,
        schema: type[ModelT],
        tool_name: str,
        overrides: dict | None = None,
    ) -> ModelT:
        """`overrides` (§9 Model Routing) is an optional
        `{"model", "temperature", "max_tokens"}` subset - any key left out
        falls back to this instance's own configured value. Always `{}`
        (no-op) unless a caller (only `_run` above, today) passes a
        non-empty dict resolved from
        `app/generation/model_routing.py MODEL_ROUTING_OVERRIDES`."""
        overrides = overrides or {}
        model_name = overrides.get("model", self._model_name)
        temperature = overrides.get("temperature", self._temperature)
        max_tokens = overrides.get("max_tokens", self._max_tokens)

        tool = _tool_for_schema(schema, tool_name)
        last_error: str = "unknown error"

        for attempt in range(1, MAX_ATTEMPTS + 1):
            message = prompt
            if attempt > 1:
                message = (
                    f"{prompt}\n\n## Retry\nYour previous response did not match the "
                    f"required schema: {last_error}\nReturn ONLY a valid tool call this time."
                )

            response = self._client.messages.create(
                model=model_name,
                max_tokens=max_tokens,
                temperature=temperature,
                tools=[tool],
                tool_choice={"type": "tool", "name": tool_name},
                messages=[{"role": "user", "content": message}],
            )

            tool_use = next(
                (block for block in response.content if block.type == "tool_use"), None
            )
            if tool_use is None:
                last_error = "model did not return a tool call"
                continue

            try:
                result = schema.model_validate(tool_use.input)
            except ValidationError as exc:
                last_error = str(exc)
                continue

            # Captured only on the attempt that actually succeeded - see
            # AI Usage Center (§5). `response.usage` attributes are only
            # present on a real Anthropic SDK response; `getattr(...,
            # None)` keeps this safe against any future/older SDK response
            # shape that happens to omit one of the cache-token fields.
            usage = getattr(response, "usage", None)
            self.last_usage = {
                "model": model_name,
                "input_tokens": getattr(usage, "input_tokens", None),
                "output_tokens": getattr(usage, "output_tokens", None),
                "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", None),
                "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", None),
            }
            return result

        raise AnthropicProviderError(
            f"{schema.__name__} output failed validation after {MAX_ATTEMPTS} attempt(s): "
            f"{last_error}"
        )
