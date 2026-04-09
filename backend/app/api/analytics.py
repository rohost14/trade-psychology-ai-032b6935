from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, cast, Date
from uuid import UUID
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Optional
import logging
import math

from app.core.database import get_db
from app.api.deps import get_verified_broker_account_id
from app.services.analytics_service import AnalyticsService
from app.services.pnl_calculator import pnl_calculator
from app.core.rate_limiter import analytics_limiter
from app.models.trade import Trade
from app.models.completed_trade import CompletedTrade
from app.models.completed_trade_feature import CompletedTradeFeature
from app.models.journal_entry import JournalEntry
from app.models.risk_alert import RiskAlert

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/risk-score")
async def get_weekly_risk_score(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(analytics_limiter)
):
    """Get weekly risk/discipline score."""
    try:
        analytics = AnalyticsService()
        score_data = await analytics.calculate_weekly_risk_score(broker_account_id, db)
        return score_data
    except Exception as e:
        logger.error(f"Failed to get risk score: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/dashboard-stats")
async def get_dashboard_stats(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(analytics_limiter)
):
    """Get all analytics for dashboard."""
    try:
        analytics = AnalyticsService()

        score_data = await analytics.calculate_weekly_risk_score(broker_account_id, db)

        return {
            "risk_score": score_data,
        }
    except Exception as e:
        logger.error(f"Failed to get dashboard stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/recalculate-pnl")
async def recalculate_pnl(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    symbol: Optional[str] = None,
    days_back: int = Query(default=30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(analytics_limiter),
):
    """
    Recalculate P&L for trades using FIFO matching.

    This fixes the issue where pnl field is 0/NULL from webhooks.
    Call this endpoint to retroactively calculate P&L for all trades.
    """
    try:
        days_back = min(max(days_back, 1), 90)  # clamp: 1–90 days
        result = await pnl_calculator.calculate_and_update_pnl(
            broker_account_id, db, symbol=symbol, days_back=days_back
        )
        return {
            "success": True,
            "processed": result["processed"],
            "updated": result["updated"],
            "total_pnl": result["total_pnl"],
            "symbols_processed": result["symbols_processed"],
            "completed_trades": result.get("completed_trades", 0),
            "features_computed": result.get("features_computed", 0),
        }
    except Exception as e:
        logger.error(f"Failed to recalculate P&L: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/unrealized-pnl")
async def get_unrealized_pnl(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db)
):
    """Get unrealized P&L for open positions."""
    try:
        unrealized = await pnl_calculator.get_unrealized_pnl(broker_account_id, db)
        return {
            "positions": {k: float(v) for k, v in unrealized.items()},
            "total_unrealized": float(sum(unrealized.values()))
        }
    except Exception as e:
        logger.error(f"Failed to get unrealized P&L: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/progress")
