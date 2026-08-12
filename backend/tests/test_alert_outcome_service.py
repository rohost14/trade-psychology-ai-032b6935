"""
Outcome labelling from trades alone.

The test that matters most is the end-of-session guard. Alerts fire when a
position closes, so they cluster late in the day, and a naive implementation
labels almost all of them "heeded" because nothing followed — producing a
dataset that says the product works and means only that the market shut.
"""
from datetime import datetime, timedelta, timezone

from app.services.alert_outcome_service import (
    HEEDED, IGNORED, NO_OPPORTUNITY, observe_session, summarise,
)

IST = timezone(timedelta(hours=5, minutes=30))


def _t(h, m):
    return datetime(2025, 6, 19, h, m, tzinfo=IST)


def _trade(entry, exit_, pnl, qty=75, price=100.0):
    return {"entry_time": entry, "exit_time": exit_, "realized_pnl": pnl,
            "total_quantity": qty, "avg_entry_price": price}


def _alert(pattern, at, severity="caution", aid="a1"):
    return {"id": aid, "pattern_type": pattern, "severity": severity,
            "detected_at": at}


def test_stopping_at_the_close_is_not_heeding():
    """The central trap: no trades after, because the session ended."""
    trades = [
        _trade(_t(9, 30), _t(10, 0), -500),
        _trade(_t(10, 30), _t(11, 0), -600),
        _trade(_t(14, 50), _t(15, 10), -700),
    ]
    obs = observe_session([_alert("revenge_trade", _t(15, 10))], trades)
    assert obs[0].behaviour == NO_OPPORTUNITY
    assert any("session left" in n for n in obs[0].notes)


def test_stopping_with_session_remaining_is_heeding():
    trades = [
        _trade(_t(9, 30), _t(10, 0), -500),
        _trade(_t(10, 15), _t(10, 30), -600),
        _trade(_t(10, 40), _t(11, 0), -700),
    ]
    obs = observe_session([_alert("revenge_trade", _t(11, 0))], trades)
    assert obs[0].behaviour == HEEDED


def test_repeat_of_the_same_pattern_is_ignored():
    trades = [
        _trade(_t(9, 30), _t(10, 0), -500),
        _trade(_t(10, 5), _t(10, 20), -600),
        _trade(_t(10, 25), _t(10, 40), -700),
    ]
    alerts = [_alert("revenge_trade", _t(10, 20), aid="a1"),
              _alert("revenge_trade", _t(10, 40), aid="a2")]
    obs = observe_session(alerts, trades)
    assert obs[0].behaviour == IGNORED


def test_repeat_beats_the_no_opportunity_guard():
    """A pattern that recurred plainly had the opportunity to recur."""
    trades = [
        _trade(_t(9, 30), _t(10, 0), -500),
        _trade(_t(14, 55), _t(15, 5), -600),
        _trade(_t(15, 6), _t(15, 15), -700),
    ]
    alerts = [_alert("revenge_trade", _t(15, 5), aid="a1"),
              _alert("revenge_trade", _t(15, 15), aid="a2")]
    obs = observe_session(alerts, trades)
    assert obs[0].behaviour == IGNORED


def test_no_established_pace_is_undecidable():
    trades = [_trade(_t(9, 30), _t(9, 45), -500)]
    obs = observe_session([_alert("revenge_trade", _t(9, 45))], trades)
    assert obs[0].behaviour == NO_OPPORTUNITY
    assert any("established pace" in n for n in obs[0].notes)


def test_warranted_when_the_behaviour_kept_costing():
    trades = [
        _trade(_t(9, 30), _t(10, 0), -500),
        _trade(_t(10, 5), _t(10, 20), -600),
        _trade(_t(10, 30), _t(11, 0), -900),
    ]
    obs = observe_session([_alert("martingale_behaviour", _t(10, 20))], trades)
    assert obs[0].warranted is True
    assert obs[0].pnl_after == -900


def test_not_warranted_when_what_followed_made_money():
    trades = [
        _trade(_t(9, 30), _t(10, 0), -500),
        _trade(_t(10, 5), _t(10, 20), -600),
        _trade(_t(10, 30), _t(11, 0), 1500),
    ]
    obs = observe_session([_alert("martingale_behaviour", _t(10, 20))], trades)
    assert obs[0].warranted is False


def test_cost_label_absent_rather_than_zero_when_nothing_followed():
    """Absence of evidence must not read as a correct silence."""
    trades = [
        _trade(_t(9, 30), _t(10, 0), -500),
        _trade(_t(10, 5), _t(10, 20), -600),
    ]
    obs = observe_session([_alert("martingale_behaviour", _t(10, 20))], trades)
    assert obs[0].warranted is None
    assert obs[0].pnl_after is None


def test_pacing_down_counts_as_heeded():
    """Trader keeps going but at half their rhythm."""
    trades = [
        _trade(_t(9, 30), _t(9, 40), -500),
        _trade(_t(9, 45), _t(9, 55), -600),
        _trade(_t(10, 0), _t(10, 10), -700),
        _trade(_t(11, 30), _t(11, 45), -100),
    ]
    obs = observe_session([_alert("revenge_trade", _t(10, 10))], trades)
    assert obs[0].behaviour == HEEDED
    assert any("paced down" in n for n in obs[0].notes)


def test_escalation_after_the_alert_is_recorded():
    trades = [
        _trade(_t(9, 30), _t(10, 0), -500, qty=75, price=100),
        _trade(_t(10, 5), _t(10, 20), -600, qty=75, price=100),
        _trade(_t(10, 30), _t(11, 0), -900, qty=300, price=100),
    ]
    obs = observe_session([_alert("size_escalation", _t(10, 20))], trades)
    assert obs[0].escalated_after is True


def test_summary_keeps_the_two_denominators_apart():
    trades = [
        _trade(_t(9, 30), _t(10, 0), -500),
        _trade(_t(10, 5), _t(10, 20), -600),
        _trade(_t(10, 30), _t(11, 0), -900),
    ]
    obs = observe_session([_alert("revenge_trade", _t(10, 20))], trades)
    obs += observe_session([_alert("revenge_trade", _t(15, 10))], [
        _trade(_t(9, 30), _t(10, 0), -500),
        _trade(_t(10, 5), _t(10, 20), -600),
        _trade(_t(14, 50), _t(15, 10), -700),
    ])
    rows = summarise(obs)["revenge_trade"]
    assert rows["alerts"] == 2
    assert rows["no_opportunity"] == 1
    # The excluded alert must not inflate either rate.
    assert rows["n_behaviour"] == 1
    assert rows["n_cost"] == 1
