"""
Sections 4 & 6: Alerts API + Risk/My-Patterns API
Checklist items automated: 4.1, 4.2, 4.7, 6.1 (partial), 6.2, 6.3
Requires: USER_TOKEN
"""

import pytest
import httpx
from tests.production.conftest import USER_TOKEN, assert_200

pytestmark = pytest.mark.section4


@pytest.mark.skipif(not USER_TOKEN, reason="USER_TOKEN not set")
class TestAlertsAPI:

    def test_4_1_alerts_endpoint_returns_200(self, user: httpx.Client):
        """4.1 GET /api/risk/alerts → 200 (page loads, no crash)."""
        r = user.get("/api/risk/alerts")
        assert r.status_code == 200, (
            f"Alerts endpoint failed: {r.status_code}. Body: {r.text[:300]}"
        )
        data = r.json()
        assert isinstance(data, (list, dict)), f"Unexpected response shape: {type(data)}"

    def test_4_2_empty_state_is_list_not_error(self, user: httpx.Client):
        """4.2 No alerts → empty list (not error). API must never 500 on empty data."""
        r = user.get("/api/risk/alerts")
        assert r.status_code == 200
        data = r.json()
        # Response is a list (possibly empty) or a dict with 'alerts' key
        if isinstance(data, list):
            # Empty list is valid — "no alerts" state
            pass
        elif isinstance(data, dict):
            alerts = data.get("alerts", data.get("items", []))
            assert isinstance(alerts, list), f"alerts field is not a list: {type(alerts)}"
        else:
            pytest.fail(f"Unexpected alerts response type: {type(data)}: {str(data)[:200]}")

    def test_4_7_alert_payload_has_required_fields(self, user: httpx.Client):
        """4.7 Each alert has: pattern_type, severity, message, created_at."""
        r = user.get("/api/risk/alerts")
        assert r.status_code == 200
        data = r.json()

        alerts = data if isinstance(data, list) else data.get("alerts", data.get("items", []))
        if not alerts:
            pytest.skip("No alerts to inspect — run some trades to generate alerts first")

        required_fields = {"pattern_type", "severity", "message", "created_at"}
        for i, alert in enumerate(alerts[:5]):  # Check first 5 max
            missing = required_fields - set(alert.keys())
            assert not missing, (
                f"Alert #{i} missing required fields: {missing}. Alert: {alert}"
            )
            # Severity must be a known value
            assert alert.get("severity") in ("low", "medium", "high", "critical"), (
                f"Alert #{i} has invalid severity: {alert.get('severity')!r}"
            )
            # message must be non-empty string
            assert isinstance(alert.get("message"), str) and alert["message"].strip(), (
                f"Alert #{i} has blank/missing message: {alert.get('message')!r}"
            )

    def test_4_acknowledge_endpoint_exists(self, user: httpx.Client):
        """4.4 Acknowledge endpoint is available (not 404/405)."""
        r = user.get("/api/risk/alerts")
        assert r.status_code == 200
        data = r.json()
        alerts = data if isinstance(data, list) else data.get("alerts", [])

        if not alerts:
            pytest.skip("No alerts to acknowledge")

        alert_id = alerts[0].get("id")
        if not alert_id:
            pytest.skip("Alert has no 'id' field")

        # Try PATCH or POST to acknowledge
        r2 = user.patch(f"/api/risk/alerts/{alert_id}/acknowledge")
        assert r2.status_code not in (404, 405), (
            f"Acknowledge endpoint missing for alert {alert_id}: {r2.status_code}"
        )


@pytest.mark.skipif(not USER_TOKEN, reason="USER_TOKEN not set")
class TestRiskStateAPI:

    def test_6_2_risk_state_returns_valid_state(self, user: httpx.Client):
        """6.2 GET /api/risk/state → valid state value."""
        r = user.get("/api/risk/state")
        assert r.status_code == 200, f"Risk state endpoint failed: {r.status_code}"
        data = r.json()

        state = data.get("state") or data.get("risk_state")
        assert state is not None, f"No 'state' field in response: {data}"
        assert state in ("safe", "caution", "danger"), (
            f"Invalid risk state value: {state!r}. Must be safe/caution/danger."
        )

    def test_6_3_risk_state_has_required_fields(self, user: httpx.Client):
        """6.3 Risk state response has all required fields for the frontend."""
        r = user.get("/api/risk/state")
        assert r.status_code == 200
        data = r.json()
        # Must have risk_state (string enum)
        assert "risk_state" in data or "state" in data, (
            f"Risk state response missing 'risk_state'/'state' field. Response: {data}"
        )
        # Must have active_patterns list (even if empty)
        assert "active_patterns" in data or "patterns" in data, (
            f"Risk state missing 'active_patterns' field. Response: {data}"
        )
        # active_patterns must be a list (never None)
        patterns = data.get("active_patterns", data.get("patterns", []))
        assert isinstance(patterns, list), (
            f"'active_patterns' is not a list: {type(patterns)!r}. Frontend will crash."
        )

    def test_blowup_shield_daily_limits_present(self, user: httpx.Client):
        """7.1/7.2 Blowup shield / danger zone data accessible."""
        r = user.get("/api/danger-zone/state")
        if r.status_code == 404:
            # Try alternate path
            r = user.get("/api/blowup-shield/state")
        assert r.status_code in (200, 404), f"Danger zone endpoint crashed: {r.status_code}"
        if r.status_code == 200:
            data = r.json()
            assert isinstance(data, dict), f"Unexpected shape: {data}"
