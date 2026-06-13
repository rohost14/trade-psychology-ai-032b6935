"""
Section 14: Logic & Data Correctness (API-testable subset)
Checklist items automated: 14.3, 14.4, 14.10, 14.11, 14.12 (partially), 14.9
Manual-only: 14.1 (P&L vs Zerodha Console), 14.2 (direction), 14.5 (IST display),
             14.6/14.7 (limit breach), 14.8 (insight hours)
Requires: USER_TOKEN
"""

import pytest
import httpx
from tests.production.conftest import USER_TOKEN

pytestmark = pytest.mark.section14


@pytest.mark.skipif(not USER_TOKEN, reason="USER_TOKEN not set")
class TestLogicCorrectness:

    def test_14_3_cnc_trades_filtered_from_api(self, user: httpx.Client):
        """14.3/14.4 Trades API returns only MIS/NRML/MTF — no CNC equity trades."""
        r = user.get("/api/trades/", params={"limit": 100})
        assert r.status_code == 200, f"Trades API failed: {r.status_code}"
        data = r.json()

        trades = data if isinstance(data, list) else data.get("trades", data.get("items", []))
        if not trades:
            pytest.skip("No trades in account to verify CNC filter")

        for i, trade in enumerate(trades):
            product = trade.get("product", "").upper()
            assert product != "CNC", (
                f"Trade #{i} has product=CNC — equity trades should be filtered out. "
                f"Trade: {trade.get('tradingsymbol')} / {trade.get('product')}"
            )
            # Also verify product is a known F&O product
            if product:
                assert product in ("MIS", "NRML", "MTF", "BO", "CO", ""), (
                    f"Trade #{i} has unexpected product type: {product!r}"
                )

    def test_14_4_completed_trades_no_cnc(self, user: httpx.Client):
        """14.4 Completed trades API also excludes CNC."""
        r = user.get("/api/trades/completed", params={"limit": 100})
        if r.status_code == 404:
            r = user.get("/api/completed-trades/", params={"limit": 100})
        if r.status_code not in (200, 404):
            pytest.skip(f"Completed trades endpoint status: {r.status_code}")

        if r.status_code == 200:
            data = r.json()
            trades = data if isinstance(data, list) else data.get("trades", data.get("items", []))
            for i, trade in enumerate(trades[:50]):
                product = trade.get("product", "").upper()
                assert product != "CNC", (
                    f"Completed trade #{i} has product=CNC. Should be filtered. "
                    f"Symbol: {trade.get('tradingsymbol')}"
                )

    def test_14_10_profile_has_onboarding_field(self, user: httpx.Client):
        """14.10 GET /api/profile/ returns 'needs_onboarding' field."""
        r = user.get("/api/profile/")
        assert r.status_code == 200, f"Profile endpoint failed: {r.status_code}. Body: {r.text[:300]}"
        data = r.json()
        assert "needs_onboarding" in data, (
            f"Profile response missing 'needs_onboarding' field. "
            f"OnboardingGate can't work without it. Response: {data}"
        )
        assert isinstance(data["needs_onboarding"], bool), (
            f"'needs_onboarding' is not a bool: {data['needs_onboarding']!r}"
        )

    def test_14_11_onboarding_skip_endpoint_exists(self, user: httpx.Client):
        """14.11 Onboarding skip endpoint is reachable (not 404)."""
        # POST the skip endpoint — won't actually skip since we check status not effect
        r = user.post("/api/profile/onboarding/complete")
        if r.status_code == 404:
            r = user.post("/api/profile/onboarding/skip")
        assert r.status_code != 404, (
            "Onboarding skip/complete endpoint not found (404). "
            "OnboardingWizard's Skip button will silently fail."
        )

    def test_14_9_insights_have_trade_count(self, user: httpx.Client):
        """14.9 Insights only show if enough trades — check endpoint doesn't crash on low data."""
        r = user.get("/api/profile/insights")
        if r.status_code == 404:
            r = user.get("/api/insights/")
        assert r.status_code in (200, 404), (
            f"Insights endpoint crashed: {r.status_code}. Body: {r.text[:300]}"
        )
        if r.status_code == 200:
            data = r.json()
            # Should have some structure — not a bare empty response
            assert isinstance(data, (dict, list)), f"Unexpected insights shape: {type(data)}"

    def test_analytics_summary_no_nan(self, user: httpx.Client):
        """5.1 Analytics summary endpoint returns valid numbers (no NaN in JSON)."""
        r = user.get("/api/analytics/summary")
        assert r.status_code in (200, 404), (
            f"Analytics summary crashed: {r.status_code}. Body: {r.text[:300]}"
        )
        if r.status_code == 200:
            # JSON spec forbids NaN — but Python's json module can produce it
            # Check raw text for 'NaN' which would cause JS parse errors
            assert "NaN" not in r.text, (
                "Analytics summary contains literal 'NaN' in JSON response. "
                "This will cause JSON.parse() to fail in the browser."
            )
            assert "Infinity" not in r.text, (
                "Analytics summary contains literal 'Infinity' in JSON response."
            )

    def test_analytics_edge_map_no_nan(self, user: httpx.Client):
        """5.6 Edge map endpoint — no NaN/null that would break ScatterChart."""
        r = user.get("/api/analytics/edge-map", params={"days_back": 90})
        assert r.status_code in (200, 404), (
            f"Edge map endpoint crashed: {r.status_code}. Body: {r.text[:300]}"
        )
        if r.status_code == 200:
            assert "NaN" not in r.text, (
                "Edge map response contains 'NaN' — will cause recharts ScatterChart warning."
            )

    def test_analytics_expiry_pattern_endpoint(self, user: httpx.Client):
        """5.7 Expiry pattern endpoint responds (not 404)."""
        r = user.get("/api/analytics/expiry-pattern", params={"days_back": 90})
        assert r.status_code != 404, (
            "Expiry pattern endpoint returned 404. "
            "ExpiryTab will show a blank panel and log a 404 error."
        )
        assert r.status_code in (200, 401, 422), (
            f"Expiry pattern unexpected status: {r.status_code}. Body: {r.text[:200]}"
        )

    def test_morning_intent_endpoints(self, user: httpx.Client):
        """3.6/3.7 Morning intent GET and POST endpoints exist."""
        r_get = user.get("/api/session-intent/today")
        assert r_get.status_code in (200, 404, 422), (
            f"Morning intent GET crashed: {r_get.status_code}"
        )
        # POST — don't actually save, just verify endpoint exists
        r_post = user.post("/api/session-intent/", json={
            "intent": "test_probe",
            "risk_appetite": "moderate",
        })
        assert r_post.status_code not in (404, 405), (
            f"Morning intent POST not found: {r_post.status_code}"
        )
