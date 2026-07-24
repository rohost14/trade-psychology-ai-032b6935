"""
Position Guardrail Rules API

User-defined alert rules on open positions.
Rules fire once (WhatsApp + push), never re-arm.
Expire at 15:30 IST on creation day.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from uuid import UUID
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pydantic import BaseModel, validator
from typing import List, Optional, Literal
import logging

from app.core.database import get_db
from app.api.deps import get_verified_broker_account_id
from app.models.guardrail_rule import GuardrailRule

router = APIRouter()
logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


def _next_market_close() -> datetime:
    """Return the next 15:30 IST as UTC datetime (today's, or tomorrow's if already past)."""
    now_ist = datetime.now(IST)
    close_ist = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)
    if now_ist >= close_ist:
        close_ist += timedelta(days=1)
    return close_ist.astimezone(timezone.utc)


def _rule_to_dict(r: GuardrailRule) -> dict:
    now_utc = datetime.now(timezone.utc)
    return {
        "id": str(r.id),
        "name": r.name,
        "target_symbols": r.target_symbols,
        "condition_type": r.condition_type,
        "condition_value": float(r.condition_value),
        "notify_whatsapp": r.notify_whatsapp,
        "notify_push": r.notify_push,
        "status": r.status,
        "triggered_at": r.triggered_at.isoformat() if r.triggered_at else None,
        "trigger_count": r.trigger_count,
        "expires_at": r.expires_at.isoformat() if r.expires_at else None,
        "is_expired": r.expires_at < now_utc if r.expires_at else False,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


class GuardrailCreate(BaseModel):
    name: str
    target_symbols: Optional[List[str]] = None  # None = all positions
    condition_type: Literal["loss_threshold", "loss_range_time", "total_pnl_drop", "profit_target"]
    condition_value: float
    notify_whatsapp: bool = True
    notify_push: bool = True

    @validator("condition_value")
    def validate_value(cls, v, values):
        ct = values.get("condition_type")
        if ct in ("loss_threshold", "total_pnl_drop") and v >= 0:
            raise ValueError(f"{ct} condition_value must be negative (e.g. -5000)")
        if ct == "profit_target" and v <= 0:
            raise ValueError("profit_target condition_value must be positive (e.g. 8000)")
        if ct == "loss_range_time" and v <= 0:
            raise ValueError("loss_range_time condition_value must be positive minutes (e.g. 30)")
        return v

    @validator("name")
    def validate_name(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("name cannot be empty")
        return v[:100]


@router.get("/")
async def list_guardrails(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """List all guardrail rules for today (includes triggered/expired for history)."""
    # Show rules created in last 36h (covers overnight viewing)
    since = datetime.now(timezone.utc) - timedelta(hours=36)
    result = await db.execute(
        select(GuardrailRule)
        .where(
            GuardrailRule.broker_account_id == broker_account_id,
            GuardrailRule.created_at >= since,
        )
        .order_by(GuardrailRule.created_at.desc())
    )
    rules = result.scalars().all()
    return [_rule_to_dict(r) for r in rules]


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_guardrail(
    body: GuardrailCreate,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a new guardrail rule. Expires at 15:30 IST today."""
    # Max 10 active rules per account to prevent abuse
    active_result = await db.execute(
        select(GuardrailRule).where(
            GuardrailRule.broker_account_id == broker_account_id,
            GuardrailRule.status == "active",
        )
    )
    active_count = len(active_result.scalars().all())
    if active_count >= 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 active guardrail rules per account",
        )

    rule = GuardrailRule(
        broker_account_id=broker_account_id,
        name=body.name,
        target_symbols=body.target_symbols,
        condition_type=body.condition_type,
        condition_value=body.condition_value,
        notify_whatsapp=body.notify_whatsapp,
        notify_push=body.notify_push,
        status="active",
        expires_at=_next_market_close(),
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    logger.info(f"Guardrail created: {rule.id} ({rule.condition_type}) for {broker_account_id}")
    return _rule_to_dict(rule)


@router.patch("/{rule_id}/pause")
async def toggle_pause(
    rule_id: UUID,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """Toggle pause/resume on an active or paused rule."""
    result = await db.execute(
        select(GuardrailRule).where(
            GuardrailRule.id == rule_id,
            GuardrailRule.broker_account_id == broker_account_id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    if rule.status == "triggered":
        raise HTTPException(status_code=400, detail="Cannot pause a triggered rule")
    if rule.status == "active":
        rule.status = "paused"
    elif rule.status == "paused":
        rule.status = "active"
    rule.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return _rule_to_dict(rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_guardrail(
    rule_id: UUID,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
):
    """Delete a guardrail rule."""
    result = await db.execute(
        select(GuardrailRule).where(
            GuardrailRule.id == rule_id,
            GuardrailRule.broker_account_id == broker_account_id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.delete(rule)
    await db.commit()
