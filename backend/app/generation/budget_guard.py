"""Budget Guard (§6): observational spend warnings only.

Never blocks or aborts a generation run - `compute_budget_warning` only
ever returns a warning *string* to attach to the job
(`GenerationJob.budget_warning`), never raises, never stops the pipeline.
Re-read from the request: "do not silently stop generation without
preserving work" - budget enforcement that could abort a run mid-flight is
explicitly out of scope for this pass, only warning is in scope.

If both `ai_monthly_budget_usd` and `ai_course_budget_usd` are unset
(`None`, the default), this always returns `None` and never even queries
the database - budgets are strictly opt-in.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.config import Settings
from app.config import settings as default_settings
from app.models.ai_usage_event import AIUsageEvent


def _month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _sum_estimated_cost(
    session: Session, *, course_id: int | None = None, since: datetime | None = None
) -> float:
    statement = select(AIUsageEvent)
    if course_id is not None:
        statement = statement.where(AIUsageEvent.course_id == course_id)
    if since is not None:
        statement = statement.where(AIUsageEvent.created_at >= since)
    return sum((row.estimated_cost_usd or 0.0) for row in session.exec(statement))


def compute_budget_warning(
    session: Session, course_id: int, config: Settings = default_settings
) -> str | None:
    """`None` if no budget is configured, or if spend is below
    `ai_warn_at_percent` of every configured budget. Otherwise a short,
    human-readable warning naming which budget(s) it crossed."""
    if config.ai_monthly_budget_usd is None and config.ai_course_budget_usd is None:
        return None

    warnings: list[str] = []
    now = datetime.now(timezone.utc)

    if config.ai_monthly_budget_usd is not None and config.ai_monthly_budget_usd > 0:
        month_spend = _sum_estimated_cost(session, since=_month_start(now))
        percent = (month_spend / config.ai_monthly_budget_usd) * 100
        if percent >= config.ai_warn_at_percent:
            warnings.append(
                f"Estimated AI spend this month is ${month_spend:.2f} "
                f"({percent:.0f}% of the ${config.ai_monthly_budget_usd:.2f} monthly budget)."
            )

    if config.ai_course_budget_usd is not None and config.ai_course_budget_usd > 0:
        course_spend = _sum_estimated_cost(session, course_id=course_id)
        percent = (course_spend / config.ai_course_budget_usd) * 100
        if percent >= config.ai_warn_at_percent:
            warnings.append(
                f"This course's estimated AI spend is ${course_spend:.2f} "
                f"({percent:.0f}% of its ${config.ai_course_budget_usd:.2f} budget)."
            )

    return " ".join(warnings) if warnings else None
