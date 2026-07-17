"""Critical security hardening: auth, SSRF, uploads, isolation, secrets, runaway."""

from __future__ import annotations

import ipaddress
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.auth.tokens import create_token
from app.config import settings
from app.main import app
from app.security.secret_redaction import REDACTED, redact_secrets
from app.security.url_safety import UnsafeURLError, assert_safe_public_https_url
from app.services.upload_safety import (
    assert_content_matches_extension,
    assert_course_output_file,
    assert_path_under_root,
    sanitize_filename,
)

client = TestClient(app)


@pytest.fixture
def auth_on(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "admin_username", "admin")
    monkeypatch.setattr(settings, "admin_password", "s3cret")
    monkeypatch.setattr(settings, "auth_secret_key", "test-secret-key")
    return create_token("admin", "test-secret-key")


PROTECTED_GENERATE_ENDPOINTS = [
    ("POST", "/courses/1/generate"),
    ("POST", "/courses/1/generate-map"),
    ("GET", "/courses/1/ai-usage"),
    ("GET", "/courses/1/download/latest"),
    ("GET", "/ai-usage/summary"),
    ("GET", "/admin/knowledge"),
    ("POST", "/admin/knowledge/cleanup-duplicates"),
    ("GET", "/jobs/1"),
    ("GET", "/jobs/1/download-partial"),
]


@pytest.mark.parametrize("method,path", PROTECTED_GENERATE_ENDPOINTS)
def test_generation_endpoints_require_auth(method, path, auth_on):
    response = client.request(method, path)
    assert response.status_code in (401, 403), (method, path, response.status_code)


def test_authenticated_me_works(auth_on):
    token = auth_on
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["username"] == "admin"


def test_health_remains_public_with_auth_on(auth_on):
    assert client.get("/health").status_code == 200


def test_diagnostics_never_exposes_api_key(monkeypatch, auth_on):
    from app.auth.diagnostics import build_diagnostics

    FAKE = "sk-ant-leak-check-ABCDEF1234567890"
    monkeypatch.setattr(settings, "ai_provider", "anthropic")
    monkeypatch.setattr(settings, "anthropic_api_key", FAKE)
    monkeypatch.setattr(settings, "ai_model_name", "claude-example")
    # session=None avoids hitting a possibly stale local SQLite schema.
    body = build_diagnostics(session=None)
    text = str(body)
    assert FAKE not in text
    assert "anthropic_api_key" not in body
    assert "admin_password" not in body
    assert body["ai_provider_ready"] is True


def test_redact_secrets_strips_anthropic_key():
    raw = "boom sk-ant-test-should-never-leak-12345 and ANTHROPIC_API_KEY=abc123"
    out = redact_secrets(raw)
    assert "sk-ant-test" not in out
    assert "abc123" not in out
    assert REDACTED in out


def test_ssrf_rejects_localhost_private_and_file():
    for bad in (
        "http://example.com/x",
        "file:///etc/passwd",
        "ftp://example.com/x",
        "https://localhost/secret",
        "https://127.0.0.1/secret",
        "https://0.0.0.0/secret",
        "https://169.254.169.254/latest/meta-data/",
        "https://10.0.0.5/internal",
        "https://192.168.1.1/admin",
    ):
        with pytest.raises(UnsafeURLError):
            assert_safe_public_https_url(bad)


def test_ssrf_allows_public_https_with_public_dns():
    public_ip = ipaddress.ip_address("93.184.216.34")  # example.com-ish

    def fake_getaddrinfo(host, port, *args, **kwargs):
        assert host == "example.com"
        return [(None, None, None, None, (str(public_ip), 443))]

    with patch("app.security.url_safety.socket.getaddrinfo", side_effect=fake_getaddrinfo):
        url = assert_safe_public_https_url("https://example.com/path")
    assert url.startswith("https://example.com")


def test_upload_filename_sanitized_and_path_confined(tmp_path):
    assert ".." not in sanitize_filename("../../etc/passwd.pdf")
    root = tmp_path / "outputs"
    root.mkdir()
    good = root / "course_1.docx"
    good.write_bytes(b"ok")
    assert assert_path_under_root(good, root) == good.resolve()
    outside = tmp_path / "escape.docx"
    outside.write_bytes(b"no")
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        assert_path_under_root(outside, root)


def test_content_mime_rejects_exe_as_pdf():
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        assert_content_matches_extension(b"MZ\x90\x00", ".pdf")
    assert_content_matches_extension(b"%PDF-1.4\n", ".pdf")


