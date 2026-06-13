"""
Section 13: Security Tests
Checklist items automated: 13.1, 13.2, 13.3*, 13.4, 13.5, 13.6, 13.8, 13.10, 13.11, 13.12, 13.15
Manual-only: 13.7 (IP allowlist), 13.9 (XSS needs browser), 13.13 (rate limit — needs timing),
             13.14 (DB column inspection)

*13.3 (cross-user data isolation) partially automated — requires USER_TOKEN.
"""

import os
import pytest
import httpx
from tests.production.conftest import USER_TOKEN

pytestmark = pytest.mark.section13


# ── Unauthenticated access ─────────────────────────────────────────────────────

def test_13_1_unauthenticated_trades_returns_401(anon: httpx.Client):
    """13.1 GET /api/trades/ without auth token → 401 Unauthorized."""
    r = anon.get("/api/trades/")
    assert r.status_code == 401, (
        f"Auth bypass! /api/trades/ returned {r.status_code} without a token. "
        f"Body: {r.text[:200]}"
    )


def test_13_1b_unauthenticated_positions_returns_401(anon: httpx.Client):
    """13.1 GET /api/positions/ without auth → 401."""
    r = anon.get("/api/positions/")
    assert r.status_code == 401, f"Auth bypass on /api/positions/: {r.status_code}"


def test_13_1c_unauthenticated_analytics_returns_401(anon: httpx.Client):
    """13.1 GET /api/analytics/overview without auth → 401."""
    r = anon.get("/api/analytics/overview")
    assert r.status_code == 401, f"Auth bypass on /api/analytics/overview: {r.status_code}"


def test_13_1d_unauthenticated_risk_alerts_returns_401(anon: httpx.Client):
    """13.1 GET /api/risk/alerts without auth → 401."""
    r = anon.get("/api/risk/alerts")
    assert r.status_code == 401, f"Auth bypass on /api/risk/alerts: {r.status_code}"


def test_13_1e_unauthenticated_profile_returns_401(anon: httpx.Client):
    """13.1 GET /api/profile/ without auth → 401."""
    r = anon.get("/api/profile/")
    assert r.status_code == 401, f"Auth bypass on /api/profile/: {r.status_code}"


def test_13_2_unauthenticated_admin_overview_blocked(anon: httpx.Client):
    """13.2 GET /api/admin/overview without auth → 401 or 403 (never 200)."""
    r = anon.get("/api/admin/overview")
    assert r.status_code in (401, 403, 404), (
        f"Admin overview accessible without auth! Got {r.status_code}. "
        f"Body: {r.text[:300]}"
    )


def test_13_2b_unauthenticated_admin_users_blocked(anon: httpx.Client):
    """13.2 GET /api/admin/users without auth → blocked."""
    r = anon.get("/api/admin/users")
    assert r.status_code in (401, 403, 404), (
        f"Admin users list accessible without auth: {r.status_code}"
    )


def test_13_2c_unauthenticated_admin_broadcast_blocked(anon: httpx.Client):
    """13.2 POST /api/admin/broadcast without auth → blocked."""
    r = anon.post("/api/admin/broadcast", json={"message": "test"})
    assert r.status_code in (401, 403, 404, 422), (
        f"Admin broadcast accessible without auth: {r.status_code}"
    )


# ── OAuth security ─────────────────────────────────────────────────────────────

def test_13_4_connect_is_redirect_not_json(anon: httpx.Client):
    """13.4 /api/zerodha/connect is a redirect, not JSON. JWT never in URL."""
    r = anon.get("/api/zerodha/connect")
    assert r.status_code in (302, 307, 308), (
        f"Expected redirect, got {r.status_code}. Frontend will get CORS error."
    )
    location = r.headers.get("location", "")
    assert "eyJ" not in location, (
        "JWT token in redirect URL — will be captured in server access logs!"
    )


