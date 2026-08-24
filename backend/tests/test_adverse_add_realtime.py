"""
Pattern #1 fires on the FILL, not at exit.

The reason is the whole point of the detector. A trader who goes 50 -> 40 -> 30
and then closes at 25 gets an exit-time alert about a decision they made three
fills ago, when nothing can be done about it. Fired on the add, they are looking
at the position they just added to.

These tests pin the timing, the gating that keeps the ledger query off the hot
path, and the fact that the exit-time loop no longer double-reports it.
"""
from types import SimpleNamespace

import pytest

from app.services.detector_registry import BY_NAME, REGISTRY
from app.services.fill_classification import (
    ADD_TO_LOSER,
    ADD_TO_WINNER,
    classify_scale_in,
)
from app.tasks.position_monitor_tasks import _adverse_add_symbols


# ── the trigger contract ─────────────────────────────────────────────────

def test_the_detector_is_entry_triggered():
    spec = BY_NAME["adding_to_adverse_position"]
    assert spec.trigger == "entry"
    assert spec.disposition == "alerting"


def test_it_is_the_only_entry_triggered_detector():
    """
    `trigger` was descriptive until this detector needed it to mean something.
    If a second one appears, the exit loop silently stops running it — which
    must be a deliberate decision, not a surprise.
    """
    entry = [s.name for s in REGISTRY if s.trigger == "entry"]
    assert entry == ["adding_to_adverse_position"]


def test_the_exit_loop_skips_entry_triggered_detectors():
    """The engine must not also fire it when the position closes."""
    import inspect

    from app.services.behavior_engine import BehaviorEngine

    src = inspect.getsource(BehaviorEngine._run_all_detectors)
    assert 'spec.trigger == "entry"' in src, (
        "the exit-time loop no longer skips entry-triggered detectors, so this "
        "pattern would fire twice: once on the fill and again at close"
    )


# ── the gate that keeps the ledger query off the hot path ────────────────

class TestAdverseAddGate:
    """
    classify_scale_in already answered "was this an add to a loser?" on the fill
    itself. The batch reads that answer, so the ledger is only queried for
    symbols where the behaviour genuinely happened.
    """

    def test_add_to_loser_is_selected(self):
        fills = [{"symbol": "NIFTY25AUG24000CE", "scale_in": ADD_TO_LOSER}]
        assert _adverse_add_symbols(fills) == {"NIFTY25AUG24000CE"}

    def test_add_to_winner_is_not_selected(self):
        fills = [{"symbol": "NIFTY25AUG24000CE", "scale_in": ADD_TO_WINNER}]
        assert _adverse_add_symbols(fills) == set()

    def test_a_plain_open_is_not_selected(self):
        """A first entry has nothing to be adverse to — no query, no work."""
        fills = [{"symbol": "NIFTY25AUG24000CE", "entry_type": "OPEN",
                  "scale_in": None}]
        assert _adverse_add_symbols(fills) == set()

    def test_only_the_adverse_symbol_is_selected_from_a_mixed_batch(self):
        fills = [
            {"symbol": "AAA", "scale_in": ADD_TO_WINNER},
            {"symbol": "BBB", "scale_in": ADD_TO_LOSER},
            {"symbol": "CCC", "entry_type": "OPEN", "scale_in": None},
        ]
        assert _adverse_add_symbols(fills) == {"BBB"}

    def test_a_symbol_added_to_twice_in_one_window_is_queried_once(self):
        fills = [
            {"symbol": "BBB", "scale_in": ADD_TO_LOSER},
            {"symbol": "BBB", "scale_in": ADD_TO_LOSER},
        ]
        assert _adverse_add_symbols(fills) == {"BBB"}, "a set, so one query"


# ── the classification the gate rests on, both directions ────────────────

class TestScaleInIsDirectionSymmetric:
    """
    This is the test that has to hold for shorts to work at all, and the book
    has almost no short positions to prove it on.
    """

    @pytest.mark.parametrize("qty_after,fill,avg_after,expected", [
        # long: adding BELOW the average is averaging down
        (150, 40.0, 45.0, ADD_TO_LOSER),
        (150, 60.0, 55.0, ADD_TO_WINNER),
        # short: adding ABOVE the average is averaging down
        (-150, 60.0, 55.0, ADD_TO_LOSER),
        (-150, 40.0, 45.0, ADD_TO_WINNER),
    ])
    def test_long_and_short_mirror(self, qty_after, fill, avg_after, expected):
        assert classify_scale_in("INCREASE", qty_after, fill, avg_after) == expected

    def test_exactly_at_the_average_says_nothing(self):
        assert classify_scale_in("INCREASE", 150, 50.0, 50.0) is None

    @pytest.mark.parametrize("entry_type", ["OPEN", "DECREASE", "CLOSE", "FLIP"])
    def test_only_an_increase_can_be_a_scale_in(self, entry_type):
        assert classify_scale_in(entry_type, 150, 40.0, 45.0) is None

    def test_no_price_feed_is_involved(self):
        """
        Nothing here reads an LTP. The fill price is a market print and the
        average comes from the ledger, so a stale tick cannot make it wrong.
        """
        import inspect

        from app.services import fill_classification

        src = inspect.getsource(fill_classification)
        assert "ltp" not in src.lower()
        assert "get_cached" not in src


# ── the timing claim, stated as a test ───────────────────────────────────

def test_the_alert_is_raised_before_the_position_is_closed():
    """
    Structural, not behavioural: the entry path is dispatched from the fill
    pipeline's opening-fill gate, and INCREASE is in that gate. If INCREASE ever
    left POSITION_OPENING_FILLS, this detector would go back to being exit-only
    without anything else failing.
    """
    from app.services.fill_classification import POSITION_OPENING_FILLS

    assert "INCREASE" in POSITION_OPENING_FILLS


# ── delivery ─────────────────────────────────────────────────────────────

def test_the_alert_goes_out_over_the_websocket_path():
    """
    The entry task must raise its alert through _fire_position_alert, which is
    what publishes alert_update to the browser and applies the 30-minute
    per-symbol dedup. Raising a RiskAlert directly would persist an alert the
    trader never sees — which is the opposite of the point of moving this
    detector to the fill.
    """
    import inspect

    from app.tasks import position_monitor_tasks as pmt

    src = inspect.getsource(pmt._adverse_add_task)
    assert "_fire_position_alert" in src
    assert "publish_event" in inspect.getsource(pmt._fire_position_alert)


def test_only_an_increase_re_evaluates():
    """
    The task guards itself rather than trusting its caller. A DECREASE arriving
    from a retry or a future caller must not re-raise the alert the adds already
    earned.
    """
    import inspect

    from app.tasks import position_monitor_tasks as pmt

    src = inspect.getsource(pmt._adverse_add_task)
    assert 'last.entry_type or ""' in src and '!= "INCREASE"' in src


def test_the_task_reads_the_ledger_not_the_positions_table():
    """
    positions is a snapshot refreshed by a broker sync, so at the instant a fill
    lands it can be missing or stale. The ledger is written by the same pipeline
    that just wrote this fill. Reading positions here made the detector silent
    in replay, where no sync ever runs.
    """
    import inspect

    from app.tasks import position_monitor_tasks as pmt

    src = inspect.getsource(pmt._adverse_add_task)
    assert "PositionLedger" in src
    assert "select(Position)" not in src
