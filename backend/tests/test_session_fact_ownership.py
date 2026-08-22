"""
Session facts have exactly one writer.

WHY THIS EXISTS

`trading_sessions.trade_count` had NO writer at all. Nothing failed, because
nothing tested it and its two consumers both degrade silently:

  * the session log rendered "0 trades" for every session ever traded, and
  * the end-of-day intent comparison read 0 against the trader's declared
    maximum, so it always reported that they had kept to it.

`session_pnl` was one step better off — the engine derived it — but a dormant
incremental setter sat beside that, one call site away from two writers
disagreeing.

Both are now derived from the session's CompletedTrades by
`behavior_engine._load_context`, and these tests hold that line: the values are
right, they are idempotent under re-analysis, and no second writer has reappeared.
"""
import inspect
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.models.completed_trade import CompletedTrade
from app.models.trading_session import TradingSession
from app.services.behavior_engine import BehaviorEngine
from app.services.trading_session_service import TradingSessionService


engine = BehaviorEngine()


def _session_open():
    """
    Today's market open, in UTC.

    Trades are anchored to this rather than to `now` because `_load_context`
    filters the session's trades on `exit_time >= session.market_open`. A test
    that says "ninety minutes ago" silently produces zero session trades whenever
    it runs before 10:45 IST - which looks exactly like the bug under test.
    """
    from app.core.market_hours import get_session_boundaries, MarketSegment
    today_ist = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    open_utc, _ = get_session_boundaries(segment=MarketSegment.FNO, for_date=today_ist)
    return open_utc


async def _trade(db, broker, pnl, *, minute):
    exit_at = _session_open() + timedelta(minutes=minute)
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
        avg_exit_price=Decimal(str(22000 + pnl / 50)),
        realized_pnl=Decimal(str(pnl)),
        entry_time=exit_at - timedelta(minutes=20),
        exit_time=exit_at,
        duration_minutes=20,
        status="closed",
    )
    db.add(ct)
    await db.flush()
    return ct


async def _session(db, broker):
    res = await db.execute(
        select(TradingSession).where(TradingSession.broker_account_id == broker.id)
    )
    return res.scalars().first()


@pytest.mark.asyncio
async def test_trade_count_reflects_trades_actually_taken(db, broker):
    """
    The regression that shipped: this was 0 no matter how much the trader traded.
    """
    for i, pnl in enumerate([-2000, -1500, 3000]):
        ct = await _trade(db, broker, pnl, minute=30 + i * 30)
        await engine.analyze(broker_account_id=broker.id, completed_trade=ct, db=db)

    session = await _session(db, broker)
    assert session is not None
    assert session.trade_count == 3, (
        f"trade_count is {session.trade_count}; the session log and the intent "
        "comparison both read this field directly"
    )


@pytest.mark.asyncio
async def test_session_pnl_is_the_sum_of_the_day(db, broker):
    for i, pnl in enumerate([-2000, -1500, 3000]):
        ct = await _trade(db, broker, pnl, minute=30 + i * 30)
        await engine.analyze(broker_account_id=broker.id, completed_trade=ct, db=db)

    session = await _session(db, broker)
    assert Decimal(str(session.session_pnl)) == Decimal("-500")


@pytest.mark.asyncio
async def test_reanalysis_does_not_double_count(db, broker):
    """
    Deriving rather than incrementing is what buys this. A retried Celery task, a
    replay, or a late fill re-running the same trade must not inflate the day.
    """
    ct = await _trade(db, broker, -2000, minute=30)
    for _ in range(3):
        await engine.analyze(broker_account_id=broker.id, completed_trade=ct, db=db)

    session = await _session(db, broker)
    assert session.trade_count == 1
    assert Decimal(str(session.session_pnl)) == Decimal("-2000")


def test_no_second_writer_has_reappeared():
    """
    A dormant incremental setter is an invitation, not a spare part. If someone
    reintroduces one, they own reconciling it with the derivation in
    `_load_context` — and this test is where they find out.
    """
    for name in ("increment_trade_count", "add_session_pnl"):
        assert not hasattr(TradingSessionService, name), (
            f"{name} is back. session_pnl and trade_count are derived from "
            "CompletedTrades in behavior_engine._load_context; an increment path "
            "alongside a derive path is how the two silently disagree."
        )

    src = inspect.getsource(TradingSessionService)
    for field in ("trade_count", "session_pnl"):
        assert f"{field} +" not in src and f"{field}=" not in src, (
            f"TradingSessionService writes {field}; that field's owner is "
            "behavior_engine._load_context"
        )
