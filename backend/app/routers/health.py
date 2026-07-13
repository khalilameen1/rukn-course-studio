from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """Basic liveness check used by the frontend and local dev setup."""
    return {"status": "ok", "environment": settings.environment}
