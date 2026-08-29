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
from app.core import session_facts
from app.core.baseline_rules import (
    RECENT_WINDOW_TRADES,
    cap_adaptation,
    clean_for_learning,
    divergence,
    mad,
    median,
)

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


def _mad(values: List[float]) -> float:
    """Median absolute deviation - the robust spread measure."""
    from app.core.baseline_rules import mad as _m
    return _m(values) or 0.0


def _percentile(values: List[float], p: float) -> Optional[float]:
    """Nearest-rank percentile. Robust for the small, skewed samples here."""
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round(p / 100.0 * len(ordered))))
    return float(ordered[idx])


def _pct_metric(values: List[float], p: float, n: int, target: int,
                floor: float = 0.0,
                excluded_indices=()) -> Optional[Dict]:
    """
    A percentile of the trader's own distribution, carrying its own confidence.

    This is how the OTHER baseline service derived its thresholds, and it is the
    better derivation: a direct percentile needs no arbitrary multiplier, where
    the reader's blend used `median x 1.5` and `median / 4`. Merging them means
    the multipliers can go.
    """
    # Learn only from observations a baseline is ALLOWED to learn from. Extremes
    # are excluded from the UPDATE (global rule 5): an outlier is evidence about
    # a day, not about a habit. It stays in the trade record and can still fire a
    # detector - it simply does not get to redefine what is typical.
    #
    # `excluded_indices` is global baseline rule 4: observations belonging
    # to a confirmed harmful sequence must not train the baseline they will
    # later be judged against. The argument has always existed here and
    # nothing ever passed it.
    learnable = clean_for_learning(values, excluded_indices)
    v = _percentile(learnable, p)
    if v is None:
        return None
    return {
        "value": round(max(v, floor), 4),
        "percentile": p,
        "confidence": round(min(1.0, n / max(target, 1)), 3),
        "n": n,
        "n_learned": len(learnable),
        "n_excluded": len(values) - len(learnable),
        # Kept separate so the two exclusion reasons stay distinguishable:
        # an outlier is excluded because it says nothing about a habit, a
        # harmful sequence because letting it teach would let the behaviour
        # redefine what counts as normal.
        "n_excluded_harmful": len(set(excluded_indices)),
    }


def _distribution(values: List[float], unit: str) -> Optional[Dict]:
    """
    A recorded distribution: the shape of what this trader actually did.

    NOT a threshold. It carries several percentiles rather than one because
    the percentile that marks "unusual" has not been decided, and picking one
    here would be exactly the invented constant this work exists to remove.
    Storing the shape lets that decision be argued from evidence later, and
    lets anyone check afterwards what it was argued from.

    Outliers are excluded on the same rule as everywhere else - an extreme
    observation is evidence about a day, not about a habit - and both counts
    are kept so the exclusion is visible rather than implied.
    """
    if not values:
        return None
    learnable = clean_for_learning(values)
    if not learnable:
        return None
    ordered = sorted(learnable)

    def pct(q):
        idx = min(len(ordered) - 1, int(round(q / 100.0 * len(ordered))))
        return round(float(ordered[idx]), 2)

    return {
        "unit": unit,
        "n": len(values),
        "n_learned": len(learnable),
        "n_excluded": len(values) - len(learnable),
        "median": round(float(median(learnable)), 2),
        "mad": round(float(mad(learnable) or 0.0), 2),
        "percentiles": {"p%d" % q: pct(q) for q in (25, 50, 60, 75, 85, 95)},
        "active": False,
        "provenance": (
            "observed distribution; no percentile selected as a threshold "
            "(P1 unresolved)"
        ),
    }


