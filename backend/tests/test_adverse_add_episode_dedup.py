"""
One alert per severity level per open position.

The problem this closes, seen in the real book: ASIANPAINT25JUN2400CE was added
to seven times across a session. The adds were hours apart, so each one landed
in a fresh 30-minute dedup window and re-alerted at `danger` three times with
nothing new to say.

A time window is the wrong instrument here. A ladder is one episode whether its
rungs are ninety seconds or four hours apart, so any window is wrong at one end
or the other. The position IS the episode, and the ledger already identifies it.

The last test in this file is the important one: it asserts the shared
30-minute rule that holding_loser, overexposure and portfolio_concentration
depend on has NOT changed.
"""
import inspect
from datetime import datetime, timedelta, timezone

import pytest

from app.core.position_fills import PositionFill
from app.tasks import position_monitor_tasks as pmt
from app.tasks.position_monitor_tasks import position_epoch

T0 = datetime(2026, 8, 24, 4, 0, tzinfo=timezone.utc)


class Row:
    """A ledger row, only the fields the epoch needs."""

    def __init__(self, entry_type, minute):
        self.entry_type = entry_type
        self.occurred_at = T0 + timedelta(minutes=minute)


# ── the episode identity ─────────────────────────────────────────────────

class TestPositionEpoch:

    def test_the_epoch_is_the_opening_fill(self):
        rows = [Row("OPEN", 0), Row("INCREASE", 5), Row("INCREASE", 200)]
        assert position_epoch(rows) == (T0).isoformat()

    def test_adds_hours_apart_share_one_epoch(self):
        """
        The whole point. Four hours between the first add and the last does not
        make them two episodes — the position never closed.
        """
        early = [Row("OPEN", 0), Row("INCREASE", 5)]
        late = [Row("OPEN", 0), Row("INCREASE", 5), Row("INCREASE", 240)]
        assert position_epoch(early) == position_epoch(late)

    def test_closing_and_re_entering_starts_a_new_epoch(self):
        first = [Row("OPEN", 0), Row("INCREASE", 5), Row("CLOSE", 10)]
        second = first + [Row("OPEN", 60), Row("INCREASE", 65)]
        assert position_epoch(first) != position_epoch(second)
        assert position_epoch(second) == (T0 + timedelta(minutes=60)).isoformat()

    def test_a_flip_starts_a_new_epoch(self):
        rows = [Row("OPEN", 0), Row("INCREASE", 5), Row("FLIP", 10),
                Row("INCREASE", 15)]
        assert position_epoch(rows) == (T0 + timedelta(minutes=10)).isoformat()

    def test_no_opening_row_in_view_yields_none(self):
        """
        The lookback is bounded, so a very long-lived position can lose sight of
        its OPEN. Returning None sends the caller back to the shared window
        rather than inventing an identity.
        """
        assert position_epoch([Row("INCREASE", 5), Row("INCREASE", 10)]) is None

    def test_an_empty_sequence_yields_none(self):
        assert position_epoch([]) is None


# ── the gate ─────────────────────────────────────────────────────────────

class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeDb:
    """Returns the severities already alerted for the queried episode."""

    def __init__(self, already):
        self.already = already
        self.queried = 0

    async def execute(self, _stmt):
        self.queried += 1
        return FakeResult([(s,) for s in self.already])


ACCOUNT = "11111111-2222-3333-4444-555555555555"
EPOCH = T0.isoformat()


class TestEscalationOnly:

    async def test_the_same_severity_again_is_suppressed(self):
        """Two adds, both caution, hours apart. The second says nothing new."""
        db = FakeDb(["caution"])
        assert await pmt._already_alerted_at_or_above(db, ACCOUNT, EPOCH, "caution")

    async def test_a_lower_severity_is_suppressed(self):
        db = FakeDb(["danger"])
        assert await pmt._already_alerted_at_or_above(db, ACCOUNT, EPOCH, "caution")

    @pytest.mark.parametrize("already,now", [
        (["caution"], "danger"),
        (["caution"], "critical"),
        (["danger"], "critical"),
    ])
    async def test_escalation_passes(self, already, now):
        """Going from 'added once' to 'added four times, 34% down' is news."""
        db = FakeDb(already)
        assert not await pmt._already_alerted_at_or_above(db, ACCOUNT, EPOCH, now)

    async def test_a_fresh_episode_passes(self):
        """close then re-entry: no alert carries the new epoch, so nothing suppresses."""
        db = FakeDb([])
        assert not await pmt._already_alerted_at_or_above(db, ACCOUNT, EPOCH, "caution")

    async def test_no_epoch_means_no_episode_gate(self):
        db = FakeDb(["danger"])
        assert not await pmt._already_alerted_at_or_above(db, ACCOUNT, None, "caution")
        assert db.queried == 0, "must not query without an identity to query for"

    async def test_the_alert_count_is_bounded_by_the_ladder(self):
        """
        Three notifiable rungs, so one open position can produce at most three
        alerts however many times it is added to. A bound by construction, not
        a cap that discards whichever detection came last.
        """
        delivered = []
        for severity in ["caution", "caution", "danger", "danger",
                         "critical", "critical", "danger", "caution"]:
            db = FakeDb(delivered)
            if not await pmt._already_alerted_at_or_above(db, ACCOUNT, EPOCH, severity):
                delivered.append(severity)
        assert delivered == ["caution", "danger", "critical"]


# ── the guarantee for every other detector ───────────────────────────────

def test_the_shared_thirty_minute_dedup_is_unchanged():
    """
    holding_loser, overexposure and portfolio_concentration all share
    _fire_position_alert. The episode rule deliberately lives in the
    adverse-add task instead, so their behaviour cannot move.
    """
    src = inspect.getsource(pmt._fire_position_alert)
    assert "timedelta(minutes=30)" in src, "the shared window moved"
    assert "episode" not in src, (
        "the episode rule leaked into the shared alert path, which would change "
        "dedup for three detectors that have not been reviewed"
    )
    assert 'return (d.get("rule"), d.get("symbol"))' in src, "the shared scope moved"


def test_the_episode_rule_lives_in_the_adverse_add_task_only():
    src = inspect.getsource(pmt._adverse_add_task)
    assert "position_epoch" in src
    assert "_already_alerted_at_or_above" in src
