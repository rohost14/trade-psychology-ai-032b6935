"""
Entry-time checks must run on fills that OPEN a position, not on BUY fills.

The gate used to be `trade.transaction_type == "BUY"`, which conflates the side
of an order with its effect on the position. Covering a short is a BUY and an
EXIT, so every short seller received "your cooldown was violated — position is
OPEN" while closing out. The ledger already classifies each fill; these tests
pin the classification to the gate so the two cannot drift apart.

_compute_fill_effect is pure, so the classifications here are the real ones the
pipeline sees, not a restatement of the gate.
"""
from decimal import Decimal

import pytest

from app.services.position_ledger_service import _compute_fill_effect
from app.tasks.trade_tasks import _POSITION_OPENING_FILLS

PRICE = Decimal("100")


def effect(current_qty: int, fill_qty: int, avg=PRICE, price=PRICE) -> str:
    """entry_type for a fill against a position of current_qty."""
    entry_type, _new_qty, _new_avg, _pnl = _compute_fill_effect(
        current_qty, avg if current_qty else None, fill_qty, price
    )
    return entry_type


def opens_position(current_qty: int, fill_qty: int) -> bool:
    """Would the pipeline run entry-time checks for this fill?"""
    return effect(current_qty, fill_qty) in _POSITION_OPENING_FILLS


# ── The regression: covering a short is a BUY, and is not an entry ───────────

def test_covering_a_short_is_not_an_entry():
    """
    Short 100, then buy 100 to cover. transaction_type is BUY, so the old gate
    fired entry-time cooldown and restricted-window alerts on the way OUT.
    """
    assert effect(-100, +100) == "CLOSE"
    assert opens_position(-100, +100) is False


def test_partially_covering_a_short_is_not_an_entry():
    assert effect(-100, +40) == "DECREASE"
    assert opens_position(-100, +40) is False


def test_selling_to_close_a_long_is_not_an_entry():
    assert effect(+100, -100) == "CLOSE"
    assert opens_position(+100, -100) is False


def test_partially_selling_a_long_is_not_an_entry():
    assert effect(+100, -40) == "DECREASE"
    assert opens_position(+100, -40) is False


# ── What must still count as an entry ────────────────────────────────────────

def test_opening_a_long_is_an_entry():
    assert effect(0, +100) == "OPEN"
    assert opens_position(0, +100) is True


def test_opening_a_short_is_an_entry():
    """
    A SELL that opens a short. The old gate missed this entirely, so a trader
    who only shorts got no entry-time checks and no holding-loser chain.
    """
    assert effect(0, -100) == "OPEN"
    assert opens_position(0, -100) is True


def test_adding_to_a_long_is_an_entry():
    assert effect(+100, +50) == "INCREASE"
    assert opens_position(+100, +50) is True


def test_adding_to_a_short_is_an_entry():
    assert effect(-100, -50) == "INCREASE"
    assert opens_position(-100, -50) is True


def test_flipping_direction_is_an_entry():
    """A flip closes one position and opens the opposite — it is both."""
    assert effect(+100, -150) == "FLIP"
    assert opens_position(+100, -150) is True


def test_flipping_from_short_to_long_is_an_entry():
    assert effect(-100, +150) == "FLIP"
    assert opens_position(-100, +150) is True


# ── The gate itself ──────────────────────────────────────────────────────────

def test_exit_classifications_are_excluded_from_the_gate():
    """No exit-shaped fill may ever be treated as an entry."""
    assert "CLOSE" not in _POSITION_OPENING_FILLS
    assert "DECREASE" not in _POSITION_OPENING_FILLS


def test_unknown_classification_does_not_open_a_position():
    """
    _fill_entry_type stays None when the ledger step failed. Skipping the entry
    checks is the safe failure — guessing from the order side is what caused
    this bug.
    """
    assert None not in _POSITION_OPENING_FILLS
    assert "" not in _POSITION_OPENING_FILLS


# ── Entry-time alerts must be recorded as live, not post-hoc ─────────────────

class _Res:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _AlertDB:
    """Captures what _fire_position_alert adds."""

    def __init__(self):
        self.added = []

    async def execute(self, *_a, **_k):
        return _Res([])          # no recent alerts — nothing deduped

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass

    async def commit(self):
        pass

    async def refresh(self, _obj):
        pass


async def test_position_monitor_alerts_are_marked_live(monkeypatch):
    """
    Every alert from the position monitor is raised while the position is open —
    the copy says so. Migration 076 added `lifecycle` for exactly this and it was
    never set, so live findings were stored as 'post' alongside post-hoc ones.
    """
    from uuid import uuid4

    import app.tasks.position_monitor_tasks as pm
    from app.models.risk_alert import RiskAlert

    monkeypatch.setattr(pm, "publish_event", lambda *_a, **_k: None, raising=False)

    sent = []
    monkeypatch.setattr(
        pm.celery_app, "send_task", lambda *a, **k: sent.append(a), raising=False
    )
    import app.tasks.trade_tasks as tt
    monkeypatch.setattr(tt.send_danger_alert, "delay", lambda *a, **k: sent.append(a))

    db = _AlertDB()
    created = await pm._fire_position_alert(
        broker_account_id=str(uuid4()),
        pattern_type="overexposure",
        severity="danger",
        message="Position is OPEN and 3x your usual size",
        details={"symbol": "NIFTY25AUG24500CE"},
        db=db,
    )

    assert created is True
    alerts = [o for o in db.added if isinstance(o, RiskAlert)]
    assert len(alerts) == 1
    assert alerts[0].lifecycle == "live", "entry-time alert stored as post-hoc"
