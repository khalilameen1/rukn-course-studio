"""CORS / FRONTEND_ORIGIN normalization — prevents Network/CORS misconfig."""

from app.config import Settings
from app.cors_origins import normalize_cors_origins, normalize_origin


def test_normalize_origin_strips_trailing_slash_and_health():
    assert normalize_origin("https://app.onrender.com/") == "https://app.onrender.com"
    assert normalize_origin("https://app.onrender.com/health") == "https://app.onrender.com"
    assert normalize_origin("https://app.onrender.com/auth/login") == "https://app.onrender.com"
    assert normalize_origin("  https://app.onrender.com  ") == "https://app.onrender.com"


def test_settings_merges_frontend_origin_without_trailing_slash():
    settings = Settings(
        frontend_origin="https://rukn-frontend.onrender.com/",
        cors_origins=["http://localhost:3000/"],
    )
    assert settings.frontend_origin == "https://rukn-frontend.onrender.com"
    assert "https://rukn-frontend.onrender.com" in settings.cors_origins
    assert "http://localhost:3000/" not in settings.cors_origins
    assert "http://localhost:3000" in settings.cors_origins


def test_normalize_cors_origins_dedupes():
    assert normalize_cors_origins(
        ["http://localhost:3000/", "http://localhost:3000", ""]
    ) == ["http://localhost:3000"]
