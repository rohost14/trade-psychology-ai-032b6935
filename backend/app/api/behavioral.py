from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import logging

from app.core.database import get_db
from app.api.deps import get_verified_broker_account_id
from app.services.behavioral_analysis_service import BehavioralAnalysisService
from app.services.behavioral_baseline_service import behavioral_baseline_service
from app.core.trading_defaults import COLD_START_DEFAULTS, UNIVERSAL_FLOORS

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/analysis")
async def get_behavioral_analysis(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    time_window_days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db)
):
    """Get comprehensive behavioral analysis."""
    try:
        service = BehavioralAnalysisService()
        analysis = await service.analyze_behavior(
            broker_account_id,
            db,
            time_window_days
        )
        return analysis
    except Exception as e:
        logger.error(f"Behavioral analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/patterns")
async def get_detected_patterns(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Get list of detected behavioral patterns."""
    try:
        service = BehavioralAnalysisService()
        analysis = await service.analyze_behavior(broker_account_id, db)

        return {
            "patterns": analysis["patterns_detected"],
            "behavior_score": analysis["behavior_score"],
            "top_strength": analysis["top_strength"],
            "focus_area": analysis["focus_area"]
        }
    except Exception as e:
        logger.error(f"Pattern detection failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/baseline")
async def get_behavioral_baseline(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
    force_recompute: bool = Query(False, description="Force recomputation even if recent baseline exists"),
):
    """
    Get the behavior-derived alert thresholds for this account.

    On first call (or when force_recompute=true), computes thresholds from the last
    90 days of completed trades. Subsequent calls within 24h return the cached result.

    Returns:
      - baseline: computed thresholds (null if < 5 sessions of data)
      - cold_start_defaults: universal defaults used when no baseline exists
      - active_thresholds: the thresholds currently in use (baseline or cold-start)
      - session_count: how many distinct trading days were analysed
      - is_personalized: true when using behavior-derived thresholds
    """
    try:
        if force_recompute:
            baseline = await behavioral_baseline_service.compute_and_store(
                db=db,
                broker_account_id=broker_account_id,
                force=True,
            )
        else:
            # Return cached if fresh, trigger compute if stale/missing
            baseline = await behavioral_baseline_service.compute_and_store(
                db=db,
                broker_account_id=broker_account_id,
                force=False,
            )

        is_personalized = baseline is not None
        active = baseline if is_personalized else COLD_START_DEFAULTS

        return {
            "is_personalized": is_personalized,
            "session_count": baseline.get("session_count") if baseline else 0,
            "computed_at": baseline.get("computed_at") if baseline else None,
            "baseline": baseline,
            "cold_start_defaults": COLD_START_DEFAULTS,
            "universal_floors": UNIVERSAL_FLOORS,
            "active_thresholds": {
                "daily_trade_limit":        active.get("daily_trade_limit"),
                "burst_trades_per_15min":   active.get("burst_trades_per_15min"),
                "revenge_window_min":       active.get("revenge_window_min"),
                "consecutive_loss_caution": active.get("consecutive_loss_caution"),
                "consecutive_loss_danger":  active.get("consecutive_loss_danger"),
            },
        }
    except Exception as e:
        logger.error(f"Baseline endpoint failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/trade-tags")
async def get_trade_tags(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Get behavioral tags for all trades."""
    try:
        service = BehavioralAnalysisService()
        tags = await service.tag_trades(broker_account_id, db)
        return {"trade_tags": tags}
    except Exception as e:
        logger.error(f"Trade tagging failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
