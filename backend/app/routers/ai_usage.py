"""Read-only AI Usage Center endpoints (§5).

Every dollar figure this router returns is an ESTIMATE of app usage,
computed from token counts and `app/generation/pricing.py`'s hardcoded,
approximate pricing table - never a real Anthropic account balance (the
Anthropic API doesn't expose that, and this app never fakes one). See
README.md "AI Usage Center" for the full explanation shown to users.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.config import settings
from app.db import get_session
from app.generation.presets import DEFAULT_GENERATION_PRESET
from app.models.ai_usage_event import AIUsageEvent
from app.models.generation_job import GenerationJob
from app.schemas.ai_usage import AIUsageSummary

router = APIRouter(prefix="/ai-usage", tags=["ai-usage"])


def _day_start(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


@router.get("/summary", response_model=AIUsageSummary)
def usage_summary(session: Session = Depends(get_session)) -> AIUsageSummary:
    """Current provider/model, today's/this-month's estimated spend, and
    the last provider error (category + already-sanitized message - see
    app/generation/errors.py) - never raw exception text, never a
    credential."""
    now = datetime.now(timezone.utc)
    events = list(session.exec(select(AIUsageEvent)))

    today_total = round(
        sum((e.estimated_cost_usd or 0.0) for e in events if e.created_at >= _day_start(now)), 6
    )
    month_total = round(
        sum((e.estimated_cost_usd or 0.0) for e in events if e.created_at >= _month_start(now)), 6
    )
    latest_event = max(events, key=lambda e: e.created_at, default=None)

    latest_error_job = session.exec(
        select(GenerationJob)
        .where(GenerationJob.error_category.is_not(None))
        .order_by(GenerationJob.updated_at.desc())
    ).first()

    provider = (settings.ai_provider or "fake").strip().lower()
    model = settings.ai_model_name if provider == "anthropic" else "fake"

    return AIUsageSummary(
        provider=provider,
        model=model,
        default_preset=DEFAULT_GENERATION_PRESET.value,
        last_request_status=latest_event.status if latest_event else None,
        last_request_at=latest_event.created_at if latest_event else None,
        estimated_cost_today_usd=today_total,
        estimated_cost_this_month_usd=month_total,
        last_error_category=latest_error_job.error_category if latest_error_job else None,
        last_error_message=latest_error_job.error_message if latest_error_job else None,
    )
