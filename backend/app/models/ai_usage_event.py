"""One row per AI-provider call (AI Usage Center, §5).

Every cost figure here is an ESTIMATE computed from token counts and the
hardcoded, approximate pricing table in `app/generation/pricing.py` -
never a real Anthropic account balance (the Anthropic API doesn't expose
that). Rows with `provider == "fake"` are entirely synthetic (no real
spend ever happened) - see `app/ai/fake_provider.py` - and always carry
`estimated_cost_usd == 0.0`.

Never stores an API key, `AUTH_SECRET_KEY`, `DATABASE_URL`, or any other
secret - only token counts and short, sanitized labels (`stage`,
`provider`, `model`, `preset`, `error_category` - the same category
vocabulary as `app/generation/errors.py`, already scrubbed of raw
exception text).
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AIUsageEvent(SQLModel, table=True):
    __tablename__ = "ai_usage_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    # Nullable: a future call site outside a generation run (there is none
    # today) shouldn't be forced to fabricate a job just to log usage.
    job_id: Optional[int] = Field(default=None, foreign_key="generation_jobs.id", index=True)
    # Denormalized from the job's course_id at write time, purely so
    # per-course totals (GET /courses/{course_id}/ai-usage) don't need a
    # join through generation_jobs - never a source of truth on its own.
    course_id: Optional[int] = Field(default=None, foreign_key="courses.id", index=True)
    # The app/prompts/prompt_registry.py PipelineStage value this call was
    # for (e.g. "write_single_reel") - a plain string column since this
    # table has no reason to import that enum type directly.
    stage: str
    provider: str
    model: str
    preset: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cache_read_tokens: Optional[int] = None
    cache_write_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    status: str = Field(default="ok")
    error_category: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow, index=True)
