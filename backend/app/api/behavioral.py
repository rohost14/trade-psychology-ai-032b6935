from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import logging

from app.core.database import get_db
from app.api.deps import get_verified_broker_account_id
# Dual-engine retired (deep-review E1): the legacy behavioral_analysis_service is
# archived. These endpoints now derive from the single source of truth — the live
# BehaviorEngine's stored RiskAlerts — via behavior_summary.
from app.services.behavior_summary import get_behavior_summary
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
    """Behavioral summary (patterns_detected / emotional_tax), sourced from the
    live engine's RiskAlerts."""
    try:
        return await get_behavior_summary(broker_account_id, db, time_window_days)
    except Exception as e:
        logger.error(f"Behavioral analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/patterns")
async def get_detected_patterns(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Get list of detected behavioral patterns (from the live engine's RiskAlerts)."""
    try:
        summary = await get_behavior_summary(broker_account_id, db)
        return {
            "patterns": summary["patterns_detected"],
            "top_strength": summary["top_strength"],
            "focus_area": summary["focus_area"],
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

        # active_thresholds used to read flat keys straight off `baseline`. Since
        # 05962ae the baseline is v2 ({version, metrics{...}}) and shares none of
        # those keys, so every value came back null. Ask the resolver instead -
        # it reports what is genuinely in force, which is what this endpoint
        # claims to show.
        from app.models.user_profile import UserProfile as _UP
        from sqlalchemy import select as _select
        from app.core.threshold_resolution import resolve_thresholds
        _prof = (await db.execute(
            _select(_UP).where(_UP.broker_account_id == broker_account_id)
        )).scalar_one_or_none()
        active = resolve_thresholds(_prof)

        return {
            "is_personalized": is_personalized,
            "session_count": (baseline.get("sessions_analyzed")
                              or baseline.get("session_count", 0)) if baseline else 0,
            "computed_at": baseline.get("computed_at") if baseline else None,
            "baseline": baseline,
            "cold_start_defaults": COLD_START_DEFAULTS,
            "universal_floors": UNIVERSAL_FLOORS,
            "active_thresholds": {
                "daily_trade_limit":        active.get("daily_trade_limit"),
                # was burst_trades_per_15min - no detector reads that key; the
                # live burst detectors use the 30-minute pair.
                "burst_trades_per_30min_caution": active.get("burst_trades_per_30min_caution"),
                "revenge_window_caution_min": active.get("revenge_window_caution_min"),
                "consecutive_loss_caution": active.get("consecutive_loss_caution"),
                "consecutive_loss_danger":  active.get("consecutive_loss_danger"),
            },
        }
    except Exception as e:
        logger.error(f"Baseline endpoint failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# NOTE: GET /trade-tags removed with the dual-engine retirement (E1) — it was
# backed only by the archived behavioral_analysis_service and had no live caller.
# Per-trade behavioural tagging now lives in BehaviorEvent.trigger_completed_trade_id.