async def get_progress_tracking(
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(analytics_limiter)
):
    """
    Get week-over-week progress tracking data.
    Compares this week vs last week for key metrics.
    """
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select, and_, func
    from app.models.trade import Trade
    from app.models.risk_alert import RiskAlert

    try:
        now = datetime.now(timezone.utc)

        # Calculate week boundaries
        today = now.date()
        this_week_start = today - timedelta(days=today.weekday())
        last_week_start = this_week_start - timedelta(days=7)
        last_week_end = this_week_start

        # Helper to get stats for a period
        async def get_period_stats(start_date, end_date):
            trades_result = await db.execute(
                select(Trade).where(
                    and_(
                        Trade.broker_account_id == broker_account_id,
                        Trade.order_timestamp >= datetime.combine(start_date, datetime.min.time()),
                        Trade.order_timestamp < datetime.combine(end_date, datetime.min.time()),
                        Trade.status == 'COMPLETE'
                    )
                )
            )
            trades = trades_result.scalars().all()

            if not trades:
                return {
                    "total_pnl": 0,
                    "trade_count": 0,
                    "win_rate": 0,
                    "winners": 0,
                    "losers": 0,
                    "avg_win": 0,
                    "avg_loss": 0,
                }

            pnls = [float(t.pnl or 0) for t in trades]
            winners = [p for p in pnls if p > 0]
            losers = [p for p in pnls if p < 0]

            return {
                "total_pnl": sum(pnls),
                "trade_count": len(trades),
                "win_rate": (len(winners) / len(pnls) * 100) if pnls else 0,
                "winners": len(winners),
                "losers": len(losers),
                "avg_win": sum(winners) / len(winners) if winners else 0,
                "avg_loss": sum(losers) / len(losers) if losers else 0,
            }

        # Get stats for both weeks
        this_week = await get_period_stats(this_week_start, today + timedelta(days=1))
        last_week = await get_period_stats(last_week_start, last_week_end)

        # Get pattern alerts for both weeks
        async def get_pattern_count(start_date, end_date):
            result = await db.execute(
                select(func.count(RiskAlert.id)).where(
                    and_(
                        RiskAlert.broker_account_id == broker_account_id,
                        RiskAlert.detected_at >= datetime.combine(start_date, datetime.min.time()),
                        RiskAlert.detected_at < datetime.combine(end_date, datetime.min.time()),
                        RiskAlert.severity.in_(['danger', 'critical'])
                    )
                )
            )
            return result.scalar() or 0

        this_week_alerts = await get_pattern_count(this_week_start, today + timedelta(days=1))
        last_week_alerts = await get_pattern_count(last_week_start, last_week_end)

        # Calculate improvements
        def calc_change(current, previous, higher_is_better=True):
            if previous == 0:
                return {"change": 0, "improved": True, "percent": 0}
            change = current - previous
            percent = (change / abs(previous)) * 100
            improved = (change > 0) if higher_is_better else (change < 0)
            return {"change": change, "improved": improved, "percent": percent}

        return {
            "this_week": this_week,
            "last_week": last_week,
            "comparison": {
                "pnl": calc_change(this_week["total_pnl"], last_week["total_pnl"]),
                "win_rate": calc_change(this_week["win_rate"], last_week["win_rate"]),
                "trade_count": calc_change(this_week["trade_count"], last_week["trade_count"], False),
                "danger_alerts": calc_change(this_week_alerts, last_week_alerts, False),
            },
            "alerts": {
                "this_week": this_week_alerts,
                "last_week": last_week_alerts,
            },
            "streaks": await _get_discipline_streaks(broker_account_id, db),
        }
    except Exception as e:
        logger.error(f"Failed to get progress tracking: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def _get_discipline_streaks(account_id: UUID, db: AsyncSession):
    """Calculate discipline streaks."""
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select, and_
    from app.models.risk_alert import RiskAlert

    try:
        # Get all danger alerts in last 30 days
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        result = await db.execute(
            select(RiskAlert.detected_at).where(
                and_(
                    RiskAlert.broker_account_id == account_id,
                    RiskAlert.detected_at >= thirty_days_ago,
                    RiskAlert.pattern_type.in_(['revenge_trading', 'tilt', 'overtrading', 'martingale'])
                )
            ).order_by(RiskAlert.detected_at.desc())
        )
        alert_dates = [r[0].date() for r in result.fetchall()]

        # Calculate days since last bad pattern
        if not alert_dates:
            days_clean = 30
        else:
            days_clean = (datetime.now(timezone.utc).date() - alert_dates[0]).days

        return {
            "days_without_revenge": days_clean,
            "current_streak": days_clean,
            "best_streak": max(days_clean, 7),  # Simplified - would need history
        }
    except Exception:
        return {"days_without_revenge": 0, "current_streak": 0, "best_streak": 0}


# ─── NEW ANALYTICS ENDPOINTS (for Analytics page tabs) ───────────────────────


@router.get("/overview")
async def get_analytics_overview(
    days: int = Query(default=30, ge=1, le=365),
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(analytics_limiter),
):
    """
    Overview tab: KPIs, equity curve, daily P&L, streaks.
    Data source: CompletedTrade (flat-to-flat position lifecycle).
    """
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        result = await db.execute(
            select(CompletedTrade)
            .where(
                and_(
                    CompletedTrade.broker_account_id == broker_account_id,
                    CompletedTrade.exit_time >= cutoff,
                )
            )
            .order_by(CompletedTrade.exit_time)
        )
        trades = result.scalars().all()

        if not trades:
            return {
                "has_data": False,
                "period_days": days,
                "kpis": None,
                "equity_curve": [],
                "daily_pnl": [],
            }

        # --- KPIs ---
        pnls = [float(t.realized_pnl or 0) for t in trades]
        winners = [p for p in pnls if p > 0]
        losers = [p for p in pnls if p < 0]
        total_pnl = sum(pnls)

        avg_win = sum(winners) / len(winners) if winners else 0
        avg_loss = sum(losers) / len(losers) if losers else 0
        profit_factor = (sum(winners) / abs(sum(losers))) if losers else 0
        expectancy = total_pnl / len(trades) if trades else 0

        # Win/loss streaks
        max_win_streak = 0
        max_loss_streak = 0
        current_streak = 0
        current_streak_type = None
        cur_w = 0
        cur_l = 0
        for p in pnls:
            if p > 0:
                cur_w += 1
                cur_l = 0
                max_win_streak = max(max_win_streak, cur_w)
            elif p < 0:
                cur_l += 1
                cur_w = 0
                max_loss_streak = max(max_loss_streak, cur_l)
            else:
                cur_w = 0
                cur_l = 0

        # Current streak (from end)
        if pnls:
            last = pnls[-1]
            current_streak_type = "win" if last > 0 else "loss" if last < 0 else "flat"
            count = 0
            for p in reversed(pnls):
                if (current_streak_type == "win" and p > 0) or (current_streak_type == "loss" and p < 0):
                    count += 1
                else:
                    break
            current_streak = count

        # Daily aggregation for best/worst day and daily P&L
        daily_map: dict[str, dict] = {}
        for t in trades:
            day_str = t.exit_time.strftime("%Y-%m-%d") if t.exit_time else "unknown"
            if day_str not in daily_map:
                daily_map[day_str] = {"pnl": 0, "trades": 0, "wins": 0}
            pnl_val = float(t.realized_pnl or 0)
            daily_map[day_str]["pnl"] += pnl_val
            daily_map[day_str]["trades"] += 1
            if pnl_val > 0:
                daily_map[day_str]["wins"] += 1

        daily_pnl = [
            {
                "date": d,
                "pnl": round(v["pnl"], 2),
                "trades": v["trades"],
                "win_rate": round((v["wins"] / v["trades"]) * 100, 1) if v["trades"] else 0,
            }
            for d, v in sorted(daily_map.items())
        ]

        best_day = max(daily_pnl, key=lambda x: x["pnl"]) if daily_pnl else None
        worst_day = min(daily_pnl, key=lambda x: x["pnl"]) if daily_pnl else None

        # Equity curve (cumulative P&L)
        cumulative = 0
        equity_curve = []
        for dp in daily_pnl:
            cumulative += dp["pnl"]
            equity_curve.append({
                "date": dp["date"],
                "cumulative_pnl": round(cumulative, 2),
                "trade_count": dp["trades"],
            })

        # Avg trade duration
        durations = [t.duration_minutes for t in trades if t.duration_minutes and t.duration_minutes > 0]
        avg_duration_min = round(sum(durations) / len(durations)) if durations else 0

        # Win/loss day counts
        win_days = sum(1 for dp in daily_pnl if dp["pnl"] > 0)
        loss_days = sum(1 for dp in daily_pnl if dp["pnl"] < 0)

        # Largest single trade win/loss
        largest_win = max(pnls) if pnls else 0
        largest_loss = min(pnls) if pnls else 0

        return {
            "has_data": True,
            "period_days": days,
            "kpis": {
                "total_pnl": round(total_pnl, 2),
                "total_trades": len(trades),
                "winners": len(winners),
                "losers": len(losers),
                "win_rate": round((len(winners) / len(trades)) * 100, 1) if trades else 0,
                "avg_win": round(avg_win, 2),
                "avg_loss": round(avg_loss, 2),
                "profit_factor": round(profit_factor, 2),
                "expectancy": round(expectancy, 2),
                "best_day": best_day,
                "worst_day": worst_day,
                "max_win_streak": max_win_streak,
                "max_loss_streak": max_loss_streak,
                "current_streak": current_streak,
                "current_streak_type": current_streak_type,
                "avg_duration_min": avg_duration_min,
                "win_days": win_days,
                "loss_days": loss_days,
                "trading_days": len(daily_pnl),
                "largest_win": round(largest_win, 2),
                "largest_loss": round(largest_loss, 2),
            },
            "equity_curve": equity_curve,
            "daily_pnl": daily_pnl,
        }
    except Exception as e:
        logger.error(f"Failed to get analytics overview: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/performance")
async def get_analytics_performance(
    days: int = Query(default=30, ge=1, le=365),
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(analytics_limiter),
):
    """
    Performance tab: instrument, direction, time, position size breakdowns.
    Data source: CompletedTrade + CompletedTradeFeature.
    """
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        result = await db.execute(
            select(CompletedTrade, CompletedTradeFeature)
            .outerjoin(
                CompletedTradeFeature,
                CompletedTrade.id == CompletedTradeFeature.completed_trade_id,
            )
            .where(
                and_(
                    CompletedTrade.broker_account_id == broker_account_id,
                    CompletedTrade.exit_time >= cutoff,
                )
            )
            .order_by(CompletedTrade.exit_time)
        )
        rows = result.all()

        if not rows:
            return {"has_data": False, "period_days": days}

        # --- By Instrument ---
        instr_map: dict[str, dict] = {}
        for ct, feat in rows:
            sym = ct.tradingsymbol
            if sym not in instr_map:
                instr_map[sym] = {"trades": 0, "pnl": 0, "wins": 0, "duration_sum": 0}
            pnl_val = float(ct.realized_pnl or 0)
            instr_map[sym]["trades"] += 1
            instr_map[sym]["pnl"] += pnl_val
            if pnl_val > 0:
                instr_map[sym]["wins"] += 1
            instr_map[sym]["duration_sum"] += (ct.duration_minutes or 0)

        by_instrument = sorted(
            [
                {
                    "symbol": sym,
                    "trades": v["trades"],
                    "pnl": round(v["pnl"], 2),
                    "win_rate": round((v["wins"] / v["trades"]) * 100, 1) if v["trades"] else 0,
                    "avg_pnl": round(v["pnl"] / v["trades"], 2) if v["trades"] else 0,
                    "avg_duration_min": round(v["duration_sum"] / v["trades"]) if v["trades"] else 0,
                }
                for sym, v in instr_map.items()
            ],
            key=lambda x: x["trades"],
            reverse=True,
        )

        # --- By Direction ---
        dir_map: dict[str, dict] = {"LONG": {"trades": 0, "pnl": 0, "wins": 0}, "SHORT": {"trades": 0, "pnl": 0, "wins": 0}}
        for ct, feat in rows:
            d = ct.direction or "LONG"
            dir_map.setdefault(d, {"trades": 0, "pnl": 0, "wins": 0})
            pnl_val = float(ct.realized_pnl or 0)
            dir_map[d]["trades"] += 1
            dir_map[d]["pnl"] += pnl_val
            if pnl_val > 0:
                dir_map[d]["wins"] += 1

        by_direction = {
            k: {
                "trades": v["trades"],
                "pnl": round(v["pnl"], 2),
                "win_rate": round((v["wins"] / v["trades"]) * 100, 1) if v["trades"] else 0,
            }
            for k, v in dir_map.items()
        }

        # --- By Product ---
        prod_map: dict[str, dict] = {}
        for ct, feat in rows:
            p = ct.product or "OTHER"
            prod_map.setdefault(p, {"trades": 0, "pnl": 0, "wins": 0})
            pnl_val = float(ct.realized_pnl or 0)
            prod_map[p]["trades"] += 1
            prod_map[p]["pnl"] += pnl_val
            if pnl_val > 0:
                prod_map[p]["wins"] += 1

        by_product = {
            k: {
                "trades": v["trades"],
                "pnl": round(v["pnl"], 2),
                "wins": v["wins"],
                "losses": v["trades"] - v["wins"],
                "win_rate": round((v["wins"] / v["trades"]) * 100, 1) if v["trades"] else 0,
                "avg_pnl": round(v["pnl"] / v["trades"], 2) if v["trades"] else 0,
            }
            for k, v in prod_map.items()
        }

        # --- By Hour (from feature.entry_hour_ist) ---
        hour_map: dict[int, dict] = {}
        for ct, feat in rows:
            h = feat.entry_hour_ist if feat and feat.entry_hour_ist is not None else None
            if h is None and ct.entry_time:
                # Fallback: derive from entry_time (UTC+5:30)
                h = (ct.entry_time.hour + 5 + (1 if ct.entry_time.minute >= 30 else 0)) % 24
            if h is None:
                continue
            hour_map.setdefault(h, {"trades": 0, "pnl": 0, "wins": 0})
            pnl_val = float(ct.realized_pnl or 0)
            hour_map[h]["trades"] += 1
            hour_map[h]["pnl"] += pnl_val
            if pnl_val > 0:
                hour_map[h]["wins"] += 1

        by_hour = sorted(
            [
                {
                    "hour": h,
                    "label": f"{h}:00",
                    "trades": v["trades"],
                    "pnl": round(v["pnl"], 2),
                    "win_rate": round((v["wins"] / v["trades"]) * 100, 1) if v["trades"] else 0,
                }
                for h, v in hour_map.items()
            ],
            key=lambda x: x["hour"],
        )

        # --- By Day of Week (from feature.entry_day_of_week) ---
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        dow_map: dict[int, dict] = {}
        for ct, feat in rows:
            d = feat.entry_day_of_week if feat and feat.entry_day_of_week is not None else None
            if d is None and ct.entry_time:
                d = ct.entry_time.weekday()
            if d is None:
                continue
            dow_map.setdefault(d, {"trades": 0, "pnl": 0, "wins": 0})
            pnl_val = float(ct.realized_pnl or 0)
            dow_map[d]["trades"] += 1
            dow_map[d]["pnl"] += pnl_val
            if pnl_val > 0:
                dow_map[d]["wins"] += 1

        by_day_of_week = sorted(
            [
                {
                    "day": d,
                    "name": day_names[d] if d < 7 else f"Day {d}",
                    "trades": v["trades"],
                    "pnl": round(v["pnl"], 2),
                    "win_rate": round((v["wins"] / v["trades"]) * 100, 1) if v["trades"] else 0,
                }
                for d, v in dow_map.items()
            ],
            key=lambda x: x["day"],
        )

        # --- Position Size Analysis (from feature.size_relative_to_avg) ---
        size_buckets: dict[str, dict] = {
            "Small (<0.7x)": {"trades": 0, "pnl": 0, "wins": 0},
            "Medium (0.7-1.3x)": {"trades": 0, "pnl": 0, "wins": 0},
            "Large (>1.3x)": {"trades": 0, "pnl": 0, "wins": 0},
        }
        for ct, feat in rows:
            s = float(feat.size_relative_to_avg) if feat and feat.size_relative_to_avg is not None else 1.0
            if s < 0.7:
                bucket = "Small (<0.7x)"
            elif s <= 1.3:
                bucket = "Medium (0.7-1.3x)"
            else:
                bucket = "Large (>1.3x)"
            pnl_val = float(ct.realized_pnl or 0)
            size_buckets[bucket]["trades"] += 1
            size_buckets[bucket]["pnl"] += pnl_val
            if pnl_val > 0:
                size_buckets[bucket]["wins"] += 1

        size_analysis = [
            {
                "bucket": k,
                "trades": v["trades"],
                "pnl": round(v["pnl"], 2),
                "win_rate": round((v["wins"] / v["trades"]) * 100, 1) if v["trades"] else 0,
                "avg_pnl": round(v["pnl"] / v["trades"], 2) if v["trades"] else 0,
            }
            for k, v in size_buckets.items()
            if v["trades"] > 0
        ]

        return {
            "has_data": True,
            "period_days": days,
            "total_trades": len(rows),
            "by_instrument": by_instrument,
            "by_direction": by_direction,
            "by_product": by_product,
            "by_hour": by_hour,
            "by_day_of_week": by_day_of_week,
            "size_analysis": size_analysis,
        }
    except Exception as e:
        logger.error(f"Failed to get analytics performance: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/risk-metrics")
async def get_analytics_risk_metrics(
    days: int = Query(default=30, ge=1, le=365),
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(analytics_limiter),
):
    """
    Risk tab: drawdown, VaR, volatility, streaks, alert history.
    Data source: CompletedTrade + RiskAlert.
    """
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Fetch completed trades
        result = await db.execute(
            select(CompletedTrade)
            .where(
                and_(
                    CompletedTrade.broker_account_id == broker_account_id,
                    CompletedTrade.exit_time >= cutoff,
                )
            )
            .order_by(CompletedTrade.exit_time)
        )
        trades = result.scalars().all()

        if not trades:
            return {"has_data": False, "period_days": days}

        pnls = [float(t.realized_pnl or 0) for t in trades]
        winners = [p for p in pnls if p > 0]
        losers = [p for p in pnls if p < 0]

        # --- Daily P&L for volatility and VaR ---
        daily_pnl_map: dict[str, float] = {}
        for t in trades:
            day_str = t.exit_time.strftime("%Y-%m-%d") if t.exit_time else "unknown"
            daily_pnl_map[day_str] = daily_pnl_map.get(day_str, 0) + float(t.realized_pnl or 0)

        daily_pnls = sorted(daily_pnl_map.values())
        daily_volatility = 0
        var_95 = 0
        if len(daily_pnls) >= 2:
            mean_daily = sum(daily_pnls) / len(daily_pnls)
            variance = sum((x - mean_daily) ** 2 for x in daily_pnls) / (len(daily_pnls) - 1)
            daily_volatility = round(math.sqrt(variance), 2)
            # VaR at 95%: 5th percentile of daily P&L
            idx_5 = max(0, int(len(daily_pnls) * 0.05))
            var_95 = round(daily_pnls[idx_5], 2)

        # --- Drawdown calculation ---
        cumulative = 0
        peak = 0
        max_drawdown = 0
        max_dd_start = None
        max_dd_end = None
        current_dd_start = None
        drawdown_periods = []
        current_dd_depth = 0

        sorted_daily = sorted(daily_pnl_map.items())
        for date_str, day_pnl in sorted_daily:
            cumulative += day_pnl
            if cumulative > peak:
                # Recovery from drawdown
                if current_dd_depth < -0.01:
                    drawdown_periods.append({
                        "start": current_dd_start,
                        "end": date_str,
                        "depth": round(current_dd_depth, 2),
                        "duration_days": _days_between(current_dd_start, date_str),
                    })
                peak = cumulative
                current_dd_start = date_str
                current_dd_depth = 0
            else:
                dd = cumulative - peak
                if dd < current_dd_depth:
                    current_dd_depth = dd
                if dd < max_drawdown:
                    max_drawdown = dd
                    max_dd_start = current_dd_start
                    max_dd_end = date_str

        # If still in drawdown at the end
        if current_dd_depth < -0.01:
            drawdown_periods.append({
                "start": current_dd_start,
                "end": sorted_daily[-1][0] if sorted_daily else None,
                "depth": round(current_dd_depth, 2),
                "duration_days": _days_between(current_dd_start, sorted_daily[-1][0]) if sorted_daily else 0,
            })

        # --- Consecutive win/loss streaks ---
        max_win_streak = 0
        max_loss_streak = 0
        cur_w = 0
        cur_l = 0
        for p in pnls:
            if p > 0:
                cur_w += 1
                cur_l = 0
                max_win_streak = max(max_win_streak, cur_w)
            elif p < 0:
                cur_l += 1
                cur_w = 0
                max_loss_streak = max(max_loss_streak, cur_l)
            else:
                cur_w = 0
                cur_l = 0

        # --- Risk-reward ratio ---
        avg_win = sum(winners) / len(winners) if winners else 0
        avg_loss = abs(sum(losers) / len(losers)) if losers else 0
        risk_reward = round(avg_win / avg_loss, 2) if avg_loss > 0 else 0

        # --- Risk Alert History ---
        alert_result = await db.execute(
            select(
                RiskAlert.pattern_type,
                func.count(RiskAlert.id).label("count"),
                func.max(RiskAlert.detected_at).label("last_detected"),
            )
            .where(
                and_(
                    RiskAlert.broker_account_id == broker_account_id,
                    RiskAlert.detected_at >= cutoff,
                )
            )
            .group_by(RiskAlert.pattern_type)
            .order_by(func.count(RiskAlert.id).desc())
        )
        alert_rows = alert_result.all()
        alerts_summary = [
            {
                "pattern_type": r.pattern_type,
                "count": r.count,
                "last_detected": r.last_detected.isoformat() if r.last_detected else None,
            }
            for r in alert_rows
        ]

        # Recent alerts (last 20)
        recent_alerts_result = await db.execute(
            select(RiskAlert)
            .where(
                and_(
                    RiskAlert.broker_account_id == broker_account_id,
                    RiskAlert.detected_at >= cutoff,
                )
            )
            .order_by(RiskAlert.detected_at.desc())
            .limit(20)
        )
        recent_alerts = [
            {
                "id": str(a.id),
                "pattern_type": a.pattern_type,
                "severity": a.severity,
                "message": a.message,
                "detected_at": a.detected_at.isoformat() if a.detected_at else None,
                "acknowledged": a.acknowledged_at is not None,
            }
            for a in recent_alerts_result.scalars().all()
        ]

        return {
            "has_data": True,
            "period_days": days,
            "max_drawdown": {
                "amount": round(max_drawdown, 2),
                "start_date": max_dd_start,
                "end_date": max_dd_end,
            },
            "drawdown_periods": drawdown_periods[-5:],  # Last 5
            "daily_volatility": daily_volatility,
            "var_95": var_95,
            "risk_reward_ratio": risk_reward,
            "consecutive_max": {
                "wins": max_win_streak,
                "losses": max_loss_streak,
            },
            "alerts_summary": alerts_summary,
            "recent_alerts": recent_alerts,
        }
    except Exception as e:
        logger.error(f"Failed to get risk metrics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/journal-correlation")
async def get_journal_correlation(
    days: int = 90,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(analytics_limiter),
):
    """
    Behavior tab supplement: emotion → P&L correlation from journal entries.
    Data source: JournalEntry joined with Trade for accurate P&L.
    """
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Join JournalEntry with Trade for accurate, up-to-date P&L
        result = await db.execute(
            select(JournalEntry, Trade.pnl)
            .outerjoin(Trade, JournalEntry.trade_id == Trade.id)
            .where(
                and_(
                    JournalEntry.broker_account_id == broker_account_id,
                    JournalEntry.created_at >= cutoff,
                    JournalEntry.trade_id.is_not(None),
                )
            )
            .order_by(JournalEntry.created_at.desc())
        )
        rows = result.all()

        if not rows:
            return {"has_data": False, "period_days": days, "total_journaled": 0}

        # Group by emotion tag
        emotion_stats: dict[str, dict] = {}
        entry_type_stats: dict[str, dict] = {}

        for entry, trade_pnl_from_db in rows:
            # Prefer fresh P&L from Trade table; fall back to journal snapshot
            pnl_val = 0
            if trade_pnl_from_db is not None:
                pnl_val = float(trade_pnl_from_db)
            elif entry.trade_pnl:
                try:
                    pnl_val = float(entry.trade_pnl)
                except (ValueError, TypeError):
                    pass

            # Process emotion tags
            tags = entry.emotion_tags or []
            for tag in tags:
                emotion_stats.setdefault(tag, {"count": 0, "pnl_sum": 0, "wins": 0})
                emotion_stats[tag]["count"] += 1
                emotion_stats[tag]["pnl_sum"] += pnl_val
                if pnl_val > 0:
                    emotion_stats[tag]["wins"] += 1

            # Process entry type
            et = entry.entry_type or "trade"
            entry_type_stats.setdefault(et, {"count": 0, "pnl_sum": 0, "wins": 0})
            entry_type_stats[et]["count"] += 1
            entry_type_stats[et]["pnl_sum"] += pnl_val
            if pnl_val > 0:
                entry_type_stats[et]["wins"] += 1

        by_emotion = sorted(
            [
                {
                    "emotion": tag,
                    "trade_count": v["count"],
                    "avg_pnl": round(v["pnl_sum"] / v["count"], 2) if v["count"] else 0,
                    "total_pnl": round(v["pnl_sum"], 2),
                    "win_rate": round((v["wins"] / v["count"]) * 100, 1) if v["count"] else 0,
                }
                for tag, v in emotion_stats.items()
            ],
            key=lambda x: x["trade_count"],
            reverse=True,
        )

        by_entry_type = [
            {
                "entry_type": et,
                "trade_count": v["count"],
                "avg_pnl": round(v["pnl_sum"] / v["count"], 2) if v["count"] else 0,
                "win_rate": round((v["wins"] / v["count"]) * 100, 1) if v["count"] else 0,
            }
            for et, v in entry_type_stats.items()
        ]

        return {
            "has_data": True,
            "period_days": days,
            "total_journaled": len(rows),
            "by_emotion": by_emotion,
            "by_entry_type": by_entry_type,
        }
    except Exception as e:
        logger.error(f"Failed to get journal correlation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/ai-insights")
async def get_ai_insights(
    days: int = Query(default=30, ge=1, le=365),
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(analytics_limiter),
):
    """
    AI-powered insights: personalized danger windows, pattern cost breakdown,
    and actionable recommendations aggregated from multiple data sources.
    """
    try:
        from app.services.ai_personalization_service import ai_personalization_service

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # 1. Get personalized insights (danger hours, problem symbols, etc.)
        personalization = await ai_personalization_service.get_personalized_insights(
            broker_account_id=broker_account_id, db=db
        )

        # 2. Get pattern cost breakdown from risk alerts
        alert_cost_result = await db.execute(
            select(
                RiskAlert.pattern_type,
                func.count(RiskAlert.id).label("occurrences"),
            )
            .where(
                and_(
                    RiskAlert.broker_account_id == broker_account_id,
                    RiskAlert.detected_at >= cutoff,
                )
            )
            .group_by(RiskAlert.pattern_type)
            .order_by(func.count(RiskAlert.id).desc())
        )
        pattern_frequency = [
            {"pattern": r.pattern_type, "occurrences": r.occurrences}
            for r in alert_cost_result.all()
        ]

        # 3. Calculate recent trading intensity for burnout detection
        result = await db.execute(
            select(CompletedTrade.exit_time)
            .where(
                and_(
                    CompletedTrade.broker_account_id == broker_account_id,
                    CompletedTrade.exit_time >= cutoff,
                )
            )
            .order_by(CompletedTrade.exit_time.desc())
        )
        trade_times = [r[0] for r in result.all() if r[0]]

        # Trades per day distribution
        daily_counts: dict[str, int] = {}
        for t in trade_times:
            d = t.strftime("%Y-%m-%d")
            daily_counts[d] = daily_counts.get(d, 0) + 1

        avg_daily_trades = round(sum(daily_counts.values()) / len(daily_counts), 1) if daily_counts else 0
        max_daily_trades = max(daily_counts.values()) if daily_counts else 0
        overtrade_days = sum(1 for c in daily_counts.values() if c > avg_daily_trades * 1.5) if daily_counts else 0

        # 4. Get real-time pattern predictions
        from app.services.pattern_prediction_service import pattern_prediction_service
        try:
            prediction_data = await pattern_prediction_service.predict_patterns(
                broker_account_id, db
            )
            predictions = prediction_data.get("predictions", {})
            risk_assessment = prediction_data.get("risk_assessment", {})
        except Exception as pred_err:
            logger.warning(f"Pattern prediction failed (non-fatal): {pred_err}")
            predictions = {}
            risk_assessment = {}

        return {
            "has_data": True,
            "period_days": days,
            "personalization": personalization,
            "pattern_frequency": pattern_frequency,
            "trading_intensity": {
                "avg_daily_trades": avg_daily_trades,
                "max_daily_trades": max_daily_trades,
                "active_days": len(daily_counts),
                "overtrade_days": overtrade_days,
            },
            "predictions": predictions,
            "risk_assessment": risk_assessment,
        }
    except Exception as e:
        logger.error(f"Failed to get AI insights: {e}")
        # Return empty rather than error — this is supplementary data
        return {
            "has_data": False,
            "period_days": days,
            "personalization": None,
            "pattern_frequency": [],
            "trading_intensity": None,
            "predictions": {},
            "risk_assessment": {},
        }


@router.get("/ai-summary")
async def get_ai_summary(
    tab: str = "overview",
    days: int = Query(default=30, ge=1, le=365),
    force: bool = False,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(analytics_limiter),
):
    """
    AI-generated narrative summary for an analytics tab.
    Uses 24hr caching in UserProfile.ai_cache to minimize LLM costs.
    Hybrid: LLM when OPENROUTER_API_KEY is set, rule-based templates otherwise.
    """
    from app.models.user_profile import UserProfile
    from app.services.ai_service import ai_service

    valid_tabs = ("overview", "behavior", "performance", "risk")
    if tab not in valid_tabs:
        raise HTTPException(status_code=400, detail=f"tab must be one of {valid_tabs}")

    try:
        # 1. Check cache
        cache_key = f"{tab}_{days}"
        if not force:
            profile_result = await db.execute(
                select(UserProfile).where(UserProfile.broker_account_id == broker_account_id)
            )
            profile = profile_result.scalar_one_or_none()

            if profile and profile.ai_cache:
                cached = profile.ai_cache.get(cache_key)
                if cached:
                    cached_at = cached.get("generated_at", "")
                    try:
                        generated = datetime.fromisoformat(cached_at)
                        if datetime.now(timezone.utc) - generated < timedelta(hours=24):
                            return {
                                "narrative": cached.get("narrative", ""),
                                "key_insight": cached.get("key_insight", ""),
                                "action_item": cached.get("action_item", ""),
                                "cached": True,
                                "generated_at": cached_at,
                            }
                    except (ValueError, TypeError):
                        pass

        # 2. Gather tab-specific data
        if tab == "overview":
            data_result = await db.execute(
                select(CompletedTrade)
                .where(and_(
                    CompletedTrade.broker_account_id == broker_account_id,
                    CompletedTrade.exit_time >= datetime.now(timezone.utc) - timedelta(days=days),
                ))
                .order_by(CompletedTrade.exit_time)
            )
            trades = data_result.scalars().all()
            pnls = [float(t.realized_pnl or 0) for t in trades]
            winners = [p for p in pnls if p > 0]
            losers = [p for p in pnls if p < 0]
            tab_data = {
                "kpis": {
                    "total_pnl": sum(pnls),
                    "total_trades": len(trades),
                    "win_rate": round((len(winners) / len(trades)) * 100, 1) if trades else 0,
                    "profit_factor": round(sum(winners) / abs(sum(losers)), 2) if losers else 0,
                    "expectancy": round(sum(pnls) / len(trades), 2) if trades else 0,
                    "largest_win": max(pnls) if pnls else 0,
                    "largest_loss": min(pnls) if pnls else 0,
                    "max_win_streak": 0,
                    "max_loss_streak": 0,
                }
            }
        elif tab == "behavior":
            from app.services.behavioral_analysis_service import BehavioralAnalysisService
            svc = BehavioralAnalysisService()
            analysis = await svc.analyze_behavior(broker_account_id, db, days)
            tab_data = {
                "emotional_tax": analysis.get("emotional_tax", 0),
                "behavior_score": analysis.get("behavior_score"),
            }
            behavior_score = analysis.get("behavior_score")
            patterns = [p["name"] for p in analysis.get("patterns_detected", []) if not p.get("is_positive")]
        elif tab == "performance":
            # Reuse performance endpoint logic inline (minimal data needed for narrative)
            perf_result = await db.execute(
                select(CompletedTrade)
                .where(and_(
                    CompletedTrade.broker_account_id == broker_account_id,
                    CompletedTrade.exit_time >= datetime.now(timezone.utc) - timedelta(days=days),
                ))
            )
            trades = perf_result.scalars().all()
            instr_map = {}
            dir_map = {"LONG": {"trades": 0, "pnl": 0, "wins": 0}, "SHORT": {"trades": 0, "pnl": 0, "wins": 0}}
            for t in trades:
                sym = t.tradingsymbol
                instr_map.setdefault(sym, {"trades": 0, "pnl": 0, "wins": 0})
                pv = float(t.realized_pnl or 0)
                instr_map[sym]["trades"] += 1
                instr_map[sym]["pnl"] += pv
                if pv > 0:
                    instr_map[sym]["wins"] += 1
                d = t.direction or "LONG"
                dir_map.setdefault(d, {"trades": 0, "pnl": 0, "wins": 0})
                dir_map[d]["trades"] += 1
                dir_map[d]["pnl"] += pv
                if pv > 0:
                    dir_map[d]["wins"] += 1

            by_instr = sorted(
                [{"symbol": s, "trades": v["trades"], "win_rate": round((v["wins"] / v["trades"]) * 100, 1) if v["trades"] else 0}
                 for s, v in instr_map.items()],
                key=lambda x: x["trades"], reverse=True,
            )
            by_dir = {k: {"win_rate": round((v["wins"] / v["trades"]) * 100, 1) if v["trades"] else 0} for k, v in dir_map.items()}
            tab_data = {"total_trades": len(trades), "by_instrument": by_instr, "by_direction": by_dir}
        elif tab == "risk":
            risk_result = await db.execute(
                select(CompletedTrade)
                .where(and_(
                    CompletedTrade.broker_account_id == broker_account_id,
                    CompletedTrade.exit_time >= datetime.now(timezone.utc) - timedelta(days=days),
                ))
                .order_by(CompletedTrade.exit_time)
            )
            trades = risk_result.scalars().all()
            pnls = [float(t.realized_pnl or 0) for t in trades]
            winners = [p for p in pnls if p > 0]
            losers = [p for p in pnls if p < 0]

            # Max drawdown
            cumulative = 0
            peak = 0
            max_dd = 0
            for p in pnls:
                cumulative += p
                peak = max(peak, cumulative)
                max_dd = min(max_dd, cumulative - peak)

            # Daily vol
            daily_map = {}
            for t in trades:
                ds = t.exit_time.strftime("%Y-%m-%d") if t.exit_time else "x"
                daily_map[ds] = daily_map.get(ds, 0) + float(t.realized_pnl or 0)
            daily_vals = list(daily_map.values())
            if len(daily_vals) >= 2:
                mean_d = sum(daily_vals) / len(daily_vals)
                var = sum((x - mean_d) ** 2 for x in daily_vals) / (len(daily_vals) - 1)
                vol = round(var ** 0.5, 2)
            else:
                vol = 0

            avg_win = sum(winners) / len(winners) if winners else 0
            avg_loss = abs(sum(losers) / len(losers)) if losers else 0
            rr = round(avg_win / avg_loss, 2) if avg_loss > 0 else 0

            tab_data = {
                "max_drawdown": {"amount": round(max_dd, 2)},
                "daily_volatility": vol,
                "var_95": round(sorted(daily_vals)[max(0, int(len(daily_vals) * 0.05))], 2) if daily_vals else 0,
                "risk_reward_ratio": rr,
            }
        else:
            tab_data = {}

        # 3. Fire Celery task to generate narrative — non-blocking.
        # The task writes the result to UserProfile.ai_cache; the next
        # request will return it as a cache hit.
        bscore = tab_data.get("behavior_score") if tab == "behavior" else None
        pats = patterns if tab == "behavior" else None

        try:
            from app.tasks.report_tasks import generate_analytics_narrative_task
            generate_analytics_narrative_task.delay(
                str(broker_account_id),
                tab,
                days,
                tab_data,
                bscore,
                pats,
            )
        except Exception as task_err:
            logger.warning(f"Could not queue narrative generation: {task_err}")

        # 4. Return immediately with "generating" status.
        # Frontend shows a spinner; it re-polls after ~5s (same pattern as coach insight).
        return {
            "narrative": None,
            "key_insight": None,
            "action_item": None,
            "cached": False,
            "status": "generating",
            "generated_at": None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get AI summary: {e}")
        return {
            "narrative": None,
            "key_insight": None,
            "action_item": None,
            "cached": False,
            "generated_at": None,
        }


def _days_between(start_str: str | None, end_str: str | None) -> int:
    """Calculate days between two date strings."""
    if not start_str or not end_str:
        return 0
    try:
        start = datetime.strptime(start_str, "%Y-%m-%d")
        end = datetime.strptime(end_str, "%Y-%m-%d")
        return (end - start).days
    except (ValueError, TypeError):
        return 0


@router.get("/edge-confidence")
async def get_edge_confidence(
    days: int = Query(default=30, ge=1, le=365),
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(analytics_limiter),
):
    """Wilson confidence interval on win rate — tells you if your edge is real or noise."""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await db.execute(
            select(CompletedTrade)
            .where(and_(
                CompletedTrade.broker_account_id == broker_account_id,
                CompletedTrade.exit_time >= cutoff,
            ))
        )
        trades = result.scalars().all()

        n = len(trades)
        if n == 0:
            return {"has_data": False}

        wins = sum(1 for t in trades if float(t.realized_pnl or 0) > 0)
        p = wins / n
        z = 1.96  # 95% CI

        # Wilson interval
        denominator = 1 + z * z / n
        center = (p + z * z / (2 * n)) / denominator
        half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denominator

        lower = max(0.0, center - half)
        upper = min(1.0, center + half)

        # Interpretation
        if n < 20:
            verdict = "too_few"
            message = f"Only {n} trades — need at least 20 for a reliable reading."
        elif lower > 0.50:
            verdict = "real_edge"
            message = f"Your win rate is statistically above 50%. This looks like a real edge."
        elif upper < 0.50:
            verdict = "losing_edge"
            message = f"Your win rate is statistically below 50%. The losses are not random variance."
        else:
            verdict = "inconclusive"
            message = f"Win rate could be 50/50 variance with {n} trades. Need more data to confirm edge."

        return {
            "has_data": True,
            "n": n,
            "wins": wins,
            "observed_win_rate": round(p * 100, 1),
            "ci_lower": round(lower * 100, 1),
            "ci_upper": round(upper * 100, 1),
            "ci_center": round(center * 100, 1),
            "verdict": verdict,
            "message": message,
            "is_reliable": n >= 30,
        }
    except Exception as e:
        logger.error(f"Failed to get edge confidence: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/conditional-performance")
async def get_conditional_performance(
    days: int = Query(default=30, ge=1, le=365),
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(analytics_limiter),
):
    """How win rate changes under specific conditions (narrative style)."""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await db.execute(
            select(CompletedTrade, CompletedTradeFeature)
            .outerjoin(CompletedTradeFeature, CompletedTrade.id == CompletedTradeFeature.completed_trade_id)
            .where(and_(
                CompletedTrade.broker_account_id == broker_account_id,
                CompletedTrade.exit_time >= cutoff,
            ))
        )
        rows = result.all()

        if not rows:
            return {"has_data": False}

        def bucket_stats(condition_fn):
            wins, total = 0, 0
            for ct, feat in rows:
                if condition_fn(ct, feat):
                    total += 1
                    if float(ct.realized_pnl or 0) > 0:
                        wins += 1
            wr = round(wins / total * 100, 1) if total else 0
            avg_pnl = 0
            if total:
                pnls = [float(ct.realized_pnl or 0) for ct, feat in rows if condition_fn(ct, feat)]
                avg_pnl = round(sum(pnls) / len(pnls), 2) if pnls else 0
            return {"wins": wins, "total": total, "win_rate": wr, "avg_pnl": avg_pnl}

        # Baseline
        all_pnls = [float(ct.realized_pnl or 0) for ct, _ in rows]
        baseline_wr = round(sum(1 for p in all_pnls if p > 0) / len(all_pnls) * 100, 1) if all_pnls else 0
        baseline_avg = round(sum(all_pnls) / len(all_pnls), 2) if all_pnls else 0

        conditions = []

        # 1. After a loss
        s = bucket_stats(lambda ct, feat: feat is not None and bool(feat.entry_after_loss))
        if s["total"] >= 5:
            delta = round(s["win_rate"] - baseline_wr, 1)
            direction = "drops" if delta < 0 else "improves"
            conditions.append({
                "key": "after_loss",
                "label": "After a loss",
                "win_rate": s["win_rate"],
                "avg_pnl": s["avg_pnl"],
                "trade_count": s["total"],
                "delta_vs_baseline": delta,
                "narrative": f"Your win rate {direction} to {s['win_rate']}% after a loss (vs {baseline_wr}% baseline) across {s['total']} trades.",
            })

        # 2. First 30 minutes (9:15–9:45 IST = hour 9)
        s = bucket_stats(lambda ct, feat: (feat.entry_hour_ist == 9 if feat and feat.entry_hour_ist is not None else False))
        if s["total"] >= 5:
            delta = round(s["win_rate"] - baseline_wr, 1)
            direction = "drops" if delta < 0 else "improves"
            conditions.append({
                "key": "first_30min",
                "label": "Opening 30 minutes",
                "win_rate": s["win_rate"],
                "avg_pnl": s["avg_pnl"],
                "trade_count": s["total"],
                "delta_vs_baseline": delta,
                "narrative": f"In the opening 30 minutes your win rate {direction} to {s['win_rate']}% (vs {baseline_wr}% baseline) across {s['total']} trades.",
            })

        # 3. Expiry day
        s = bucket_stats(lambda ct, feat: feat is not None and bool(feat.is_expiry_day))
        if s["total"] >= 3:
            delta = round(s["win_rate"] - baseline_wr, 1)
            direction = "drops" if delta < 0 else "improves"
            conditions.append({
                "key": "expiry_day",
                "label": "Expiry day",
                "win_rate": s["win_rate"],
                "avg_pnl": s["avg_pnl"],
                "trade_count": s["total"],
                "delta_vs_baseline": delta,
                "narrative": f"On expiry days your win rate {direction} to {s['win_rate']}% (vs {baseline_wr}% baseline) across {s['total']} trades.",
            })

        # 4. Oversized positions (>1.5x avg)
        s = bucket_stats(lambda ct, feat: float(feat.size_relative_to_avg) > 1.5 if feat and feat.size_relative_to_avg is not None else False)
        if s["total"] >= 3:
            delta = round(s["win_rate"] - baseline_wr, 1)
            direction = "drops" if delta < 0 else "improves"
            conditions.append({
                "key": "large_position",
                "label": "Oversized positions (>1.5×)",
                "win_rate": s["win_rate"],
                "avg_pnl": s["avg_pnl"],
                "trade_count": s["total"],
                "delta_vs_baseline": delta,
                "narrative": f"When you size up (>1.5× avg) your win rate {direction} to {s['win_rate']}% (vs {baseline_wr}% baseline) across {s['total']} trades.",
            })

        # 5. Quick re-entry (<20 min since last round-trip)
        s = bucket_stats(lambda ct, feat: float(feat.minutes_since_last_round) < 20 if feat and feat.minutes_since_last_round is not None else False)
        if s["total"] >= 5:
            delta = round(s["win_rate"] - baseline_wr, 1)
            direction = "drops" if delta < 0 else "improves"
            conditions.append({
                "key": "quick_reentry",
                "label": "Quick re-entry (<20 min)",
                "win_rate": s["win_rate"],
                "avg_pnl": s["avg_pnl"],
                "trade_count": s["total"],
                "delta_vs_baseline": delta,
                "narrative": f"Quick re-entries (<20 min) show win rate {direction} to {s['win_rate']}% (vs {baseline_wr}% baseline) across {s['total']} trades.",
            })

        # Sort by absolute delta (most impactful first)
        conditions.sort(key=lambda c: abs(c["delta_vs_baseline"]), reverse=True)

        return {
            "has_data": True,
            "total_trades": len(rows),
            "baseline_win_rate": baseline_wr,
            "baseline_avg_pnl": baseline_avg,
            "conditions": conditions,
        }
    except Exception as e:
        logger.error(f"Failed to get conditional performance: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/critical-trades")
async def get_critical_trades(
    days: int = Query(default=30, ge=1, le=365),
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(analytics_limiter),
):
    """Critical trades: large losses, behavioral alerts, or oversized positions."""
    try:
        from app.models.behavioral_event import BehavioralEvent

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Fetch completed trades + features
        result = await db.execute(
            select(CompletedTrade, CompletedTradeFeature)
            .outerjoin(CompletedTradeFeature, CompletedTrade.id == CompletedTradeFeature.completed_trade_id)
            .where(and_(
                CompletedTrade.broker_account_id == broker_account_id,
                CompletedTrade.exit_time >= cutoff,
            ))
            .order_by(CompletedTrade.exit_time.desc())
        )
        rows = result.all()

        if not rows:
            return {"has_data": False, "trades": []}

        # Compute baseline avg loss to flag large losses
        pnls = [float(ct.realized_pnl or 0) for ct, _ in rows]
        losses = [p for p in pnls if p < 0]
        avg_loss = sum(losses) / len(losses) if losses else 0  # negative number
        loss_threshold = avg_loss * 2  # 2x avg loss = critical (more negative)

        # Fetch all behavioral events in period
        be_result = await db.execute(
            select(BehavioralEvent)
            .where(and_(
                BehavioralEvent.broker_account_id == broker_account_id,
                BehavioralEvent.detected_at >= cutoff,
            ))
            .order_by(BehavioralEvent.detected_at)
        )
        behavioral_events = be_result.scalars().all()

        # Build critical trades list
        critical = []
        for ct, feat in rows:
            pnl = float(ct.realized_pnl or 0)
            reasons = []

            # Reason 1: Large loss
            if pnl < 0 and avg_loss != 0 and pnl <= loss_threshold:
                reasons.append({"type": "large_loss", "label": "Large loss (>2× avg)"})

            # Reason 2: Behavioral alert during this trade
            if ct.entry_time and ct.exit_time:
                trade_end = ct.exit_time + timedelta(minutes=10)
                alerts_during = [
                    be for be in behavioral_events
                    if be.detected_at and ct.entry_time <= be.detected_at <= trade_end
                ]
                for be in alerts_during:
                    reasons.append({
                        "type": "behavioral_alert",
                        "label": be.event_type.replace("_", " ").title() if be.event_type else "Alert",
                        "event_type": be.event_type,
                        "severity": be.severity,
                    })

            # Reason 3: Oversized position
            if feat and feat.size_relative_to_avg is not None and float(feat.size_relative_to_avg) >= 1.5:
                reasons.append({
                    "type": "oversized",
                    "label": f"Position {float(feat.size_relative_to_avg):.1f}× avg size",
                })

            # Reason 4: Quick re-entry after loss
            if feat and feat.entry_after_loss and feat.minutes_since_last_round is not None and float(feat.minutes_since_last_round) < 20:
                reasons.append({"type": "quick_reentry", "label": f"Re-entered {float(feat.minutes_since_last_round):.0f}m after loss"})

            if reasons:
                critical.append({
                    "id": str(ct.id),
                    "tradingsymbol": ct.tradingsymbol,
                    "entry_time": ct.entry_time.isoformat() if ct.entry_time else None,
                    "exit_time": ct.exit_time.isoformat() if ct.exit_time else None,
                    "direction": ct.direction,
                    "realized_pnl": round(pnl, 2),
                    "duration_minutes": ct.duration_minutes,
                    "reasons": reasons,
                    "severity": "critical" if any(r["type"] == "large_loss" for r in reasons) or len(reasons) >= 3
                                else "high" if len(reasons) >= 2
                                else "medium",
                })

        # Sort by PnL ascending (worst first) then limit
        critical.sort(key=lambda t: t["realized_pnl"])
        critical = critical[:50]  # max 50

        return {
            "has_data": len(critical) > 0,
            "total_critical": len(critical),
            "avg_loss_threshold": round(loss_threshold, 2),
            "trades": critical,
        }
    except Exception as e:
        logger.error(f"Failed to get critical trades: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/timing-heatmap")
async def get_timing_heatmap(
    days: int = Query(default=30, ge=1, le=365),
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(analytics_limiter),
):
    """2D performance grid: entry hour (IST) × day of week."""
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await db.execute(
            select(CompletedTrade, CompletedTradeFeature)
            .outerjoin(CompletedTradeFeature, CompletedTrade.id == CompletedTradeFeature.completed_trade_id)
            .where(and_(
                CompletedTrade.broker_account_id == broker_account_id,
                CompletedTrade.exit_time >= cutoff,
            ))
        )
        rows = result.all()

        if not rows:
            return {"has_data": False, "cells": [], "by_hour": [], "by_day": []}

        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri"]

        # 2D grid: hour 9–15, day 0–4
        grid: dict[tuple, dict] = {}
        for ct, feat in rows:
            h = feat.entry_hour_ist if feat and feat.entry_hour_ist is not None else None
            if h is None and ct.entry_time:
                # Convert UTC to IST (UTC+5:30)
                ist_hour = (ct.entry_time.hour * 60 + ct.entry_time.minute + 330) // 60 % 24
                h = ist_hour
            d = feat.entry_day_of_week if feat and feat.entry_day_of_week is not None else None
            if d is None and ct.entry_time:
                d = ct.entry_time.weekday()
            if h is None or d is None or h < 9 or h > 15 or d > 4:
                continue
            key = (h, d)
            if key not in grid:
                grid[key] = {"trades": 0, "pnl": 0.0, "wins": 0}
            pnl_val = float(ct.realized_pnl or 0)
            grid[key]["trades"] += 1
            grid[key]["pnl"] += pnl_val
            if pnl_val > 0:
                grid[key]["wins"] += 1

        cells = [
            {
                "hour": h,
                "day": d,
                "day_name": day_names[d] if d < 5 else f"D{d}",
                "hour_label": f"{h}:00",
                "trades": v["trades"],
                "pnl": round(v["pnl"], 2),
                "avg_pnl": round(v["pnl"] / v["trades"], 2) if v["trades"] else 0,
                "win_rate": round(v["wins"] / v["trades"] * 100, 1) if v["trades"] else 0,
            }
            for (h, d), v in grid.items()
        ]

        # Also compute marginals
        hour_map: dict[int, dict] = {}
        day_map: dict[int, dict] = {}
        for cell in cells:
            h, d = cell["hour"], cell["day"]
            hour_map.setdefault(h, {"trades": 0, "pnl": 0.0, "wins": 0})
            hour_map[h]["trades"] += cell["trades"]
            hour_map[h]["pnl"] += cell["pnl"]
            hour_map[h]["wins"] += round(cell["win_rate"] / 100 * cell["trades"])
            day_map.setdefault(d, {"trades": 0, "pnl": 0.0, "wins": 0})
            day_map[d]["trades"] += cell["trades"]
            day_map[d]["pnl"] += cell["pnl"]
            day_map[d]["wins"] += round(cell["win_rate"] / 100 * cell["trades"])

        by_hour = sorted([
            {
                "hour": h,
                "label": f"{h}:00",
                "trades": v["trades"],
                "pnl": round(v["pnl"], 2),
                "win_rate": round(v["wins"] / v["trades"] * 100, 1) if v["trades"] else 0,
            }
            for h, v in hour_map.items()
        ], key=lambda x: x["hour"])

        by_day = sorted([
            {
                "day": d,
                "name": day_names[d] if d < 5 else f"D{d}",
                "trades": v["trades"],
                "pnl": round(v["pnl"], 2),
                "win_rate": round(v["wins"] / v["trades"] * 100, 1) if v["trades"] else 0,
            }
            for d, v in day_map.items()
        ], key=lambda x: x["day"])

        return {
            "has_data": True,
            "cells": cells,
            "by_hour": by_hour,
            "by_day": by_day,
        }
    except Exception as e:
        logger.error(f"Failed to get timing heatmap: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/options-behavior")
async def get_options_behavior(
    days: int = Query(default=30, ge=1, le=365),
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(analytics_limiter),
):
    """
    Monthly summary of options-specific behavioral patterns.
    Aggregates direction_confusion, premium_avg_down, iv_crush alerts
    from risk_alerts table — gives "happened N times this month" insight.
    """
    OPTIONS_PATTERNS = (
        "options_direction_confusion",
        "options_premium_avg_down",
        "iv_crush_behavior",
    )
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await db.execute(
            select(RiskAlert).where(and_(
                RiskAlert.broker_account_id == broker_account_id,
                RiskAlert.pattern_type.in_(OPTIONS_PATTERNS),
                RiskAlert.detected_at >= cutoff,
            ))
        )
        alerts = result.scalars().all()

        # Bucket by pattern
        direction: list[RiskAlert] = []
        avg_down: list[RiskAlert] = []
        iv_crush: list[RiskAlert] = []
        for a in alerts:
            if a.pattern_type == "options_direction_confusion":
                direction.append(a)
            elif a.pattern_type == "options_premium_avg_down":
                avg_down.append(a)
            elif a.pattern_type == "iv_crush_behavior":
                iv_crush.append(a)

        # ── Direction confusion ──────────────────────────────────────────
        underlying_counts: dict[str, int] = defaultdict(int)
        flip_intervals: list[float] = []
        for a in direction:
            d = a.details or {}
            if d.get("underlying"):
                underlying_counts[d["underlying"]] += 1
            if d.get("minutes_apart") is not None:
                flip_intervals.append(float(d["minutes_apart"]))

        direction_data = {
            "count": len(direction),
            "underlying_breakdown": dict(
                sorted(underlying_counts.items(), key=lambda x: -x[1])
            ),
            "avg_flip_minutes": round(
                sum(flip_intervals) / len(flip_intervals), 1
            ) if flip_intervals else None,
        }

        # ── Premium averaging down ───────────────────────────────────────
        total_re_entry_premium = 0.0
        worst_loss_pcts: list[float] = []
        for a in avg_down:
            d = a.details or {}
            total_re_entry_premium += float(d.get("current_premium_paid") or 0)
            if d.get("worst_loss_pct") is not None:
                worst_loss_pcts.append(float(d["worst_loss_pct"]))

        avg_down_data = {
            "count": len(avg_down),
            "total_re_entry_premium": round(total_re_entry_premium),
            "avg_worst_loss_pct": round(
                sum(worst_loss_pcts) / len(worst_loss_pcts), 1
            ) if worst_loss_pcts else None,
        }

        # ── IV crush ─────────────────────────────────────────────────────
        total_iv_loss = 0.0
        hold_mins: list[float] = []
        loss_pcts: list[float] = []
        for a in iv_crush:
            d = a.details or {}
            total_iv_loss += abs(float(d.get("realized_pnl") or 0))
            if d.get("hold_minutes") is not None:
                hold_mins.append(float(d["hold_minutes"]))
            if d.get("loss_pct") is not None:
                loss_pcts.append(float(d["loss_pct"]))

        iv_crush_data = {
            "count": len(iv_crush),
            "total_loss": round(total_iv_loss),
            "avg_hold_minutes": round(
                sum(hold_mins) / len(hold_mins), 1
            ) if hold_mins else None,
            "avg_loss_pct": round(
                sum(loss_pcts) / len(loss_pcts), 1
            ) if loss_pcts else None,
        }

        has_data = any(
            x["count"] > 0
            for x in (direction_data, avg_down_data, iv_crush_data)
        )

        return {
            "period_days": days,
            "has_data": has_data,
            "direction_confusion": direction_data,
            "premium_avg_down": avg_down_data,
            "iv_crush": iv_crush_data,
        }

    except Exception as e:
        logger.error(f"Failed to get options behavior: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/btst")
async def get_btst_analytics(
    days: int = 90,
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(analytics_limiter),
):
    """
    BTST (Buy Today Sell Tomorrow) analytics.

    Identifies NRML trades entered after 15:00 IST and exited before 09:45 IST
    the next trading day — a behavioural signal of late-day emotional/distress
    entries (planned swing trades enter before 14:45).

    Computes:
    - Total BTST trades and win rate
    - Total realised P&L across all BTST trades
    - Overnight reversals: was profitable at EOD but closed at a loss next day
    """
    try:
        from zoneinfo import ZoneInfo
        IST = ZoneInfo("Asia/Kolkata")

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Fetch all NRML completed_trades in window; IST time-of-day filters applied
        # in Python (simpler than AT TIME ZONE in SQLAlchemy for portability).
        result = await db.execute(
            select(CompletedTrade).where(and_(
                CompletedTrade.broker_account_id == broker_account_id,
                CompletedTrade.product == "NRML",
                CompletedTrade.entry_time >= cutoff,
                CompletedTrade.entry_time.is_not(None),
                CompletedTrade.exit_time.is_not(None),
            )).order_by(CompletedTrade.entry_time.desc())
        )
        candidates = result.scalars().all()

        btst_trades = []
        for ct in candidates:
            entry_ist = ct.entry_time.astimezone(IST)
            exit_ist = ct.exit_time.astimezone(IST)

            # Must be different calendar dates in IST
            if entry_ist.date() == exit_ist.date():
                continue

            # Entry must be after 15:00 IST (late-day emotional entry)
            if not (entry_ist.hour > 15 or (entry_ist.hour == 15 and entry_ist.minute >= 0)):
                continue

            # Exit must be before 09:45 IST on the next session
            if not (exit_ist.hour < 9 or (exit_ist.hour == 9 and exit_ist.minute < 45)):
                continue

            btst_trades.append(ct)

        if not btst_trades:
            return {
                "has_data": False,
                "period_days": days,
                "total_btst_trades": 0,
                "btst_win_rate": 0.0,
                "btst_total_pnl": 0.0,
                "overnight_reversals": 0,
                "reversal_pnl_lost": 0.0,
                "trades": [],
            }

        total = len(btst_trades)
        winners = sum(1 for ct in btst_trades if float(ct.realized_pnl or 0) > 0)
        total_pnl = sum(float(ct.realized_pnl or 0) for ct in btst_trades)
        win_rate = round(winners / total * 100, 1) if total else 0.0

        # Overnight reversal: position was profitable at EOD but closed at a loss
        reversals = []
        for ct in btst_trades:
            ocp = ct.overnight_close_price
            if ocp is None:
                continue
            avg_entry = float(ct.avg_entry_price or 0)
            realized = float(ct.realized_pnl or 0)

            was_profitable_at_eod = False
            if ct.direction == "LONG":
                was_profitable_at_eod = float(ocp) > avg_entry
            elif ct.direction == "SHORT":
                was_profitable_at_eod = float(ocp) < avg_entry

            is_reversal = was_profitable_at_eod and realized < 0

            if is_reversal:
                reversals.append(ct)

        reversal_pnl_lost = round(sum(abs(float(ct.realized_pnl or 0)) for ct in reversals), 2)

        # Build trade list (all BTST trades with reversal flags)
        reversal_ids = {ct.id for ct in reversals}
        trade_list = []
        for ct in btst_trades:
            ocp = ct.overnight_close_price
            avg_entry = float(ct.avg_entry_price or 0)
            realized = float(ct.realized_pnl or 0)

            was_profitable_at_eod = None
            if ocp is not None:
                if ct.direction == "LONG":
                    was_profitable_at_eod = float(ocp) > avg_entry
                elif ct.direction == "SHORT":
                    was_profitable_at_eod = float(ocp) < avg_entry

            entry_ist = ct.entry_time.astimezone(IST)
            hold_type = "weekend_hold" if entry_ist.weekday() == 4 else "overnight"

            trade_list.append({
                "id": str(ct.id),
                "tradingsymbol": ct.tradingsymbol,
                "instrument_type": ct.instrument_type,
                "entry_time": ct.entry_time.isoformat() if ct.entry_time else None,
                "exit_time": ct.exit_time.isoformat() if ct.exit_time else None,
                "direction": ct.direction,
                "realized_pnl": round(realized, 2),
                "avg_entry_price": round(avg_entry, 4) if avg_entry else None,
                "overnight_close_price": round(float(ocp), 4) if ocp is not None else None,
                "was_profitable_at_eod": was_profitable_at_eod,
                "is_reversal": ct.id in reversal_ids,
                "duration_minutes": ct.duration_minutes,
                "hold_type": hold_type,
            })

        return {
            "has_data": True,
            "period_days": days,
            "total_btst_trades": total,
            "btst_win_rate": win_rate,
            "btst_total_pnl": round(total_pnl, 2),
            "overnight_reversals": len(reversals),
            "reversal_pnl_lost": reversal_pnl_lost,
            "trades": trade_list,
        }

    except Exception as e:
        logger.error(f"Failed to get BTST analytics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/instrument")
async def get_instrument_analytics(
    underlying: str,
    days: int = Query(default=30, ge=1, le=365),
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(analytics_limiter),
):
    """
    Drill-down analytics for a single underlying (e.g. NIFTY, SENSEX, BANKNIFTY).
    Matches all CompletedTrades whose tradingsymbol starts with the underlying name.
    Returns per-instrument KPIs, CE/PE/FUT split, by-hour, equity curve, recent trades.
    """
    import re
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        result = await db.execute(
            select(CompletedTrade)
            .where(
                and_(
                    CompletedTrade.broker_account_id == broker_account_id,
                    CompletedTrade.exit_time >= cutoff,
                    CompletedTrade.tradingsymbol.ilike(f"{underlying}%"),
                )
            )
            .order_by(CompletedTrade.exit_time)
        )
        trades = result.scalars().all()

        if not trades:
            return {"has_data": False, "underlying": underlying}

        # ── KPIs ───────────────────────────────────────────────────────────
        total_pnl = sum(float(t.realized_pnl or 0) for t in trades)
        wins = [t for t in trades if float(t.realized_pnl or 0) > 0]
        losses = [t for t in trades if float(t.realized_pnl or 0) < 0]
        win_rate = round(len(wins) / len(trades) * 100, 1) if trades else 0
        avg_win = round(sum(float(t.realized_pnl) for t in wins) / len(wins), 2) if wins else 0
        avg_loss = round(sum(float(t.realized_pnl) for t in losses) / len(losses), 2) if losses else 0
        gross_profit = sum(float(t.realized_pnl) for t in wins)
        gross_loss = abs(sum(float(t.realized_pnl) for t in losses))
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0
        avg_hold = round(sum(t.duration_minutes or 0 for t in trades) / len(trades))

        # ── Option type split (CE / PE / FUT / EQ) ────────────────────────
        def option_type(sym: str) -> str:
            s = sym.upper()
            if s.endswith("CE"):  return "CE"
            if s.endswith("PE"):  return "PE"
            if "FUT" in s:        return "FUT"
            return "EQ"

        otype_map: dict[str, dict] = {}
        for t in trades:
            ot = option_type(t.tradingsymbol)
            otype_map.setdefault(ot, {"trades": 0, "pnl": 0.0, "wins": 0})
            pnl_v = float(t.realized_pnl or 0)
            otype_map[ot]["trades"] += 1
            otype_map[ot]["pnl"] += pnl_v
            if pnl_v > 0:
                otype_map[ot]["wins"] += 1

        by_option_type = {
            k: {
                "trades": v["trades"],
                "pnl": round(v["pnl"], 2),
                "win_rate": round(v["wins"] / v["trades"] * 100, 1) if v["trades"] else 0,
                "avg_pnl": round(v["pnl"] / v["trades"], 2) if v["trades"] else 0,
            }
            for k, v in otype_map.items()
        }

        # ── By hour ────────────────────────────────────────────────────────
        import pytz
        IST = pytz.timezone("Asia/Kolkata")
        hour_map: dict[int, dict] = {}
        for t in trades:
            if not t.entry_time:
                continue
            hr = t.entry_time.astimezone(IST).hour
            hour_map.setdefault(hr, {"trades": 0, "pnl": 0.0, "wins": 0})
            pnl_v = float(t.realized_pnl or 0)
            hour_map[hr]["trades"] += 1
            hour_map[hr]["pnl"] += pnl_v
            if pnl_v > 0:
                hour_map[hr]["wins"] += 1

        by_hour = sorted(
            [
                {
                    "hour": h,
                    "label": f"{h:02d}:00",
                    "trades": v["trades"],
                    "pnl": round(v["pnl"], 2),
                    "win_rate": round(v["wins"] / v["trades"] * 100, 1) if v["trades"] else 0,
                }
                for h, v in hour_map.items()
            ],
            key=lambda x: x["hour"],
        )

        # ── Equity curve ───────────────────────────────────────────────────
        from collections import defaultdict
        from datetime import date as dt_date
        daily: dict[str, float] = defaultdict(float)
        for t in trades:
            d = t.exit_time.astimezone(IST).date().isoformat()
            daily[d] += float(t.realized_pnl or 0)

        cumulative = 0.0
        equity_curve = []
        for d in sorted(daily):
            cumulative += daily[d]
            equity_curve.append({"date": d, "cumulative_pnl": round(cumulative, 2)})

        # ── Recent trades (latest 15) ──────────────────────────────────────
        recent = sorted(trades, key=lambda t: t.exit_time, reverse=True)[:15]
        trade_list = [
            {
                "id": str(t.id),
                "tradingsymbol": t.tradingsymbol,
                "direction": t.direction,
                "total_quantity": t.total_quantity,
                "avg_entry_price": float(t.avg_entry_price or 0),
                "avg_exit_price": float(t.avg_exit_price or 0),
                "realized_pnl": float(t.realized_pnl or 0),
                "duration_minutes": t.duration_minutes,
                "exit_time": t.exit_time.isoformat(),
                "option_type": option_type(t.tradingsymbol),
            }
            for t in recent
        ]

        return {
            "has_data": True,
            "underlying": underlying,
            "period_days": days,
            "total_trades": len(trades),
            "total_pnl": round(total_pnl, 2),
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "avg_hold_min": avg_hold,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "by_option_type": by_option_type,
            "by_hour": by_hour,
            "equity_curve": equity_curve,
            "trades": trade_list,
        }

    except Exception as e:
        logger.error(f"Failed to get instrument analytics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
