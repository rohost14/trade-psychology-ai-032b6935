"""
The engine's cost per trade, pinned as query count rather than wall clock.

MEASURED, NOT ASSUMED

Against the real database, per completed trade:

    _load_context          median  51.6ms   p90  68.2ms
    _run_all_detectors     median   3.2ms   p90   5.4ms
    analyze() end-to-end   median  73.0ms   p90  89.9ms

So all 27 detectors together are about 4% of the work and the round trips are
the other 96%. That settles a question that had been argued without numbers: the
hot path does not need optimising, and any future claim that it does needs a
measurement like this one rather than an intuition about 27 of anything.

WHY QUERY COUNT AND NOT MILLISECONDS

A wall-clock assertion against a remote database is flaky and would be
suppressed within a month. Query count is deterministic, and it is the thing
that actually drives the number above. Two properties are worth defending:

  1. **Detectors do no IO.** They are pure functions over the context. A single
     query inside a detector runs 27 times per trade in the worst case, and the
     failure is invisible - everything still works, just slower per trade than
     the last one.
  2. **The cost does not grow with the session.** `_load_context` must cost the
     same on a trader's fortieth trade of the day as on their second. An N+1
     introduced here is silent on a two-trade test and quadratic in production.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import event

from app.core import session_facts
from app.models.completed_trade import CompletedTrade
from app.services.behavior_engine import BehaviorEngine
from app.services.trading_session_service import TradingSessionService

engine = BehaviorEngine()


class QueryCounter:
    """Counts statements issued on a session's connection."""

    def __init__(self, db):
        self.db = db
        self.count = 0
        self.statements = []

    def _on_execute(self, conn, cursor, statement, *args, **kwargs):
        self.count += 1
        self.statements.append(statement.split("\n")[0][:80])

    def __enter__(self):
        self.sync_engine = self.db.get_bind().engine
        event.listen(self.sync_engine, "before_cursor_execute", self._on_execute)
        return self

    def __exit__(self, *exc):
        event.remove(self.sync_engine, "before_cursor_execute", self._on_execute)
        return False


async def _trade(db, broker, minute, pnl=-1500):
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
        avg_exit_price=Decimal("21990"),
        realized_pnl=Decimal(str(pnl)),
        entry_time=exit_at - timedelta(minutes=10),
        exit_time=exit_at,
        duration_minutes=10,
        status="closed",
    )
    db.add(ct)
    await db.flush()
    return ct


@pytest.mark.asyncio
async def test_detectors_do_no_database_work(db, broker):
    """
    Detectors are pure functions over the context. One query inside one detector
    runs up to 27 times a trade and nothing looks broken - it just gets slower
    per trade than the trade before.
    """
    from app.services.detector_flag_service import detector_flags

    flags = await detector_flags.get_flags(db)
    for i in range(6):
        await _trade(db, broker, 20 + i * 10)
    ct = await _trade(db, broker, 100)
    session = await TradingSessionService.get_or_create_session(
        broker.id, session_facts.session_date_now(), db
    )
    ctx = await engine._load_context(broker.id, ct, session, db)

    with QueryCounter(db) as counter:
        engine._run_all_detectors(ctx, flags)

    assert counter.count == 0, (
        "a detector queried the database: "
        + "; ".join(counter.statements[:5])
        + " — detectors read ctx, they do not fetch"
    )


@pytest.mark.asyncio
async def test_load_context_cost_does_not_grow_with_the_session(db, broker):
    """
    The fortieth trade of the day must cost the same as the second. An N+1 here
    is invisible on a two-trade test and quadratic on a real session.
    """
    session = await TradingSessionService.get_or_create_session(
        broker.id, session_facts.session_date_now(), db
    )

    early = await _trade(db, broker, 20)
    with QueryCounter(db) as c_small:
        await engine._load_context(broker.id, early, session, db)

    for i in range(25):
        await _trade(db, broker, 30 + i * 8)
    late = await _trade(db, broker, 260)

    with QueryCounter(db) as c_large:
        await engine._load_context(broker.id, late, session, db)

    assert c_large.count <= c_small.count, (
        f"_load_context issued {c_small.count} queries on a 1-trade session and "
        f"{c_large.count} on a 27-trade one — the cost is growing with the session"
    )


@pytest.mark.asyncio
async def test_the_whole_analysis_stays_within_a_query_budget(db, broker):
    """
    A ceiling, not a target. It exists so that adding a query to the hot path is
    a decision someone makes on purpose, with this number in front of them.

    Measured at 73ms end to end, of which the round trips are ~96%. Raising this
    budget means raising that.
    """
    for i in range(4):
        await _trade(db, broker, 20 + i * 10)
    ct = await _trade(db, broker, 80)

    with QueryCounter(db) as counter:
        await engine.analyze(broker_account_id=broker.id, completed_trade=ct, db=db)

    assert counter.count <= 15, (
        f"analyze() issued {counter.count} queries:\n  "
        + "\n  ".join(counter.statements)
    )
