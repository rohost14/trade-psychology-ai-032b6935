"""
Admin broadcast — send a WhatsApp message to a filtered segment of users.
Segments: 'all_with_phone' | 'connected' | 'test' (just returns count, no send).
Receipt tracking: broadcast_logs (one per send) + broadcast_receipts (one per user).
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Literal

from app.core.database import get_db
from app.api.admin.deps import get_current_admin, require_role
from app.api.admin.audit_writer import audit
from app.models.broker_account import BrokerAccount
from app.models.user import User
from app.models.broadcast_log import BroadcastLog, BroadcastReceipt

router = APIRouter()
logger = logging.getLogger(__name__)
_EXCLUDED_STATUSES = ("deleted", "suspended", "erased")


class BroadcastRequest(BaseModel):
    segment: Literal["all_with_phone", "connected"]
    message: str
    dry_run: bool = False


def _build_recipient_query(segment: str):
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
    return q


@router.post("/broadcast")
async def broadcast_message(
    body: BroadcastRequest,
    db:    AsyncSession = Depends(get_db),
    admin: dict         = Depends(require_role("superadmin", "ops")),
):
    """
    Send a WhatsApp message to a user segment.
    Excludes deleted/suspended/erased accounts automatically.
    Always do dry_run=true first to preview recipient count.
    Returns broadcast_id on real sends for receipt lookup.
    """
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="message is required")
    if len(body.message) > 700:
        raise HTTPException(status_code=400, detail="Message too long (max 700 chars)")

    rows = (await db.execute(_build_recipient_query(body.segment))).all()
    phones: list[tuple[str, str | None]] = [
        (u.guardian_phone, str(ba.id))
        for ba, u in rows
        if u and u.guardian_phone
    ]

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
    await db.flush()  # get log.id before inserting receipts

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
            ok = await whatsapp_service.send_alert(phone, body.message)
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
    limit: int = 20,
    db:    AsyncSession = Depends(get_db),
    _admin: dict        = Depends(require_role("superadmin", "ops")),
):
    """Return last N broadcasts with aggregate delivery counts."""
    from sqlalchemy import text
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
    db:    AsyncSession = Depends(get_db),
    _admin: dict        = Depends(require_role("superadmin", "ops")),
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
                "phone":   r.phone[:-4] + "****",  # mask last 4 digits for privacy
                "status":  r.status,
                "error":   r.error,
                "sent_at": r.sent_at.isoformat() if r.sent_at else None,
            }
            for r in receipts
        ],
    }
