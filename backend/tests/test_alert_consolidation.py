"""
Alert consolidation — the 5-minute bucket and the session hard cap.

This function had no test, and it was silently returning [] for every live alert:
the caller commits the new alerts and *then* calls this, so the bucket query found
each alert's own freshly-written row and treated it as "already fired". Because
the caller rebinds its alert list to this return value, push, WhatsApp and the
alert_update WebSocket event were all gated off together.

The bug is a self-reference, so the tests are built around one question: does an
alert suppress itself? A stub DB is enough — the ordering, not the storage, is
what was wrong. `subject_ids` filtering happens in SQL, so the stub applies it
here to model what Postgres would return.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.tasks.trade_tasks import _apply_alert_consolidation

NOW = datetime.now(timezone.utc)


def make_alert(pattern_type: str, minutes_ago: float = 0.2, severity: str = "danger"):
    """detected_at is the TRADE's exit time — seconds ago on the live path."""
    return SimpleNamespace(
        id=uuid4(),
        pattern_type=pattern_type,
        severity=severity,
        detected_at=NOW - timedelta(minutes=minutes_ago),
    )


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalars(self):
        return self

    def all(self):
        return self._rows


class StubDB:
    """
    First execute() is the TradingSession lookup, second is the bucket query.

    `stored` is everything in risk_alerts. The stub applies the exclusion **only
    if the statement actually asks for it** — it reads the compiled SQL rather
    than assuming. Without that, these tests would pass against the broken code:
    a stub that filters on its own initiative tests the stub, not the query.
    """

    def __init__(self, session, stored, subject_ids=()):
        self.session = session
        self.stored = list(stored)
        self.subject_ids = set(subject_ids)
        self.calls = 0
        self.bucket_sql = ""

    async def execute(self, statement=None, *_args, **_kwargs):
        self.calls += 1
        if self.calls == 1:
            return _Result([self.session] if self.session else [])

        self.bucket_sql = str(statement) if statement is not None else ""
        excludes_subjects = "NOT IN" in self.bucket_sql.upper()

        five_min_ago = NOW - timedelta(minutes=5)
        rows = [
            a for a in self.stored
            if a.detected_at >= five_min_ago
            and not (excludes_subjects and a.id in self.subject_ids)
        ]
        return _Result(rows)

    async def get(self, *_args, **_kwargs):
        return None

    async def commit(self):
        pass


def session(alerts_fired: int = 0):
    return SimpleNamespace(id=uuid4(), alerts_fired=alerts_fired)


async def consolidate(alerts, stored=None, sess=None):
    stored = alerts if stored is None else stored
    db = StubDB(sess or session(), stored, subject_ids=[a.id for a in alerts])
    return await _apply_alert_consolidation(uuid4(), list(alerts), db)


# ── The regression ───────────────────────────────────────────────────────────

async def test_alert_does_not_suppress_itself():
    """
    The whole bug. One alert, already committed, must still notify.
    Before the fix this returned [] and the trader heard nothing.
    """
    alert = make_alert("revenge_trade")
    assert await consolidate([alert]) == [alert]


async def test_every_alert_of_a_batch_is_considered():
    """Distinct patterns from one trade each get their own notification."""
    alerts = [make_alert("revenge_trade"), make_alert("size_escalation")]
    assert len(await consolidate(alerts)) == 2


async def test_death_spiral_alert_is_not_suppressed_by_its_own_row():
    """
    The meta-detector commits its alert before consolidation too, and it is the
    guardian-eligible one — the single alert we least want silently dropped.
    """
    spiral = make_alert("death_spiral", severity="critical")
    assert await consolidate([spiral]) == [spiral]


# ── The behaviour that must survive the fix ──────────────────────────────────

async def test_earlier_alert_of_same_pattern_still_suppresses():
    """A genuinely earlier alert inside the bucket is what this feature is for."""
    earlier = make_alert("revenge_trade", minutes_ago=3)
    new = make_alert("revenge_trade")
    assert await consolidate([new], stored=[earlier, new]) == []


async def test_duplicate_pattern_within_one_batch_notifies_once():
    """Two alerts, same pattern, same trade — one notification."""
    first, second = make_alert("overtrading_burst"), make_alert("overtrading_burst")
    assert len(await consolidate([first, second])) == 1


async def test_alert_outside_the_bucket_does_not_suppress():
    """Same pattern six minutes ago is outside the window — this one notifies."""
    old = make_alert("revenge_trade", minutes_ago=6)
    new = make_alert("revenge_trade")
    assert await consolidate([new], stored=[old, new]) == [new]


async def test_session_hard_cap_suppresses_everything():
    """Past the cap, alerts are still saved but nothing notifies."""
    alerts = [make_alert("revenge_trade")]
    assert await consolidate(alerts, sess=session(alerts_fired=8)) == []


async def test_just_under_the_cap_still_notifies():
    alerts = [make_alert("revenge_trade")]
    assert await consolidate(alerts, sess=session(alerts_fired=7)) == alerts


async def test_no_session_row_does_not_block_notification():
    """A missing TradingSession must not be read as 'cap reached'."""
    alert = make_alert("revenge_trade")
    db = StubDB(None, [alert], subject_ids=[alert.id])
    assert await _apply_alert_consolidation(uuid4(), [alert], db) == [alert]
