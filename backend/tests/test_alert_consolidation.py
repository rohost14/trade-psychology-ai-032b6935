"""
The alert budget: atomic, charged to the right day, and never silent on a critical.

Three defects are pinned here.

  1. The cap returned [] for the whole batch with no severity check, so a
     critical raised as the ninth alert of a session was dropped without a
     trace — on exactly the sessions the product exists for.
  2. The caller rebound its list to that empty return, so the alert_update
     WebSocket event was suppressed too. The row existed in risk_alerts and the
     dashboard was never told.
  3. The budget was looked up by wall-clock today rather than by the session
     the alert belongs to, and incremented with a read-modify-write in Python.
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.tasks.trade_tasks import _apply_alert_consolidation

IST = timezone(timedelta(hours=5, minutes=30))


def _alert(pattern, severity="caution", at=None):
    # Recent by default: an alert older than the push window cannot interrupt
    # anyone, so a stale default would make every budget assertion vacuous.
    return SimpleNamespace(
        id=uuid.uuid4(),
        pattern_type=pattern,
        severity=severity,
        detected_at=at or datetime.now(timezone.utc),
    )


class _Result:
    def __init__(self, rows=(), scalar=None):
        self._rows, self._scalar = list(rows), scalar

    def scalars(self):
        return SimpleNamespace(all=lambda: self._rows)

    def all(self):
        return self._rows

    def scalar_one_or_none(self):
        return self._scalar


class _FakeDb:
    """
    Minimal stand-in: the bucket SELECT returns alert rows, the mute SELECT
    returns pattern names, the budget UPDATE returns a number. Enough to
    exercise the decision logic without a database.
    """

    def __init__(self, recent=(), budget_after=None, muted=()):
        self.recent = list(recent)
        self.budget_after = budget_after
        self.muted = list(muted)
        self.executed = []
        self.commits = 0

    async def execute(self, stmt):
        self.executed.append(stmt)
        text = str(stmt).strip().upper()
        if text.startswith("UPDATE"):
            return _Result(scalar=self.budget_after)
        if "ALERT_MUTES" in text:
            return _Result(rows=[(p,) for p in self.muted])
        return _Result(rows=self.recent)

    async def commit(self):
        self.commits += 1


@pytest.mark.asyncio
async def test_critical_survives_the_cap():
    """The ninth alert of a bad session is the one most worth delivering."""
    account = uuid.uuid4()
    alerts = [_alert("death_spiral", "critical"), _alert("fomo_entry", "caution")]
    # 8 already fired + these 2 → UPDATE returns 10, so `before` is 8.
    db = _FakeDb(budget_after=10)

    out = await _apply_alert_consolidation(account, alerts, db)

    assert [a.severity for a in out] == ["critical"]


@pytest.mark.asyncio
async def test_below_the_cap_everything_passes():
    account = uuid.uuid4()
    alerts = [_alert("revenge_trade", "danger"), _alert("fomo_entry", "caution")]
    db = _FakeDb(budget_after=4)          # before = 2

    out = await _apply_alert_consolidation(account, alerts, db)

    assert len(out) == 2


@pytest.mark.asyncio
async def test_cap_with_no_critical_returns_nothing():
    account = uuid.uuid4()
    alerts = [_alert("revenge_trade", "danger")]
    db = _FakeDb(budget_after=9)          # before = 8

    out = await _apply_alert_consolidation(account, alerts, db)

    assert out == []


@pytest.mark.asyncio
async def test_missing_session_row_does_not_silently_uncap():
    """
    No session row means the budget is unknown, not zero. Returning the alerts
    is the honest failure: the alternative is a silent cap reset, which is what
    the wall-clock lookup used to do whenever the dates diverged.
    """
    account = uuid.uuid4()
    alerts = [_alert("revenge_trade", "danger")]
    db = _FakeDb(budget_after=None)

    out = await _apply_alert_consolidation(account, alerts, db)

    assert len(out) == 1


@pytest.mark.asyncio
async def test_five_minute_bucket_still_suppresses_a_repeat():
    account = uuid.uuid4()
    recent = [SimpleNamespace(pattern_type="revenge_trade")]
    alerts = [_alert("revenge_trade", "danger"), _alert("fomo_entry", "caution")]
    db = _FakeDb(recent=recent, budget_after=3)

    out = await _apply_alert_consolidation(account, alerts, db)

    assert [a.pattern_type for a in out] == ["fomo_entry"]


@pytest.mark.asyncio
async def test_duplicate_patterns_in_one_batch_collapse():
    account = uuid.uuid4()
    alerts = [_alert("revenge_trade", "danger"), _alert("revenge_trade", "caution")]
    db = _FakeDb(budget_after=2)

    out = await _apply_alert_consolidation(account, alerts, db)

    assert len(out) == 1


@pytest.mark.asyncio
async def test_empty_batch_touches_nothing():
    """It used to log a cap hit for an empty list — seen in a real replay."""
    db = _FakeDb(budget_after=99)

    out = await _apply_alert_consolidation(uuid.uuid4(), [], db)

    assert out == []
    assert db.executed == []
    assert db.commits == 0


@pytest.mark.asyncio
async def test_budget_is_charged_to_the_trades_session_not_today(monkeypatch):
    """
    detected_at is the trade's exit time. An alert from a session that closed
    just before IST midnight must be charged to THAT day, even when the task
    runs after midnight and wall-clock 'today' has already moved on.

    The push window is widened for this test only: the real 30-minute window
    would mark an alert this old as stale, which is correct behaviour but
    hides the date arithmetic under test.
    """
    from app.tasks import trade_tasks
    monkeypatch.setitem(trade_tasks.COLD_START_DEFAULTS, "alert_stale_push_min", 10 ** 7)

    account = uuid.uuid4()
    late = datetime(2025, 6, 19, 23, 55, tzinfo=IST)
    db = _FakeDb(budget_after=1)

    await _apply_alert_consolidation(account, [_alert("revenge_trade", "danger", at=late)], db)

    update = [s for s in db.executed if str(s).strip().upper().startswith("UPDATE")]
    assert len(update) == 1
    assert date(2025, 6, 19) in update[0].compile().params.values()


@pytest.mark.asyncio
async def test_budget_counts_only_alerts_that_can_interrupt():
    """
    B7. The cap is a fatigue guard, so it must count notifications, not rows.
    A caution has no channel — three of them used to spend three of the eight
    slots the trader has for alerts they would actually receive.
    """
    account = uuid.uuid4()
    alerts = [_alert("revenge_trade", "danger"),
              _alert("early_exit", "caution"),
              _alert("panic_exit", "caution")]
    db = _FakeDb(budget_after=1)

    await _apply_alert_consolidation(account, alerts, db)

    update = [s for s in db.executed if str(s).strip().upper().startswith("UPDATE")][0]
    assert 1 in update.compile().params.values(), "caution alerts charged the budget"


@pytest.mark.asyncio
async def test_a_muted_pattern_does_not_spend_the_budget():
    """
    The backwards case: muting a noisy pattern used to reduce how many OTHER
    alerts the trader could receive that day.
    """
    account = uuid.uuid4()
    alerts = [_alert("fomo_entry", "danger")]
    db = _FakeDb(budget_after=99, muted={"fomo_entry"})

    out = await _apply_alert_consolidation(account, alerts, db)

    assert not [s for s in db.executed if str(s).strip().upper().startswith("UPDATE")]
    assert out == alerts        # still saved, still returned; just not charged


@pytest.mark.asyncio
async def test_stale_alerts_do_not_spend_the_budget():
    """Bulk-synced history is saved and shown, never pushed."""
    account = uuid.uuid4()
    old = datetime.now(timezone.utc) - timedelta(hours=6)
    db = _FakeDb(budget_after=99)

    await _apply_alert_consolidation(account, [_alert("revenge_trade", "danger", at=old)], db)

    assert not [s for s in db.executed if str(s).strip().upper().startswith("UPDATE")]


@pytest.mark.asyncio
async def test_budget_increments_by_the_number_that_will_interrupt():
    account = uuid.uuid4()
    alerts = [_alert("revenge_trade", "danger"), _alert("fomo_entry", "danger"),
              _alert("size_escalation", "danger")]
    db = _FakeDb(budget_after=3)

    await _apply_alert_consolidation(account, alerts, db)

    update = [s for s in db.executed if str(s).strip().upper().startswith("UPDATE")][0]
    assert 3 in update.compile().params.values()
