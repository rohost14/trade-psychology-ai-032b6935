"""
The resolution ladder changes provenance for everything and values for exactly
three keys.

`resolve_thresholds` replaced the body of `get_thresholds`. The headline test
compares it against `_get_thresholds_pre_ladder` — the previous implementation,
kept as a parity oracle — across every profile shape that reaches it in
production, and requires byte-identical output except for `CAPITAL_DERIVED`.

Those three (`revenge_min_loss_inr`, `profit_giveaway_min_peak`,
`profit_giveaway_min_erosion`) were absolute rupee floors, which cannot be
universal: ₹500 is 1% of a ₹50,000 account and 0.1% of a ₹5,00,000 one — the
same money describing two different events. They are now ratios of capital,
calibrated so a ₹50,000 account resolves to exactly the constants it had
before. `test_reference_account_is_unchanged` pins that calibration, so the
conversion cannot quietly re-tune three detectors while claiming to generalise
one thing.

The provenance tests matter as much as the values: the Rules page will tell a
trader "this is your number", and it must only say that when it is true. A
threshold we guessed must stay marked as ours.
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

#: The only keys the ladder deliberately changes, and only when capital is
#: known: three rupee floors that are now ratios of capital. Everything else
#: must still match the pre-ladder implementation exactly.
CAPITAL_DERIVED = {
    "revenge_min_loss_inr",
    "profit_giveaway_min_peak",
    "profit_giveaway_min_erosion",
}


@pytest.mark.parametrize("name", list(PROFILES))
def test_ladder_returns_identical_values(name):
    profile = PROFILES[name]
    old = _get_thresholds_pre_ladder(profile)
    new = get_thresholds(profile)

    differing = {
        k: (old.get(k), new.get(k))
        for k in set(old) | set(new)
        if old.get(k) != new.get(k) and k not in CAPITAL_DERIVED
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


# ---------------------------------------------------------------------------
# Rung 4 — rupee floors become ratios of capital
# ---------------------------------------------------------------------------

CAPITAL_KEYS = ("revenge_min_loss_inr", "profit_giveaway_min_peak",
                "profit_giveaway_min_erosion")


def test_reference_account_is_unchanged():
    """
    The ratios are calibrated against a Rs 50,000 account, so that account must
    resolve to exactly the constants it had before. Anything else would mean the
    conversion quietly re-tuned three detectors while claiming to generalise one.
    """
    ts = resolve_thresholds(FakeProfile(trading_capital=50000))
    assert ts["revenge_min_loss_inr"] == 500
    assert ts["profit_giveaway_min_peak"] == 1500
    assert ts["profit_giveaway_min_erosion"] == 500


@pytest.mark.parametrize("capital,expected_revenge", [
    (20_000, 200),
    (50_000, 500),
    (200_000, 2_000),
    (2_000_000, 20_000),
])
def test_rupee_floors_scale_with_capital(capital, expected_revenge):
    """Rs 500 is 1% of one account and 0.1% of another. The ratio is the claim."""
    ts = resolve_thresholds(FakeProfile(trading_capital=capital))
    assert ts["revenge_min_loss_inr"] == expected_revenge
    assert ts.explain("revenge_min_loss_inr").source is Source.CAPITAL


def test_unknown_capital_keeps_the_absolute_fallback_and_says_so():
    """
    A user we know nothing about still gets a working number — but it must be
    marked as ours, not theirs, so the UI never calls it "your" threshold.
    """
    for profile in (None, FakeProfile(), FakeProfile(trading_capital=0)):
        ts = resolve_thresholds(profile)
        for key in CAPITAL_KEYS:
            assert ts.explain(key).source is Source.GLOBAL
            assert not ts.explain(key).is_personal
        assert ts["revenge_min_loss_inr"] == 500


def test_capital_derived_detail_names_the_ratio_and_the_capital():
    """Provenance has to be readable by a human on the Rules page."""
    ts = resolve_thresholds(FakeProfile(trading_capital=200_000))
    detail = ts.explain("profit_giveaway_min_peak").detail
    assert "3.0%" in detail
    assert "200,000" in detail


def test_non_numeric_capital_does_not_break_resolution():
    """Profile fields come from JSON and the DB; a bad value must not 500."""
    ts = resolve_thresholds(FakeProfile(trading_capital="not-a-number"))
    assert ts["revenge_min_loss_inr"] == 500
    assert ts.explain("revenge_min_loss_inr").source is Source.GLOBAL


# ---------------------------------------------------------------------------
# Rung 2 — what this trader has done today
# ---------------------------------------------------------------------------

from datetime import datetime, timedelta, timezone  # noqa: E402


class FakeTrade:
    def __init__(self, entry_time, exit_time):
        self.entry_time = entry_time
        self.exit_time = exit_time


def a_session(hold_min, n, gap_min=20):
    """n trades, each held `hold_min`, separated by `gap_min`."""
    start = datetime(2026, 8, 21, 9, 20, tzinfo=timezone.utc)
    out = []
    for i in range(n):
        entry = start + timedelta(minutes=i * (hold_min + gap_min))
        out.append(FakeTrade(entry, entry + timedelta(minutes=hold_min)))
    return out


def test_no_session_data_leaves_everything_on_the_global_rung():
    """Every caller that has not been updated must behave exactly as before."""
    for st in (None, [], a_session(10, 1)):   # 1 trade yields 0 gaps, 1 hold
        ts = resolve_thresholds(None, session_trades=st)
        assert ts["panic_exit_min"] == 5
        assert ts.explain("panic_exit_min").source is Source.GLOBAL


@pytest.mark.parametrize("hold_min,expected", [
    (3, 1.5),      # scalper: half of a 3-minute normal hold
    (45, 22.5),    # intraday
    (240, 120.0),  # positional
])
def test_fast_is_measured_against_the_traders_own_pace(hold_min, expected):
    """
    The point of this rung. A five-minute exit is panic for someone whose normal
    hold is four hours and routine for someone whose normal is three minutes.
    One constant cannot serve both; their own median can.
    """
    ts = resolve_thresholds(None, session_trades=a_session(hold_min, 8))
    assert ts["panic_exit_min"] == pytest.approx(expected)
    assert ts.explain("panic_exit_min").source is Source.SESSION


def test_thin_evidence_barely_moves_the_number():
    """
    Two trades is not a distribution. Shrinkage must keep the value near the
    default rather than letting a single fast scalp redefine "normal".
    """
    ts = resolve_thresholds(None, session_trades=a_session(3, 2))
    r = ts.explain("panic_exit_min")
    assert r.confidence == pytest.approx(2 / 8)
    assert 4.0 < r.value < 5.0        # nudged down from 5, nowhere near 1.5


def test_confidence_grows_with_the_session():
    seen = [
        resolve_thresholds(None, session_trades=a_session(3, n))
        .explain("panic_exit_min").confidence
        for n in (2, 4, 8, 16)
    ]
    assert seen == sorted(seen), "confidence must be non-decreasing in n"
    assert seen[-1] == 1.0


def test_floors_still_win_over_session_evidence():
    """A one-minute median must not drive the threshold below the safety rail."""
    ts = resolve_thresholds(None, session_trades=a_session(1, 8))
    assert ts["panic_exit_min"] >= 1        # UNIVERSAL_FLOORS['panic_exit_min']


def test_session_rung_only_touches_analytics_thresholds():
    """
    Rung 2 is deliberately scoped to detectors that never notify, so it cannot
    change alert volume. If this list grows, that decision is being revisited
    and needs a replay behind it.
    """
    plain = resolve_thresholds(None)
    with_session = resolve_thresholds(None, session_trades=a_session(60, 10))
    moved = {k for k in plain.values
             if plain[k] != with_session[k]}
    assert moved == {"panic_exit_min", "rapid_reentry_min"}, moved


def test_a_break_is_not_a_re_entry():
    """Gaps over an hour are lunch, not a decision — they must not skew the median."""
    st = a_session(5, 6, gap_min=20) + a_session(5, 2, gap_min=600)
    ts = resolve_thresholds(None, session_trades=st)
    assert ts.explain("rapid_reentry_min").source is Source.SESSION
    assert ts["rapid_reentry_min"] < 20
