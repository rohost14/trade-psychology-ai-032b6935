"""
Baseline Service — Engine v2 Phase 3 (master §1B.4, Q23).

Computes the per-metric behavioral baseline that personalizes detection
thresholds. Every metric carries its own confidence — a scalper's hold-time
baseline matures in days (trade-count driven) while their daily-count
baseline needs weeks (session-count driven). No fixed activation gate:
get_thresholds() blends personal values with universal defaults continuously
by confidence (LOW ≈ defaults, HIGH ≈ personal), so thresholds adapt
gradually with zero cliffs.

Data source: CompletedTrade.realized_pnl (the truth layer). The legacy
learn_patterns time/symbol analysis reads Trade.pnl which is always 0 —
this service deliberately does not share that path.

Output shape (stored at user_profile.detected_patterns["baseline"]):
{
  "computed_at": iso,
  "days_window": 90,
  "sessions_analyzed": N,
  "trades_analyzed": M,
  "metrics": {
     "<name>": {"value": float, "confidence": 0-1, "n": int, "stddev": float|null},
     ...
  }
}
"""
import logging
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.completed_trade import CompletedTrade
from app.core.trading_defaults import COLD_START_DEFAULTS, estimate_capital_at_risk

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


def _percentile(values: List[float], p: float) -> Optional[float]:
    """Nearest-rank percentile. Robust for the small, skewed samples here."""
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round(p / 100.0 * len(ordered))))
    return float(ordered[idx])


def _pct_metric(values: List[float], p: float, n: int, target: int,
                floor: float = 0.0) -> Optional[Dict]:
    """
    A percentile of the trader's own distribution, carrying its own confidence.

    This is how the OTHER baseline service derived its thresholds, and it is the
    better derivation: a direct percentile needs no arbitrary multiplier, where
    the reader's blend used `median x 1.5` and `median / 4`. Merging them means
    the multipliers can go.
    """
    v = _percentile(values, p)
    if v is None:
        return None
    return {
        "value": round(max(v, floor), 4),
        "percentile": p,
        "confidence": round(min(1.0, n / max(target, 1)), 3),
        "n": n,
    }


def _metric(values: List[float], n: int, target: int) -> Optional[Dict]:
    """Build one metric record. confidence = sample size vs target, capped 1."""
    if not values:
        return None
    return {
        "value": round(statistics.median(values), 4),
        "mean": round(statistics.fmean(values), 4),
        "confidence": round(min(1.0, n / max(target, 1)), 3),
        "n": n,
        "stddev": round(statistics.pstdev(values), 4) if len(values) > 1 else None,
    }


def _profit_factor(trades) -> float | None:
    gross_win = sum(float(t.realized_pnl or 0) for t in trades if float(t.realized_pnl or 0) > 0)
    gross_loss = abs(sum(float(t.realized_pnl or 0) for t in trades if float(t.realized_pnl or 0) < 0))
    if gross_loss <= 0:
        return None  # no losses in window - PF undefined/infinite
    return round(gross_win / gross_loss, 3)


