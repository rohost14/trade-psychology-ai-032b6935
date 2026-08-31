"""
INFO evidence visibility — the closed rule, enforced.

Decision: docs/DEEP_REVIEW/INFO_EVIDENCE_VISIBILITY.md (29 Aug 2026).

    1. severity="info" patterns are evidence and analytics only.
    2. INFO events MUST NOT create RiskAlert rows.
    3. INFO events MUST NOT influence danger_zone, severity escalation, or any
       trader-facing alert.
    4. The rapid_reentry CAUTION path in danger_zone_service MUST NOT be
       activated.
    5. No INFO pattern may be promoted to a trader-facing alert.
    6. Making one trader-facing is an explicit future product decision.

These tests exist so the rule is not a convention. The separation they protect
is between RECORDING and INTERRUPTING: an info event is the product's memory,
an alert is an interruption, and letting the first leak into the second raises
alert volume without anyone deciding it should.
"""
import inspect
from pathlib import Path

import pytest

from app.core.severity import SEVERITY_ORDER, is_notifiable, rank

APP = Path(__file__).resolve().parents[1] / "app"


# ── 1 & 5. info is never notifiable ────────────────────────────────────────

def test_info_is_not_a_notifiable_severity():
    """
    Note what this asserts and what it does not. `caution` is ALSO not
    notifiable - it has no channel and is analytics, per trade_tasks' own
    comment. The rule being enforced here is about `info` specifically; the
    caution question is separate and untouched.
    """
    assert is_notifiable("info") is False
    assert is_notifiable("caution") is False
    for s in ("danger", "critical"):
        assert is_notifiable(s) is True, s


def test_info_ranks_below_every_alerting_severity():
    for s in ("caution", "danger", "critical"):
        assert rank("info") < rank(s), s
    # An unrecognised severity must never outrank info either - a typo must not
    # become an escalation.
    assert rank("nonsense") < rank("info")


# ── 2. info never becomes a RiskAlert ──────────────────────────────────────

def test_the_engine_skips_info_before_building_a_risk_alert():
    """
    behavior_engine builds RiskAlert rows from events. The info skip must come
    BEFORE construction, not be filtered afterwards, or an intermediate change
    could let one through.
    """
    src = (APP / "services" / "behavior_engine.py").read_text(encoding="utf-8")
    block = src[src.index("alerts = []"):]
    block = block[:block.index("alerts.append(RiskAlert(")]
    assert 'e.severity == "info"' in block, (
        "the info gate must precede RiskAlert construction")
    assert "continue" in block


def test_every_risk_alert_construction_site_is_gated():
    """
    Three modules build RiskAlert rows. Each must refuse info, or the rule has
    a hole somewhere other than the engine.
    """
    sites = {
        "services/behavior_engine.py": 'e.severity == "info"',
        "services/live_position_engine.py": None,
        "tasks/trade_tasks.py": None,
    }
    for rel, gate in sites.items():
        text = (APP / rel).read_text(encoding="utf-8")
        if "RiskAlert(" not in text:
            continue
        if gate:
            assert gate in text, rel
        else:
            # The other two must either gate on info or never produce it.
            produces_info = 'severity="info"' in text or "severity='info'" in text
            gated = ('== "info"' in text or "is_notifiable" in text
                     or "severity != \"info\"" in text)
            assert gated or not produces_info, (
                f"{rel} can build a RiskAlert from an info severity")


# ── 3 & 4. the danger zone cannot see info ─────────────────────────────────

def test_danger_zone_reads_risk_alerts_not_behaviour_events():
    """
    This is what makes the rule hold structurally rather than by filtering.
    _get_recent_alerts queries RiskAlert, and info never reaches RiskAlert, so
    no info event can enter patterns_active.
    """
    from app.services.danger_zone_service import DangerZoneService

    src = inspect.getsource(DangerZoneService._get_recent_alerts)
    assert "select(RiskAlert)" in src
    assert "BehaviorEvent" not in src, (
        "reading evidence here would let info events drive the danger zone")


def test_the_rapid_reentry_caution_path_stays_unreachable():
    """
    Clause 4, stated positively. The path is present in the source and is NOT
    activated. Activating it - by making the detector notify, or by making the
    danger zone read evidence - is a product decision, not a repair.

    This test does not require the branch to be deleted. It requires that
    nothing has quietly made it reachable.
    """
    from app.services.behavior_engine import BehaviorEngine
    from app.services.danger_zone_service import DangerZoneService

    dz = (APP / "services" / "danger_zone_service.py").read_text(encoding="utf-8")
    assert '"rapid_reentry"' in dz, "the branch is expected to still be present"

    # It is fed only from RiskAlert...
    assert "BehaviorEvent" not in inspect.getsource(DangerZoneService._get_recent_alerts)
    # ...and rapid_reentry can only ever emit info.
    det = inspect.getsource(BehaviorEngine._detect_rapid_reentry)
    assert 'severity="info"' in det
    assert 'severity="caution"' not in det and 'severity="danger"' not in det


# ── 6. no INFO detector has been promoted ──────────────────────────────────

# Was four: `panic_exit` retired 2026-08-29 (Pattern 14) and `early_exit`
# 2026-08-30 (Pattern 18).
ANALYTICS_INFO_DETECTORS = (
    # `opening_5min_trap` was the second member until it was retired
    # 2026-08-30 (Pattern 21). `rapid_reentry` is now the ONLY analytics
    # detector left, and the only one this rule governs.
    "rapid_reentry",
)


@pytest.mark.parametrize("name", ANALYTICS_INFO_DETECTORS)
def test_analytics_info_detectors_still_emit_only_info(name):
    """
    Promotion must be an explicit product decision. If one of these gains a
    caution/danger path, this fails and the decision gets made deliberately.
    """
    from app.services.behavior_engine import BehaviorEngine
    from app.services.detector_registry import BY_NAME

    assert BY_NAME[name].disposition == "analytics", name
    src = inspect.getsource(getattr(BehaviorEngine, BY_NAME[name].method))
    assert 'severity="info"' in src, name
    for promoted in ('severity="caution"', 'severity="danger"',
                     'severity="critical"'):
        assert promoted not in src, (
            f"{name} now emits {promoted} - promoting an INFO pattern to a "
            f"trader-facing alert is an explicit product decision "
            f"(docs/DEEP_REVIEW/INFO_EVIDENCE_VISIBILITY.md)")


def test_the_severity_scale_still_places_info_at_the_bottom():
    """The whole rule rests on this ordering."""
    assert SEVERITY_ORDER[0] == "info"


def test_the_decision_is_documented():
    """
    A rule enforced only by tests is a rule nobody can look up. The document is
    part of the mechanism.
    """
    doc = (Path(__file__).resolve().parents[2] / "docs" / "DEEP_REVIEW"
           / "INFO_EVIDENCE_VISIBILITY.md")
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    assert "CLOSED DECISION" in text
    assert "MUST NOT" in text
    assert "explicit future product" in text
