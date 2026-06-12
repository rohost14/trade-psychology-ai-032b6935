"""
Morning Intent + EOD Comparison Push Notifications

send_morning_intent_push  — fires at 08:30 IST Mon–Fri
send_eod_comparison_push  — fires at 15:35 IST Mon–Fri (after market close)
"""

import asyncio
import logging
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select, and_, func
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.broker_account import BrokerAccount
from app.models.user_profile import UserProfile
from app.models.trading_session import TradingSession
from app.services.push_notification_service import push_service

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


def _today_ist() -> date:
    return datetime.now(IST).date()


def _fmt_inr(amount: float) -> str:
    return f"₹{abs(amount):,.0f}"


@celery_app.task(name="app.tasks.intent_tasks.send_morning_intent_push", bind=True, max_retries=1)
def send_morning_intent_push(self):
    """
    08:30 IST: intent reminder push to accounts with limits configured.
    """
    async def _run():
        today = _today_ist()
        async with SessionLocal() as db:
            rows = (await db.execute(
                select(BrokerAccount, UserProfile)
                .outerjoin(UserProfile, BrokerAccount.id == UserProfile.broker_account_id)
                .where(
                    and_(
                        BrokerAccount.access_token.isnot(None),
                        BrokerAccount.is_active == True,
                    )
                )
            )).all()

            for account, profile in rows:
                try:
                    max_trades = profile.daily_trade_limit if profile else None
                    max_loss   = float(profile.daily_loss_limit) if profile and profile.daily_loss_limit else None

                    if max_trades is None and max_loss is None:
                        continue

                    parts = []
                    if max_trades:
                        parts.append(f"max {max_trades} trades")
                    if max_loss:
                        parts.append(f"{_fmt_inr(max_loss)} loss limit")

                    rules = " · ".join(parts)
                    body = f"Market opens in 45 min. Your rules: {rules}. Ready to commit?"

                    # Append danger-day context if today is a historically bad day
                    try:
                        from app.services.ai_personalization_service import ai_personalization_service
                        ins = await ai_personalization_service.get_personalized_insights(account.id, db)
                        if ins.get("has_data"):
                            today_name = datetime.now(IST).strftime("%A")
                            if today_name in (ins.get("danger_days") or []):
                                body += f" ⚠️ {today_name} is your worst trading day historically — trade smaller."
                    except Exception:
                        pass  # Non-critical — push still goes without danger-day context

                    await push_service.send_notification(
                        broker_account_id=account.id,
                        title="TradeMentor — Pre-Market Intent",
                        body=body,
                        db=db,
                        data={"action": "open_dashboard", "type": "morning_intent"},
                        severity="info",
                        tag="morning-intent",
                    )
                except Exception as e:
                    logger.warning(f"Morning intent push failed for {account.id}: {e}")

    asyncio.run(_run())


@celery_app.task(name="app.tasks.intent_tasks.send_eod_comparison_push", bind=True, max_retries=1)
def send_eod_comparison_push(self):
    """
    15:35 IST: EOD comparison for accounts that acknowledged intent today.
    """
    async def _run():
        today = _today_ist()
        async with SessionLocal() as db:
            rows = (await db.execute(
                select(BrokerAccount, TradingSession, UserProfile)
                .join(TradingSession, and_(
                    TradingSession.broker_account_id == BrokerAccount.id,
                    TradingSession.session_date == today,
                    TradingSession.intent_acknowledged == True,
                ))
                .outerjoin(UserProfile, BrokerAccount.id == UserProfile.broker_account_id)
                .where(BrokerAccount.access_token.isnot(None))
            )).all()

            for account, session, profile in rows:
                try:
                    eff_max_trades = (
                        session.intent_max_trades if session.intent_max_trades is not None
                        else (profile.daily_trade_limit if profile else None)
                    )
                    eff_max_loss = (
                        float(session.intent_max_loss) if session.intent_max_loss is not None
                        else (float(profile.daily_loss_limit) if profile and profile.daily_loss_limit else None)
                    )

                    actual_trades = session.trade_count or 0
                    actual_pnl    = float(session.session_pnl) if session.session_pnl else 0.0

                    lines = []
                    if eff_max_trades:
                        over = actual_trades - eff_max_trades
                        lines.append(
                            f"Trades: {actual_trades}/{eff_max_trades} ✓"
                            if over <= 0
                            else f"Trades: {actual_trades} taken, {eff_max_trades} planned (+{over} over)"
                        )
                    if eff_max_loss:
                        loss = -actual_pnl
                        lines.append(
                            f"Loss limit respected ✓ P&L {'+' if actual_pnl >= 0 else ''}{_fmt_inr(actual_pnl)}"
                            if loss <= eff_max_loss
                            else f"Loss: {_fmt_inr(loss)} vs {_fmt_inr(eff_max_loss)} limit"
                        )

                    if not lines:
                        continue

                    trades_ok = eff_max_trades is None or actual_trades <= eff_max_trades
                    loss_ok   = eff_max_loss   is None or actual_pnl    >= -eff_max_loss
                    respected = trades_ok and loss_ok

                    await push_service.send_notification(
                        broker_account_id=account.id,
                        title="TradeMentor — Session Closed ✓" if respected else "TradeMentor — Session Review",
                        body=" | ".join(lines),
                        db=db,
                        data={"action": "open_dashboard", "type": "eod_comparison"},
                        severity="info" if respected else "caution",
                        tag="eod-comparison",
                    )
                except Exception as e:
                    logger.warning(f"EOD comparison push failed for {account.id}: {e}")

    asyncio.run(_run())


