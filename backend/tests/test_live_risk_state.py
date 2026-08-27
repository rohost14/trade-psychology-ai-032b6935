"""
Live premium-loss risk state — the tick-path evaluator.

Pattern #8's 2026-08-27 review moved it from a 60-second Celery beat that
re-queried the world (≈20,001 DB round trips a minute at 10k users, in a serial
loop) onto the tick stream, with state in memory and the database touched only
when a position or a rule changes.

The properties these tests hold:

  * **zero I/O on evaluation** — the reason it can run per tick at all
  * **crossings, not states** — a position sitting at 42% says nothing
  * **per-position band memory** — recovery then re-crossing does not re-announce
  * **positions are independent** — two bleeding positions are two stories, which
    is the measured bug in the old exit path where 7 of 48 detections were
    swallowed, one of them a critical at 86.7%
  * **two layers stay two** — the universal band is `UNIVERSAL_SAFETY` and the
    declared rule is a `USER_RULE`; both may speak, neither is blended into the
    other
"""

from types import SimpleNamespace

import pytest

from app.services.live_risk_state import (
    DECLARED,
    UNIVERSAL,
    LiveRiskState,
    PositionWatch,
    build_watches,
)

BANDS = (40.0, 60.0, 80.0)


def _watch(entry=100.0, qty=75, declared=None, bands=BANDS, token=111,
           symbol="NIFTY25AUG25000CE", account="acct-1", epoch="e1",
           expiry=False):
    return PositionWatch(
        broker_account_id=account, tradingsymbol=symbol, instrument_token=token,
        epoch=epoch, avg_entry_price=entry, quantity=qty,
        universal_bands=bands, declared_pct=declared, expiry_day=expiry,
    )


def _price_for(entry, loss_pct):
    return entry * (1 - loss_pct / 100.0)


# ── crossings, not states ──────────────────────────────────────────────────

def test_a_position_under_the_first_band_says_nothing():
    assert _watch().evaluate(_price_for(100, 39)) == []


def test_crossing_the_first_band_reports_once():
    w = _watch()
    first = w.evaluate(_price_for(100, 45))
    assert len(first) == 1 and first[0].severity == "caution"
    assert first[0].kind == UNIVERSAL and first[0].band_index == 0


def test_sitting_inside_a_band_already_reported_says_nothing():
    w = _watch()
    w.evaluate(_price_for(100, 45))
    assert w.evaluate(_price_for(100, 48)) == []
    assert w.evaluate(_price_for(100, 59)) == []


def test_escalation_40_60_80_reports_three_times():
    w = _watch()
    sev = []
    for loss in (45, 65, 85):
        out = w.evaluate(_price_for(100, loss))
        assert len(out) == 1
        sev.append(out[0].severity)
    assert sev == ["caution", "danger", "critical"]


def test_a_jump_past_two_bands_reports_the_higher_one_only():
    """
    Telling a trader "you passed 40%" when they are at 85% would be accurate and
    useless. The lower band is marked covered, not announced.
    """
    w = _watch()
    out = w.evaluate(_price_for(100, 85))
    assert len(out) == 1
    assert out[0].severity == "critical"
    assert w.evaluate(_price_for(100, 86)) == []


# ── recovery and re-crossing ───────────────────────────────────────────────

def test_recovery_then_recrossing_does_not_reannounce():
    w = _watch()
    assert len(w.evaluate(_price_for(100, 45))) == 1
    assert w.evaluate(_price_for(100, 20)) == []       # recovered
    assert w.evaluate(_price_for(100, 47)) == []       # band already reported


def test_recovery_then_a_deeper_band_still_escalates():
    w = _watch()
    w.evaluate(_price_for(100, 45))
    w.evaluate(_price_for(100, 10))
    out = w.evaluate(_price_for(100, 65))
    assert len(out) == 1 and out[0].severity == "danger"


def test_a_profitable_position_says_nothing():
    assert _watch().evaluate(150.0) == []
    assert _watch().loss_pct(150.0) is None


# ── the impossible reading is clamped, not printed ─────────────────────────

def test_loss_cannot_exceed_the_premium_paid():
    """A long option's downside IS the premium; past 100% the input is wrong."""
    w = _watch()
    assert w.loss_pct(0.0) == 100.0
    out = w.evaluate(0.0)
    assert out[0].loss_pct == 100.0


def test_a_missing_or_nonsense_price_says_nothing():
    w = _watch()
    assert w.loss_pct(None) is None
    assert w.evaluate(None) == []
    assert _watch(entry=0.0).evaluate(50.0) == []


