"""
User Profile & Onboarding API Endpoints

Handles user preferences, onboarding wizard, and adaptive settings.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List
from datetime import datetime, timezone
import logging

from app.core.database import get_db
from app.api.deps import get_verified_broker_account_id, get_current_user_id
from app.models.user import User
from app.models.user_profile import UserProfile

router = APIRouter()
logger = logging.getLogger(__name__)


# Request/Response Models
class OnboardingStep1(BaseModel):
    """Basic info step"""
    display_name: Optional[str] = None
    trading_since: Optional[int] = None  # Year


class OnboardingStep2(BaseModel):
    """Trading style quiz"""
    experience_level: str  # beginner, intermediate, experienced, professional
    trading_style: str     # scalper, intraday, swing, positional, mixed
    risk_tolerance: str    # conservative, moderate, aggressive


class OnboardingStep3(BaseModel):
    """Preferences"""
    preferred_instruments: List[str] = []  # ['NIFTY', 'BANKNIFTY', 'STOCKS']
    preferred_segments: List[str] = []     # ['OPTIONS', 'FUTURES', 'EQUITY']
    trading_hours_start: Optional[str] = "09:15"
    trading_hours_end: Optional[str] = "15:30"


class OnboardingStep4(BaseModel):
    """Risk management"""
    daily_loss_limit: Optional[float] = None
    daily_trade_limit: Optional[int] = None
    max_position_size: Optional[float] = None
    cooldown_after_loss: int = 15
    known_weaknesses: List[str] = []  # Self-reported weaknesses


class OnboardingStep5(BaseModel):
    """Notifications & Guardian"""
    push_enabled: bool = True
    whatsapp_enabled: bool = False
    alert_sensitivity: str = "medium"  # low, medium, high
    guardian_enabled: bool = False
    ai_persona: str = "coach"  # coach, mentor, friend, strict


class ProfileUpdate(BaseModel):
    """Full profile update"""
    display_name: Optional[str] = None
    trading_since: Optional[int] = None
    experience_level: Optional[str] = None
    trading_style: Optional[str] = None
    risk_tolerance: Optional[str] = None
    preferred_instruments: Optional[List[str]] = None
    preferred_segments: Optional[List[str]] = None
    trading_hours_start: Optional[str] = None
    trading_hours_end: Optional[str] = None
    daily_loss_limit: Optional[float] = None
    daily_trade_limit: Optional[int] = None
    max_position_size: Optional[float] = None
    cooldown_after_loss: Optional[int] = None
    known_weaknesses: Optional[List[str]] = None
    push_enabled: Optional[bool] = None
    whatsapp_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    alert_sensitivity: Optional[str] = None
    guardian_enabled: Optional[bool] = None
    guardian_alert_threshold: Optional[str] = None
    guardian_daily_summary: Optional[bool] = None
    ai_persona: Optional[str] = None
    guardian_phone: Optional[str] = None
    guardian_name: Optional[str] = None
    eod_report_time: Optional[str] = None    # HH:MM IST, e.g. "16:00"
    morning_brief_time: Optional[str] = None # HH:MM IST, e.g. "08:30"


@router.get("/notification-status")
async def get_notification_status(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
):
    """Check which notification channels are configured on the server."""
    from app.services.whatsapp_service import whatsapp_service
    from app.core.config import settings

    return {
        "whatsapp": {"twilio_configured": whatsapp_service.is_configured},
        "push": {"vapid_configured": bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)},
    }


@router.get("/")
async def get_profile(
    user_id: UUID = Depends(get_current_user_id),
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Get user profile. Creates one if doesn't exist."""
    try:
        result = await db.execute(
            select(UserProfile).where(UserProfile.broker_account_id == broker_account_id)
        )
        profile = result.scalar_one_or_none()

        if not profile:
            profile = UserProfile(broker_account_id=broker_account_id)
            db.add(profile)
            await db.commit()
            await db.refresh(profile)

        # Merge guardian fields from User into profile dict
        profile_dict = profile.to_dict()
        user = await db.get(User, user_id)
        if user:
            profile_dict["guardian_phone"] = user.guardian_phone
            profile_dict["guardian_name"] = user.guardian_name

        return {
            "profile": profile_dict,
            "needs_onboarding": not profile.onboarding_completed
        }

    except Exception as e:
        logger.error(f"Failed to get profile: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/onboarding-status")
