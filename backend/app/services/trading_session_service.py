"""
TradingSessionService

Manages one TradingSession row per (broker_account, trading_day).

Responsibilities:
  - get_or_create_session: idempotent, safe to call multiple times per day
  - update_risk_score: accumulates risk score, tracks peak, advances state
  - increment_trade_count / increment_alerts_fired: lightweight counters
  - close_session: records closing equity at end of day

Risk score state transitions:
  0-39  → normal
  40-69 → caution
  70-89 → danger
  90+   → blowup

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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trading_session import TradingSession
from app.core.market_hours import get_session_boundaries, MarketSegment

logger = logging.getLogger(__name__)

# Risk score → session state thresholds
_STATE_THRESHOLDS = [
    (Decimal("90"), "blowup"),
    (Decimal("70"), "danger"),
    (Decimal("40"), "caution"),
    (Decimal("0"),  "normal"),
]


def _state_for_score(score: Decimal) -> str:
    """Return session_state string for a given risk score."""
    for threshold, state in _STATE_THRESHOLDS:
        if score >= threshold:
            return state
    return "normal"


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
        db.add(session)

        try:
            await db.flush()
        except Exception:
            # Race condition: another request already inserted this row.
            await db.rollback()
            result = await db.execute(
                select(TradingSession).where(
                    TradingSession.broker_account_id == broker_account_id,
                    TradingSession.session_date == session_date,
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                return existing
            raise  # Unexpected error — re-raise

        return session

    # ------------------------------------------------------------------
    # Risk score management
    # ------------------------------------------------------------------

    @staticmethod
    async def update_risk_score(
        session_id: UUID,
        delta: Decimal,
        db: AsyncSession,
    ) -> TradingSession:
        """
        Add delta to the session risk score.

        Score is clamped to [0, 100].
        peak_risk_score is updated if the new score exceeds it.
        session_state advances automatically based on thresholds.

        delta can be negative (risk reducing events).
        Returns the updated TradingSession.
        """
        session = await db.get(TradingSession, session_id)
        if not session:
            raise ValueError(f"TradingSession {session_id} not found")

        new_score = max(Decimal("0"), min(Decimal("100"), session.risk_score + delta))
        session.risk_score = new_score

        if new_score > session.peak_risk_score:
            session.peak_risk_score = new_score

        new_state = _state_for_score(new_score)
        if new_state != session.session_state:
            logger.info(
                f"[session:{session_id}] state {session.session_state} → {new_state} "
                f"(score: {session.risk_score} → {new_score})"
            )
            session.session_state = new_state

        session.updated_at = datetime.now(timezone.utc)
        await db.flush()
        return session

    # ------------------------------------------------------------------
    # Lightweight counters
    # ------------------------------------------------------------------

    @staticmethod
    async def increment_trade_count(session_id: UUID, db: AsyncSession) -> None:
        session = await db.get(TradingSession, session_id)
        if session:
            session.trade_count += 1
            session.updated_at = datetime.now(timezone.utc)
            await db.flush()

    @staticmethod
    async def increment_alerts_fired(session_id: UUID, db: AsyncSession) -> None:
        session = await db.get(TradingSession, session_id)
        if session:
            session.alerts_fired += 1
            session.updated_at = datetime.now(timezone.utc)
            await db.flush()

    @staticmethod
    async def add_session_pnl(
        session_id: UUID,
        pnl_delta: Decimal,
        db: AsyncSession,
    ) -> None:
        """Add realized P&L from a trade to the session total."""
        session = await db.get(TradingSession, session_id)
        if session:
            session.session_pnl = (session.session_pnl or Decimal("0")) + pnl_delta
            session.updated_at = datetime.now(timezone.utc)
            await db.flush()

    # ------------------------------------------------------------------
    # Session close
    # ------------------------------------------------------------------

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
