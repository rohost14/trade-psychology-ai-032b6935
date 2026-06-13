"""
Section 2: Zerodha OAuth Flow (automatable subset)
Checklist items automated: 2.2 (cookie), 2.4 (redirect not JSON), 2.6 (nonce reuse), 2.7 (cancel)
Manual-only: 2.1, 2.3, 2.5, 2.8, 2.9, 2.10 (require real Zerodha login)
"""

import pytest
import httpx

pytestmark = pytest.mark.section2


def test_2_4_connect_returns_redirect_not_json(anon: httpx.Client):
    """2.4 GET /api/zerodha/connect → 302 redirect to Zerodha, NOT JSON.
    Ensures BrokerContext.connect() does window.location.href, not XHR.
    """
    r = anon.get("/api/zerodha/connect")
    # Must be a redirect
    assert r.status_code in (302, 307, 308), (
        f"Expected redirect (302/307/308), got {r.status_code}. "
        f"If 200, frontend will get CORS error instead of navigating."
    )
    location = r.headers.get("location", "")
    # Must redirect to Zerodha (not back to app or another endpoint)
    assert "kite.zerodha.com" in location or "zerodha.com" in location, (
        f"Not redirecting to Zerodha. Location: {location!r}"
    )
    # JWT must NEVER appear in the redirect URL (would expose it in server access logs)
    assert "eyJ" not in location, (
        "JWT token found in OAuth redirect URL! This is a security vulnerability — "
        "server access logs will capture it."
    )


def test_2_2_oauth_nonce_cookie_set(anon: httpx.Client):
    """2.2 GET /api/zerodha/connect sets httpOnly oauth_nonce cookie.
    This is the CSRF protection replacing the broken state-param approach.
    """
    r = anon.get("/api/zerodha/connect")
    cookie = r.cookies.get("oauth_nonce")
    assert cookie is not None, (
        "oauth_nonce cookie NOT set on /api/zerodha/connect. "
        "CSRF protection is broken — anyone can forge a callback."
    )
    # httpx doesn't expose cookie flags directly, but we can verify the cookie is set
    # (httpOnly prevents JS access, verified via browser DevTools in manual test 2.2)


def test_2_6_callback_without_nonce_cookie_rejected(anon: httpx.Client):
    """2.6 Attacker calling /api/zerodha/callback directly (no cookie) is rejected.
    This simulates a CSRF attack where attacker tricks victim into visiting a crafted URL.
    """
    # No cookie set — simulate an attacker forging a callback
    r = anon.get(
        "/api/zerodha/callback",
        params={"request_token": "FAKE_ATTACKER_TOKEN", "status": "success"},
    )
    # Should redirect to an error page, NOT a success page
    if r.status_code in (302, 307, 308):
        location = r.headers.get("location", "")
        assert "connected=true" not in location, (
            "CSRF VULNERABILITY: callback without oauth_nonce cookie succeeded! "
            f"Redirect: {location}"
        )
        # Error redirect should contain 'error' or 'session' or 'failed'
        assert any(kw in location.lower() for kw in ("error", "session", "failed", "expired")), (
            f"Callback rejected but redirect URL has no error indicator: {location!r}"
        )
    else:
        # 4xx is also acceptable (immediate rejection)
        assert r.status_code >= 400, (
            f"Expected error response for forged callback, got {r.status_code}. "
            f"Body: {r.text[:200]}"
        )


def test_2_7_cancelled_oauth_redirects_to_error(anon: httpx.Client):
    """2.7 Zerodha sends status=cancelled → app redirects to error page gracefully.
    This happens when user clicks Cancel on Zerodha's login page.
    """
    # First get a valid nonce cookie
    connect_r = anon.get("/api/zerodha/connect")
    assert connect_r.status_code in (302, 307, 308)

    # Now simulate Zerodha's cancelled callback (using the nonce cookie from connect)
    r = anon.get(
        "/api/zerodha/callback",
        params={"status": "cancelled"},
        cookies={"oauth_nonce": connect_r.cookies.get("oauth_nonce", "dummy")},
    )
    # Should redirect to an error page
    if r.status_code in (302, 307, 308):
        location = r.headers.get("location", "")
        assert "connected=true" not in location, (
            f"Cancelled OAuth resulted in success redirect: {location}"
        )
        # Should mention error, cancelled, or OAuth
        assert any(kw in location.lower() for kw in ("error", "cancel", "oauth", "failed")), (
            f"Cancelled OAuth didn't produce a clear error redirect: {location!r}"
        )
    else:
        # Some backends return 400 directly — that's fine too
        assert r.status_code in (400, 422, 302, 307), (
            f"Unexpected status for cancelled OAuth: {r.status_code}"
        )
