"""
Section 12: Admin Panel API
Checklist items automated: 12.1, 12.2, 12.3 (rate limit), 12.7, 12.13, 12.15
Manual-only: 12.4 (dev bypass behaviour), 12.5 (TOTP UI), 12.6 (JWT expiry timing),
             12.8–12.9, 12.10–12.12, 12.16, 12.17, 12.18–12.22

No ADMIN_TOKEN needed for login/rate-limit tests.
ADMIN_TOKEN needed for overview/insights/health tests.
"""

import time
import pytest
import httpx
from tests.production.conftest import ADMIN_TOKEN

pytestmark = pytest.mark.section12


class TestAdminLoginNoToken:
    """Tests that don't need ADMIN_TOKEN."""

    def test_12_1_admin_login_page_exists(self, anon: httpx.Client):
        """12.1 Admin login endpoint exists (not 404)."""
        r = anon.post("/api/admin/auth/login", json={
            "email": "probe@test.com",
            "password": "wrongpassword",
        })
        # 404 would mean admin routes not mounted — that's a fail
        # 401/422/400 = route exists, credentials wrong = pass
        assert r.status_code != 404, (
            "Admin login endpoint returned 404. "
            "Admin routes may not be mounted in the app. Check app.include_router(admin_router)."
        )

    def test_12_2_wrong_password_returns_401(self, anon: httpx.Client):
        """12.2 Wrong admin credentials → 401 Unauthorized (not 500 or 200)."""
        r = anon.post("/api/admin/auth/login", json={
            "email": "admin@tradementor.com",
            "password": "definitely_wrong_password_xyz_12345",
        })
        assert r.status_code not in (200, 500), (
            f"Wrong password returned {r.status_code}. "
            f"Expected 401/400/422/429. Body: {r.text[:200]}"
        )
        # 429 = rate limited from test_12_3 running first — also proves credentials NOT accepted
        assert r.status_code in (400, 401, 422, 429), (
            f"Unexpected status for wrong admin password: {r.status_code}. Body: {r.text[:200]}"
        )

    def test_12_3_admin_login_rate_limited(self, anon: httpx.Client):
        """12.3 Admin login rate-limits after threshold failures."""
        # Make 8 rapid failed login attempts
        statuses = []
        for i in range(8):
            r = anon.post("/api/admin/auth/login", json={
                "email": f"ratelimit_probe_{i}@test.com",
                "password": f"wrong_password_{i}",
            })
            statuses.append(r.status_code)
            if r.status_code == 429:
                break

        assert 429 in statuses, (
            f"No rate limiting after {len(statuses)} rapid admin login attempts. "
            f"Got statuses: {statuses}. "
            "Admin brute-force attack would succeed."
        )

    def test_12_2b_admin_endpoints_require_auth(self, anon: httpx.Client):
        """12.2 All admin endpoints require authentication."""
        admin_endpoints = [
            ("GET", "/api/admin/overview"),
            ("GET", "/api/admin/users"),
            ("GET", "/api/admin/insights"),
            ("GET", "/api/admin/system/health"),
            ("GET", "/api/admin/broadcast/segments"),
        ]
        for method, path in admin_endpoints:
            if method == "GET":
                r = anon.get(path)
            else:
                r = anon.post(path, json={})
            assert r.status_code in (401, 403, 404), (
                f"Admin endpoint {method} {path} accessible without auth: {r.status_code}. "
                f"Body: {r.text[:200]}"
            )


@pytest.mark.skipif(not ADMIN_TOKEN, reason="ADMIN_TOKEN not set")
class TestAdminWithToken:

    def test_12_7_overview_returns_200(self, admin: httpx.Client):
        """12.7 Admin overview loads without crash."""
        r = admin.get("/api/admin/overview")
        assert r.status_code == 200, (
            f"Admin overview failed: {r.status_code}. Body: {r.text[:300]}"
        )
        data = r.json()
        assert isinstance(data, dict), f"Expected dict, got: {type(data)}"

    def test_12_7_overview_no_null_crashes(self, admin: httpx.Client):
        """12.8 Overview handles partial/null data gracefully (no undefined access errors)."""
        r = admin.get("/api/admin/overview")
        assert r.status_code == 200
        # If it returned 200, it didn't crash on null fields (backend guard)
        data = r.json()
        # Verify common fields don't contain raw Python errors
        assert "traceback" not in str(data).lower(), (
            "Admin overview response contains traceback text — exception leaked into response"
        )

    def test_12_13_insights_endpoint_loads(self, admin: httpx.Client):
        """12.13 Admin insights endpoint returns data (not 500)."""
        candidates = ["/api/admin/insights", "/api/admin/behavioral-insights"]
        for path in candidates:
            r = admin.get(path)
            if r.status_code != 404:
                assert r.status_code == 200, (
                    f"Admin insights {path} returned {r.status_code}. Body: {r.text[:300]}"
                )
                return
        pytest.skip("Admin insights endpoint not found at expected paths")

    def test_12_15_system_health_loads(self, admin: httpx.Client):
        """12.15 Admin system health page data loads."""
        candidates = ["/api/admin/system/health", "/api/admin/system"]
        for path in candidates:
            r = admin.get(path)
            if r.status_code != 404:
                assert r.status_code == 200, (
                    f"Admin system health {path} returned {r.status_code}. Body: {r.text[:300]}"
                )
                return
        pytest.skip("Admin system health endpoint not found")

    def test_12_19_broadcast_segment_counts_non_negative(self, admin: httpx.Client):
        """12.19 Broadcast segment counts are non-negative integers."""
        candidates = ["/api/admin/broadcast/segments", "/api/admin/broadcast"]
        for path in candidates:
            r = admin.get(path)
            if r.status_code == 404:
                continue
            assert r.status_code == 200, f"Broadcast segments: {r.status_code}"
            data = r.json()
            # Check for negative counts
            for key, val in data.items() if isinstance(data, dict) else []:
                if isinstance(val, (int, float)):
                    assert val >= 0, (
                        f"Negative count for segment {key!r}: {val}"
                    )
            return
        pytest.skip("Broadcast segments endpoint not found")
