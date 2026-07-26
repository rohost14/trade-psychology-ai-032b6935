"""
Admin broadcast — send WhatsApp messages to targeted user segments.
Segments: connected | all_with_phone | long_inactive | high_alerts
Receipt tracking: broadcast_logs (one per send) + broadcast_receipts (one per user).
"""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from typing import Literal

from app.core.database import get_db
from app.api.admin.deps import get_current_admin, require_role
from app.api.admin.audit_writer import audit
from app.models.broker_account import BrokerAccount
from app.models.user import User
from app.models.risk_alert import RiskAlert
from app.models.trade import Trade
from app.models.broadcast_log import BroadcastLog, BroadcastReceipt

router = APIRouter()
logger = logging.getLogger(__name__)

_EXCLUDED_STATUSES = ("deleted", "suspended", "erased")
_MAX_MSG_LEN       = 700

SegmentType = Literal["connected", "all_with_phone", "long_inactive", "high_alerts"]


class BroadcastRequest(BaseModel):
    segment: SegmentType
    message: str
    dry_run: bool = False

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message is required")
        if len(v) > _MAX_MSG_LEN:
            raise ValueError(f"Message too long (max {_MAX_MSG_LEN} chars)")
        return v


async def _resolve_segment(segment: SegmentType, db: AsyncSession) -> list[tuple[str, str]]:
    """Return list of (phone, account_id) for a given segment.
    All segments exclude deleted/suspended/erased accounts.
    """
    now = datetime.now(timezone.utc)

    if segment in ("connected", "all_with_phone"):
        q = (
            select(BrokerAccount, User)
            .outerjoin(User, BrokerAccount.user_id == User.id)
            .where(
                User.guardian_phone.isnot(None),
                BrokerAccount.status.notin_(_EXCLUDED_STATUSES),
            )
        )
        if segment == "connected":
            q = q.where(BrokerAccount.status == "connected")
        rows = (await db.execute(q)).all()
        return [(u.guardian_phone, str(ba.id)) for ba, u in rows if u and u.guardian_phone]

    elif segment == "long_inactive":
        # Connected users with no trade in the last 14 days.
        # Re-engagement target: they signed up and linked but stopped trading.
        cutoff = now - timedelta(days=14)
        recently_active_ids = (await db.execute(
            select(func.distinct(Trade.broker_account_id))
            .where(Trade.created_at >= cutoff)
        )).scalars().all()

        q = (
            select(BrokerAccount, User)
            .outerjoin(User, BrokerAccount.user_id == User.id)
            .where(
                BrokerAccount.status == "connected",
                User.guardian_phone.isnot(None),
                BrokerAccount.id.notin_(recently_active_ids) if recently_active_ids else True,
            )
        )
        rows = (await db.execute(q)).all()
        return [(u.guardian_phone, str(ba.id)) for ba, u in rows if u and u.guardian_phone]

    elif segment == "high_alerts":
        # Connected users who triggered >5 alerts in the last 7 days.
        # Intervention target: active traders with persistent harmful patterns.
        alert_cutoff = now - timedelta(days=7)
        high_alert_ids = (await db.execute(
            select(RiskAlert.broker_account_id)
            .where(RiskAlert.created_at >= alert_cutoff)
            .group_by(RiskAlert.broker_account_id)
            .having(func.count() > 5)
        )).scalars().all()

        if not high_alert_ids:
            return []

        q = (
            select(BrokerAccount, User)
            .outerjoin(User, BrokerAccount.user_id == User.id)
            .where(
                BrokerAccount.id.in_(high_alert_ids),
                User.guardian_phone.isnot(None),
                BrokerAccount.status.notin_(_EXCLUDED_STATUSES),
            )
        )
        rows = (await db.execute(q)).all()
        return [(u.guardian_phone, str(ba.id)) for ba, u in rows if u and u.guardian_phone]

    return []


@router.get("/broadcast/segment-counts")
async def get_segment_counts(
    db:     AsyncSession = Depends(get_db),
    _admin: dict         = Depends(get_current_admin),
):
    """Return live recipient counts for all segments. Use before composing a broadcast."""
    segments: list[SegmentType] = ["connected", "all_with_phone", "long_inactive", "high_alerts"]
    result = {}
    for seg in segments:
        phones = await _resolve_segment(seg, db)
        result[seg] = len(phones)
    return result


