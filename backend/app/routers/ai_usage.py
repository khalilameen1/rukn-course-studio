"""Read-only AI Usage Center endpoints (§5).

Every dollar figure this router returns is an ESTIMATE of app usage,
computed from token counts and `app/generation/pricing.py`'s hardcoded,
approximate pricing table - never a real Anthropic account balance (the
Anthropic API doesn't expose that, and this app never fakes one). See
README.md "AI Usage Center" for the full explanation shown to users.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db import get_session
from app.schemas.ai_usage import AIUsageSummary
from app.services.ai_usage_summary import build_usage_summary

router = APIRouter(prefix="/ai-usage", tags=["ai-usage"])


@router.get("/summary", response_model=AIUsageSummary)
def usage_summary(session: Session = Depends(get_session)) -> AIUsageSummary:
    """Current provider/model, today's/this-month's estimated spend, and
    the last provider error (category + already-sanitized message - see
    app/generation/errors.py) - never raw exception text, never a
    credential."""
    return build_usage_summary(session)
