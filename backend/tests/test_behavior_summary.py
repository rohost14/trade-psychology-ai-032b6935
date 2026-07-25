"""
E1 (deep-review P2): retire the dual engine. The behavioral summary the FE reads
(patterns_detected / behavior_score / emotional_tax) must come from the REAL
engine's stored RiskAlerts, not the legacy behavioral_analysis_service. Pure
mapper test (no DB).
"""
from types import SimpleNamespace

from app.services.behavior_summary import summarize_behavior


def _a(pattern_type, severity, message=""):
    return SimpleNamespace(pattern_type=pattern_type, severity=severity, message=message)


def test_empty():
    s = summarize_behavior([], session_risk_score=None, flagged_pnl=0.0)
    assert s["patterns_detected"] == []
    assert s["focus_area"] is None


def test_distinct_patterns_worst_severity_wins():
    alerts = [
        _a("revenge_trade", "caution", "c"),
        _a("revenge_trade", "danger", "d"),   # same pattern, worse severity
        _a("overtrading_burst", "caution", "o"),
    ]
    s = summarize_behavior(alerts, session_risk_score=60, flagged_pnl=-1234.5)
    pats = {p["pattern_type"]: p for p in s["patterns_detected"]}
    assert set(pats) == {"revenge_trade", "overtrading_burst"}          # deduped
    assert pats["revenge_trade"]["severity"] == "danger"                # worst wins
    assert pats["revenge_trade"]["description"] == "d"
    assert all(p["is_positive"] is False for p in s["patterns_detected"])
    assert s["behavior_score"] == 60
    assert s["emotional_tax"] == -1234.5


def test_focus_area_is_worst_pattern():
    alerts = [_a("size_escalation", "caution"), _a("session_meltdown", "critical")]
    s = summarize_behavior(alerts, session_risk_score=80, flagged_pnl=0)
    assert s["patterns_detected"][0]["pattern_type"] == "session_meltdown"  # sorted worst-first
    assert s["focus_area"] == "session_meltdown"


def test_shape_has_keys_the_fe_reads():
    s = summarize_behavior([_a("fomo_entry", "caution", "x")], 40, -10)
    for k in ("patterns_detected", "behavior_score", "emotional_tax", "top_strength", "focus_area"):
        assert k in s
    p = s["patterns_detected"][0]
    for k in ("pattern_type", "name", "severity", "description", "is_positive"):
        assert k in p
