"""
Pattern #2 end to end, through the REAL production path.

Everything else about this detector is unit-tested. This file exists because
unit tests cannot answer the question that actually matters: does a fill landing
in the live pipeline produce an alert? The wiring runs through four systems that
the unit tests each stub out — the Celery fill task, PositionLedger, the Redis
coalescing window, and the entry-batch flush — and a break in any of them is
silent.

It came from a real failure. The task originally read the `positions` table,
which the fill pipeline does not populate, so every unit test passed while the
detector produced nothing on real fills.

Nothing is monkeypatched. Fills go in; a RiskAlert row is asserted.
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.risk_alert import RiskAlert
from app.services.fill_classification import ADD_TO_LOSER, classify_scale_in

pytestmark = pytest.mark.asyncio


def _redis_or_skip():
    try:
        from app.core.redis_pool import get_sync_redis
        r = get_sync_redis()
        r.ping()
        return r
    except Exception as e:  # pragma: no cover - environment dependent
        pytest.skip(f"redis unavailable, entry-batch path cannot run: {e}")


def _postback(symbol, side, qty, price, at, order_id):
    """
    The payload Zerodha posts, exactly as webhooks.py assembles it.

    Built here rather than imported from the alertlab harness so the backend
    suite has no dependency outside backend/ — this test must run wherever the
    rest of them do.
    """
    stamp = at.strftime("%Y-%m-%d %H:%M:%S")
    return {
        "order_id": order_id,
        "exchange_order_id": f"X{order_id}",
        "status": "COMPLETE",
        "tradingsymbol": symbol,
        "exchange": "NFO",
        "transaction_type": side,
        "order_type": "MARKET",
        "product": "MIS",
        "quantity": abs(qty),
        "filled_quantity": abs(qty),
        "pending_quantity": 0,
        "cancelled_quantity": 0,
        "price": price,
        "average_price": price,
        "trigger_price": 0.0,
        "status_message": None,
        "order_timestamp": stamp,
        "exchange_timestamp": stamp,
        "validity": "DAY",
        "variety": "regular",
        "disclosed_quantity": 0,
        "parent_order_id": None,
        "tag": "integration",
        "guid": None,
        "instrument_token": None,
        "raw_payload": {},
    }


async def _inject(account_id, symbol, fills, day):
    """
    Drive the genuine pipeline: process_webhook_trade, ledger, entry batch.

    The task calls asyncio.run() internally, which raises inside an already
    running loop, so it goes to a thread. Eager Celery keeps it synchronous:
    when this returns, the ledger row and the batch entry both exist.
    """
    import asyncio

    from app.tasks.trade_tasks import process_webhook_trade

    base = datetime.combine(day, datetime.min.time()) + timedelta(hours=9, minutes=30)
    for i, (side, qty, price) in enumerate(fills):
        payload = _postback(symbol, side, qty, price,
                            base + timedelta(minutes=i * 3),
                            order_id=f"IT{day:%Y%m%d}{i:03d}")

        def _run(p=payload):
            outcome = process_webhook_trade.apply(
                args=[p, str(account_id), "integration"])
            if outcome.failed():
                raise AssertionError(f"fill task failed: {outcome.result!r}")
            return outcome.result

        await asyncio.to_thread(_run)


async def _publish(db):
    """
    Commit, because the fill task runs in its own session in another thread.

    The shared fixtures flush but never commit, which is right for unit tests
    and fatal here: process_webhook_trade opens its own session and would not
    see the broker account at all. The test cleans up after itself in _cleanup.
    """
    await db.commit()


async def _cleanup(db, account_id, user_id):
    """
    Remove what this test committed. Ordered by dependency, deepest first.

    The shared `db` fixture rolls back on teardown, and a rollback cannot undo
    a commit — so anything committed here has to be deleted here or it stays in
    the database for every future run.
    """
    from sqlalchemy import delete, text

    for table in ("behavior_events", "risk_alerts", "completed_trades",
                  "position_ledger", "positions", "trades", "trading_sessions",
                  "alert_mutes"):
        try:
            await db.execute(
                text(f"DELETE FROM {table} WHERE broker_account_id = :a"),
                {"a": str(account_id)})
        except Exception:
            await db.rollback()
    await db.execute(text("DELETE FROM broker_accounts WHERE id = :a"),
                     {"a": str(account_id)})
    await db.execute(text("DELETE FROM users WHERE id = :u"), {"u": str(user_id)})
    await db.commit()


async def _alerts(db, account_id, pattern="adding_to_adverse_position"):
    rows = await db.execute(
        select(RiskAlert)
        .where(RiskAlert.broker_account_id == account_id,
               RiskAlert.pattern_type == pattern)
        .order_by(RiskAlert.created_at)
    )
    return list(rows.scalars())


# ── the wiring, on the real path ─────────────────────────────────────────

class TestEndToEndThroughTheEntryBatch:

    async def test_an_averaging_down_ladder_produces_an_alert(self, db, broker, user):
        """
        The NIFTY ladder from 2025-11-25, the largest single loss in the book:
        75 @59, then +75 at 50, 42.70 and 34.35. The same size every time, so
        there is nothing here a multiplier rule could see.
        """
        _redis_or_skip()
        from app.tasks.position_monitor_tasks import _flush_entry_batch

        await _publish(db)
        try:
            day = datetime.now().date()
            await _inject(broker.id, "NIFTY25NOV26000CE", [
                ("BUY", 75, 59.00),
                ("BUY", 75, 50.00),
                ("BUY", 75, 42.70),
                ("BUY", 75, 34.35),
            ], day)
            await _flush_entry_batch(str(broker.id))

            found = await _alerts(db, broker.id)
            assert found, (
                "no alert from the real pipeline. Every unit test can pass "
                "while this fails - which is exactly what happened when the "
                "task read the positions table instead of the ledger."
            )
            latest = found[-1]
            assert latest.severity in ("caution", "danger", "critical")
            assert (latest.details or {}).get("at_fill") is True
            assert (latest.details or {}).get("adverse_add_count", 0) >= 1
        finally:
            await _cleanup(db, broker.id, user.id)

    async def test_a_pyramiding_ladder_produces_nothing(self, db, broker, user):
        """
        The same shape with the price going the trader's way. If this ever
        alerts, the sign handling has inverted and every disciplined scale-in
        becomes a false positive.
        """
        _redis_or_skip()
        from app.tasks.position_monitor_tasks import _flush_entry_batch

        await _publish(db)
        try:
            day = datetime.now().date()
            await _inject(broker.id, "TITAN25AUG3600CE", [
                ("BUY", 175, 19.20),
                ("BUY", 175, 21.20),
                ("BUY", 175, 23.40),
            ], day)
            await _flush_entry_batch(str(broker.id))

            assert not await _alerts(db, broker.id)
        finally:
            await _cleanup(db, broker.id, user.id)


# ── the classification the whole path rests on ───────────────────────────

class TestTheLadderIsClassifiedCorrectly:
    """
    If these ever disagree with the ledger, the entry-batch gate stops
    dispatching and the detector goes quiet with nothing failing.
    """

    async def test_each_add_of_the_real_ladder_reads_as_add_to_loser(self):
        # (position_after, fill_price, avg_after) as the ledger records them
        for qty_after, price, avg_after in [
            (150, 50.00, 54.50),
            (225, 42.70, 50.57),
            (300, 34.35, 46.51),
            (375, 30.50, 43.31),
        ]:
            assert classify_scale_in("INCREASE", qty_after, price, avg_after) \
                == ADD_TO_LOSER

    async def test_the_titan_ladder_is_not_add_to_loser(self):
        """175 @19.20 then +175 @21.20 — added while in profit."""
        assert classify_scale_in("INCREASE", 350, 21.20, 20.20) != ADD_TO_LOSER
