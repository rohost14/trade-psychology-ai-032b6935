"""
Every completed round gets a feature row, whichever path created it.

WHAT WAS BROKEN

Three code paths create a CompletedTrade:

  1. `pnl_calculator.calculate_and_update_pnl` — the bulk FIFO recompute, which
     also wrote feature rows;
  2. `PositionLedgerService.build_completed_trade_on_close` — the LIVE postback
     path, which did not;
  3. the overnight-position backfill in `trade_sync_service`, which did not.

Production only exercises 2 and 3 in the ordinary course, so the features table
held **0 rows against 1,515 completed trades**. Nothing errored: `my_record.py`
guards every feature-derived statistic with `f is not None`, so "your record
after 2+ losses in a row", "after a loss", "on expiry day" and "quick re-entry"
all rendered as nothing at all.

That is the failure mode this project keeps meeting — a silent empty, not a
crash. These tests assert the row exists, because nothing else will notice if it
stops.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core import session_facts
from app.models.completed_trade import CompletedTrade
from app.models.completed_trade_feature import CompletedTradeFeature
from app.services.pnl_calculator import pnl_calculator


async def _ct(db, broker, pnl, minute, *, session_date=None):
    session_date = session_date or session_facts.session_date_now()
    exit_at = session_facts.session_start(session_date) + timedelta(minutes=minute)
    ct = CompletedTrade(
        broker_account_id=broker.id,
        tradingsymbol="NIFTY25JANFUT",
        exchange="NFO",
        instrument_type="FUT",
        product="MIS",
        direction="LONG",
        total_quantity=50,
        num_entries=1,
        num_exits=1,
        avg_entry_price=Decimal("22000"),
        avg_exit_price=Decimal("22010"),
        realized_pnl=Decimal(str(pnl)),
        entry_time=exit_at - timedelta(minutes=15),
        exit_time=exit_at,
        duration_minutes=15,
        status="closed",
    )
    db.add(ct)
    await db.flush()
    return ct


async def _feature(db, ct):
    res = await db.execute(
        select(CompletedTradeFeature).where(
            CompletedTradeFeature.completed_trade_id == ct.id
        )
    )
    return res.scalar_one_or_none()


@pytest.mark.asyncio
async def test_a_completed_trade_gets_a_feature_row(db, broker):
    ct = await _ct(db, broker, -2000, 30)
    await pnl_calculator.ensure_feature_for(ct, db)
    await db.flush()

    f = await _feature(db, ct)
    assert f is not None, "the row My Record reads was never written"
    assert f.is_winner is False
    assert f.holding_duration_minutes == 15


@pytest.mark.asyncio
async def test_it_is_idempotent(db, broker):
    """A retried Celery task must not write a second row for one trade."""
    ct = await _ct(db, broker, 1500, 30)
    assert await pnl_calculator.ensure_feature_for(ct, db) is not None
    await db.flush()
    assert await pnl_calculator.ensure_feature_for(ct, db) is None
    await db.flush()

    rows = await db.execute(
        select(CompletedTradeFeature).where(
            CompletedTradeFeature.completed_trade_id == ct.id
        )
    )
    assert len(list(rows.scalars().all())) == 1


@pytest.mark.asyncio
async def test_the_streak_it_records_is_session_scoped(db, broker):
    """
    The feature row carries the state the trader was in AT ENTRY, under the same
    definitions as everything else — so a run that ended yesterday is not
    recorded against today's trade.
    """
    today = session_facts.session_date_now()
    yesterday = today - timedelta(days=1)

    for i in range(3):
        await _ct(db, broker, -1000, 30 + i * 20, session_date=yesterday)
    first_today = await _ct(db, broker, -500, 30)

    await pnl_calculator.ensure_feature_for(first_today, db)
    await db.flush()

    f = await _feature(db, first_today)
    assert f.consecutive_loss_count == 0, (
        "yesterday's losing run must not be attributed to today's first trade"
    )
    assert f.entry_after_loss is False
    assert float(f.session_pnl_at_entry) == 0.0


@pytest.mark.asyncio
async def test_it_sees_earlier_trades_in_the_same_session(db, broker):
    today = session_facts.session_date_now()
    await _ct(db, broker, -1000, 30, session_date=today)
    await _ct(db, broker, -700, 60, session_date=today)
    third = await _ct(db, broker, -300, 90, session_date=today)

    await pnl_calculator.ensure_feature_for(third, db)
    await db.flush()

    f = await _feature(db, third)
    assert f.consecutive_loss_count == 2, "two losses had closed before this entry"
    assert f.entry_after_loss is True
    assert float(f.session_pnl_at_entry) == -1700.0
