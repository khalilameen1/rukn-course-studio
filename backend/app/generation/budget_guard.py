"""Budget Guard (§6): observational warnings + optional emergency hard cap.



Hard cap (`AI_RUNAWAY_HARD_CAP_USD`) is opt-in and default-disabled. When

enabled and crossed, `EmergencyRunawayGuard` stops the run cleanly so the

orchestrator can save completed lessons and export a partial DOCX.

"""



from __future__ import annotations



from datetime import datetime, timezone



from sqlmodel import Session, select



from app.config import Settings

from app.config import settings as default_settings

from app.models.ai_usage_event import AIUsageEvent





class EmergencyRunawayGuard(Exception):

    """Raised only when the optional hard USD cap is configured and reached."""



    def __init__(self, message: str = "Stopped by emergency runaway guard"):

        super().__init__(message)

        self.user_message = message





def _month_start(now: datetime) -> datetime:

    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)





def _sum_estimated_cost(

    session: Session, *, course_id: int | None = None, job_id: int | None = None, since: datetime | None = None

) -> float:

    statement = select(AIUsageEvent)

    if course_id is not None:

        statement = statement.where(AIUsageEvent.course_id == course_id)

    if job_id is not None:

        statement = statement.where(AIUsageEvent.job_id == job_id)

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





def check_runaway_hard_cap(

    session: Session,

    *,

    job_id: int,

    course_id: int,

    config: Settings = default_settings,

) -> None:

    """Raise EmergencyRunawayGuard if optional hard cap is set and reached.



    Cap is disabled when `ai_runaway_hard_cap_usd` is None or <= 0.

    Uses this job's estimated AIUsageEvent spend (and course total as a

    secondary signal) — bug/runaway protection only, not a product budget UX.

    """

    cap = config.ai_runaway_hard_cap_usd

    if cap is None or cap <= 0:

        return



    job_spend = _sum_estimated_cost(session, job_id=job_id)

    course_spend = _sum_estimated_cost(session, course_id=course_id)

    spend = max(job_spend, course_spend)

    if spend >= cap:

        raise EmergencyRunawayGuard(

            "Stopped by emergency runaway guard "

            f"(estimated spend ${spend:.2f} >= hard cap ${cap:.2f})."

        )

