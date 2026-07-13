"""Minimal production smoke test for a running Rukn Course Studio backend.

Not a pytest suite - a standalone script meant to be pointed at a live
deployment (e.g. right after a Render deploy) to confirm the core
login -> protected-route flow actually works end to end, without touching
generation (which is covered separately by the fake-provider test scenario
mentioned below).

Usage:
    python backend/scripts/smoke_test.py --base-url https://your-backend.onrender.com \\
        --username admin --password '...'

Or via environment variables (recommended so real credentials never appear
in shell history):
    SMOKE_BASE_URL=https://your-backend.onrender.com \\
    SMOKE_ADMIN_USERNAME=admin \\
    SMOKE_ADMIN_PASSWORD='...' \\
    python backend/scripts/smoke_test.py

Checks, in order:
    1. GET  /health           -> 200, no token
    2. POST /auth/login       -> 200 with a token, using the given credentials
    3. GET  /courses          -> 401 without a token
    4. GET  /courses          -> 200 with the token from step 2

Exits non-zero on the first failed check. Does not create/modify any data.

For an end-to-end check that also exercises the generation pipeline (fake
provider, no network/API key needed), see:
    backend/tests/test_scenario_meta_ads_no_sources.py
run via: .venv/Scripts/python.exe -m pytest tests/test_scenario_meta_ads_no_sources.py -q
"""

from __future__ import annotations

import argparse
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "http://localhost:8000"
TIMEOUT_SECONDS = 15


def _request(method: str, url: str, *, token: str | None = None, json_body: dict | None = None):
    import json as json_module

    headers = {}
    data = None
    if json_body is not None:
        data = json_module.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, body
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")
    except URLError as exc:
        print(f"FAIL  could not reach {url}: {exc}", file=sys.stderr)
        sys.exit(1)


def _check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"PASS  {label}")
        return
    print(f"FAIL  {label}{f' - {detail}' if detail else ''}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("SMOKE_BASE_URL", DEFAULT_BASE_URL),
        help="Backend base URL, no trailing slash (default: %(default)s)",
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("SMOKE_ADMIN_USERNAME"),
        help="Admin username (default: $SMOKE_ADMIN_USERNAME)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("SMOKE_ADMIN_PASSWORD"),
        help="Admin password (default: $SMOKE_ADMIN_PASSWORD)",
    )
    args = parser.parse_args()

    if not args.username or not args.password:
        print(
            "Missing credentials: pass --username/--password or set "
            "SMOKE_ADMIN_USERNAME/SMOKE_ADMIN_PASSWORD.",
            file=sys.stderr,
        )
        sys.exit(2)

    base_url = args.base_url.rstrip("/")
    print(f"Smoke testing {base_url} ...")

    status, _ = _request("GET", f"{base_url}/health")
    _check("GET /health (no token) -> 200", status == 200, f"got {status}")

    status, body = _request(
        "POST",
        f"{base_url}/auth/login",
        json_body={"username": args.username, "password": args.password},
    )
    _check("POST /auth/login -> 200 with token", status == 200, f"got {status}: {body}")
    import json as json_module

    token = json_module.loads(body)["access_token"]
    _check("login response includes access_token", bool(token))

    status, _ = _request("GET", f"{base_url}/courses")
    _check("GET /courses (no token) -> 401", status == 401, f"got {status}")

    status, _ = _request("GET", f"{base_url}/courses", token=token)
    _check("GET /courses (with token) -> 200", status == 200, f"got {status}")

    print("All smoke checks passed.")


if __name__ == "__main__":
    main()
