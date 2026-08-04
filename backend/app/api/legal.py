"""
Terms of Service acceptance status and explicit re-acceptance.

Backs the one-time interstitial shown when the terms change under a logged-in
user. Normal case is that `needs_acceptance` is false and the frontend renders
nothing — this is deliberately cheap enough to call on app load.

See app/core/legal.py for the versioning rule and why a bump is not free.
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.core.database import get_db
from app.core.legal import CURRENT_TERMS_VERSION, needs_reacceptance
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


class TermsStatus(BaseModel):
    current_version: str
    accepted_version: str | None = None
    accepted_at: datetime | None = None
    needs_acceptance: bool


@router.get("/terms-status", response_model=TermsStatus)
async def get_terms_status(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Whether this user has accepted the current Terms.

    `needs_acceptance` is true only when a stored acceptance exists and is for an
    older version. A NULL acceptance does NOT trigger the interstitial: those users
    predate migration 078 and get stamped on their next OAuth login, where pressing
    the button is itself the acceptance. Prompting them as well would be asking
    twice for the same thing.
    """
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return TermsStatus(
        current_version=CURRENT_TERMS_VERSION,
        accepted_version=user.terms_version,
        accepted_at=user.terms_accepted_at,
        needs_acceptance=needs_reacceptance(user.terms_version),
    )


@router.post("/accept", response_model=TermsStatus)
async def accept_terms(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Record explicit acceptance of the CURRENT terms version.

    The version is taken from the server, never from the request body — a client
    must not be able to claim acceptance of a version that does not exist, or of a
    newer one than it was actually shown.
    """
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    previous = user.terms_version
    user.terms_accepted_at = datetime.now(timezone.utc)
    user.terms_version = CURRENT_TERMS_VERSION
    user.updated_at = datetime.now(timezone.utc)
    await db.commit()

    logger.info(
        "[legal] user %s accepted terms %s (previously %s)",
        user_id, CURRENT_TERMS_VERSION, previous or "none",
    )
    return TermsStatus(
        current_version=CURRENT_TERMS_VERSION,
        accepted_version=user.terms_version,
        accepted_at=user.terms_accepted_at,
        needs_acceptance=False,
    )