# ── the two layers ─────────────────────────────────────────────────────────

def test_a_tighter_declared_rule_speaks_first():
    """
    The trader said 25%. That is their own line and it is reached before the
    universal band, so they hear about it first — and separately.
    """
    w = _watch(declared=25.0)
    out = w.evaluate(_price_for(100, 30))
    assert len(out) == 1
    assert out[0].kind == DECLARED and out[0].boundary_pct == 25.0
    assert out[0].loss_pct == 30.0


def test_the_declared_rule_does_not_replace_the_universal_band():
    w = _watch(declared=25.0)
    w.evaluate(_price_for(100, 30))              # declared fires
    out = w.evaluate(_price_for(100, 45))        # universal still fires
    assert len(out) == 1 and out[0].kind == UNIVERSAL


def test_both_layers_can_cross_on_one_price():
    w = _watch(declared=25.0)
    out = w.evaluate(_price_for(100, 45))
    kinds = {c.kind for c in out}
    assert kinds == {DECLARED, UNIVERSAL}, "both are true and both are reported"


def test_the_declared_rule_reports_once_per_position():
    w = _watch(declared=25.0)
    assert len(w.evaluate(_price_for(100, 30))) == 1
    assert w.evaluate(_price_for(100, 35)) == []


def test_a_looser_declared_rule_cannot_delay_the_universal_band():
    """
    `safety_bounds` says a declared value may only tighten. A trader who says
    "I exit at 90%" still hears the 40% safety band at 40%.
    """
    w = _watch(declared=90.0)
    out = w.evaluate(_price_for(100, 45))
    assert len(out) == 1
    assert out[0].kind == UNIVERSAL and out[0].boundary_pct == 40.0


def test_no_declared_rule_means_only_the_universal_layer():
    w = _watch(declared=None)
    out = w.evaluate(_price_for(100, 45))
    assert len(out) == 1 and out[0].kind == UNIVERSAL


# ── independence ───────────────────────────────────────────────────────────

def test_two_positions_on_one_account_are_independent():
    """
    The measured bug in the old exit path: account-scoped dedup swallowed 7 of
    48 detections, including MAZDOCK25OCT3400CE at 86.7% and critical.
    """
    state = LiveRiskState()
    state.replace_account("acct-1", [
        _watch(token=111, symbol="NIFTY25AUG25000CE", epoch="e1"),
        _watch(token=222, symbol="MAZDOCK25OCT3400CE", epoch="e2"),
    ])
    a = state.evaluate(111, _price_for(100, 45))
    b = state.evaluate(222, _price_for(100, 85))
    assert len(a) == 1 and len(b) == 1
    assert a[0].tradingsymbol != b[0].tradingsymbol
    assert b[0].severity == "critical"


def test_two_accounts_holding_the_same_instrument_both_hear_it():
    state = LiveRiskState()
    state.replace_account("acct-1", [_watch(account="acct-1", token=111)])
    state.replace_account("acct-2", [_watch(account="acct-2", token=111)])
    out = state.evaluate(111, _price_for(100, 45))
    assert {c.broker_account_id for c in out} == {"acct-1", "acct-2"}


def test_a_new_epoch_gets_a_fresh_memory():
    """Closed and re-entered is a different position, not a continuation."""
    state = LiveRiskState()
    state.replace_account("acct-1", [_watch(epoch="e1")])
    assert len(state.evaluate(111, _price_for(100, 45))) == 1
    state.replace_account("acct-1", [_watch(epoch="e2")])
    assert len(state.evaluate(111, _price_for(100, 45))) == 1, "new position, new story"


def test_a_rebuild_does_not_reannounce_a_band_already_reported():
    """An unrelated fill rebuilds the account; that must not re-alert."""
    state = LiveRiskState()
    state.replace_account("acct-1", [_watch(epoch="e1")])
    assert len(state.evaluate(111, _price_for(100, 45))) == 1
    state.replace_account("acct-1", [_watch(epoch="e1")])   # same epoch
    assert state.evaluate(111, _price_for(100, 45)) == []


def test_dropping_an_account_removes_its_watches():
    state = LiveRiskState()
    state.replace_account("acct-1", [_watch()])
    assert state.watch_count == 1
    state.drop_account("acct-1")
    assert state.watch_count == 0
    assert state.evaluate(111, _price_for(100, 90)) == []


