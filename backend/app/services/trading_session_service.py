"""
TradingSessionService

Manages one TradingSession row per (broker_account, trading_day).

Responsibilities:
  - get_or_create_session: idempotent, safe to call multiple times per day
  - alert-budget counters
  - close_session: records closing equity at end of day

This service does NOT own `session_pnl` or `trade_count`. Both are derived from
the session's CompletedTrades by `behavior_engine._load_context`, which is their
single writer. The incremental setters that used to live here are gone — see the
note below.

`update_risk_score` and the 40/70/90 session_state ladder were removed
2026-08-13 — see docs/GLOBALS_DERIVATION.md. The `risk_score` and
`peak_risk_score` columns remain on the table (dropping them needs a
migration) but nothing writes them.

Design rules:
  - This service ONLY writes to trading_sessions.
  - It NEVER reads or writes trades, positions, P&L, or alerts.
  - Callers pass in all context — service is stateless.
  - All methods are async and expect a SQLAlchemy AsyncSession.
"""

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trading_session import TradingSession
from app.core.market_hours import get_session_boundaries, MarketSegment

logger = logging.getLogger(__name__)

#: Postgres SQLSTATE for a unique-constraint violation. The ONLY error that
#: means "someone else created this session first".
_UNIQUE_VIOLATION = "23505"


def _is_duplicate(err: Exception) -> bool:
    """
    True only for a genuine unique-constraint violation.

    A foreign-key violation is also an IntegrityError and is emphatically not a
    race — it means the caller handed us an account that does not exist, and
    swallowing it would hide a real bug.
    """
    orig = getattr(err, "orig", None)
    code = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
    if code:
        return str(code) == _UNIQUE_VIOLATION
    # No SQLSTATE (a driver we do not recognise): fall back to the text, and
    # err towards RE-RAISING rather than treating an unknown error as a race.
    return "duplicate key" in str(err).lower()


