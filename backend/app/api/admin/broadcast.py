"""
Admin broadcast — send a WhatsApp message to a filtered segment of users.
Segments: 'all_with_phone' | 'connected' | 'test' (just returns count, no send).
"""
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Literal

from app.core.database import get_db
from app.api.admin.deps import get_current_admin
from app.api.admin.audit_writer import audit
from app.models.broker_account import BrokerAccount
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)


class BroadcastRequest(BaseModel):
    segment: Literal["all_with_phone", "connected"]
    message: str
    dry_run: bool = False   # True = count only, no messages sent


@router.post("/broadcast")
async def broadcast_message(
    body: BroadcastRequest,
    db:    AsyncSession = Depends(get_db),
    admin: dict         = Depends(get_current_admin),
):
    """
    Send a WhatsApp message to a user segment.
    Always do a dry_run=true first to preview recipient count.
    """
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="message is required")
    if len(body.message) > 700:
        raise HTTPException(status_code=400, detail="Message too long (max 700 chars)")

    # Build target list
    q = (
        select(BrokerAccount, User)
        .outerjoin(User, BrokerAccount.user_id == User.id)
        .where(User.guardian_phone.isnot(None))
    )
    if body.segment == "connected":
        q = q.where(BrokerAccount.status == "connected")

    rows = (await db.execute(q)).all()
    phones = [u.guardian_phone for _, u in rows if u and u.guardian_phone]

    if body.dry_run:
        return {"dry_run": True, "recipient_count": len(phones)}

    # Send in batches of 5 with 0.2s gap to avoid rate-limit
    from app.services.whatsapp_service import whatsapp_service
    sent = failed = 0
    for phone in phones:
        try:
            ok = await whatsapp_service.send_alert(phone, body.message)
            if ok: sent += 1
            else:  failed += 1
        except Exception as e:
            logger.warning(f"Broadcast send failed for {phone}: {e}")
            failed += 1
        await asyncio.sleep(0.2)

    await audit(db, admin["email"], "broadcast",
                target_type="global", target_id=body.segment,
                details={
                    "segment":    body.segment,
                    "preview":    body.message[:120],
                    "sent":       sent,
                    "failed":     failed,
                    "total":      len(phones),
                })
    logger.info(f"Broadcast by {admin['email']}: segment={body.segment} sent={sent} failed={failed}")
    return {"sent": sent, "failed": failed, "total": len(phones)}