def test_a_closed_position_stops_being_watched():
    state = LiveRiskState()
    state.replace_account("acct-1", [_watch(token=111), _watch(token=222, epoch="e2")])
    state.replace_account("acct-1", [_watch(token=111)])       # 222 closed
    assert state.evaluate(222, _price_for(100, 90)) == []


# ── batch, as the ticker delivers it ───────────────────────────────────────

def test_a_tick_batch_evaluates_every_token():
    state = LiveRiskState()
    state.replace_account("acct-1", [
        _watch(token=111, epoch="e1"),
        _watch(token=222, symbol="BANKNIFTY25AUG55000CE", epoch="e2"),
    ])
    out = state.evaluate_batch({111: _price_for(100, 45), 222: _price_for(100, 85)})
    assert len(out) == 2


def test_a_batch_survives_a_bad_value():
    state = LiveRiskState()
    state.replace_account("acct-1", [_watch(token=111)])
    out = state.evaluate_batch({111: _price_for(100, 45), 222: "nonsense"})
    assert len(out) == 1


def test_an_unknown_token_is_free():
    assert LiveRiskState().evaluate(999, 10.0) == []


# ── the property that makes it viable at all ───────────────────────────────

def test_evaluation_performs_no_io():
    """
    No database, no Redis, no network on the tick path. This is the whole reason
    the state lives in memory; if it ever stops being true the beat's scale
    problem comes straight back.
    """
    import inspect

    from app.services import live_risk_state as mod

    src = inspect.getsource(mod)
    body = src[src.index("class LiveRiskState"):]
    for forbidden in ("await ", "SessionLocal", "select(", "redis", "requests",
                      "httpx", "execute("):
        assert forbidden not in body, f"tick path reaches for {forbidden!r}"


def test_the_module_imports_no_io_libraries():
    import inspect

    from app.services import live_risk_state as mod

    head = inspect.getsource(mod).split("class Crossing")[0]
    for forbidden in ("from app.core.database", "import redis", "from sqlalchemy"):
        assert forbidden not in head


# ── building watches from positions ────────────────────────────────────────

def _pos(symbol="NIFTY25AUG25000CE", qty=75, entry=100.0, token=111):
    return SimpleNamespace(tradingsymbol=symbol, total_quantity=qty,
                           average_entry_price=entry, instrument_token=token,
                           opened_at="2026-08-27T09:20:00", id="p1")


TH = {"premium_loss_caution_pct": 40, "premium_loss_danger_pct": 60,
      "premium_loss_critical_pct": 80, "premium_loss_expiry_shift_pct": 15}


def test_build_keeps_long_options_only():
    made = build_watches([_pos()], TH, "acct-1")
    assert len(made) == 1 and made[0].universal_bands == (40.0, 60.0, 80.0)


def test_build_skips_short_options():
    """Premium received, not paid; a percentage of it lost is meaningless."""
    assert build_watches([_pos(qty=-75)], TH, "acct-1") == []


@pytest.mark.parametrize("symbol", ["NIFTY25AUGFUT", "INFY"])
def test_build_skips_anything_that_is_not_an_option(symbol):
    assert build_watches([_pos(symbol=symbol)], TH, "acct-1") == []


def test_build_skips_positions_it_cannot_price():
    assert build_watches([_pos(entry=0)], TH, "acct-1") == []
    assert build_watches([_pos(token=None)], TH, "acct-1") == []


def test_build_carries_the_declared_rule():
    made = build_watches([_pos()], {**TH, "sl_percent_options": 25}, "acct-1")
    assert made[0].declared_pct == 25.0


def test_build_applies_the_expiry_shift_to_both_layers():
    made = build_watches([_pos()], {**TH, "sl_percent_options": 25}, "acct-1",
                         is_expiry_day_fn=lambda s: True)
    assert made[0].universal_bands == (55.0, 75.0, 95.0)
    assert made[0].declared_pct == 40.0
    assert made[0].expiry_day is True


def test_build_does_not_shift_on_an_ordinary_day():
    made = build_watches([_pos()], {**TH, "sl_percent_options": 25}, "acct-1",
                         is_expiry_day_fn=lambda s: False)
    assert made[0].universal_bands == (40.0, 60.0, 80.0)
    assert made[0].declared_pct == 25.0


def test_the_bands_come_from_resolved_thresholds_not_this_module():
    """
    A change in trading_defaults must not be silently contradicted here, so the
    numbers are passed in rather than written down twice.
    """
    made = build_watches([_pos()], {**TH, "premium_loss_caution_pct": 33}, "acct-1")
    assert made[0].universal_bands[0] == 33.0
