"""
`trading_sessions.trade_count` must reflect the session's real trade count.

WHY THIS FILE EXISTS

The column had **no writer at all** until commit `3dc9fc0` (2026-08-23). Two
live consumers read it anyway, so for months:

  * the session log rendered "0 trades" for every session, and
  * `session_intent` compared actual_trades (always 0) against the trader's
    declared limit, so the end-of-day comparison always reported that they had
    kept to it — including on days they had not.

A writer was added (`behavior_engine._load_context`, `session.trade_count =
facts.trades`). **It has never executed against real data**: the account was
disconnected on 2026-07-30, three and a half weeks before the fix shipped. Every
one of the nine session rows in the database still reads
`trade_count = 0` while `session_pnl` on the same row is correct.

So the fix is correct by inspection and unproven by execution. This file is the
execution.

WHAT DEPENDS ON IT BEING RIGHT

Three user-facing behaviours read this column, and one of them is a gate:

    intent_tasks.py:188   if not session or (session.trade_count or 0) == 0: continue
                          ^ decides whether the daily score push is sent AT ALL
    intent_tasks.py:126   "you traded N against your limit of M"  (EOD comparison)
    intent_tasks.py:215   "{N} trades today"                      (push body)
    session_intent.py:215 the same EOD comparison, via the API

A permanently-zero column silently suppresses the push for every trader.

WHAT THIS TESTS, AND WHAT IT DOES NOT

It drives the real `BehaviorEngine.analyze()` — the function that owns the write
— against real CompletedTrade rows in a real session. It does not go through the
webhook/Celery path; `test_adverse_add_integration.py` already covers that, and
the writer sits below it either way.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core import session_facts
from app.models.completed_trade import CompletedTrade
from app.models.trading_session import TradingSession
from app.services.behavior_engine import BehaviorEngine

pytestmark = pytest.mark.asyncio

engine = BehaviorEngine()


async def _completed_trade(db, broker, minute: int, pnl: float) -> CompletedTrade:
    """One closed round trip, `minute` minutes into today's session."""
    exit_at = session_facts.session_start(session_facts.session_date_now()) + timedelta(
        minutes=minute
    )
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
        avg_exit_price=Decimal("22000") + Decimal(str(pnl)) / 50,
        realized_pnl=Decimal(str(pnl)),
        entry_time=exit_at - timedelta(minutes=15),
        exit_time=exit_at,
        duration_minutes=15,
        status="closed",
    )
    db.add(ct)
    await db.flush()
    return ct


async def _session_row(db, broker) -> TradingSession | None:
    return (await db.execute(
        select(TradingSession).where(
            TradingSession.broker_account_id == broker.id,
            TradingSession.session_date == session_facts.session_date_now(),
        )
    )).scalar_one_or_none()


# ── the regression the fix was written for ─────────────────────────────────

async def test_trade_count_matches_the_real_number_of_trades(db, broker):
    """
    THE POINT OF THIS FILE. Three completed trades must leave `trade_count = 3`.

    Before `3dc9fc0` this was 0 no matter how many trades the session held.
    """
    for i, pnl in enumerate((-2000.0, -1500.0, 800.0)):
        ct = await _completed_trade(db, broker, minute=30 + i * 15, pnl=pnl)
        result = await engine.analyze(
            broker_account_id=broker.id, completed_trade=ct, db=db
        )
        assert result is not None, "analyze() did not run"
        assert not result.failed_detectors, (
            f"detectors raised: {result.failed_detectors} — this is an engine "
            f"failure, not a statement about trade_count"
        )

    session = await _session_row(db, broker)
    assert session is not None, "analyze() did not create a TradingSession"
    assert session.trade_count == 3, (
        f"trade_count is {session.trade_count}, expected 3. This is the exact "
        f"defect 3dc9fc0 fixed — a permanently-zero trade_count silently "
        f"suppresses the daily score push (intent_tasks.py:188) and makes the "
        f"end-of-day limit comparison always report compliance."
    )


async def test_trade_count_grows_with_each_trade(db, broker):
    """
    Not just correct at the end — correct after every trade, because the engine
    runs per completed trade and the session row is read between them.
    """
    for expected, pnl in enumerate((-500.0, -700.0, -900.0, 1200.0), start=1):
        ct = await _completed_trade(db, broker, minute=30 + expected * 10, pnl=pnl)
        await engine.analyze(broker_account_id=broker.id, completed_trade=ct, db=db)

        session = await _session_row(db, broker)
        assert session.trade_count == expected, (
            f"after {expected} trade(s) trade_count is {session.trade_count}"
        )


async def test_session_pnl_and_trade_count_agree_on_the_same_row(db, broker):
    """
    The live data shows `session_pnl` correct and `trade_count` zero on the SAME
    row — which is what made the defect easy to miss. Both come from the same
    `session_facts.derive()` call, so they must move together or the writer is
    only half wired.
    """
    pnls = (-2000.0, -1500.0, 800.0, -300.0)
    for i, pnl in enumerate(pnls):
        ct = await _completed_trade(db, broker, minute=30 + i * 12, pnl=pnl)
        await engine.analyze(broker_account_id=broker.id, completed_trade=ct, db=db)

    session = await _session_row(db, broker)
    assert session.trade_count == len(pnls)
    assert float(session.session_pnl) == pytest.approx(sum(pnls), abs=0.01), (
        "session_pnl and trade_count are derived from one facts object; if only "
        "one is right the writer is half wired"
    )


async def test_a_single_trade_is_counted(db, broker):
    """
    The boundary that matters most. `intent_tasks.py:188` skips the daily push
    entirely when trade_count == 0, so a trader with exactly one trade must not
    be treated as having none.
    """
    ct = await _completed_trade(db, broker, minute=45, pnl=-1000.0)
    await engine.analyze(broker_account_id=broker.id, completed_trade=ct, db=db)

    session = await _session_row(db, broker)
    assert session.trade_count == 1, (
        "one trade counted as zero would suppress that trader's daily push"
    )


# ── the writer must stay where it is ───────────────────────────────────────

async def test_the_engine_still_owns_the_write():
    """
    Structural. `trade_count` and `session_pnl` had five writers once; the
    2026-08-23 refactor gave them exactly one owner, and
    `trading_session_service` documents that it is deliberately not it.

    A second writer reappearing is how the column drifted the first time.
    """
    import inspect

    from app.services import trading_session_service
    from app.services.behavior_engine import BehaviorEngine as _BE

    engine_src = inspect.getsource(_BE._load_context)
    assert "session.trade_count = facts.trades" in engine_src, (
        "the engine no longer writes trade_count — the column will silently "
        "return to zero"
    )

    # The service may MENTION trade_count in its docstring — it documents that
    # it deliberately does not own it. What it must never do is assign to it.
    svc_src = inspect.getsource(trading_session_service)
    assignments = [
        line.strip() for line in svc_src.splitlines()
        if "trade_count" in line and "=" in line
        and not line.strip().startswith("#")
        and "==" not in line
    ]
    assert not assignments, (
        f"trading_session_service assigns trade_count again: {assignments}. "
        f"It documents that behavior_engine is the single owner; two writers "
        f"is how this column drifted to zero in the first place."
    )
