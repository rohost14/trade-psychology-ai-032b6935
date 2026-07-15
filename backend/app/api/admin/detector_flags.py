"""Admin — detector feature flags (Engine v2 migration control).

Lets an admin flip a detector through off → shadow → canary(%) → on without a
deploy. Backed by the detector_flags table (migration 068); the running engine
picks changes up within ~60s (Redis-cached flag map).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin.deps import get_current_admin
from app.api.admin.audit_writer import audit
from app.core.database import get_db
from app.services.detector_flag_service import detector_flags, VALID_MODES

router = APIRouter()


class DetectorFlagRequest(BaseModel):
    detector: str
    mode: str = Field(description="off | shadow | canary | on")
    rollout_pct: int = Field(default=100, ge=0, le=100, description="canary: % of accounts live")


@router.get("/detector-flags")
async def list_detector_flags(
    _: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Effective mode + rollout for every detector (registry defaults + overrides)."""
    flags = await detector_flags.list_flags(db)
    return {
        "flags": [
            {"detector": name, "mode": mode, "rollout_pct": pct}
            for name, (mode, pct) in sorted(flags.items())
        ]
    }


@router.post("/detector-flags")
async def set_detector_flag(
    body: DetectorFlagRequest,
    admin: dict = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Set a detector's mode. Validated against VALID_MODES; audited."""
    if body.mode not in VALID_MODES:
        raise HTTPException(status_code=422, detail=f"mode must be one of {sorted(VALID_MODES)}")
    try:
        await detector_flags.set_flag(
            db, body.detector, body.mode, body.rollout_pct, updated_by=admin["email"]
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    await audit(
        db, admin["email"], "set_detector_flag",
        target_type="detector", target_id=body.detector,
        details={"mode": body.mode, "rollout_pct": body.rollout_pct},
    )
    return {"detector": body.detector, "mode": body.mode, "rollout_pct": body.rollout_pct}