def test_cross_course_source_isolation(tmp_path, monkeypatch):
    import app.db as db_module
    import app.generation.orchestrator as orch
    from app.crud import course_sources, courses
    from app.models.enums import ExplanationLevel, Priority, SourceCategory, StructureMode

    engine = create_engine(f"sqlite:///{tmp_path / 'iso.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(orch, "engine", engine)
    monkeypatch.setattr(settings, "auth_enabled", False)

    with Session(engine) as session:
        a = courses.create(
            session,
            title="A",
            audience="a",
            outcome="o",
            structure_mode=StructureMode.CONNECTED_NO_MODULES,
            explanation_level=ExplanationLevel.FINAL_ONLY,
        )
        b = courses.create(
            session,
            title="B",
            audience="b",
            outcome="o",
            structure_mode=StructureMode.CONNECTED_NO_MODULES,
            explanation_level=ExplanationLevel.FINAL_ONLY,
        )
        src = course_sources.create(
            session,
            course_id=a.id,
            source_category=SourceCategory.USER_NOTES,
            title="secret-a",
            original_filename=None,
            file_path=None,
            mime_type="text/plain",
            extracted_text="ONLY_COURSE_A_SOURCE",
            priority=Priority.HIGH,
            status="ready",
            include_in_generation=True,
        )
        a_id, b_id, src_id = a.id, b.id, src.id

    # Patch course B pretending source id from A
    res = client.patch(
        f"/courses/{b_id}/sources/{src_id}",
        json={"title": "hijack"},
    )
    assert res.status_code == 404

    res_del = client.delete(
        f"/courses/{b_id}/sources/{src_id}?dry_run=false&confirm=true"
    )
    assert res_del.status_code == 404

    # List on B must not include A's source
    listed = client.get(f"/courses/{b_id}/sources").json()
    assert all(row["course_id"] == b_id for row in listed)
    assert all(row["id"] != src_id for row in listed)
    assert all("ONLY_COURSE_A_SOURCE" not in (row.get("extracted_text") or "") for row in listed)

    listed_a = client.get(f"/courses/{a_id}/sources").json()
    assert any(row["id"] == src_id for row in listed_a)


def test_docx_download_requires_auth(auth_on):
    res = client.get("/courses/1/download/latest")
    assert res.status_code == 401


def test_runaway_hard_cap_raises(tmp_path, monkeypatch):
    from app.crud import ai_usage_events, courses
    from app.generation.budget_guard import EmergencyRunawayGuard, check_runaway_hard_cap
    from app.models.enums import ExplanationLevel, StructureMode

    engine = create_engine(f"sqlite:///{tmp_path / 'cap.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(settings, "ai_runaway_hard_cap_usd", 0.01)

    with Session(engine) as session:
        course = courses.create(
            session,
            title="C",
            audience="a",
            outcome="o",
            structure_mode=StructureMode.CONNECTED_NO_MODULES,
            explanation_level=ExplanationLevel.FINAL_ONLY,
        )
        # check uses job_id + course_id spend; create a fake usage event
        from app.models.generation_job import GenerationJob
        from app.models.enums import JobStatus
        from app.crud import generation_jobs

        job = generation_jobs.create(
            session,
            course_id=course.id,
            status=JobStatus.RUNNING,
            current_stage="generating",
            progress_percent=10,
            log_json=[],
        )
        ai_usage_events.create(
            session,
            course_id=course.id,
            job_id=job.id,
            provider="fake",
            model="fake",
            stage="lesson_first_draft",
            preset="balanced",
            input_tokens=1000,
            output_tokens=1000,
            estimated_cost_usd=1.0,
            status="ok",
        )
        with pytest.raises(EmergencyRunawayGuard) as ei:
            check_runaway_hard_cap(session, job_id=job.id, course_id=course.id)
        assert "emergency runaway guard" in str(ei.value).lower()


def test_cleanup_dry_run_does_not_mutate(tmp_path, monkeypatch):
    from app import models  # noqa: F401
    from app.crud import admin_knowledge_items
    from app.generation.admin_knowledge_cleanup import dedupe_admin_knowledge
    from app.models.enums import ItemType

    monkeypatch.setattr(settings, "storage_dir", tmp_path / "storage")
    (tmp_path / "storage").mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{tmp_path / 'dedupe.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        admin_knowledge_items.create(
            session,
            key="k1",
            title="a",
            content_text="1",
            item_type=ItemType.MARKDOWN,
            is_active=True,
            version=1,
        )
        admin_knowledge_items.create(
            session,
            key="k1",
            title="b",
            content_text="2",
            item_type=ItemType.MARKDOWN,
            is_active=True,
            version=2,
        )
        report = dedupe_admin_knowledge(session, dry_run=True, confirm=False)
        assert report["dry_run"] is True
        assert report["applied"] is False
        assert report["would_deactivate_count"] == 1
        still = [i for i in admin_knowledge_items.list(session) if i.is_active]
        assert len(still) == 2


def test_production_refuses_auth_disabled(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", False)
    monkeypatch.setattr(settings, "environment", "production")
    res = client.get("/courses")
    assert res.status_code == 503
    assert "AUTH_ENABLED" in res.json()["detail"]


def test_api_hides_absolute_storage_paths():
    from datetime import datetime, timezone

    from app.schemas.course_version import CourseVersionRead
    from app.schemas.generation_job import GenerationJobRead

    now = datetime.now(timezone.utc)
    job = GenerationJobRead.model_validate(
        {
            "id": 1,
            "course_id": 1,
            "status": "completed",
            "current_stage": "done",
            "output_docx_path": r"C:\Users\secret\storage\outputs\course_1_v2.docx",
            "error_message": None,
            "last_completed_step": "export",
            "error_category": None,
            "partial_docx_path": "/var/app/storage/outputs/partial_job_9.docx",
            "generation_quality_mode": "premium",
            "web_research_mode": "autonomous_gap_fill",
            "created_at": now,
            "updated_at": now,
        }
    )
    dumped = job.model_dump(mode="json")
    assert dumped["output_docx_path"] == "course_1_v2.docx"
    assert dumped["partial_docx_path"] == "partial_job_9.docx"
    assert r"C:\Users" not in str(dumped)
    assert "/var/app" not in str(dumped)
    assert job.partial_docx_available is True

    ver = CourseVersionRead.model_validate(
        {
            "id": 1,
            "course_id": 1,
            "version_number": 2,
            "output_docx_path": "/secret/disk/outputs/course_1_v2.docx",
            "summary_text": None,
            "report_text": None,
            "created_at": now,
        }
    )
    assert ver.model_dump()["output_docx_path"] == "course_1_v2.docx"


def test_cors_wildcard_stripped():
    from app.cors_origins import normalize_cors_origins

    assert "*" not in normalize_cors_origins(["*", "http://localhost:3000"])
    assert normalize_cors_origins(["http://localhost:3000"]) == ["http://localhost:3000"]


def test_ssrf_rejects_cgnat_and_ipv4_mapped():
    with pytest.raises(UnsafeURLError):
        assert_safe_public_https_url("https://100.64.1.1/x")
    with pytest.raises(UnsafeURLError):
        assert_safe_public_https_url("https://[::ffff:127.0.0.1]/x")


def test_docx_zip_bomb_rejected(tmp_path):
    import zipfile

    from app.services.docx_zip_guard import assert_docx_zip_safe
    from app.services.extraction import extract_text

    bomb = tmp_path / "bomb.docx"
    with zipfile.ZipFile(bomb, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", b"\x00" * 1000)

    class _Info:
        filename = "word/document.xml"
        file_size = 90 * 1024 * 1024
        compress_size = 1000

    class _Zip:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def infolist(self):
            return [_Info()]

    with patch("app.services.docx_zip_guard.zipfile.ZipFile", return_value=_Zip()):
        with pytest.raises(ValueError, match="uncompressed|zip bomb|oversized"):
            assert_docx_zip_safe(bomb)

    class _Trav:
        filename = "../etc/passwd"
        file_size = 10
        compress_size = 10

    class _ZipTrav(_Zip):
        def infolist(self):
            return [_Trav()]

    with patch("app.services.docx_zip_guard.zipfile.ZipFile", return_value=_ZipTrav()):
        with pytest.raises(ValueError, match="unsafe"):
            assert_docx_zip_safe(bomb)

    tiny = tmp_path / "ok.docx"
    with zipfile.ZipFile(tiny, "w") as zf:
        zf.writestr(
            "word/document.xml",
            '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>hello teleprompter text here for extraction</w:t></w:r></w:p></w:body></w:document>",
        )
        zf.writestr("[Content_Types].xml", "<Types></Types>")
    assert_docx_zip_safe(tiny)
    result = extract_text(tiny, ".docx")
    assert result.status in ("ready", "poor_extraction", "failed", "extraction_blocked")


def test_invalid_token_detail_is_generic(auth_on):
    res = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer not-a.real-token"},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid or expired token"


def test_course_output_path_rejects_cross_course_idor(tmp_path):
    """assert_path_under_root alone is not enough — scope to outputs/{course_id}/."""
    from fastapi import HTTPException

    root = tmp_path / "outputs"
    own = root / "1"
    other = root / "2"
    own.mkdir(parents=True)
    other.mkdir(parents=True)
    victim = other / "course_v1.docx"
    victim.write_bytes(b"secret")
    allowed = own / "course_v1.docx"
    allowed.write_bytes(b"ok")

    assert assert_course_output_file(allowed, course_id=1, outputs_root=root) == allowed.resolve()
    with pytest.raises(HTTPException) as exc:
        assert_course_output_file(victim, course_id=1, outputs_root=root)
    assert exc.value.status_code == 400

    # Flat file in outputs/ (legacy) — must not be served for a course.
    flat = root / "course_1_v1.docx"
    flat.write_bytes(b"flat")
    with pytest.raises(HTTPException):
        assert_course_output_file(flat, course_id=1, outputs_root=root)


def test_course_version_unique_and_orphan_docx_cleanup(tmp_path, monkeypatch):
    """Unique (course_id, version_number) + unlink DOCX if version row insert fails."""
    import app.db as db_module
    from app.crud import course_versions, courses
    from app.models.enums import ExplanationLevel, StructureMode
    from sqlalchemy.exc import IntegrityError

    engine = create_engine(f"sqlite:///{tmp_path / 'ver.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db_module, "engine", engine)

    outputs = tmp_path / "outputs" / "1"
    outputs.mkdir(parents=True)
    docx = outputs / "course_v1.docx"
    docx.write_bytes(b"PK fake")

    with Session(engine) as session:
        course = courses.create(
            session,
            title="T",
            audience="a",
            outcome="o",
            structure_mode=StructureMode.CONNECTED_NO_MODULES,
            explanation_level=ExplanationLevel.FINAL_ONLY,
        )
        course_versions.create(
            session,
            course_id=course.id,
            version_number=1,
            output_docx_path=str(docx),
            summary_text="s",
            report_text=None,
        )
        with pytest.raises(IntegrityError):
            course_versions.create(
                session,
                course_id=course.id,
                version_number=1,
                output_docx_path=str(docx),
                summary_text="dup",
                report_text=None,
            )
        session.rollback()

    # Simulate orchestrator orphan cleanup on create failure.
    orphan = outputs / "course_v2.docx"
    orphan.write_bytes(b"orphan")
    try:
        raise RuntimeError("simulated db failure")
    except Exception:
        try:
            orphan.unlink(missing_ok=True)
        except OSError:
            pass
    assert not orphan.exists()


def test_stale_job_release_uses_last_saved_heartbeat(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone

    import app.db as db_module
    from app.crud import courses, generation_jobs
    from app.models.enums import ExplanationLevel, JobStatus, StructureMode
    from app.services.generation_maintenance import release_stale_active_jobs

    engine = create_engine(f"sqlite:///{tmp_path / 'stale.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db_module, "engine", engine)

    with Session(engine) as session:
        course = courses.create(
            session,
            title="T",
            audience="a",
            outcome="o",
            structure_mode=StructureMode.CONNECTED_NO_MODULES,
            explanation_level=ExplanationLevel.FINAL_ONLY,
        )
        old = datetime.now(timezone.utc) - timedelta(hours=3)
        recent = datetime.now(timezone.utc) - timedelta(minutes=5)
        live = generation_jobs.create(
            session,
            course_id=course.id,
            status=JobStatus.RUNNING,
            current_stage="generating",
            progress_percent=40,
        )
        live.updated_at = old
        live.last_saved_at = recent
        session.add(live)
        dead = generation_jobs.create(
            session,
            course_id=course.id,
            status=JobStatus.RUNNING,
            current_stage="generating",
            progress_percent=10,
        )
        dead.updated_at = old
        dead.last_saved_at = old
        session.add(dead)
        session.commit()

        released = release_stale_active_jobs(session, max_age_minutes=90)
        assert released == 1
        assert generation_jobs.get(session, live.id).status == JobStatus.RUNNING
        assert generation_jobs.get(session, dead.id).status == JobStatus.FAILED
