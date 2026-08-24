"""
Pattern coverage the entry-batch audit found missing, in three parts.

1. WIRING — the batch flush dispatches the adverse-add check for the right
   symbols and only those. The existing entry-batch tests cover the window and
   the classification thoroughly; none of them knew this check existed.

2. LIFECYCLE — what counts as "the same position". Buying, closing and buying
   again is not an add, however similar the prices look. This is the difference
   between reading the open position's state and reading the previous trade's
   price, and only the first is correct.

3. SEMANTICS — `adding_to_adverse_position` and `martingale_behaviour` are
   different behaviours and the tests say so in cases, not prose. One needs an
   OPEN losing position and does not care about size; the other needs a CLOSED
   loss and cares about nothing else.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.position_fills import PositionFill, adverse_adds
from app.services.behavior_engine import BehaviorEngine, EngineContext
from app.services.fill_classification import ADD_TO_LOSER, ADD_TO_WINNER

engine = BehaviorEngine()
T0 = datetime(2026, 8, 24, 4, 0, tzinfo=timezone.utc)
ACCOUNT = "11111111-2222-3333-4444-555555555555"


# ═══════════════════════════════════════════════════════════════════════
# 1. WIRING — is the check dispatched, and only where it should be?
# ═══════════════════════════════════════════════════════════════════════

class FakeRedis:
    def __init__(self):
        self.lists, self.keys = {}, {}

    def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)

    def ltrim(self, key, start, end):
        items = self.lists.get(key, [])
        self.lists[key] = items[start:] if end == -1 else items[start:end + 1]

    def expire(self, key, ttl):
        pass

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.keys:
            return None
        self.keys[key] = value
        return True

    def rename(self, src, dst):
        if src not in self.lists:
            raise RuntimeError("no such key")
        self.lists[dst] = self.lists.pop(src)

    def lrange(self, key, start, end):
        return list(self.lists.get(key, []))

    def delete(self, key):
        self.lists.pop(key, None)
        self.keys.pop(key, None)


def _fill(symbol, entry_type="INCREASE", scale_in=None):
    return {"entry_type": entry_type, "symbol": symbol, "scale_in": scale_in}


def _add_fill(r, payload):
    from app.services import entry_batch_service as batch
    batch.add_fill(r, ACCOUNT, payload)


async def _flush(monkeypatch, fills):
    """Run the real flush with everything except the adverse-add check stubbed."""
    import app.tasks.position_monitor_tasks as pm

    r = FakeRedis()
    for f in fills:
        _add_fill(r, f)
    monkeypatch.setattr(pm, "_get_redis", lambda: r)

    seen = []

    async def noop(*_a, **_k):
        return None

    async def spy(_acct, symbol):
        seen.append(symbol)

    monkeypatch.setattr(pm, "_concentration_task", noop)
    monkeypatch.setattr(pm, "_entry_rules_task", noop)
    monkeypatch.setattr(pm, "_overexposure_task", noop)
    monkeypatch.setattr(pm, "_shadow_entry_detection", noop)
    monkeypatch.setattr(pm, "_adverse_add_task", spy)
    await pm._flush_entry_batch(ACCOUNT)
    return seen


class TestFlushWiring:

    async def test_an_adverse_add_is_dispatched(self, monkeypatch):
        seen = await _flush(monkeypatch, [_fill("NIFTY25AUG24000CE",
                                                scale_in=ADD_TO_LOSER)])
        assert seen == ["NIFTY25AUG24000CE"]

    async def test_a_favourable_add_is_not_dispatched(self, monkeypatch):
        seen = await _flush(monkeypatch, [_fill("NIFTY25AUG24000CE",
                                                scale_in=ADD_TO_WINNER)])
        assert seen == []

    async def test_a_plain_open_is_not_dispatched(self, monkeypatch):
        """A first entry has nothing to be adverse to — no query at all."""
        seen = await _flush(monkeypatch, [_fill("NIFTY25AUG24000CE", "OPEN")])
        assert seen == []

    async def test_two_adverse_fills_of_one_symbol_dispatch_once(self, monkeypatch):
        """
        The whole point of the 5-second window: a sliced add is one decision.
        """
        seen = await _flush(monkeypatch, [
            _fill("NIFTY25AUG24000CE", scale_in=ADD_TO_LOSER),
            _fill("NIFTY25AUG24000CE", scale_in=ADD_TO_LOSER),
        ])
        assert seen == ["NIFTY25AUG24000CE"]

    async def test_only_the_adverse_leg_of_a_mixed_window_is_dispatched(self, monkeypatch):
        seen = await _flush(monkeypatch, [
            _fill("AAA25AUG100CE", scale_in=ADD_TO_WINNER),
            _fill("BBB25AUG200CE", scale_in=ADD_TO_LOSER),
            _fill("CCC25AUG300CE", "OPEN"),
        ])
        assert seen == ["BBB25AUG200CE"]

    async def test_a_failing_adverse_check_does_not_break_the_flush(self, monkeypatch):
        """One bad check must not lose the other entry checks."""
        import app.tasks.position_monitor_tasks as pm

        r = FakeRedis()
        _add_fill(r, _fill("NIFTY25AUG24000CE", scale_in=ADD_TO_LOSER))
        monkeypatch.setattr(pm, "_get_redis", lambda: r)

        ran = []

        async def boom(*_a, **_k):
            raise RuntimeError("ledger unavailable")

        async def rules(_acct, symbols):
            ran.append("rules")

        async def noop(*_a, **_k):
            return None

        monkeypatch.setattr(pm, "_adverse_add_task", boom)
        monkeypatch.setattr(pm, "_concentration_task", noop)
        monkeypatch.setattr(pm, "_overexposure_task", noop)
        monkeypatch.setattr(pm, "_shadow_entry_detection", noop)
        monkeypatch.setattr(pm, "_entry_rules_task", rules)

        result = await pm._flush_entry_batch(ACCOUNT)
        assert result["fills"] == 1
        assert ran == ["rules"]


# ═══════════════════════════════════════════════════════════════════════
# 2. LIFECYCLE — what counts as the same position
# ═══════════════════════════════════════════════════════════════════════

def fills(*specs):
    """(entry_type, signed_qty, price) → ledger-shaped rows."""
    out, held, avg = [], 0, 0.0
    for et, qty, price in specs:
        if et in ("OPEN", "FLIP"):
            held, avg = qty, price
        elif et == "INCREASE":
            new = held + qty
            avg = (avg * abs(held) + price * abs(qty)) / abs(new)
            held = new
        elif et == "DECREASE":
            held += qty
        elif et == "CLOSE":
            held, avg = 0, 0.0
        out.append(PositionFill(
            entry_type=et, fill_qty=qty, fill_price=price,
            position_qty_after=held,
            avg_entry_price_after=avg if held else None,
            occurred_at=T0 + timedelta(minutes=len(out) * 5),
        ))
    return out


def run(position_fills, direction="LONG", qty=150, entry=45.0):
    ct = SimpleNamespace(
        id=uuid4(), broker_account_id=uuid4(),
        tradingsymbol="NIFTY25AUG24000CE", exchange="NFO", product="MIS",
        instrument_type="CE", direction=direction, total_quantity=qty,
        avg_entry_price=Decimal(str(entry)), avg_exit_price=None,
        realized_pnl=None, pnl_pct=None, duration_minutes=None,
        entry_time=T0, exit_time=None,
        num_entries=sum(1 for f in position_fills
                        if f.entry_type in ("OPEN", "INCREASE")),
        num_exits=0, closed_by_flip=False, status="open", quality_score=None,
    )
    ctx = EngineContext(
        broker_account_id=ct.broker_account_id, session=None,
        completed_trade=ct, session_trades=[], active_cooldowns=[],
        thresholds={}, position_fills=position_fills,
    )
    return engine._detect_adding_to_adverse_position(ctx)


class TestPositionLifecycle:
    """
    The three cases that separate "the position is still open" from "the price
    happens to be lower than last time".
    """

    def test_buy_close_then_buy_lower_is_a_NEW_position(self):
        """
        50 → close @45 → later buy @30.

        Every price is below the first entry, so anything comparing the new
        trade against the previous TRADE PRICE would call this averaging down.
        It is not: the first position was closed and taken. This is a fresh
        decision at a fresh price, and it belongs to whatever detector reviews
        re-entry — not to this one.
        """
        r = run(fills(("OPEN", 75, 50.0), ("CLOSE", -75, 45.0),
                      ("OPEN", 75, 30.0)))
        assert not r.fired
        assert not r.abstained

    def test_buy_hold_then_add_lower_is_an_adverse_add(self):
        """50 → position stays open → add @30. The position was never let go."""
        r = run(fills(("OPEN", 75, 50.0), ("INCREASE", 75, 30.0)))
        assert r.fired
        assert r.context["adverse_add_count"] == 1
        assert round(r.context["deepest_adverse_pct"]) == 40

    def test_partial_exit_then_add_lower_is_still_an_adverse_add(self):
        """
        Buy 2 @50 → sell 1 @45 → add 1 @30.

        Exposure never went to zero, so the position is the same one. And the
        add is measured against the average COST of what is still held — a
        partial exit realises P&L but does not change what the remaining lot
        cost, so the reference is still 50, not 45.
        """
        r = run(fills(("OPEN", 150, 50.0), ("DECREASE", -75, 45.0),
                      ("INCREASE", 75, 30.0)))
        assert r.fired
        assert r.context["adverse_add_count"] == 1
        assert round(r.context["deepest_adverse_pct"]) == 40, (
            "measured against the 50 it still costs, not the 45 it sold at"
        )

    def test_the_reference_is_the_open_position_not_the_last_fill_price(self):
        """
        Add at 45 when the average is 50 but the LAST fill was 40.

        Comparing against the last fill price would call this favourable —
        45 is above 40. Against the position's own average it is adverse, which
        is the thing that is actually true.
        """
        adds = adverse_adds(fills(("OPEN", 75, 50.0), ("INCREASE", 75, 40.0),
                                  ("INCREASE", 75, 43.0)))
        assert len(adds) == 2, "both are adverse against the running average"
        assert adds[1].avg_before == 45.0
        assert adds[1].fill_price == 43.0

    def test_a_flip_starts_a_new_position(self):
        r = run(fills(("OPEN", 75, 50.0), ("INCREASE", 75, 40.0),
                      ("FLIP", -150, 35.0)))
        assert not r.fired, "the adds belonged to the position that was closed"


# ═══════════════════════════════════════════════════════════════════════
# 3. SEMANTICS — two behaviours, not one
# ═══════════════════════════════════════════════════════════════════════

def _ct(symbol, qty, entry, exit_px, minute, direction="LONG"):
    pnl = (exit_px - entry) * qty * (1 if direction == "LONG" else -1)
    return SimpleNamespace(
        id=uuid4(), broker_account_id=None, tradingsymbol=symbol,
        exchange="NFO", product="MIS", instrument_type="CE",
        direction=direction, total_quantity=qty,
        avg_entry_price=Decimal(str(entry)), avg_exit_price=Decimal(str(exit_px)),
        realized_pnl=Decimal(str(pnl)), pnl_pct=None, duration_minutes=10,
        entry_time=T0 + timedelta(minutes=minute),
        exit_time=T0 + timedelta(minutes=minute + 10),
        num_entries=1, num_exits=1, closed_by_flip=False, status="closed",
        quality_score=None,
    )


def _martingale(trades):
    ctx = EngineContext(
        broker_account_id=uuid4(),
        session=SimpleNamespace(session_pnl=Decimal("0"),
                                session_date=T0.date(), market_open=None),
        completed_trade=trades[-1], session_trades=trades[:-1],
        active_cooldowns=[], thresholds={},
    )
    return engine._detect_martingale_behaviour(ctx)


class TestTheTwoBehavioursAreDistinct:
    """
    `adding_to_adverse_position` needs an OPEN position moving against the
    trader and does not care about the size of the add.

    `martingale_behaviour` needs a CLOSED loss and an escalation on the next
    attempt. The earlier position is gone by the time it fires.

    They are not the same claim, they can both be true, and neither implies the
    other. These four cases are the proof.
    """

    def test_1_same_size_adverse_adds_are_adding_not_martingale(self):
        """Nothing gets bigger, so there is no escalation to call martingale."""
        r = run(fills(("OPEN", 75, 50.0), ("INCREASE", 75, 40.0),
                      ("INCREASE", 75, 30.0)))
        assert r.fired, "adding to a loser"

        # The same trader, as martingale sees them: one open position, which is
        # a single CompletedTrade, so martingale has nothing to compare.
        assert not _martingale([_ct("NIFTY25AUG24000CE", 225, 40.0, 30.0, 0)]).fired

    def test_2_closed_loss_then_a_bigger_trade_is_martingale_not_adding(self):
        """
        Four separate positions, each closed, each larger. No position was ever
        added to, so the adverse-add detector must stay silent — and does,
        because there is no fill sequence to read.
        """
        trades = [_ct("NIFTY25AUG24000CE", q, 50 - i, 45 - i, i * 20)
                  for i, q in enumerate([75, 150, 300, 600])]
        assert _martingale(trades).fired, "escalation across attempts"

        r = run(fills(("OPEN", 600, 47.0)))
        assert not r.fired, "a single-fill position was never added to"

    def test_3_an_adverse_add_that_grows_can_be_both(self):
        """
        Legitimately both: the trader added to an open loser AND the attempts
        escalated. Two true statements about one session; neither is redundant.
        """
        r = run(fills(("OPEN", 75, 50.0), ("INCREASE", 150, 40.0),
                      ("INCREASE", 300, 30.0)))
        assert r.fired
        assert r.context["at_least_doubled_down"] is True

        trades = [_ct("NIFTY25AUG24000CE", q, 50 - i, 45 - i, i * 20)
                  for i, q in enumerate([75, 150, 300, 600])]
        assert _martingale(trades).fired

    def test_4_a_favourable_add_is_neither(self):
        r = run(fills(("OPEN", 75, 50.0), ("INCREASE", 75, 60.0)))
        assert not r.fired

        # Sizes rising while WINNING is not martingale either: it requires
        # losses among the prior trades.
        trades = [_ct("NIFTY25AUG24000CE", q, 50, 55, i * 20)
                  for i, q in enumerate([75, 150, 300, 600])]
        assert not _martingale(trades).fired

    def test_neither_detector_can_see_what_the_other_sees(self):
        """
        The structural reason they cannot be merged: they read different
        objects. One reads a fill sequence inside one position; the other reads
        a list of completed positions.
        """
        from app.services.detector_registry import BY_NAME

        adding = BY_NAME["adding_to_adverse_position"]
        mart = BY_NAME["martingale_behaviour"]
        assert "position_fills" in adding.consumes
        assert "position_fills" not in mart.consumes
        assert adding.trigger == "entry" and mart.trigger == "exit"
