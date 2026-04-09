"""
Cooldown & Pre-Trade Intervention API

Manages cooling-off periods and pre-trade checks.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List
from datetime import datetime, timedelta, timezone
import logging

from app.core.database import get_db
from app.api.deps import get_verified_broker_account_id
from app.models.cooldown import Cooldown, create_cooldown
from app.models.trade import Trade
from app.models.risk_alert import RiskAlert
from app.models.user_profile import UserProfile
from app.services.ai_personalization_service import ai_personalization_service

router = APIRouter()
logger = logging.getLogger(__name__)


class CooldownCreate(BaseModel):
    reason: str = "manual"
    duration_minutes: int = 15
    message: Optional[str] = None


class PreTradeCheckRequest(BaseModel):
    symbol: Optional[str] = None
    quantity: Optional[int] = None
    direction: Optional[str] = None  # BUY/SELL
    order_value: Optional[float] = None


class PreTradeCheckResponse(BaseModel):
    action: str  # 'allow', 'warn', 'cooldown'
    reasons: List[str]
    recommendations: List[str]
    cooldown: Optional[dict] = None
    patterns_detected: List[str]
    risk_level: str  # 'low', 'medium', 'high'


@router.get("/active")
async def get_active_cooldown(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Get currently active cooldown, if any."""
    try:
        now = datetime.now(timezone.utc)

        result = await db.execute(
            select(Cooldown).where(
                and_(
                    Cooldown.broker_account_id == broker_account_id,
                    Cooldown.expires_at > now,
                    Cooldown.skipped == False
                )
            ).order_by(Cooldown.expires_at.desc())
        )
        cooldown = result.scalar_one_or_none()

        if cooldown:
            return {
                "active": True,
                "cooldown": cooldown.to_dict()
            }
        else:
            return {
                "active": False,
                "cooldown": None
            }

    except Exception as e:
        logger.error(f"Failed to get active cooldown: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/history")