def _metric(values: List[float], n: int, target: int) -> Optional[Dict]:
    """Build one metric record. confidence = sample size vs target, capped 1."""
    if not values:
        return None
    learnable = clean_for_learning(values)
    if not learnable:
        return None
    return {
        "value": round(statistics.median(learnable), 4),
        # Diagnosis only. NOTHING may resolve a threshold from a mean: nine
        # Rs 500 losses and one Rs 25,000 loss put the mean at 2,950, which is
        # true of nothing this trader does.
        "mean": round(statistics.fmean(learnable), 4),
        "confidence": round(min(1.0, n / max(target, 1)), 3),
        "n": n,
        "n_learned": len(learnable),
        "n_excluded": len(values) - len(learnable),
        # MAD, not stddev: stddev is defined around the mean and inherits its
        # sensitivity to exactly the outliers trading data is full of.
        "mad": round(_mad(learnable), 4) if len(learnable) > 1 else None,
        "stddev": round(statistics.pstdev(learnable), 4) if len(learnable) > 1 else None,
    }


def _profit_factor(trades) -> float | None:
    gross_win = sum(float(t.realized_pnl or 0) for t in trades if float(t.realized_pnl or 0) > 0)
    gross_loss = abs(sum(float(t.realized_pnl or 0) for t in trades if float(t.realized_pnl or 0) < 0))
    if gross_loss <= 0:
        return None  # no losses in window - PF undefined/infinite
    return round(gross_win / gross_loss, 3)



def _apply_adaptation_cap(metrics: Dict, previous: Optional[Dict]) -> Dict:
    """
    Limit how far each metric may move in one recompute (global rule 3).

    Without a cap a trader who escalates for a fortnight has simply taught the
    system that escalation is normal: they size up, the baseline follows, and the
    detector never fires again. The cap is what makes that impossible.

    The uncapped value is kept alongside, so the fact that a cap bound is visible
    rather than silent.
    """
    if not previous:
        return metrics
    prev_metrics = (previous or {}).get("metrics") or {}
    capped = {}
    for name, rec in metrics.items():
        prev = prev_metrics.get(name)
        prev_value = prev.get("value") if isinstance(prev, dict) else None
        if prev_value is None or rec.get("value") is None:
            capped[name] = rec
            continue
        proposed = float(rec["value"])
        limited = cap_adaptation(float(prev_value), proposed)
        if limited != proposed:
            rec = {**rec, "value": round(limited, 4),
                   "uncapped_value": round(proposed, 4),
                   "adaptation_capped": True}
        capped[name] = rec
    return capped


def _compute_divergence(by_session: Dict, trades: List) -> Optional[Dict]:
    """
    Recent behaviour against long-term behaviour, for the two metrics where
    escalation actually matters: how much they trade, and how big.

    Deliberately not computed for every metric. The plan flagged universal
    two-window tracking as premature - it doubles state for a benefit only a
    couple of metrics have.
    """
    daily_counts = [float(len(v)) for v in by_session.values()]
    sizes = [abs(float(t.avg_entry_price or 0)) * abs(int(t.total_quantity or 0))
             for t in trades]
    sizes = [v for v in sizes if v > 0]

    out = {}
    d = divergence(daily_counts, daily_counts[-RECENT_WINDOW_TRADES:])
    if d.ratio is not None:
        out["daily_trades"] = {"long_term": d.long_term, "recent": d.recent,
                               "ratio": round(d.ratio, 3), "notable": d.is_notable,
                               "direction": d.direction}
    d = divergence(sizes, sizes[-RECENT_WINDOW_TRADES:])
    if d.ratio is not None:
        out["position_size"] = {"long_term": d.long_term, "recent": d.recent,
                                "ratio": round(d.ratio, 3), "notable": d.is_notable,
                                "direction": d.direction}
    return out or None


