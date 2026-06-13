"""
Shared fixtures for production-readiness HTTP tests.

These tests hit a RUNNING backend — they do NOT mock the DB.
Start the backend before running: uvicorn app.main:app --reload --port 8000

Required env vars (set before running):
    BACKEND_URL   - defaults to http://localhost:8000
    USER_TOKEN    - your JWT from browser localStorage key 'tradementor_auth_token'
                    Get it: DevTools → Application → Local Storage → tradementor_auth_token
    ADMIN_TOKEN   - admin JWT from browser localStorage key 'tm_admin_token'
                    Get it: log into /admin, then DevTools → Application → Local Storage → tm_admin_token

Quick start:
    # Windows PowerShell
    $env:USER_TOKEN  = "<paste token>"
    $env:ADMIN_TOKEN = "<paste token>"
    python -m pytest backend/tests/production/ -v

    # bash
    export USER_TOKEN="<paste token>"
    export ADMIN_TOKEN="<paste token>"
    python -m pytest backend/tests/production/ -v
"""

import os
import pytest
import httpx

BASE_URL    = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
USER_TOKEN  = os.getenv("USER_TOKEN", "").strip()
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "").strip()


# ── Session-scoped clients ─────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL


@pytest.fixture(scope="session")
def anon(base_url) -> httpx.Client:
    """Unauthenticated client. Does NOT follow redirects by default."""
    with httpx.Client(base_url=base_url, timeout=15, follow_redirects=False) as c:
        yield c


@pytest.fixture(scope="session")
def user(base_url) -> httpx.Client:
    """Authenticated user client. Tests skip if USER_TOKEN not set."""
    if not USER_TOKEN:
        pytest.skip(
            "USER_TOKEN not set.\n"
            "  1. Open app in browser, log in via Zerodha\n"
            "  2. DevTools → Application → Local Storage → localhost:8080\n"
            "  3. Copy value of 'tradementor_auth_token'\n"
            "  4. set USER_TOKEN=<that value>  (PowerShell: $env:USER_TOKEN='...')"
        )
    with httpx.Client(
        base_url=base_url,
        headers={"Authorization": f"Bearer {USER_TOKEN}"},
        timeout=15,
        follow_redirects=False,
    ) as c:
        yield c


@pytest.fixture(scope="session")
def admin(base_url) -> httpx.Client:
    """Admin-authenticated client. Tests skip if ADMIN_TOKEN not set."""
    if not ADMIN_TOKEN:
        pytest.skip(
            "ADMIN_TOKEN not set.\n"
            "  1. Go to /admin in browser, log in\n"
            "  2. DevTools → Application → Local Storage → localhost:8080\n"
            "  3. Copy value of 'tm_admin_token'\n"
            "  4. set ADMIN_TOKEN=<that value>  (PowerShell: $env:ADMIN_TOKEN='...')"
        )
    with httpx.Client(
        base_url=base_url,
        headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
        timeout=15,
        follow_redirects=False,
    ) as c:
        yield c


# ── Helpers ────────────────────────────────────────────────────────────────────

def assert_200(r: httpx.Response, label: str = "") -> dict:
    assert r.status_code == 200, (
        f"{label}: expected 200, got {r.status_code}. Body: {r.text[:300]}"
    )
    return r.json()


def assert_401(r: httpx.Response, label: str = "") -> None:
    assert r.status_code == 401, (
        f"{label}: expected 401 (auth required), got {r.status_code}. "
        f"Body: {r.text[:200]}"
    )
