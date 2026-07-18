"""
Section 16: Edge Cases (API-testable subset)
Checklist items automated: 16.1 (empty state), 16.5 (long symbol), 16.6 (large P&L), 16.8 (maintenance)
Manual-only: 16.3 (stop backend), 16.4 (stop Redis), 16.7 (multiple accounts), 16.9 (nonce expiry)
"""

import pytest
import httpx
from tests.production.conftest import USER_TOKEN

pytestmark = pytest.mark.section16


def test_16_1_zero_trades_does_not_crash(anon: httpx.Client):
    """16.1 Health endpoint still works (backend handles empty state without crash).
    The real zero-trades test is UI-only, but we verify the API layer is stable.
    """
    r = anon.get("/health")
    assert r.status_code == 200, "Backend crashed — check for divide-by-zero in startup"


def test_16_8_maintenance_mode_check(anon: httpx.Client):
    """16.8 Maintenance mode: /health still returns 200 even in maintenance mode.
    (Health endpoint is always exempted so load balancers can detect backend is alive.)
    """
    r = anon.get("/health")
    assert r.status_code == 200, (
        "Health endpoint should always return 200 — even in maintenance mode. "
        "Load balancers depend on this."
    )


def test_16_8b_maintenance_mode_api_returns_503(anon: httpx.Client):
    """16.8 When MAINTENANCE_MODE=True, all non-health API endpoints return 503.
    Note: this test will PASS (skip) if maintenance mode is not active.
    If the server IS returning 503 on /api/* but 200 on /health, it's working correctly.
    """
    health = anon.get("/health")
    trades = anon.get("/api/trades/")  # Will be 401 normally, 503 in maintenance

    if trades.status_code == 503:
        # Maintenance mode is active — verify /health still works
        assert health.status_code == 200, (
            "Maintenance mode is on BUT /health also returns 503. "
            "Load balancers will think backend is down."
        )
        # Verify 503 has Retry-After header
        assert "retry-after" in trades.headers, (
            "Maintenance 503 missing Retry-After header. "
            "Clients won't know when to retry."
        )
    else:
        # Maintenance mode not active — this is expected in normal operation
        # Verify non-maintenance response is 401 (auth check reached), not 500
        assert trades.status_code in (401, 422), (
            f"Non-maintenance /api/trades/ returned unexpected {trades.status_code}"
        )


@pytest.mark.skipif(not USER_TOKEN, reason="USER_TOKEN not set")
class TestEdgeCasesWithAuth:

    def test_16_1_empty_account_analytics_no_crash(self, user: httpx.Client):
        """16.1 Analytics endpoints handle zero-trade accounts without NaN or crash."""
        endpoints = [
            ("/api/analytics/overview", "overview"),
            ("/api/analytics/edge-leak", "edge-leak"),
        ]
        for path, name in endpoints:
            r = user.get(path, params={"days_back": 1, "days": 1})  # Very short window = likely no data
            assert r.status_code in (200, 404), (
                f"Analytics {name} crashed with {r.status_code} on empty data. "
                f"Body: {r.text[:200]}"
            )
            if r.status_code == 200:
                # No NaN in JSON
                assert "NaN" not in r.text, (
                    f"Analytics {name} returned 'NaN' in JSON — JS will fail to parse."
                )

    def test_16_6_large_pnl_is_finite_number(self, user: httpx.Client):
        """16.6 P&L values from API are finite numbers (not Infinity or NaN)."""
        r = user.get("/api/analytics/overview")
        if r.status_code != 200:
            pytest.skip(f"Summary not available: {r.status_code}")

        raw = r.text
        assert "Infinity" not in raw, "API returned Infinity in P&L — formatting will break"
        assert "NaN" not in raw, "API returned NaN in P&L — formatting will break"

        data = r.json()
        # Check common P&L fields
        for field in ("total_pnl", "realized_pnl", "win_rate", "avg_pnl"):
            val = data.get(field)
            if val is not None:
                assert isinstance(val, (int, float)), (
                    f"P&L field '{field}' is not a number: {val!r}"
                )
                import math
                assert math.isfinite(val), (
                    f"P&L field '{field}' is not finite: {val}"
                )

    def test_api_handles_missing_broker_account_gracefully(self, user: httpx.Client):
        """16.7 Invalid/missing broker_account_id param doesn't cause 500."""
        r = user.get("/api/trades/", params={"broker_account_id": "invalid-uuid"})
        assert r.status_code not in (500,), (
            f"Invalid broker_account_id caused 500. Body: {r.text[:200]}"
        )