async def get_cooldown_history(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Get cooldown history."""
    try:
        result = await db.execute(
            select(Cooldown).where(
                Cooldown.broker_account_id == broker_account_id
            ).order_by(Cooldown.created_at.desc()).limit(limit)
        )
        cooldowns = result.scalars().all()

        return {
            "cooldowns": [c.to_dict() for c in cooldowns],
            "total": len(cooldowns)
        }

    except Exception as e:
        logger.error(f"Failed to get cooldown history: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/start")
async def start_cooldown(
    data: CooldownCreate,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Manually start a cooldown period."""
    try:
        cooldown = create_cooldown(
            broker_account_id=broker_account_id,
            reason=data.reason,
            duration_minutes=data.duration_minutes,
            message=data.message,
            can_skip=True
        )

        db.add(cooldown)
        await db.commit()
        await db.refresh(cooldown)

        logger.info(f"Cooldown started for {broker_account_id}: {data.reason} ({data.duration_minutes}min)")

        return {
            "success": True,
            "cooldown": cooldown.to_dict()
        }

    except Exception as e:
        logger.error(f"Failed to start cooldown: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{cooldown_id}/skip")
async def skip_cooldown(
    cooldown_id: str,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Skip a cooldown (if allowed). Only the owning account can skip."""
    try:
        result = await db.execute(
            select(Cooldown).where(
                Cooldown.id == UUID(cooldown_id),
                Cooldown.broker_account_id == broker_account_id
            )
        )
        cooldown = result.scalar_one_or_none()

        if not cooldown:
            raise HTTPException(status_code=404, detail="Cooldown not found")

        if not cooldown.can_skip:
            raise HTTPException(status_code=400, detail="This cooldown cannot be skipped")

        cooldown.skipped = True
        cooldown.skipped_at = datetime.now(timezone.utc)

        await db.commit()

        logger.info(f"Cooldown {cooldown_id} skipped")

        return {"success": True, "skipped": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to skip cooldown: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{cooldown_id}/acknowledge")
async def acknowledge_cooldown(
    cooldown_id: str,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Acknowledge seeing a cooldown. Only the owning account can acknowledge."""
    try:
        result = await db.execute(
            select(Cooldown).where(
                Cooldown.id == UUID(cooldown_id),
                Cooldown.broker_account_id == broker_account_id
            )
        )
        cooldown = result.scalar_one_or_none()

        if not cooldown:
            raise HTTPException(status_code=404, detail="Cooldown not found")

        cooldown.acknowledged = True
        cooldown.acknowledged_at = datetime.now(timezone.utc)

        await db.commit()

        return {"success": True, "acknowledged": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to acknowledge cooldown: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/pre-trade-check")
async def pre_trade_check(
    data: PreTradeCheckRequest,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Pre-trade intervention check.

    Call this BEFORE placing a trade to check:
    - Active cooldowns
    - Recent patterns detected
    - Risk limits
    - Trading behavior

    Returns recommendation: allow, warn, or suggest cooldown
    """
    try:
        now = datetime.now(timezone.utc)

        action = "allow"
        reasons = []
        recommendations = []
        patterns_detected = []
        risk_level = "low"
        cooldown_data = None

        # 1. Check active cooldown
        cooldown_result = await db.execute(
            select(Cooldown).where(
                and_(
                    Cooldown.broker_account_id == broker_account_id,
                    Cooldown.expires_at > now,
                    Cooldown.skipped == False
                )
            )
        )
        active_cooldown = cooldown_result.scalar_one_or_none()

        if active_cooldown:
            action = "cooldown"
            reasons.append(f"Active cooldown: {active_cooldown.reason}")
            recommendations.append(f"Wait {active_cooldown.remaining_minutes} more minutes")
            cooldown_data = active_cooldown.to_dict()
            risk_level = "high"

        # 2. Check recent alerts (last 30 minutes)
        alert_cutoff = now - timedelta(minutes=30)
        alert_result = await db.execute(
            select(RiskAlert).where(
                and_(
                    RiskAlert.broker_account_id == broker_account_id,
                    RiskAlert.detected_at >= alert_cutoff
                )
            )
        )
        recent_alerts = alert_result.scalars().all()

        danger_alerts = [a for a in recent_alerts if a.severity == "danger"]
        caution_alerts = [a for a in recent_alerts if a.severity == "caution"]

        if danger_alerts:
            if action != "cooldown":
                action = "warn"
            patterns_detected.extend([a.pattern_type for a in danger_alerts])
            reasons.append(f"Recent danger pattern: {danger_alerts[0].pattern_type}")
            risk_level = "high"

        if caution_alerts and action == "allow":
            action = "warn"
            patterns_detected.extend([a.pattern_type for a in caution_alerts])
            reasons.append(f"Recent caution pattern: {caution_alerts[0].pattern_type}")
            if risk_level == "low":
                risk_level = "medium"

        # 3. Check recent trades (overtrading, revenge patterns)
        trade_cutoff = now - timedelta(minutes=15)
        trade_result = await db.execute(
            select(Trade).where(
                and_(
                    Trade.broker_account_id == broker_account_id,
                    Trade.status == "COMPLETE",
                    Trade.order_timestamp >= trade_cutoff
                )
            ).order_by(Trade.order_timestamp.desc())
        )
        recent_trades = trade_result.scalars().all()

        # Check overtrading
        if len(recent_trades) >= 5:
            if action == "allow":
                action = "warn"
            patterns_detected.append("overtrading")
            reasons.append(f"{len(recent_trades)} trades in last 15 minutes")
            recommendations.append("Consider slowing down")
            risk_level = "medium" if risk_level == "low" else risk_level

        # Check consecutive losses
        loss_count = 0
        for trade in recent_trades[:5]:
            if trade.pnl and trade.pnl < 0:
                loss_count += 1
            else:
                break

        if loss_count >= 3:
            if action == "allow":
                action = "warn"
            patterns_detected.append("consecutive_loss")
            reasons.append(f"{loss_count} consecutive losses")
            recommendations.append("Take a break before next trade")
            risk_level = "high"

        # Check revenge trading (large trade after loss)
        if recent_trades and data.order_value:
            last_trade = recent_trades[0]
            if last_trade.pnl and last_trade.pnl < 0:
                last_value = (last_trade.average_price or 0) * (last_trade.filled_quantity or 0)
                if last_value > 0 and data.order_value > last_value * 1.5:
                    if action == "allow":
                        action = "warn"
                    patterns_detected.append("revenge_sizing")
                    reasons.append("Increased position size after loss")
                    recommendations.append("Consider keeping position size consistent")
                    risk_level = "high"

        # 4. Check user-defined limits
        profile_result = await db.execute(
            select(UserProfile).where(UserProfile.broker_account_id == broker_account_id)
        )
        profile = profile_result.scalar_one_or_none()

        if profile:
            # Daily trade limit
            if profile.daily_trade_limit:
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                today_trades_result = await db.execute(
                    select(Trade).where(
                        and_(
                            Trade.broker_account_id == broker_account_id,
                            Trade.status == "COMPLETE",
                            Trade.order_timestamp >= today_start
                        )
                    )
                )
                today_trades = today_trades_result.scalars().all()

                if len(today_trades) >= profile.daily_trade_limit:
                    action = "warn"
                    reasons.append(f"Daily trade limit reached ({profile.daily_trade_limit})")
                    recommendations.append("Consider stopping for today")
                    risk_level = "medium" if risk_level == "low" else risk_level

            # Max position size
            if profile.max_position_size and data.order_value:
                if data.order_value > profile.max_position_size:
                    action = "warn"
                    reasons.append(f"Position size exceeds your limit of ₹{profile.max_position_size:,.0f}")
                    recommendations.append("Consider reducing position size")

        # 5. Check personalized predictive alerts (learned patterns)
        predictive_alert = None
        try:
            predictive_alert = await ai_personalization_service.get_predictive_alert(
                broker_account_id=broker_account_id,
                db=db,
                context={
                    "current_time": now,
                    "proposed_symbol": data.symbol
                }
            )
        except Exception as e:
            logger.warning(f"Predictive alert check failed: {e}")

        if predictive_alert:
            if action == "allow":
                action = "warn"
            reasons.append(predictive_alert.get("message", "Personal pattern warning"))
            patterns_detected.append(f"personal_{predictive_alert.get('type', 'warning')}")

            if predictive_alert.get("severity") == "danger":
                risk_level = "high"
            elif risk_level == "low":
                risk_level = "medium"

        # 6. Build recommendations
        if not recommendations:
            if action == "allow":
                recommendations.append("No concerns detected. Trade mindfully.")
            else:
                recommendations.append("Review the patterns above before proceeding.")

        patterns_detected = list(set(patterns_detected))  # Dedupe

        return {
            "action": action,
            "reasons": reasons,
            "recommendations": recommendations,
            "cooldown": cooldown_data,
            "patterns_detected": patterns_detected,
            "risk_level": risk_level,
            "predictive_alert": predictive_alert
        }

    except Exception as e:
        logger.error(f"Pre-trade check failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
