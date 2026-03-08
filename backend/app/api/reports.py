from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta, date, timezone
from typing import Optional
from pydantic import BaseModel
import logging

from app.core.database import get_db
from app.api.deps import get_verified_broker_account_id
from app.services.ai_service import ai_service
from app.services.whatsapp_service import whatsapp_service
from app.services.behavioral_analysis_service import BehavioralAnalysisService
from app.services.daily_reports_service import daily_reports_service
from app.services.pattern_prediction_service import pattern_prediction_service
from app.models.trade import Trade
from app.core.config import settings
from uuid import UUID

router = APIRouter()
logger = logging.getLogger(__name__)
behavioral_service = BehavioralAnalysisService()


# =============================================================================
# POST-MARKET REPORT (Call at 4:00 PM)
# =============================================================================

@router.get("/post-market")
async def get_post_market_report(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    report_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Get post-market report for a trading day.

    This report includes:
    - Trade summary (count, win rate, P&L)
    - Patterns detected during the day
    - Emotional journey timeline
    - Key lessons learned
    - Tomorrow's focus area

    Default: Today's report (call after market close)
    """
    try:
        target_date = None
        if report_date:
            target_date = date.fromisoformat(report_date)

        report = await daily_reports_service.generate_post_market_report(
            broker_account_id=broker_account_id,
            db=db,
            report_date=target_date
        )

        return report

    except Exception as e:
        logger.error(f"Failed to generate post-market report: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# =============================================================================
# MORNING READINESS BRIEFING (Call at 8:45 AM)
# =============================================================================

@router.get("/morning-briefing")
async def get_morning_briefing(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Get morning readiness briefing.

    This briefing includes:
    - Readiness score (0-100)
    - Day-of-week warning (if applicable)
    - Recent trading summary
    - Today's specific watch-outs
    - Readiness checklist
    - Commitment prompt

    Call this at 8:45 AM before market opens.
    """
    try:
        briefing = await daily_reports_service.generate_morning_briefing(
            broker_account_id=broker_account_id,
            db=db
        )

        return briefing

    except Exception as e:
        logger.error(f"Failed to generate morning briefing: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# =============================================================================
# PATTERN PREDICTIONS (Real-time)
# =============================================================================

@router.get("/predictions")
async def get_pattern_predictions(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Get real-time pattern predictions based on current state.

    Returns probability of:
    - Revenge trading
    - Tilt / Loss spiral
    - Overtrading
    - FOMO
    - Recovery chasing

    Plus:
    - Overall risk assessment
    - Actionable recommendations

    Call this:
    - After each trade
    - Before placing a new trade
    - Periodically during trading session
    """
    try:
        predictions = await pattern_prediction_service.predict_patterns(
            broker_account_id=broker_account_id,
            db=db
        )

        return predictions

    except Exception as e:
        logger.error(f"Failed to get pattern predictions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


class PredictionContext(BaseModel):
    consecutive_losses: Optional[int] = None
    session_pnl: Optional[float] = None
    trades_today: Optional[int] = None
    last_trade_pnl: Optional[float] = None
    minutes_since_last_trade: Optional[float] = None


@router.post("/predictions/simulate")
async def simulate_prediction(
    context: PredictionContext,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Simulate pattern predictions with custom context.
    Useful for testing different scenarios.
    """
    try:
        now = datetime.now(timezone.utc)
        ctx = {
            "consecutive_losses": context.consecutive_losses or 0,
            "session_pnl": context.session_pnl or 0,
            "trades_today": context.trades_today or 0,
            "last_trade_pnl": context.last_trade_pnl or 0,
            "minutes_since_last_trade": context.minutes_since_last_trade or 999,
            "time_of_day": now.hour,
            "day_of_week": now.strftime("%A"),
            "is_first_hour": now.hour == 9,
            "is_last_hour": now.hour >= 15,
            "drawdown_from_peak": 0
        }

        predictions = await pattern_prediction_service.predict_patterns(
            broker_account_id=broker_account_id,
            db=db,
            current_context=ctx
        )

        return predictions

    except Exception as e:
        logger.error(f"Failed to simulate predictions: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# =============================================================================
# WEEKLY SUMMARY (Call on weekends)
# =============================================================================

@router.get("/weekly-summary")
async def get_weekly_summary(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Get weekly trading psychology summary.

    Best called on weekends for review.
    Compares this week vs last week.
    """
    try:
        today = datetime.now(timezone.utc).date()

        # This week (Mon-Sun)
        days_since_monday = today.weekday()
        this_week_start = today - timedelta(days=days_since_monday)
        last_week_start = this_week_start - timedelta(days=7)

        # Get reports for both weeks
        this_week_reports = []
        last_week_reports = []

        for i in range(7):
            # This week
            day = this_week_start + timedelta(days=i)
            if day <= today:
                report = await daily_reports_service.generate_post_market_report(
                    broker_account_id=broker_account_id,
                    db=db,
                    report_date=day
                )
                if report.get("has_trades"):
                    this_week_reports.append(report)

            # Last week
            day = last_week_start + timedelta(days=i)
            report = await daily_reports_service.generate_post_market_report(
                broker_account_id=broker_account_id,
                db=db,
                report_date=day
            )
            if report.get("has_trades"):
                last_week_reports.append(report)

        # Aggregate statistics
        this_week_stats = _aggregate_weekly_stats(this_week_reports)
        last_week_stats = _aggregate_weekly_stats(last_week_reports)

        # Calculate improvements
        improvements = _calculate_improvements(this_week_stats, last_week_stats)

        return {
            "week_start": this_week_start.isoformat(),
            "this_week": this_week_stats,
            "last_week": last_week_stats,
            "improvements": improvements,
            "trading_days_this_week": len(this_week_reports),
            "trading_days_last_week": len(last_week_reports)
        }

    except Exception as e:
        logger.error(f"Failed to generate weekly summary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


def _aggregate_weekly_stats(reports: list) -> dict:
    """Aggregate statistics from daily reports."""
    if not reports:
        return {
            "total_trades": 0,
            "total_pnl": 0,
            "win_rate": 0,
            "danger_alerts": 0,
            "patterns": {}
        }

    total_trades = sum(r["summary"]["total_trades"] for r in reports)
    total_pnl = sum(r["summary"]["total_pnl"] for r in reports)
    total_winners = sum(r["summary"]["winners"] for r in reports)

    # Count patterns
    patterns = {}
    danger_alerts = 0
    for report in reports:
        for pattern in report.get("patterns_detected", []):
            p = pattern["pattern"]
            patterns[p] = patterns.get(p, 0) + 1
            if pattern["severity"] == "danger":
                danger_alerts += 1

    return {
        "total_trades": total_trades,
        "total_pnl": round(total_pnl, 2),
        "win_rate": round((total_winners / total_trades) * 100, 1) if total_trades > 0 else 0,
        "danger_alerts": danger_alerts,
        "patterns": patterns
    }


def _calculate_improvements(this_week: dict, last_week: dict) -> dict:
    """Calculate week-over-week improvements."""
    improvements = {}

    # P&L improvement
    pnl_change = this_week["total_pnl"] - last_week["total_pnl"]
    improvements["pnl"] = {
        "change": round(pnl_change, 2),
        "improved": pnl_change > 0
    }

    # Win rate improvement
    wr_change = this_week["win_rate"] - last_week["win_rate"]
    improvements["win_rate"] = {
        "change": round(wr_change, 1),
        "improved": wr_change > 0
    }

    # Danger alerts (fewer is better)
    alert_change = last_week["danger_alerts"] - this_week["danger_alerts"]
    improvements["danger_alerts"] = {
        "change": alert_change,
        "improved": alert_change > 0,
        "message": f"{abs(alert_change)} {'fewer' if alert_change > 0 else 'more'} danger alerts"
    }

    return improvements


# =============================================================================
# WHATSAPP REPORT (Existing)
# =============================================================================

@router.post("/whatsapp")
async def send_whatsapp_report(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    period_days: int = 2,
    to_number: str = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate and send a WhatsApp report for the last N days.
    """
    try:
        # 1. Fetch trades
        cutoff = datetime.now() - timedelta(days=period_days)
        result = await db.execute(
            select(Trade).where(
                Trade.broker_account_id == broker_account_id,
                Trade.order_timestamp >= cutoff,
                Trade.status == "COMPLETE"
            ).order_by(Trade.order_timestamp)
        )
        trades = result.scalars().all()

        if not trades:
            return {"status": "skipped", "message": "No trades found in period"}

        # 2. Analyze Stats
        total_pnl = sum((t.pnl or 0) for t in trades)
        wins = [t for t in trades if (t.pnl or 0) > 0]
        losses = [t for t in trades if (t.pnl or 0) <= 0]

        trade_count = len(trades)
        win_rate = (len(wins) / trade_count * 100) if trade_count > 0 else 0

        best_trade = max((t.pnl or 0) for t in trades) if trades else 0
        worst_trade = min((t.pnl or 0) for t in trades) if trades else 0

        # 3. Analyze Behavior (Reuse existing service)
        # We reuse the full analysis logic but scoped to these trades if possible,
        # or just quick-detect. For accurate persona, we generally need more history,
        # but for "Active Patterns" in a 2-day report, we can run detection on just these trades
        # OR fetch the comprehensive analysis and filter.
        # Let's run detection on the specific set for immediate feedback.

        detected_patterns = []
        for pattern in behavioral_service.patterns:
            res = pattern.detect(trades)
            if res["detected"]:
                detected_patterns.append(pattern.name)

        # Quick strength/weakness heuristic for the report
        key_strength = "Discipline" if not any(p for p in detected_patterns if "Revenge" in p or "Overtrading" in p) else "Resilience"
        key_weakness = detected_patterns[0] if detected_patterns else "None"

        # 4. Generate AI Report
        report_content = await ai_service.generate_whatsapp_report(
            period_days=period_days,
            total_pnl=total_pnl,
            trade_count=trade_count,
            win_rate=win_rate,
            best_trade=best_trade,
            worst_trade=worst_trade,
            patterns_detected=detected_patterns,
            key_strength=key_strength,
            key_weakness=key_weakness
        )

        # 5. Send Message
        if not to_number:
            raise HTTPException(status_code=400, detail="No guardian phone number configured")
        recipient = to_number

        success = await whatsapp_service.send_message(recipient, report_content)

        return {
            "status": "success" if success else "failed",
            "recipient": recipient,
            "report_preview": report_content
        }

    except Exception as e:
        logger.error(f"Failed to generate WhatsApp report: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