@router.post("/broadcast")
async def broadcast_message(
    body:  BroadcastRequest,
    db:    AsyncSession = Depends(get_db),
    admin: dict         = Depends(require_role("superadmin", "ops")),
):
    """
    Send a WhatsApp message to a user segment.
    Always dry_run=true first to preview recipient count.
    Returns broadcast_id on real sends for receipt lookup.
    """
    phones = await _resolve_segment(body.segment, db)

    if body.dry_run:
        return {"dry_run": True, "recipient_count": len(phones)}

    # Create broadcast log row
    log = BroadcastLog(
        id=uuid.uuid4(),
        created_by=admin["email"],
        segment=body.segment,
        message=body.message,
        total=len(phones),
        created_at=datetime.now(timezone.utc),
    )
    db.add(log)
    await db.flush()

    from app.services.whatsapp_service import whatsapp_service
    sent = failed = 0
    for phone, _account_id in phones:
        receipt = BroadcastReceipt(
            id=uuid.uuid4(),
            broadcast_id=log.id,
            phone=phone,
            status="queued",
        )
        db.add(receipt)
        await db.flush()

        try:
            ok = await whatsapp_service.send_message(phone, body.message)
            if ok:
                receipt.status = "sent"
                receipt.sent_at = datetime.now(timezone.utc)
                sent += 1
            else:
                receipt.status = "failed"
                receipt.error  = "send_alert returned False"
                failed += 1
        except Exception as e:
            receipt.status = "failed"
            receipt.error  = str(e)[:200]
            logger.warning(f"Broadcast send failed for {phone}: {e}")
            failed += 1

        await asyncio.sleep(0.2)

    log.sent   = sent
    log.failed = failed
    await db.commit()

    await audit(db, admin["email"], "broadcast",
                target_type="global", target_id=body.segment,
                details={
                    "broadcast_id": str(log.id),
                    "segment":      body.segment,
                    "preview":      body.message[:120],
                    "sent":         sent,
                    "failed":       failed,
                    "total":        len(phones),
                })
    logger.info(f"Broadcast by {admin['email']}: segment={body.segment} sent={sent} failed={failed} id={log.id}")
    return {"sent": sent, "failed": failed, "total": len(phones), "broadcast_id": str(log.id)}


@router.get("/broadcast/logs")
async def list_broadcast_logs(
    limit:  int  = 20,
    db:     AsyncSession = Depends(get_db),
    _admin: dict         = Depends(require_role("superadmin", "ops")),
):
    """Return last N broadcasts with aggregate delivery counts."""
    rows = (await db.execute(
        select(BroadcastLog)
        .order_by(BroadcastLog.created_at.desc())
        .limit(min(limit, 100))
    )).scalars().all()

    return [
        {
            "id":         str(r.id),
            "created_by": r.created_by,
            "segment":    r.segment,
            "message":    r.message[:120] + ("…" if len(r.message) > 120 else ""),
            "total":      r.total,
            "sent":       r.sent,
            "failed":     r.failed,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/broadcast/logs/{broadcast_id}/receipts")
async def get_broadcast_receipts(
    broadcast_id: str,
    db:     AsyncSession = Depends(get_db),
    _admin: dict         = Depends(require_role("superadmin", "ops")),
):
    """Return per-user delivery receipts for a specific broadcast."""
    try:
        bid = uuid.UUID(broadcast_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid broadcast_id")

    log = (await db.execute(
        select(BroadcastLog).where(BroadcastLog.id == bid)
    )).scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Broadcast not found")

    receipts = (await db.execute(
        select(BroadcastReceipt)
        .where(BroadcastReceipt.broadcast_id == bid)
        .order_by(BroadcastReceipt.sent_at.asc())
    )).scalars().all()

    return {
        "broadcast": {
            "id":         str(log.id),
            "segment":    log.segment,
            "message":    log.message,
            "total":      log.total,
            "sent":       log.sent,
            "failed":     log.failed,
            "created_by": log.created_by,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        },
        "receipts": [
            {
                "phone":   r.phone[:-4] + "****",
                "status":  r.status,
                "error":   r.error,
                "sent_at": r.sent_at.isoformat() if r.sent_at else None,
            }
            for r in receipts
        ],
    }
