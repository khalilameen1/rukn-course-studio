"""Shared test setup.

Auth is disabled by default for every test in this suite, since almost all
existing tests exercise unrelated behavior (orchestrator, providers,
validators, ...) and were written before auth existed. Tests that actually
need to exercise auth (see test_auth.py) explicitly re-enable it.
"""

import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def _disable_auth_by_default(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", False)