async def get_onboarding_status(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Check if onboarding is complete."""
    try:
        result = await db.execute(
            select(UserProfile).where(UserProfile.broker_account_id == broker_account_id)
        )
        profile = result.scalar_one_or_none()

        if not profile:
            return {
                "completed": False,
                "current_step": 0,
                "total_steps": 5
            }

        return {
            "completed": profile.onboarding_completed,
            "current_step": profile.onboarding_step,
            "total_steps": 5
        }

    except Exception as e:
        logger.error(f"Failed to get onboarding status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/onboarding/step1")
async def onboarding_step1(
    data: OnboardingStep1,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Complete onboarding step 1: Basic info"""
    try:
        profile = await _get_or_create_profile(broker_account_id, db)

        if data.display_name:
            profile.display_name = data.display_name
        if data.trading_since:
            profile.trading_since = data.trading_since

        profile.onboarding_step = max(profile.onboarding_step, 1)
        await db.commit()

        return {"success": True, "step": 1, "next_step": 2}

    except Exception as e:
        logger.error(f"Onboarding step 1 failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/onboarding/step2")
async def onboarding_step2(
    data: OnboardingStep2,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Complete onboarding step 2: Trading style quiz"""
    try:
        profile = await _get_or_create_profile(broker_account_id, db)

        profile.experience_level = data.experience_level
        profile.trading_style = data.trading_style
        profile.risk_tolerance = data.risk_tolerance
        profile.onboarding_step = max(profile.onboarding_step, 2)

        await db.commit()

        return {"success": True, "step": 2, "next_step": 3}

    except Exception as e:
        logger.error(f"Onboarding step 2 failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/onboarding/step3")
async def onboarding_step3(
    data: OnboardingStep3,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Complete onboarding step 3: Preferences"""
    try:
        profile = await _get_or_create_profile(broker_account_id, db)

        profile.preferred_instruments = data.preferred_instruments
        profile.preferred_segments = data.preferred_segments
        profile.trading_hours_start = data.trading_hours_start
        profile.trading_hours_end = data.trading_hours_end
        profile.onboarding_step = max(profile.onboarding_step, 3)

        await db.commit()

        return {"success": True, "step": 3, "next_step": 4}

    except Exception as e:
        logger.error(f"Onboarding step 3 failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/onboarding/step4")
async def onboarding_step4(
    data: OnboardingStep4,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Complete onboarding step 4: Risk management"""
    try:
        profile = await _get_or_create_profile(broker_account_id, db)

        profile.daily_loss_limit = data.daily_loss_limit
        profile.daily_trade_limit = data.daily_trade_limit
        profile.max_position_size = data.max_position_size
        profile.cooldown_after_loss = data.cooldown_after_loss
        profile.known_weaknesses = data.known_weaknesses
        profile.onboarding_step = max(profile.onboarding_step, 4)

        await db.commit()

        return {"success": True, "step": 4, "next_step": 5}

    except Exception as e:
        logger.error(f"Onboarding step 4 failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/onboarding/step5")
async def onboarding_step5(
    data: OnboardingStep5,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Complete onboarding step 5: Notifications & complete"""
    try:
        profile = await _get_or_create_profile(broker_account_id, db)

        profile.push_enabled = data.push_enabled
        profile.whatsapp_enabled = data.whatsapp_enabled
        profile.alert_sensitivity = data.alert_sensitivity
        profile.guardian_enabled = data.guardian_enabled
        profile.ai_persona = data.ai_persona
        profile.onboarding_step = 5
        profile.onboarding_completed = True

        await db.commit()

        return {
            "success": True,
            "step": 5,
            "completed": True,
            "profile": profile.to_dict()
        }

    except Exception as e:
        logger.error(f"Onboarding step 5 failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/onboarding/skip")
async def skip_onboarding(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Skip onboarding and use defaults."""
    try:
        profile = await _get_or_create_profile(broker_account_id, db)

        profile.onboarding_completed = True
        profile.onboarding_step = 5

        await db.commit()

        return {
            "success": True,
            "skipped": True,
            "profile": profile.to_dict()
        }

    except Exception as e:
        logger.error(f"Skip onboarding failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/")
async def update_profile(
    data: ProfileUpdate,
    user_id: UUID = Depends(get_current_user_id),
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Update user profile."""
    try:
        profile = await _get_or_create_profile(broker_account_id, db)

        update_data = data.dict(exclude_unset=True)

        # Guardian fields live on User, not UserProfile
        guardian_phone = update_data.pop('guardian_phone', None)
        guardian_name = update_data.pop('guardian_name', None)

        if guardian_phone is not None or guardian_name is not None:
            user = await db.get(User, user_id)
            if user:
                if guardian_phone is not None:
                    user.guardian_phone = guardian_phone
                if guardian_name is not None:
                    user.guardian_name = guardian_name

        for field, value in update_data.items():
            if hasattr(profile, field) and value is not None:
                setattr(profile, field, value)

        profile.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(profile)

        # Return profile dict merged with guardian fields
        profile_dict = profile.to_dict()
        user = await db.get(User, user_id)
        if user:
            profile_dict["guardian_phone"] = user.guardian_phone
            profile_dict["guardian_name"] = user.guardian_name

        return {"success": True, "profile": profile_dict}

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Profile update failed: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/detect-style")
async def detect_trading_style(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Auto-detect trading style from trade history.
    Updates profile with detected patterns.
    """
    from app.models.trade import Trade
    from sqlalchemy import and_
    from datetime import timedelta

    try:
        # Get trades from last 30 days
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        result = await db.execute(
            select(Trade).where(
                and_(
                    Trade.broker_account_id == broker_account_id,
                    Trade.status == "COMPLETE",
                    Trade.order_timestamp >= cutoff
                )
            ).order_by(Trade.order_timestamp)
        )
        trades = result.scalars().all()

        if len(trades) < 5:
            return {
                "detected": False,
                "reason": "Not enough trade history (need at least 5 trades)"
            }

        # Analyze patterns
        detected = {
            "trading_style": "intraday",
            "experience_level": "intermediate",
            "risk_tolerance": "moderate",
            "patterns": {}
        }

        # Count trades per day
        trades_by_day = {}
        for trade in trades:
            day = trade.order_timestamp.date()
            trades_by_day[day] = trades_by_day.get(day, 0) + 1

        avg_trades_per_day = sum(trades_by_day.values()) / len(trades_by_day) if trades_by_day else 0

        # Detect style based on frequency
        if avg_trades_per_day > 10:
            detected["trading_style"] = "scalper"
        elif avg_trades_per_day > 3:
            detected["trading_style"] = "intraday"
        elif avg_trades_per_day > 1:
            detected["trading_style"] = "swing"
        else:
            detected["trading_style"] = "positional"

        detected["patterns"]["avg_trades_per_day"] = round(avg_trades_per_day, 1)
        detected["patterns"]["total_trades"] = len(trades)
        detected["patterns"]["active_days"] = len(trades_by_day)

        # Update profile
        profile = await _get_or_create_profile(broker_account_id, db)
        profile.trading_style = detected["trading_style"]
        profile.detected_patterns = detected["patterns"]

        await db.commit()

        return {
            "detected": True,
            "style": detected,
            "profile": profile.to_dict()
        }

    except Exception as e:
        logger.error(f"Style detection failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/guardian/test")
async def send_guardian_test_message(
    user_id: UUID = Depends(get_current_user_id),
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Send a test message to both the guardian (WhatsApp) and the user (push + WhatsApp if configured).
    Also generates and sends a mini analytics report to both.
    No cooldown/escalation — purely for verification.
    """
    from app.services.whatsapp_service import whatsapp_service
    from app.services.push_notification_service import push_service
    from app.models.trade import Trade
    from sqlalchemy import and_
    from datetime import timedelta

    # Load user for guardian contact info
    user = await db.get(User, user_id)
    guardian_phone = user.guardian_phone if user else None
    user_phone = None  # user's own WhatsApp — not stored separately yet

    results = {
        "guardian_whatsapp": None,
        "user_push": None,
        "analytics_report": None,
    }

    # ── 1. Build mini analytics report ─────────────────────────────────────
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    trade_result = await db.execute(
        select(Trade).where(
            and_(
                Trade.broker_account_id == broker_account_id,
                Trade.status == "COMPLETE",
                Trade.order_timestamp >= cutoff
            )
        )
    )
    trades = trade_result.scalars().all()

    trade_count = len(trades)
    total_pnl = sum((t.pnl or 0) for t in trades)
    wins = sum(1 for t in trades if (t.pnl or 0) > 0)
    win_rate = round((wins / trade_count * 100), 1) if trade_count > 0 else 0

    analytics_summary = (
        f"📊 TradeMentor Analytics Report (Last 7 Days)\n\n"
        f"Trades: {trade_count}\n"
        f"Win Rate: {win_rate}%\n"
        f"Net P&L: ₹{total_pnl:,.2f}\n\n"
        f"This is a test report sent to verify your notification setup.\n"
        f"Real reports are sent automatically after market close.\n\n"
        f"- TradeMentor AI"
    )

    push_report_body = (
        f"Last 7 days: {trade_count} trades, {win_rate}% win rate, "
        f"₹{total_pnl:,.2f} P&L. Test report generated successfully."
    )

    # ── 2. Send WhatsApp to guardian ────────────────────────────────────────
    if whatsapp_service.is_configured and guardian_phone:
        try:
            guardian_test_msg = (
                "TradeMentor Guardian — Test Alert\n\n"
                "This confirms you are set up as a trading guardian. "
                "You will receive alerts when risky patterns are detected.\n\n"
                + analytics_summary
            )
            success = await whatsapp_service.send_message(
                to_number=guardian_phone,
                content=guardian_test_msg
            )
            results["guardian_whatsapp"] = "sent" if success else "failed"
        except Exception as e:
            logger.error(f"Guardian WhatsApp test failed: {e}")
            results["guardian_whatsapp"] = "failed"
    elif not whatsapp_service.is_configured:
        results["guardian_whatsapp"] = "skipped — Twilio not configured"
    else:
        results["guardian_whatsapp"] = "skipped — no guardian phone set"

    # ── 3. Send WhatsApp to user (if user_phone stored) ─────────────────────
    if whatsapp_service.is_configured and user_phone:
        try:
            user_test_msg = (
                "TradeMentor — Test Alert\n\n"
                "Your notification setup is working correctly.\n\n"
                + analytics_summary
            )
            await whatsapp_service.send_message(to_number=user_phone, content=user_test_msg)
        except Exception as e:
            logger.error(f"User WhatsApp test failed: {e}")

    # ── 4. Send push notification to user's devices ──────────────────────────
    try:
        push_result = await push_service.send_notification(
            broker_account_id=broker_account_id,
            title="📊 Test Analytics Report",
            body=push_report_body,
            db=db,
            severity="info",
            tag="test-analytics-report"
        )
        sent = push_result.get("sent", 0)
        results["user_push"] = f"sent to {sent} device(s)" if sent > 0 else "no active push subscriptions"
    except Exception as e:
        logger.error(f"Push notification test failed: {e}")
        results["user_push"] = "failed"

    results["analytics_report"] = "generated"

    # Determine overall success
    any_success = (
        results["guardian_whatsapp"] == "sent"
        or "sent to" in (results["user_push"] or "")
    )

    if not any_success and not whatsapp_service.is_configured:
        raise HTTPException(
            status_code=503,
            detail="WhatsApp not available — Twilio credentials not configured on server"
        )

    return {
        "success": True,
        "results": results,
        "message": "Test messages and analytics report dispatched"
    }


async def _get_or_create_profile(broker_account_id: UUID, db: AsyncSession) -> UserProfile:
    """Helper to get or create a user profile."""
    result = await db.execute(
        select(UserProfile).where(UserProfile.broker_account_id == broker_account_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        profile = UserProfile(broker_account_id=broker_account_id)
        db.add(profile)
        await db.flush()

    return profile
