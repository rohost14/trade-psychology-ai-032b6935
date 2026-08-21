"""
The resolution ladder must not change a single threshold value.

`resolve_thresholds` replaced the body of `get_thresholds`. Its whole point is
to record WHERE each number came from — not to change any number. So the
headline test compares it against `_get_thresholds_pre_ladder`, the previous
implementation kept as a parity oracle, across every profile shape that reaches
it in production.

The second half asserts the provenance itself, because provenance that is wrong
is worse than no provenance: the Rules page will tell a trader "this is your
number", and it must only say that when it is true.
"""
import pytest

from app.core.trading_defaults import get_thresholds, _get_thresholds_pre_ladder
from app.core.threshold_resolution import Source, resolve_thresholds


class FakeProfile:
    """Stand-in for UserProfile — resolution only ever reads attributes."""

    _FIELDS = (
        "trading_capital", "daily_loss_limit", "max_position_size",
        "daily_trade_limit", "cooldown_after_loss", "max_consecutive_losses",
        "restricted_windows", "detected_patterns", "sl_percent_futures",
        "sl_percent_options", "risk_tolerance",
    )

    def __init__(self, **kw):
        for f in self._FIELDS:
            setattr(self, f, kw.get(f))


LEGACY_BASELINE = {
    "daily_trade_limit": 18,
    "burst_trades_per_15min": 9,
    "revenge_window_min": 4,
    "consecutive_loss_caution": 4,
    "consecutive_loss_danger": 7,
    "session_count": 40,
    "computed_at": "2026-08-01T00:00:00+00:00",
}

METRICS_BASELINE = {
    "computed_at": "2026-08-01T00:00:00+00:00",
    "sessions_analyzed": 40,
    "trades_analyzed": 150,
    "metrics": {
        "avg_daily_trades": {"value": 12.0, "confidence": 1.0, "n": 40},
        "median_reentry_after_loss_min": {"value": 6.0, "confidence": 0.9, "n": 90},
    },
}

PROFILES = {
    "no_profile": None,
    "empty_profile": FakeProfile(),
    "declared_rules_only": FakeProfile(
        trading_capital=50000, daily_loss_limit=2500, daily_trade_limit=5,
        cooldown_after_loss=15, max_consecutive_losses=3, max_position_size=4,
    ),
    "legacy_flat_baseline": FakeProfile(
        trading_capital=50000, detected_patterns={"baseline": LEGACY_BASELINE},
    ),
    "metrics_baseline": FakeProfile(
        trading_capital=50000, detected_patterns={"baseline": METRICS_BASELINE},
    ),
    "declared_and_baseline": FakeProfile(
        trading_capital=200000, daily_loss_limit=6000, daily_trade_limit=6,
        cooldown_after_loss=20, max_consecutive_losses=2, max_position_size=3,
        detected_patterns={"baseline": LEGACY_BASELINE},
    ),
    "partial_confidence_baseline": FakeProfile(
        trading_capital=50000,
        detected_patterns={"baseline": {
            "computed_at": "2026-08-01T00:00:00+00:00",
            "sessions_analyzed": 6,
            "metrics": {"avg_daily_trades": {"value": 20.0, "confidence": 0.2, "n": 6}},
        }},
    ),
}


# ---------------------------------------------------------------------------
# Parity — the ladder changes provenance, never values
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", list(PROFILES))
def test_ladder_returns_identical_values(name):
    profile = PROFILES[name]
    old = _get_thresholds_pre_ladder(profile)
    new = get_thresholds(profile)

    differing = {
        k: (old.get(k), new.get(k))
        for k in set(old) | set(new)
        if old.get(k) != new.get(k)
    }
    assert not differing, f"{name} changed value(s): {differing}"


@pytest.mark.parametrize("name", list(PROFILES))
def test_every_key_has_provenance(name):
    ts = resolve_thresholds(PROFILES[name])
    missing = [k for k in ts.values if ts.explain(k) is None]
    assert not missing, f"{name} has values with no recorded source: {missing}"


# ---------------------------------------------------------------------------
# Provenance — it must only claim "yours" when it is
# ---------------------------------------------------------------------------

def test_cold_start_claims_nothing_personal():
    """A brand-new user's numbers are ours, and must say so."""
    ts = resolve_thresholds(None)
    assert ts.explain("daily_trade_limit").source is Source.GLOBAL
    assert ts.explain("daily_trade_limit").confidence == 0.0
    assert ts.personal_keys() == {}


def test_history_is_marked_personal():
    ts = resolve_thresholds(PROFILES["legacy_flat_baseline"])
    r = ts.explain("daily_trade_limit")
    assert r.source is Source.HISTORY
    assert r.rung == 1
    assert r.is_personal
    assert "40" in r.detail          # sample size travels with the claim


def test_declared_rule_outranks_default_and_is_certain():
    ts = resolve_thresholds(PROFILES["declared_rules_only"])
    r = ts.explain("daily_trade_limit")
    assert r.source is Source.DECLARED
    assert r.confidence == 1.0       # a commitment is not an estimate
    assert r.value == 5


def test_blend_confidence_is_carried_not_invented():
    """A 6-session baseline must not be presented as though it were certain."""
    ts = resolve_thresholds(PROFILES["partial_confidence_baseline"])
    r = ts.explain("daily_trade_limit")
    assert r.source is Source.HISTORY
    assert r.confidence == pytest.approx(0.2)
    # 0.2 * (20*1.5) + 0.8 * 7 = 11.6 -> 12
    assert r.value == 12


def test_floor_records_that_it_overrode():
    """
    Floors are applied last and win over everything, including a trader's own
    rule. That is a live defect; this test pins the behaviour so the fix is a
    deliberate change rather than an accident.
    """
    p = FakeProfile(cooldown_after_loss=0, detected_patterns={"baseline": {
        "revenge_window_caution_min": 0, "session_count": 40,
    }})
    ts = resolve_thresholds(p)
    r = ts.explain("revenge_window_caution_min")
    assert r.source is Source.FLOOR
    assert r.value == 2              # UNIVERSAL_FLOORS['revenge_window_caution_min']


def test_capital_derived_pair_is_marked_capital():
    ts = resolve_thresholds(PROFILES["declared_rules_only"])
    assert ts.explain("max_position_pct_caution").source is Source.CAPITAL
    assert ts.explain("max_position_pct_danger").value == 8.0   # 2x declared 4


# ---------------------------------------------------------------------------
# ThresholdSet behaves as the dict detectors already expect
# ---------------------------------------------------------------------------

def test_threshold_set_is_dict_compatible():
    ts = resolve_thresholds(PROFILES["empty_profile"])
    assert ts["daily_trade_limit"] == ts.get("daily_trade_limit")
    assert ts.get("does_not_exist", "fallback") == "fallback"
    assert "daily_trade_limit" in ts
    assert dict(ts.items())["daily_trade_limit"] == ts["daily_trade_limit"]