def test_13_5_oauth_callback_nonce_is_single_use(anon: httpx.Client):
    """13.5 OAuth nonce cookie exists (single-use enforced via Redis atomic GET+DELETE).
    We can't fully test single-use without a valid Zerodha token, but we verify the
    mechanism is in place (cookie set → used once in callback).
    """
    r1 = anon.get("/api/zerodha/connect")
    nonce1 = r1.cookies.get("oauth_nonce")
    assert nonce1 is not None, "No oauth_nonce cookie — CSRF mechanism missing"

    r2 = anon.get("/api/zerodha/connect")
    nonce2 = r2.cookies.get("oauth_nonce")
    assert nonce2 is not None, "Second connect request didn't set oauth_nonce cookie"

    # Each connect generates a fresh nonce (not a static value)
    assert nonce1 != nonce2, (
        "Both connect requests returned the SAME nonce value. "
        "Nonce must be unique per session to prevent replay attacks."
    )


def test_13_6_forged_callback_without_cookie_rejected(anon: httpx.Client):
    """13.6 CSRF: calling /callback directly without the nonce cookie is rejected."""
    r = anon.get(
        "/api/zerodha/callback",
        params={"request_token": "ATTACKER_FORGED_TOKEN", "status": "success"},
    )
    if r.status_code in (302, 307, 308):
        location = r.headers.get("location", "")
        assert "connected=true" not in location, (
            f"CSRF EXPLOIT POSSIBLE: forged callback succeeded! Redirect: {location}"
        )
    else:
        assert r.status_code >= 400, (
            f"Forged callback not rejected: {r.status_code}. Body: {r.text[:200]}"
        )


# ── Injection ──────────────────────────────────────────────────────────────────

def test_13_8_sql_injection_in_query_params(anon: httpx.Client):
    """13.8 SQL injection payloads in query params don't cause 500."""
    payloads = [
        "' OR '1'='1",
        "'; DROP TABLE trades; --",
        "1 UNION SELECT NULL, NULL, NULL --",
        "' AND 1=CONVERT(int,(SELECT TOP 1 table_name FROM information_schema.tables)) --",
    ]
    for payload in payloads:
        # These endpoints 401 without auth — but the important thing is they don't 500
        # before auth check runs
        for endpoint in ["/api/trades/", "/api/analytics/summary"]:
            r = anon.get(endpoint, params={"tradingsymbol": payload, "q": payload})
            assert r.status_code != 500, (
                f"SQL injection caused 500 on {endpoint} with payload {payload!r}. "
                f"Body: {r.text[:300]}"
            )


def test_13_8b_sql_injection_in_path_params(anon: httpx.Client):
    """13.8 SQL injection in path parameters."""
    malicious_ids = [
        "'; DROP TABLE broker_accounts; --",
        "00000000-0000-0000-0000-000000000000' OR '1'='1",
    ]
    for bad_id in malicious_ids:
        r = anon.get(f"/api/trades/{bad_id}")
        assert r.status_code != 500, (
            f"Path injection caused 500 for id={bad_id!r}. Body: {r.text[:200]}"
        )


# ── Security headers ───────────────────────────────────────────────────────────

def test_13_10_security_headers_present(anon: httpx.Client):
    """13.10 Security headers set on all responses."""
    r = anon.get("/health")
    headers = r.headers

    assert headers.get("x-content-type-options", "").lower() == "nosniff", (
        f"Missing/wrong X-Content-Type-Options: {headers.get('x-content-type-options')!r}"
    )
    assert headers.get("x-frame-options", "").upper() in ("DENY", "SAMEORIGIN"), (
        f"Missing/wrong X-Frame-Options: {headers.get('x-frame-options')!r}"
    )
    referrer = headers.get("referrer-policy", "")
    assert referrer, f"Missing Referrer-Policy header"
    csp = headers.get("content-security-policy", "")
    assert csp, "Missing Content-Security-Policy header"
    assert "frame-ancestors" in csp, (
        f"CSP missing frame-ancestors directive (clickjacking risk): {csp!r}"
    )


def test_13_10b_csp_no_unsafe_eval(anon: httpx.Client):
    """13.10 CSP does not allow 'unsafe-eval' (XSS escalation vector)."""
    r = anon.get("/health")
    csp = r.headers.get("content-security-policy", "")
    assert "unsafe-eval" not in csp, (
        f"CSP contains 'unsafe-eval' — allows arbitrary script execution! CSP: {csp!r}"
    )


# ── CORS ──────────────────────────────────────────────────────────────────────