async def compute_baseline(
    broker_account_id: UUID,
    db: AsyncSession,
    days: int = 90,
    trading_capital: Optional[float] = None,
    previous: Optional[Dict] = None,
) -> Dict:
    """
    `previous` is the baseline this one replaces. Supplying it enables capped
    adaptation (global rule 3): without a previous value there is nothing to cap
    against, and a first baseline is legitimately unconstrained.
    """
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
        # Peak, max drawdown and the longest losing run all come from the one
        # definition (app/core/session_facts). A baseline that learned "your
        # typical peak" from arithmetic written here, while the live detector
        # measured it with arithmetic written there, would be comparing a trader
        # against a version of themselves the engine never sees.
        ordered = session_facts.in_exit_order(day_trades)
        facts = session_facts.derive(ordered)
        if facts.peak_pnl > 0:
            peak_pnls.append(float(facts.peak_pnl))
        if facts.max_drawdown > 0:
            drawdowns.append(float(facts.max_drawdown))

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

        consec_losses.append(float(facts.longest_loss_run))

    # ── Trade-level metrics (mature with TRADE count) ─────────────────────
    winner_holds, loser_holds = [], []
    wins = 0
    reentry_delays: List[float] = []
    #: indices into reentry_delays whose re-entry itself closed at a loss
    reentry_harmful: List[int] = []
    #: every losing trade's size in rupees - the P1 distribution
    own_loss_sizes: List[float] = []
    #: every trade's capital at risk in rupees - the size distribution
    own_position_risk: List[float] = []
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
                own_loss_sizes.append(abs(pnl))
                if hold is not None:
                    loser_holds.append(hold)
                # delay from this loss exit to the next entry that day
                for nxt in ordered[i + 1:]:
                    if nxt.entry_time and t.exit_time and nxt.entry_time >= t.exit_time:
                        reentry_delays.append(
                            (nxt.entry_time - t.exit_time).total_seconds() / 60
                        )
                        # A harmful sequence, defined from the TRADE RECORD
                        # alone: a loss, a re-entry, and that re-entry also
                        # lost. No alert, no threshold and no detector
                        # verdict is consulted - reading our own alerts here
                        # would make the baseline depend on what the detector
                        # previously decided, so a threshold change would
                        # silently rewrite the history it is measured against.
                        if float(nxt.realized_pnl or 0) < 0:
                            reentry_harmful.append(len(reentry_delays) - 1)
                        break
            # Capital at risk in rupees needs no declared capital, so this is
            # available for every trader. risk_pcts additionally divides by
            # capital and so is only available when capital is known.
            risk_rupees = estimate_capital_at_risk(
                t.instrument_type, t.tradingsymbol or "", t.direction or "LONG",
                float(t.avg_entry_price or 0), int(t.total_quantity or 0),
                exchange=getattr(t, "exchange", None),        # F7
            )
            if risk_rupees > 0:
                own_position_risk.append(risk_rupees)
            if trading_capital and trading_capital > 0:
                risk_pcts.append(risk_rupees / trading_capital * 100)

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
                                              target_trades // 2, floor=1.0,
                                              excluded_indices=reentry_harmful),
        "loss_streak_p60": _pct_metric(consec_losses, 60, n_sessions, target_sessions),
        "loss_streak_p85": _pct_metric(consec_losses, 85, n_sessions, target_sessions),

        # -- Distributions, recorded but NOT active -------------------------
        # Observations and counts, not thresholds. Which percentile marks
        # "unusual for this trader" is P1, an unapproved decision, so nothing
        # reads these yet. They are stored so that decision can later be
        # argued from this trader's real distribution rather than guessed,
        # and so the choice is auditable afterwards.
        "own_loss_size": _distribution(own_loss_sizes, "losing trades, rupees"),
        "own_position_risk": _distribution(own_position_risk,
                                           "capital at risk per trade, rupees"),
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
        "metrics": _apply_adaptation_cap(
            {k: v for k, v in metrics.items() if v is not None}, previous
        ),
        # Long-window vs recent behaviour, per global rule 2. Reported, never
        # used as a threshold: a trader whose sizes have doubled this month is a
        # finding in itself, and one rolling window cannot express it because by
        # the time it has adapted there is nothing left to compare against.
        "divergence": _compute_divergence(by_session, trades),
    }
    logger.info(
        f"[baseline] {broker_account_id}: {n_sessions} sessions / {n_trades} trades — "
        f"{list(baseline['metrics'].keys())}"
    )
    return baseline
