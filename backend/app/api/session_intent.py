"""
Session Intent API

POST /api/session-intent/acknowledge  — commit to today's plan (pre-market)
GET  /api/session-intent/today        — today's intent + actual vs planned
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal
from typing import Optional
import logging

from app.core.database import get_db
from app.api.deps import get_verified_broker_account_id
from app.models.trading_session import TradingSession
from app.models.user_profile import UserProfile

router = APIRouter()
logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


def _today_ist() -> date:
    return datetime.now(IST).date()


async def _get_or_create_session(
    broker_account_id: UUID,
    session_date: date,
    db: AsyncSession,
) -> TradingSession:
    result = await db.execute(
        select(TradingSession).where(
            and_(
                TradingSession.broker_account_id == broker_account_id,
                TradingSession.session_date == session_date,
            )
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        session = TradingSession(
            broker_account_id=broker_account_id,
            session_date=session_date,
        )
        db.add(session)
        await db.flush()
    return session


async def _get_profile(broker_account_id: UUID, db: AsyncSession) -> Optional[UserProfile]:
    result = await db.execute(
        select(UserProfile).where(UserProfile.broker_account_id == broker_account_id)
    )
    return result.scalar_one_or_none()


class AcknowledgeRequest(BaseModel):
    max_trades: Optional[int]   = Field(None, ge=1)   # None → use profile default
    max_loss:   Optional[float] = Field(None, gt=0)   # None → use profile default


async def _previous_session_summary(
    broker_account_id: UUID,
    today: date,
    profile_max_trades: Optional[int],
    profile_max_loss: Optional[float],
    db: AsyncSession,
) -> Optional[dict]:
    """
    Outcome of the most recent PAST session where the user committed an intent
    (looks back 7 calendar days, so a Monday still sees Friday). Powers the
    morning-intent context line: "yesterday you kept / broke your limits".

    Limitation: when the past session had no per-session override, TODAY's
    profile defaults are used as its limits — exact for overrides, approximate
    if the user changed profile defaults since. Acceptable for a context line.
    """
    result = await db.execute(
        select(TradingSession).where(
            and_(
                TradingSession.broker_account_id == broker_account_id,
                TradingSession.session_date < today,
                TradingSession.session_date >= today - timedelta(days=7),
                TradingSession.intent_acknowledged.is_(True),
            )
        ).order_by(TradingSession.session_date.desc()).limit(1)
    )
    prev = result.scalar_one_or_none()
    if prev is None:
        return None

    prev_max_trades = (
        prev.intent_max_trades if prev.intent_max_trades is not None
        else profile_max_trades
    )
    prev_max_loss = (
        float(prev.intent_max_loss) if prev.intent_max_loss is not None
        else profile_max_loss
    )
    p_trades = prev.trade_count or 0
    p_pnl = float(prev.session_pnl) if prev.session_pnl else 0.0

    trades_ok = prev_max_trades is None or p_trades <= prev_max_trades
    loss_ok   = prev_max_loss   is None or p_pnl    >= -prev_max_loss

    return {
        "session_date": str(prev.session_date),
        "trades": p_trades,
        "pnl": p_pnl,
        "max_trades": prev_max_trades,
        "max_loss": prev_max_loss,
        "trades_ok": trades_ok,
        "loss_ok": loss_ok,
        "respected": trades_ok and loss_ok,
    }


@router.post("/acknowledge")
async def acknowledge_intent(
    body: AcknowledgeRequest,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """
    User commits to today's trading plan.
    Optional overrides for max_trades / max_loss replace the profile defaults
    for today's session only.
    """
    try:
        today = _today_ist()
        session = await _get_or_create_session(broker_account_id, today, db)

        session.intent_acknowledged = True
        session.intent_time = datetime.now(timezone.utc)
        if body.max_trades is not None:
            session.intent_max_trades = body.max_trades
        if body.max_loss is not None:
            session.intent_max_loss = Decimal(str(body.max_loss))

        await db.commit()
        return {"ok": True, "session_date": str(today)}
    except Exception as e:
        logger.error(f"acknowledge_intent failed: {e}")
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/today")
async def get_today_intent(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns today's session intent state + actual metrics for EOD comparison.
    """
    try:
        today = _today_ist()
        profile = await _get_profile(broker_account_id, db)

        result = await db.execute(
            select(TradingSession).where(
                and_(
                    TradingSession.broker_account_id == broker_account_id,
                    TradingSession.session_date == today,
                )
            )
        )
        session = result.scalar_one_or_none()

        # Profile defaults
        profile_max_trades = profile.daily_trade_limit if profile else None
        profile_max_loss   = float(profile.daily_loss_limit) if profile and profile.daily_loss_limit else None

        # Previous committed session — morning-intent context line. Must be
        # available even when today's session row doesn't exist yet (that IS
        # the pre-market state the morning card renders in).
        yesterday = await _previous_session_summary(
            broker_account_id, today, profile_max_trades, profile_max_loss, db
        )

        if not session:
            return {
                "has_session": False,
                "intent_acknowledged": False,
                "session_date": str(today),
                "planned": {
                    "max_trades": profile_max_trades,
                    "max_loss":   profile_max_loss,
                },
                "actual": {
                    "trades": 0,
                    "pnl": 0.0,
                },
                "comparison": None,
                "yesterday": yesterday,
            }

        # Effective limits (session override wins over profile default)
        eff_max_trades = (
            session.intent_max_trades if session.intent_max_trades is not None
            else profile_max_trades
        )
        eff_max_loss = (
            float(session.intent_max_loss) if session.intent_max_loss is not None
            else profile_max_loss
        )

        actual_trades = session.trade_count or 0
        actual_pnl    = float(session.session_pnl) if session.session_pnl else 0.0

        comparison = None
        if session.intent_acknowledged:
            trades_ok = eff_max_trades is None or actual_trades <= eff_max_trades
            loss_ok   = eff_max_loss   is None or actual_pnl    >= -eff_max_loss

            comparison = {
                "trades_ok": trades_ok,
                "loss_ok":   loss_ok,
                "respected": trades_ok and loss_ok,
                "trades_over": max(0, actual_trades - (eff_max_trades or actual_trades)),
                "loss_over":   max(0.0, -actual_pnl - (eff_max_loss or 0)),
            }

        return {
            "has_session": True,
            "intent_acknowledged": session.intent_acknowledged,
            "intent_time": session.intent_time.isoformat() if session.intent_time else None,
            "session_date": str(today),
            "planned": {
                "max_trades": eff_max_trades,
                "max_loss":   eff_max_loss,
            },
            "actual": {
                "trades": actual_trades,
                "pnl":    actual_pnl,
            },
            "comparison": comparison,
            "yesterday": yesterday,
        }
    except Exception as e:
        logger.error(f"get_today_intent failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