async def compute_baseline(
    broker_account_id: UUID,
    db: AsyncSession,
    days: int = 90,
    trading_capital: Optional[float] = None,
) -> Dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(CompletedTrade)
        .where(and_(
            CompletedTrade.broker_account_id == broker_account_id,
            CompletedTrade.exit_time >= cutoff,
        ))
        .order_by(CompletedTrade.exit_time.asc())
    )
    trades = list(result.scalars().all())

    target_sessions = COLD_START_DEFAULTS.get("baseline_target_sessions", 30)
    target_trades = COLD_START_DEFAULTS.get("baseline_target_trades", 100)

    if not trades:
        return {
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "days_window": days,
            "sessions_analyzed": 0,
            "trades_analyzed": 0,
            "metrics": {},
        }

    # Group by IST session date
    by_session: Dict = defaultdict(list)
    for t in trades:
        if t.exit_time:
            by_session[t.exit_time.astimezone(IST).date()].append(t)
    n_sessions = len(by_session)
    n_trades = len(trades)

    # ── Session-level metrics (mature with SESSION count) ────────────────
    daily_counts = [float(len(v)) for v in by_session.values()]

    peak_pnls: List[float] = []
    drawdowns: List[float] = []
    burst_counts: List[float] = []      # busiest 30 minutes of each session
    consec_losses: List[float] = []     # longest losing run of each session
    for day_trades in by_session.values():
        running = 0.0
        peak = 0.0
        max_dd = 0.0
        ordered = sorted(day_trades, key=lambda x: x.exit_time)
        for t in ordered:
            running += float(t.realized_pnl or 0)
            peak = max(peak, running)
            max_dd = max(max_dd, peak - running)
        if peak > 0:
            peak_pnls.append(peak)
        if max_dd > 0:
            drawdowns.append(max_dd)

        # Busiest 30-minute window, by entry time. Sliding rather than fixed
        # buckets: a burst that straddles a bucket boundary is still a burst.
        entries = sorted(t.entry_time for t in ordered if t.entry_time)
        busiest = 0
        for i, start in enumerate(entries):
            j = i
            while j < len(entries) and (entries[j] - start).total_seconds() <= 1800:
                j += 1
            busiest = max(busiest, j - i)
        if busiest:
            burst_counts.append(float(busiest))

        # Longest consecutive losing run in the session.
        longest = current = 0
        for t in ordered:
            if float(t.realized_pnl or 0) < 0:
                current += 1
                longest = max(longest, current)
            else:
                current = 0
        consec_losses.append(float(longest))

    # ── Trade-level metrics (mature with TRADE count) ─────────────────────
    winner_holds, loser_holds = [], []
    wins = 0
    reentry_delays: List[float] = []
    risk_pcts: List[float] = []

    for day_trades in by_session.values():
        ordered = sorted(day_trades, key=lambda x: x.exit_time)
        for i, t in enumerate(ordered):
            pnl = float(t.realized_pnl or 0)
            hold = None
            if t.entry_time and t.exit_time:
                hold = (t.exit_time - t.entry_time).total_seconds() / 60
            if pnl > 0:
                wins += 1
                if hold is not None:
                    winner_holds.append(hold)
            elif pnl < 0:
                if hold is not None:
                    loser_holds.append(hold)
                # delay from this loss exit to the next entry that day
                for nxt in ordered[i + 1:]:
                    if nxt.entry_time and t.exit_time and nxt.entry_time >= t.exit_time:
                        reentry_delays.append(
                            (nxt.entry_time - t.exit_time).total_seconds() / 60
                        )
                        break
            if trading_capital and trading_capital > 0:
                risk = estimate_capital_at_risk(
                    t.instrument_type, t.tradingsymbol or "", t.direction or "LONG",
                    float(t.avg_entry_price or 0), int(t.total_quantity or 0),
                )
                risk_pcts.append(risk / trading_capital * 100)

    metrics = {
        # session-count confidence
        "avg_daily_trades": _metric(daily_counts, n_sessions, target_sessions),
        "typical_peak_pnl": _metric(peak_pnls, len(peak_pnls), target_sessions),
        "typical_drawdown": _metric(drawdowns, len(drawdowns), target_sessions),
        # trade-count confidence
        "median_reentry_after_loss_min": _metric(reentry_delays, len(reentry_delays), target_trades // 2),
        "avg_winner_hold_min": _metric(winner_holds, len(winner_holds), target_trades // 2),
        "avg_loser_hold_min": _metric(loser_holds, len(loser_holds), target_trades // 2),
        "win_rate": _metric([wins / n_trades * 100], n_trades, target_trades),
        "profit_factor": _metric([_profit_factor(trades)], n_trades, target_trades)
                         if _profit_factor(trades) is not None else None,
        "median_position_risk_pct": _metric(risk_pcts, len(risk_pcts), target_trades),

        # ── Percentile-derived thresholds (merged in from behavioral_baseline_service)
        # Each is a point on THIS trader's own distribution, so it needs no
        # multiplier and no population assumption. The percentiles are the ones
        # that service already used: an active-but-not-outlier day, the fast end
        # of their own re-entry pace, and where their loss streaks start to be
        # unusual for them.
        "daily_trades_p75": _pct_metric(daily_counts, 75, n_sessions, target_sessions),
        "burst_per_30min_p75": _pct_metric(burst_counts, 75, n_sessions, target_sessions),
        "reentry_after_loss_p25": _pct_metric(reentry_delays, 25, len(reentry_delays),
                                              target_trades // 2, floor=1.0),
        "loss_streak_p60": _pct_metric(consec_losses, 60, n_sessions, target_sessions),
        "loss_streak_p85": _pct_metric(consec_losses, 85, n_sessions, target_sessions),
    }
    # p95 daily trades as a plain value on the avg record (upper-bound signal)
    if metrics["avg_daily_trades"] and len(daily_counts) >= 2:
        s = sorted(daily_counts)
        metrics["avg_daily_trades"]["p95"] = round(s[min(len(s) - 1, int(0.95 * len(s)))], 1)

    baseline = {
        # Shape version. The reader branches on this instead of sniffing for a
        # "metrics" key, which is what let two services write incompatible
        # shapes to the same JSONB column for months without anyone noticing.
        "version": 2,
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "days_window": days,
        "sessions_analyzed": n_sessions,
        "trades_analyzed": n_trades,
        "metrics": {k: v for k, v in metrics.items() if v is not None},
    }
    logger.info(
        f"[baseline] {broker_account_id}: {n_sessions} sessions / {n_trades} trades — "
        f"{list(baseline['metrics'].keys())}"
    )
    return baseline
