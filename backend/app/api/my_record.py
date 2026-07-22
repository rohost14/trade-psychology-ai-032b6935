"""
"What's my record here?" — a pre-trade lookup of the trader's OWN history.

The competitive gap this fills: journals (TraderSync, Edgewonk, TradesViz,
Tradervue, TradeZella) all compute win-rate-by-setup, but present it post-hoc as
insight cards you read on a Sunday. Nobody serves it as a lookup you consult at
2pm with your finger over the buy button. Sensibull models the option, not you;
Zerodha's Nudge is real-time but generic and platform-authored.

Discipline rules this obeys:
  * FACTS ONLY. Every number is the trader's own realised history. No
    prediction, no counterfactual, no "this would have saved you X". It is
    explicitly NOT the previously-rejected what-if simulator.
  * P&L stays RAW, per the standing project rule.
  * SAMPLE-GATED, and honest about it. A 2-trade bucket is never dressed up as
    an edge. When the narrow bucket is too thin the endpoint widens and SAYS SO
    via `scope` — silent widening would be a lie by omission.
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_verified_broker_account_id
from app.core.database import get_db
from app.core.rate_limiter import analytics_limiter
from app.models.completed_trade import CompletedTrade
from app.models.completed_trade_feature import CompletedTradeFeature

router = APIRouter()
logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")

# Same gate as edge-leak. Below this a bucket is reported but flagged thin.
MIN_SAMPLE = 5


def _underlying(symbol: str) -> str:
    """NIFTY25JUL25000CE -> NIFTY. Best-effort, mirrors the analytics helper."""
    if not symbol:
        return symbol
    m = re.match(r"^([A-Z&\-]+?)(?:\d{5}|\d{2}[A-Z]{3})", symbol.upper())
    return m.group(1) if m else symbol.upper()


def _instrument_type(symbol: str, stored: Optional[str]) -> str:
    t = (stored or "").upper()
    if t in ("CE", "PE", "FUT", "EQ"):
        return t
    s = (symbol or "").upper()
    m = re.search(r"(?:\d{5}\d+(?:\.\d+)?|\d{2}[A-Z]{3}(?:\d{2})?\d+(?:\.\d+)?)(CE|PE)$", s)
    if m:
        return m.group(1)
    if re.search(r"(?:\d{5}|\d{2}[A-Z]{3}(?:\d{2})?)FUT$", s):
        return "FUT"
    return "EQ"


def _stats(trades: List[Any]) -> Dict[str, Any]:
    """Factual aggregate for a bucket of completed trades."""
    n = len(trades)
    if n == 0:
        return {"trades": 0, "win_rate": None, "pnl": 0.0, "avg_pnl": 0.0, "enough": False}
    pnls = [float(t.realized_pnl or 0) for t in trades]
    wins = sum(1 for p in pnls if p > 0)
    losses = sum(1 for p in pnls if p < 0)
    decided = wins + losses
    return {
        "trades": n,
        # Breakeven trades are excluded from the denominator rather than counted
        # against the trader — same convention as the Dashboard.
        "win_rate": round(wins / decided * 100, 1) if decided else None,
        "wins": wins,
        "losses": losses,
        "pnl": round(sum(pnls), 2),
        "avg_pnl": round(sum(pnls) / n, 2),
        "best": round(max(pnls), 2),
        "worst": round(min(pnls), 2),
        "enough": n >= MIN_SAMPLE,
    }


@router.get("/search")
async def search_my_instruments(
    q: str = Query("", max_length=40),
    limit: int = Query(10, ge=1, le=25),
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(analytics_limiter),
):
    """
    Instruments this trader has actually traded, for the lookup's search box.

    Deliberately scoped to their own history — this is not an instrument master
    search. If they have never traded it, we have nothing factual to say.
    """
    try:
        stmt = (
            select(
                CompletedTrade.tradingsymbol,
                func.count(CompletedTrade.id).label("trades"),
                func.max(CompletedTrade.exit_time).label("last_traded"),
            )
            .where(CompletedTrade.broker_account_id == broker_account_id)
            .group_by(CompletedTrade.tradingsymbol)
            .order_by(func.max(CompletedTrade.exit_time).desc())
            .limit(200)
        )
        rows = (await db.execute(stmt)).all()

        needle = (q or "").strip().upper()
        by_underlying: Dict[str, Dict[str, Any]] = {}
        symbols: List[Dict[str, Any]] = []

        for sym, trades, last in rows:
            if needle and needle not in (sym or "").upper():
                continue
            symbols.append({
                "symbol": sym,
                "trades": trades,
                "last_traded": last.isoformat() if last else None,
            })
            u = _underlying(sym)
            agg = by_underlying.setdefault(u, {"underlying": u, "trades": 0, "last_traded": None})
            agg["trades"] += trades
            if last and (agg["last_traded"] is None or last.isoformat() > agg["last_traded"]):
                agg["last_traded"] = last.isoformat()

        underlyings = sorted(by_underlying.values(), key=lambda x: -x["trades"])[:limit]
        return {"underlyings": underlyings, "symbols": symbols[:limit]}
    except Exception as e:
        logger.error(f"my-record search failed: {e}", exc_info=True)
        return {"underlyings": [], "symbols": []}


@router.get("")
async def get_my_record(
    symbol: str = Query(..., min_length=1, max_length=40),
    days: int = Query(365, ge=1, le=1825),
    broker_account_id: UUID = Depends(get_verified_broker_account_id),
    db: AsyncSession = Depends(get_db),
    _limiter: None = Depends(analytics_limiter),
):
    """
    The trader's own record for an instrument, sliced by situation.

    `symbol` may be an exact tradingsymbol or an underlying (NIFTY). The
    response always states which `scope` the numbers came from, so a widened
    bucket is never mistaken for an exact-contract read.
    """
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        needle = symbol.strip().upper()

        rows = (await db.execute(
            select(CompletedTrade, CompletedTradeFeature)
            .outerjoin(
                CompletedTradeFeature,
                CompletedTrade.id == CompletedTradeFeature.completed_trade_id,
            )
            .where(and_(
                CompletedTrade.broker_account_id == broker_account_id,
                CompletedTrade.exit_time >= cutoff,
                CompletedTrade.status == "closed",
                CompletedTrade.realized_pnl.isnot(None),
                CompletedTrade.tradingsymbol.ilike(f"{_underlying(needle)}%"),
            ))
            .order_by(CompletedTrade.exit_time.desc())
        )).all()

        if not rows:
            return {
                "has_data": False,
                "query": needle,
                "period_days": days,
                "message": f"You have no completed trades on {needle} in this period.",
            }

        exact = [(ct, f) for ct, f in rows if (ct.tradingsymbol or "").upper() == needle]
        und = _underlying(needle)
        itype = _instrument_type(needle, None)
        same_type = [
            (ct, f) for ct, f in rows
            if _instrument_type(ct.tradingsymbol, ct.instrument_type) == itype
        ]

        # ── Scope cascade ────────────────────────────────────────────────────
        # Narrowest bucket that clears the sample gate wins; always reported.
        if len(exact) >= MIN_SAMPLE:
            scope, scope_label, subset = "exact_contract", needle, exact
        elif len(same_type) >= MIN_SAMPLE and itype != "EQ":
            scope, scope_label, subset = "underlying_type", f"{und} {itype}", same_type
        else:
            scope, scope_label, subset = "underlying", und, [(ct, f) for ct, f in rows]

        overall = _stats([ct for ct, _ in subset])

        # ── Situational slices ───────────────────────────────────────────────
        now_ist = datetime.now(IST)
        current_hour = now_ist.hour

        def feat_hour(ct, f) -> Optional[int]:
            if f is not None and f.entry_hour_ist is not None:
                return f.entry_hour_ist
            return ct.entry_time.astimezone(IST).hour if ct.entry_time else None

        by_hour: Dict[int, List[Any]] = {}
        for ct, f in subset:
            h = feat_hour(ct, f)
            if h is not None:
                by_hour.setdefault(h, []).append(ct)

        hours = [
            {"hour": h, "label": f"{h:02d}:00–{(h + 1) % 24:02d}:00", **_stats(ts)}
            for h, ts in sorted(by_hour.items())
        ]

        this_hour = next((h for h in hours if h["hour"] == current_hour), None)

        after_loss = _stats([ct for ct, f in subset if f is not None and bool(f.entry_after_loss)])
        streak_2plus = _stats([
            ct for ct, f in subset
            if f is not None and (f.consecutive_loss_count or 0) >= 2
        ])
        expiry_day = _stats([ct for ct, f in subset if f is not None and bool(f.is_expiry_day)])
        quick_reentry = _stats([
            ct for ct, f in subset
            if f is not None and f.minutes_since_last_round is not None
            and float(f.minutes_since_last_round) < 20
        ])

        durations = [ct.duration_minutes for ct, _ in subset if ct.duration_minutes]
        longest_hold = max(durations) if durations else None
        avg_hold = round(sum(durations) / len(durations)) if durations else None

        best_hour = max(
            (h for h in hours if h["enough"]), key=lambda x: x["avg_pnl"], default=None
        )
        worst_hour = min(
            (h for h in hours if h["enough"]), key=lambda x: x["avg_pnl"], default=None
        )

        # ── Verdict: strongest FACT present, never a prediction ──────────────
        verdict = None
        if this_hour and this_hour["enough"] and this_hour["avg_pnl"] < 0:
            verdict = (
                f"Right now is your weakest window on {scope_label}: "
                f"{this_hour['trades']} trades, {this_hour['win_rate']}% win rate, "
                f"{'+' if this_hour['pnl'] >= 0 else '-'}₹{abs(this_hour['pnl']):,.0f} net."
            )
        elif after_loss["enough"] and overall["win_rate"] is not None \
                and after_loss["win_rate"] is not None \
                and after_loss["win_rate"] < overall["win_rate"] - 10:
            verdict = (
                f"After a loss your win rate on {scope_label} drops to "
                f"{after_loss['win_rate']}% (vs {overall['win_rate']}% overall) "
                f"across {after_loss['trades']} trades."
            )
        elif this_hour and this_hour["enough"] and this_hour["avg_pnl"] > 0:
            verdict = (
                f"This is one of your stronger windows on {scope_label}: "
                f"{this_hour['trades']} trades, {this_hour['win_rate']}% win rate."
            )
        elif not overall["enough"]:
            verdict = (
                f"Only {overall['trades']} completed trades on {scope_label} — "
                f"too few to read anything into yet."
            )

        return {
            "has_data": True,
            "query": needle,
            "period_days": days,
            "scope": scope,
            "scope_label": scope_label,
            # Explicit so the UI can say "across all your NIFTY trades" rather
            # than implying an exact-contract read.
            "widened": scope != "exact_contract",
            "min_sample": MIN_SAMPLE,
            "underlying": und,
            "overall": overall,
            "current_hour": current_hour,
            "this_hour": this_hour,
            "by_hour": hours,
            "best_hour": best_hour,
            "worst_hour": worst_hour,
            "situations": {
                "after_loss": after_loss,
                "after_2plus_losses": streak_2plus,
                "expiry_day": expiry_day,
                "quick_reentry": quick_reentry,
            },
            "holding": {"longest_minutes": longest_hold, "avg_minutes": avg_hold},
            "verdict": verdict,
        }
    except Exception as e:
        logger.error(f"my-record failed: {e}", exc_info=True)
        return {"has_data": False, "query": symbol, "error": "Could not load your record."}
