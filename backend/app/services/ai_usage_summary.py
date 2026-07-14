"""Build AI Usage Center summary responses — safe with empty/missing data."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.config import settings
from app.generation.presets import DEFAULT_GENERATION_PRESET
from app.models.ai_usage_event import AIUsageEvent
from app.models.generation_job import GenerationJob
from app.schemas.ai_usage import AIUsageSummary

logger = logging.getLogger(__name__)


def _as_utc(dt: datetime) -> datetime:
    """Normalize DB datetimes so aware/naive mixes never crash summaries."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _day_start(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _to_float(value: float | Decimal | int | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _provider_model() -> tuple[str, str]:
    provider = (settings.ai_provider or "fake").strip().lower()
    model = settings.ai_model_name if provider == "anthropic" else "fake"
    return provider, model


def empty_usage_summary() -> AIUsageSummary:
    """Zeroed summary when there is no usage telemetry yet."""
    provider, model = _provider_model()
    return AIUsageSummary(
        provider=provider,
        model=model,
        default_preset=DEFAULT_GENERATION_PRESET.value,
        last_request_status=None,
        last_request_at=None,
        estimated_cost_today_usd=0.0,
        estimated_cost_this_month_usd=0.0,
        last_error_category=None,
        last_error_message=None,
    )


def list_usage_events(session: Session) -> list[AIUsageEvent]:
    try:
        return list(session.exec(select(AIUsageEvent)))
    except SQLAlchemyError:
        logger.exception("Failed to query ai_usage_events")
        return []


def latest_error_job(session: Session) -> GenerationJob | None:
    try:
        return session.exec(
            select(GenerationJob)
            .where(GenerationJob.error_category.is_not(None))
            .order_by(GenerationJob.updated_at.desc())
        ).first()
    except SQLAlchemyError:
        logger.exception("Failed to query generation_jobs for AI usage summary")
        return None


def build_usage_summary(session: Session) -> AIUsageSummary:
    """Aggregate usage events into the frontend AIUsageSummary contract."""
    now = datetime.now(timezone.utc)
    events = list_usage_events(session)
    if not events:
        summary = empty_usage_summary()
        latest_error_job_row = latest_error_job(session)
        if latest_error_job_row:
            summary.last_error_category = latest_error_job_row.error_category
            summary.last_error_message = latest_error_job_row.error_message
        return summary

    day_start = _day_start(now)
    month_start = _month_start(now)
    today_total = round(
        sum(
            _to_float(e.estimated_cost_usd)
            for e in events
            if e.created_at is not None and _as_utc(e.created_at) >= day_start
        ),
        6,
    )
    month_total = round(
        sum(
            _to_float(e.estimated_cost_usd)
            for e in events
            if e.created_at is not None and _as_utc(e.created_at) >= month_start
        ),
        6,
    )
    latest_event = max(
        events,
        key=lambda e: (
            _as_utc(e.created_at)
            if e.created_at
            else datetime.min.replace(tzinfo=timezone.utc)
        ),
    )
    latest_error_job_row = latest_error_job(session)
    provider, model = _provider_model()

    return AIUsageSummary(
        provider=provider,
        model=model,
        default_preset=DEFAULT_GENERATION_PRESET.value,
        last_request_status=latest_event.status if latest_event else None,
        last_request_at=latest_event.created_at if latest_event else None,
        estimated_cost_today_usd=today_total,
        estimated_cost_this_month_usd=month_total,
        last_error_category=(
            latest_error_job_row.error_category if latest_error_job_row else None
        ),
        last_error_message=(
            latest_error_job_row.error_message if latest_error_job_row else None
        ),
    )