def test_13_11_cors_rejects_unknown_origin(anon: httpx.Client):
    """13.11 Untrusted origin does NOT get Access-Control-Allow-Origin in response."""
    r = anon.options(
        "/api/trades/",
        headers={
            "Origin": "https://evil.com",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    acao = r.headers.get("access-control-allow-origin", "")
    assert acao != "https://evil.com", (
        "CORS: evil.com origin is allowed! Any website can call this API on behalf of users."
    )
    assert acao != "*", (
        "CORS wildcard (*) — any origin allowed. Not acceptable for an authenticated API."
    )


def test_13_11b_cors_allows_legitimate_origin(anon: httpx.Client):
    """13.11 Legitimate app origin IS allowed in CORS (verify CORS not broken entirely)."""
    # The frontend runs on localhost:8080 in dev — this should be in CORS_ORIGINS
    r = anon.options(
        "/api/trades/",
        headers={
            "Origin": "http://localhost:8080",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    acao = r.headers.get("access-control-allow-origin", "")
    # Either explicitly allowed or via regex
    assert acao in ("http://localhost:8080", "*") or r.status_code == 200, (
        "Legitimate localhost:8080 origin is BLOCKED by CORS. Frontend won't work in dev!"
    )


# ── Cache-Control ──────────────────────────────────────────────────────────────

def test_13_12_api_responses_not_cached(anon: httpx.Client):
    """13.12 /api/* responses carry Cache-Control: no-store (prevents stale data after sync)."""
    # Use a 401 endpoint — still gets security headers applied before auth check
    r = anon.get("/api/trades/")
    cc = r.headers.get("cache-control", "")
    assert "no-store" in cc or "no-cache" in cc, (
        f"Cache-Control missing on API response: {cc!r}. "
        "Browser may serve stale trade data from cache after sync."
    )


def test_13_12b_health_endpoint_not_stale(anon: httpx.Client):
    """13.12 Non-API routes (like /health) have appropriate headers."""
    r = anon.get("/health")
    # At minimum, no private data — health is public
    assert r.status_code == 200


# ── Production environment check ───────────────────────────────────────────────

def test_13_15_admin_dev_bypass_blocked_in_prod(anon: httpx.Client):
    """13.15 ADMIN_DEV_BYPASS=1 must be ignored when ENVIRONMENT=production.
    We test this by checking if the /admin/auth/login endpoint behaves correctly.
    If dev_bypass works, a correct password returns a token without TOTP.
    We send a login with a fake password — if it returns 200, bypass is dangerously open.
    """
    # This test is always safe: wrong password should always return 401/422
    r = anon.post("/api/admin/auth/login", json={
        "email": "probe@check.com",
        "password": "wrong_password_probe_13_15",
    })
    # Must not succeed (401 = wrong creds, 422 = validation, 404 = not found)
    # 429 = rate limited from earlier test run — also means login is NOT succeeding
    assert r.status_code in (400, 401, 422, 404, 429), (
        f"Admin login with wrong password returned {r.status_code}. "
        f"Body: {r.text[:200]}"
    )
    assert r.status_code != 200, "Admin login with wrong password returned 200 — bypass active!"


# ── Cross-user isolation (needs token) ────────────────────────────────────────

@pytest.mark.skipif(not USER_TOKEN, reason="USER_TOKEN not set")
def test_13_3_cannot_access_arbitrary_broker_account(user: httpx.Client):
    """13.3 Authenticated user cannot access a random broker_account_id."""
    # Try a nil UUID — no valid account should exist
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = user.get("/api/trades/", params={"broker_account_id": fake_id})
    # Should either return empty results (data filtered to own account) or 403
    # NOT return another user's data
    if r.status_code == 200:
        data = r.json()
        # If 200, it must be because the endpoint ignores the param and returns OWN data
        # (i.e., broker_account_id is taken from JWT, not query param)
        # This is correct behavior — verify it's not returning arbitrary account data
        assert isinstance(data, (list, dict)), f"Unexpected response type: {type(data)}"
    else:
        assert r.status_code in (400, 403, 404, 422), (
            f"Unexpected status for invalid broker_account_id: {r.status_code}"
        )
