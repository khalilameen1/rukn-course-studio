"""Frontend/API contract guards derived from ``frontend/src/lib/api.ts``.

No network or provider calls: this only inspects FastAPI's generated OpenAPI
document and the tracked frontend client source.
"""

from pathlib import Path

from app.main import app


FRONTEND_ENDPOINTS: tuple[tuple[str, str], ...] = (
    ("post", "/auth/login"),
    ("get", "/health"),
    ("get", "/build-info"),
    ("get", "/auth/diagnostics"),
    ("get", "/auth/diagnostics/full"),
    ("post", "/auth/logout"),
    ("get", "/admin/knowledge"),
    ("get", "/admin/knowledge/catalog"),
    ("get", "/admin/knowledge/manifest"),
    ("post", "/admin/knowledge/reset"),
    ("get", "/admin/audit"),
    ("get", "/courses"),
    ("post", "/courses"),
    ("get", "/courses/{course_id}"),
    ("put", "/courses/{course_id}"),
    ("get", "/courses/{course_id}/readiness"),
    ("get", "/courses/{course_id}/sources"),
    ("post", "/courses/{course_id}/sources/upload"),
    ("post", "/courses/{course_id}/sources/notes"),
    ("delete", "/courses/{course_id}/sources/{source_id}"),
    ("patch", "/courses/{course_id}/sources/{source_id}"),
    ("get", "/courses/{course_id}/sources/{source_id}/analysis"),
    ("post", "/courses/{course_id}/sources/{source_id}/reprocess"),
    ("post", "/courses/{course_id}/generate"),
    ("get", "/jobs/{job_id}"),
    ("get", "/courses/{course_id}/generate/latest"),
    ("post", "/courses/{course_id}/generate/{job_id}/cancel"),
    ("post", "/courses/{course_id}/generate/{job_id}/finalize-saved"),
    ("get", "/courses/{course_id}/versions"),
    ("get", "/courses/{course_id}/download/latest"),
    ("get", "/jobs/{job_id}/download-partial"),
    ("post", "/courses/{course_id}/map-preview"),
    ("post", "/courses/{course_id}/writer-test-3-reels"),
    ("get", "/courses/{course_id}/writer-test-3-reels/{job_id}"),
    ("get", "/ai-usage/summary"),
    ("get", "/courses/{course_id}/ai-usage"),
)


def test_every_frontend_api_operation_exists_in_openapi():
    paths = app.openapi()["paths"]
    missing = [
        f"{method.upper()} {path}"
        for method, path in FRONTEND_ENDPOINTS
        if path not in paths or method not in paths[path]
    ]
    assert missing == []


def test_retired_generate_map_is_absent_from_backend_and_frontend():
    paths = app.openapi()["paths"]
    frontend_api = (
        Path(__file__).parents[2] / "frontend" / "src" / "lib" / "api.ts"
    ).read_text(encoding="utf-8")

    assert "/courses/{course_id}/generate-map" not in paths
    assert "generate-map" not in frontend_api
    assert "map-preview" in frontend_api


def test_openapi_has_no_duplicate_operation_ids():
    operation_ids = [
        operation["operationId"]
        for methods in app.openapi()["paths"].values()
        for method, operation in methods.items()
        if method in {"get", "post", "put", "patch", "delete"}
    ]
    assert len(operation_ids) == len(set(operation_ids))