@celery_app.task(name="app.tasks.intent_tasks.send_daily_score_push", bind=True, max_retries=1)
def send_daily_score_push(self):
    """
    18:00 IST daily: discipline score + streak push.
    Pulls users back into the app with a single personalized number.
    """
    async def _run():
        today = _today_ist()
        async with SessionLocal() as db:
            rows = (await db.execute(
                select(BrokerAccount, TradingSession)
                .outerjoin(TradingSession, and_(
                    TradingSession.broker_account_id == BrokerAccount.id,
                    TradingSession.session_date == today,
                ))
                .where(BrokerAccount.access_token.isnot(None))
            )).all()

            for account, session in rows:
                try:
                    # Only send if they traded today
                    if not session or (session.trade_count or 0) == 0:
                        continue

                    # Fetch discipline score from analytics service
                    from app.services.analytics_service import AnalyticsService
                    analytics = AnalyticsService()
                    score_data = await analytics.calculate_weekly_risk_score(
                        account.id, db
                    )
                    score = score_data.get("score", 0)
                    grade = score_data.get("grade", "")

                    # Calculate intent adherence streak (days within limits)
                    streak = await _calc_adherence_streak(account.id, db)

                    # Build push body
                    parts = [f"Discipline: {score}/100 {grade}"]
                    if streak > 1:
                        parts.append(f"Streak: {streak} days")

                    actual_trades = session.trade_count or 0
                    parts.append(f"{actual_trades} trades today")

                    await push_service.send_notification(
                        broker_account_id=account.id,
                        title="TradeMentor — Today's Score",
                        body=" · ".join(parts),
                        db=db,
                        data={"action": "open_my_patterns", "type": "daily_score"},
                        severity="info",
                        tag="daily-score",
                    )
                except Exception as e:
                    logger.warning(f"Daily score push failed for {account.id}: {e}")

    asyncio.run(_run())


async def _calc_adherence_streak(broker_account_id, db) -> int:
    """Count consecutive days where intent was acknowledged AND respected."""
    result = await db.execute(
        select(TradingSession)
        .where(
            and_(
                TradingSession.broker_account_id == broker_account_id,
                TradingSession.intent_acknowledged == True,
            )
        )
        .order_by(TradingSession.session_date.desc())
        .limit(30)
    )
    sessions = result.scalars().all()

    streak = 0
    prev_date = None
    for s in sessions:
        # Check if respected (within limits)
        respected = True
        if s.intent_max_trades is not None and (s.trade_count or 0) > s.intent_max_trades:
            respected = False
        if s.intent_max_loss is not None and (s.session_pnl or 0) < -s.intent_max_loss:
            respected = False

        if not respected:
            break

        # Check consecutive (skip weekends)
        if prev_date is not None:
            delta = (prev_date - s.session_date).days
            if delta > 3:  # allow weekend gap
                break

        streak += 1
        prev_date = s.session_date

    return streak


@celery_app.task(name="app.tasks.intent_tasks.refresh_personalization_patterns", bind=True, max_retries=1)
def refresh_personalization_patterns(self):
    """
    18:15 IST daily: re-learn behavioral patterns for all active accounts.
    Populates UserProfile.detected_patterns so PredictiveContextStrip has real data.
    Runs 15 min after daily score push (18:00) to avoid DB contention.
    """
    async def _run():
        from app.services.ai_personalization_service import ai_personalization_service
        async with SessionLocal() as db:
            rows = (await db.execute(
                select(BrokerAccount).where(
                    and_(
                        BrokerAccount.access_token.isnot(None),
                        BrokerAccount.is_active == True,
                    )
                )
            )).scalars().all()

            for account in rows:
                try:
                    result = await ai_personalization_service.learn_patterns(
                        broker_account_id=account.id,
                        db=db,
                        days_back=90,
                    )
                    if result.get("insufficient_data"):
                        logger.debug(f"[Personalization] {account.id}: insufficient data ({result.get('trades_analyzed', 0)} trades)")
                    else:
                        logger.info(f"[Personalization] {account.id}: patterns refreshed ({result.get('trades_analyzed', 0)} trades)")
                except Exception as e:
                    logger.warning(f"[Personalization] pattern refresh failed for {account.id}: {e}")

    asyncio.run(_run())
