"""Response schemas for the AI Usage Center (§5) - `app/routers/ai_usage.py`
and the `/courses/{course_id}/ai-usage` route in `app/routers/generation.py`.

Every dollar figure below is an ESTIMATE of app usage, computed from token
counts and `app/generation/pricing.py`'s hardcoded pricing table - never a
real Anthropic account balance (the Anthropic API doesn't expose that).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AIUsageSummary(BaseModel):
    """See app/routers/ai_usage.py `GET /ai-usage/summary`."""

    provider: str
    model: str
    # The default preset (app/generation/presets.py DEFAULT_GENERATION_PRESET)
    # - actual runs may use a different per-course preset; there is no
    # single global "current preset" since it's a per-course setting.
    default_preset: str
    last_request_status: Optional[str]
    last_request_at: Optional[datetime]
    # Explicitly labeled per the request: "estimated app usage", never a
    # real provider account balance.
    estimated_cost_today_usd: float
    estimated_cost_this_month_usd: float
    last_error_category: Optional[str]
    last_error_message: Optional[str]


class CourseAIUsage(BaseModel):
    """See app/routers/generation.py `GET /courses/{course_id}/ai-usage`."""

    course_id: int
    estimated_cost_usd: float
    event_count: int