class TradingSessionService:

    # ------------------------------------------------------------------
    # Core: get or create
    # ------------------------------------------------------------------

    @staticmethod
    async def get_or_create_session(
        broker_account_id: UUID,
        session_date: date,
        db: AsyncSession,
    ) -> TradingSession:
        """
        Return the TradingSession for (account, date), creating it if absent.

        Safe to call concurrently — uses DB UNIQUE constraint as guard.
        On duplicate insert (race), re-fetches the existing row.
        """
        result = await db.execute(
            select(TradingSession).where(
                TradingSession.broker_account_id == broker_account_id,
                TradingSession.session_date == session_date,
            )
        )
        session = result.scalar_one_or_none()
        if session:
            return session

        # Compute market open/close for this date
        try:
            market_open, market_close = get_session_boundaries(
                segment=MarketSegment.FNO,
                for_date=session_date,
            )
        except Exception:
            market_open = market_close = None

        session = TradingSession(
            broker_account_id=broker_account_id,
            session_date=session_date,
            market_open=market_open,
            market_close=market_close,
        )

        # SAVEPOINT, not the whole transaction.
        #
        # This used to be a bare `db.flush()` in a `try`, with `except
        # Exception: await db.rollback()` on the theory that any failure meant
        # another request had inserted the row first. Two things were wrong
        # with that, and both were reproduced:
        #
        #   1. `flush()` flushes EVERYTHING pending on the session, not just
        #      this row. The failure it caught was often nothing to do with
        #      TradingSession.
        #   2. `db.rollback()` discards the CALLER'S transaction. This service
        #      does not own that session. On the engine path it holds the
        #      CompletedTrade being analysed and whatever else the caller had
        #      staged; a statement timeout here silently threw all of it away.
        #      Forcing one flush failure produced a ForeignKeyViolationError on
        #      the NEXT insert, because the broker account had been rolled
        #      back out from under it.
        #
        # A nested transaction confines the damage to a SAVEPOINT: if the
        # insert fails, only the insert is undone and the caller's work
        # survives. Anything that is not a duplicate — a timeout, a dead
        # connection, a foreign-key violation — now propagates as itself
        # instead of being silently reinterpreted as a race.
        try:
            async with db.begin_nested():
                db.add(session)
                await db.flush()
        except IntegrityError as err:
            if not _is_duplicate(err):
                raise                      # not a race; the caller must see it
            # A concurrent insert won. The savepoint is gone, the outer
            # transaction is intact, so re-reading is safe.
            result = await db.execute(
                select(TradingSession).where(
                    TradingSession.broker_account_id == broker_account_id,
                    TradingSession.session_date == session_date,
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                return existing
            raise                          # unique violation on something else

        return session

    # ── Removed 2026-08-23: increment_trade_count and add_session_pnl ──────
    # Both mutated session facts incrementally, and both had ZERO production
    # callers. They are gone rather than dormant because a dormant second writer
    # is an invitation: session_pnl and trade_count now have exactly one owner
    # (behavior_engine._load_context, which derives both from the session's
    # CompletedTrades), and an increment path alongside a derive path is how the
    # two disagree.
    #
    # Deriving is also what makes replay and retries safe - recomputing gives the
    # same answer, incrementing double-counts.

    # ------------------------------------------------------------------
    # Lightweight counters
    # ------------------------------------------------------------------

    @staticmethod
    async def increment_alerts_fired(session_id: UUID, db: AsyncSession, count: int = 1) -> None:
        session = await db.get(TradingSession, session_id)
        if session:
            session.alerts_fired += count
            session.updated_at = datetime.now(timezone.utc)
            await db.flush()

    @staticmethod
    async def consume_alert_budget(
        broker_account_id: UUID,
        session_date: date,
        count: int,
        db: AsyncSession,
    ) -> Optional[int]:
        """
        Add `count` to the day's alert budget and return the total BEFORE it.

        One statement, so it cannot lose an update. `increment_alerts_fired`
        above reads the row into Python, adds, and writes back: two concurrent
        detections on one account both read 5 and both write 6, and the day's
        budget silently under-counts. That is currently masked by the
        per-account Redis lock, which means the correctness of the cap depends
        on a lock that can be bypassed (an unlocked task path exists) and whose
        release is unfenced. Doing the arithmetic in the database removes that
        dependency entirely.

        Keyed by (account, date) rather than by session id because the CALLER
        must supply the date of the session the ALERT belongs to — derived from
        its detected_at, which is the trade's exit time — not whatever day it
        happens to be while the task runs. Those diverge for a postback
        processed after IST midnight and for anything that re-evaluates an
        earlier session, and when they diverge the old code looked up nothing,
        treated the budget as zero, and never incremented it either: the cap
        silently reset.

        Returns None when no session row exists for that date, which the caller
        must treat as "cannot judge the budget" rather than as zero.

        Single-row write against uq_trading_session_account_date, so the cost
        is constant in both users and trades.
        """
        result = await db.execute(
            update(TradingSession)
            .where(
                TradingSession.broker_account_id == broker_account_id,
                TradingSession.session_date == session_date,
            )
            .values(
                alerts_fired=TradingSession.alerts_fired + count,
                updated_at=datetime.now(timezone.utc),
            )
            .returning(TradingSession.alerts_fired)
        )
        row = result.scalar_one_or_none()
        return None if row is None else int(row) - count

    @staticmethod
    async def close_session(
        session_id: UUID,
        closing_equity: Decimal,
        db: AsyncSession,
    ) -> None:
        """
        Record closing equity at end of day.
        Called by EOD report task at 15:32 IST.
        """
        session = await db.get(TradingSession, session_id)
        if session:
            session.closing_equity = closing_equity
            session.updated_at = datetime.now(timezone.utc)
            await db.flush()

    # ------------------------------------------------------------------
    # Today's session helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def get_today_session(
        broker_account_id: UUID,
        db: AsyncSession,
    ) -> Optional[TradingSession]:
        """Return today's IST session if it exists, else None."""
        import pytz
        today_ist = datetime.now(pytz.timezone("Asia/Kolkata")).date()
        result = await db.execute(
            select(TradingSession).where(
                TradingSession.broker_account_id == broker_account_id,
                TradingSession.session_date == today_ist,
            )
        )
        return result.scalar_one_or_none()
