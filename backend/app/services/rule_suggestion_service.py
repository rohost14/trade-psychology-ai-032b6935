"""
Rule suggestions — derive constitution rules from the trader's own ledger.

The constitution (§1C) is the user's rulebook, and until now the only way to fill
it was to type numbers into a form. Adoption of anything that requires typing has
been zero, so this service does the deriving: it reads CompletedTrades, finds the
threshold where the user's own outcomes change, and offers it as a one-tap rule.

Three hard constraints shape everything here:

1. **Only tightening is ever suggested.** ConstitutionService exists to make
   loosening deliberate (override + next-session effect). A product that proposes
   relaxing your own rules is arguing against its own purpose. A rule that is
   already tighter than the data supports is left alone — silence is a valid answer.

2. **No counterfactuals.** We never say "this would have saved you ₹X". Behaviour→
   money is realized P&L of things that actually happened. Suggestions cite what
   the ledger contains: how many sessions, what the outcome was, nothing simulated.

3. **Nothing is auto-applied.** Every suggestion is a proposal with its evidence
   attached. Accepting routes through the normal constitution PUT, so the same
   change control applies as if the user had typed it.

Suggestions are computed on read. There is no suggestion table: the underlying
trades are immutable, so the same window always produces the same answer, and a
stored copy could only go stale.
"""
from __future__ import annotations

import logging
import re
import statistics
from collections import defaultdict
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.completed_trade import CompletedTrade

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

# ── Sampling gates ───────────────────────────────────────────────────────────
# A rule derived from four sessions is noise wearing a number's clothes. These
# are deliberately conservative: showing nothing is a better failure than showing
# a confident wrong limit, which the user would then be gated against loosening.
WINDOW_DAYS = 90
MIN_SESSIONS = 10          # distinct trading days before any session-level rule
MIN_TRADES = 30            # completed trades before any trade-level rule
MIN_BUCKET = 3            # observations required on each side of a split
MIN_SEPARATION = 0.15      # a split must move the outcome rate by 15pp to count

_ROOT_RE = re.compile(r"^([A-Z]+?)(?=\d)")


@dataclass
class Suggestion:
    """One proposed rule change, with the evidence that produced it."""
    field: str
    current_value: Optional[float]
    suggested_value: float
    headline: str
    evidence: List[Dict[str, str]] = dc_field(default_factory=list)
    confidence: str = "low"          # low | medium | high — sample size only
    sample: Dict[str, Any] = dc_field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field,
            "current_value": self.current_value,
            "suggested_value": self.suggested_value,
            "headline": self.headline,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "sample": self.sample,
        }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _pnl(t: CompletedTrade) -> float:
    return float(t.realized_pnl or 0)


def _root(symbol: Optional[str]) -> str:
    """NIFTY25AUG24500CE -> NIFTY. Falls back to the whole symbol for equities."""
    if not symbol:
        return ""
    m = _ROOT_RE.match(symbol.upper())
    return m.group(1) if m else symbol.upper()


def _session_key(t: CompletedTrade):
    """IST calendar date of the exit — one trading session."""
    ts = t.exit_time or t.entry_time
    return ts.astimezone(IST).date() if ts else None


def _group_by_session(trades: Sequence[CompletedTrade]) -> Dict[Any, List[CompletedTrade]]:
    sessions: Dict[Any, List[CompletedTrade]] = defaultdict(list)
    for t in trades:
        key = _session_key(t)
        if key is not None:
            sessions[key].append(t)
    for rows in sessions.values():
        rows.sort(key=lambda x: x.exit_time or x.entry_time or datetime.min.replace(tzinfo=timezone.utc))
    return dict(sessions)


def _confidence(n: int, floor: int) -> str:
    if n >= floor * 3:
        return "high"
    if n >= floor * 2:
        return "medium"
    return "low"


def _rate(rows: Sequence[bool]) -> float:
    return (sum(1 for r in rows if r) / len(rows)) if rows else 0.0


def _pct(x: float) -> str:
    return f"{round(x * 100)}%"


def _rs(x: float) -> str:
    return f"₹{abs(round(x)):,}"


def uses_multi_leg(trades: Sequence[CompletedTrade]) -> bool:
    """
    True when the account shows spread-style trading: two or more completed
    trades on the same underlying entered within a minute of each other.

    Why this exists: a CompletedTrade is per tradingsymbol, so one four-leg
    structure is four rows. Any suggestion derived from a *count* of trades is
    inflated for a spread trader — an iron condor reads as four trades. Rather
    than emit a limit we know is wrong, count-based suggestions are withheld for
    these accounts until the engine counts strategies instead of legs.
    """
    by_root: Dict[str, List[datetime]] = defaultdict(list)
    for t in trades:
        if t.entry_time:
            by_root[_root(t.tradingsymbol)].append(t.entry_time)
    for times in by_root.values():
        times.sort()
        for a, b in zip(times, times[1:]):
            if (b - a).total_seconds() <= 60:
                return True
    return False


# ── Individual suggestions ───────────────────────────────────────────────────

def suggest_daily_trade_limit(
    sessions: Dict[Any, List[CompletedTrade]],
    current: Optional[int],
) -> Optional[Suggestion]:
    """
    Find the trade count above which the user's sessions stop finishing green.

    Scans every candidate cut, keeps the one that separates outcomes most, and
    requires both sides of the cut to hold real sessions. If no cut separates
    anything, the user's pace is not their problem and nothing is returned.
    """
    per_session = [(len(rows), sum(_pnl(t) for t in rows)) for rows in sessions.values()]
    if len(per_session) < MIN_SESSIONS:
        return None

    counts = sorted({c for c, _ in per_session})
    best: Optional[tuple] = None
    for k in counts:
        low = [pnl > 0 for c, pnl in per_session if c <= k]
        high = [pnl > 0 for c, pnl in per_session if c > k]
        if len(low) < MIN_BUCKET or len(high) < MIN_BUCKET:
            continue
        gap = _rate(low) - _rate(high)
        if gap >= MIN_SEPARATION and (best is None or gap > best[0]):
            best = (gap, k, _rate(low), _rate(high), len(low), len(high))

    if best is None:
        return None

    _, k, low_rate, high_rate, n_low, n_high = best
    if current is not None and k >= current:
        return None  # their rule is already at least this tight

    return Suggestion(
        field="daily_trade_limit",
        current_value=current,
        suggested_value=k,
        headline=f"Set your daily trade limit to {k}",
        evidence=[
            {"label": f"Sessions with {k} trades or fewer",
             "value": f"{n_low} sessions · {_pct(low_rate)} finished green"},
            {"label": f"Sessions above {k} trades",
             "value": f"{n_high} sessions · {_pct(high_rate)} finished green"},
        ],
        confidence=_confidence(len(per_session), MIN_SESSIONS),
        sample={"sessions": len(per_session), "window_days": WINDOW_DAYS},
    )


def suggest_daily_loss_limit(
    sessions: Dict[Any, List[CompletedTrade]],
    current: Optional[float],
) -> Optional[Suggestion]:
    """
    Place the daily loss limit where the user's own red days usually stop.

    Uses the 70th percentile of red-session losses: most bad days stay inside it,
    and the tail that breaks it is the tail worth interrupting. Stated as a count
    of sessions that would have reached the limit — never as money "saved", which
    would be a counterfactual we have no basis for.
    """
    reds = sorted(
        abs(s) for s in (sum(_pnl(t) for t in rows) for rows in sessions.values()) if s < 0
    )
    if len(sessions) < MIN_SESSIONS or len(reds) < MIN_BUCKET * 2:
        return None

    idx = max(0, min(len(reds) - 1, int(round(0.70 * (len(reds) - 1)))))
    raw = reds[idx]
    # Round to a number a person would actually choose.
    step = 500 if raw < 10_000 else 1_000
    suggested = float(max(step, round(raw / step) * step))

    if current is not None and current > 0 and suggested >= current:
        return None

    reached = sum(1 for r in reds if r >= suggested)
    worst = reds[-1]
    median_red = statistics.median(reds)

    return Suggestion(
        field="daily_loss_limit",
        current_value=current,
        suggested_value=suggested,
        headline=f"Set your daily loss limit to {_rs(suggested)}",
        evidence=[
            {"label": "Red sessions in this window",
             "value": f"{len(reds)} of {len(sessions)} · median {_rs(median_red)}"},
            {"label": f"Sessions that reached {_rs(suggested)}",
             "value": f"{reached} · deepest {_rs(worst)}"},
        ],
        confidence=_confidence(len(sessions), MIN_SESSIONS),
        sample={"sessions": len(sessions), "red_sessions": len(reds), "window_days": WINDOW_DAYS},
    )


def suggest_max_consecutive_losses(
    sessions: Dict[Any, List[CompletedTrade]],
    current: Optional[int],
) -> Optional[Suggestion]:
    """
    Find the losing streak after which the user's next trade stops working.

    Walks each session in exit order and records the outcome of the trade that
    followed a streak of exactly n losses. The smallest n whose follow-up trade
    wins rarely is the point worth stopping at.
    """
    after_streak: Dict[int, List[bool]] = defaultdict(list)
    total = 0
    for rows in sessions.values():
        streak = 0
        for t in rows:
            total += 1
            if streak > 0:
                after_streak[streak].append(_pnl(t) > 0)
            streak = streak + 1 if _pnl(t) < 0 else 0

    if total < MIN_TRADES or len(sessions) < MIN_SESSIONS:
        return None

    baseline_rows = [_pnl(t) > 0 for rows in sessions.values() for t in rows]
    baseline = _rate(baseline_rows)

    for n in (2, 3, 4, 5):
        rows = after_streak.get(n, [])
        if len(rows) < MIN_BUCKET:
            continue
        rate = _rate(rows)
        if baseline - rate < MIN_SEPARATION:
            continue
        if current is not None and n >= current:
            return None
        wins = sum(1 for r in rows if r)
        return Suggestion(
            field="max_consecutive_losses",
            current_value=current,
            suggested_value=n,
            headline=f"Stop after {n} consecutive losses",
            evidence=[
                {"label": f"Your next trade after {n} losses in a row",
                 "value": f"won {wins} of {len(rows)} · {_pct(rate)}"},
                {"label": "Your win rate the rest of the time",
                 "value": f"{_pct(baseline)} across {len(baseline_rows)} trades"},
            ],
            confidence=_confidence(len(rows), MIN_BUCKET),
            sample={"trades": total, "sessions": len(sessions), "window_days": WINDOW_DAYS},
        )
    return None


# `suggest_cooldown_after_loss` was removed 2026-09-02 with the user input.
# `cooldown_after_loss` is no longer a user-configurable rule, so there is
# nothing to suggest a value for. The engine keeps its own revenge window
# (`revenge_window_min`, fallback 10), which the trader never set.


# ── Entry point ──────────────────────────────────────────────────────────────

async def build_suggestions(
    broker_account_id: UUID,
    db: AsyncSession,
    current_rules: Dict[str, Any],
    window_days: int = WINDOW_DAYS,
) -> Dict[str, Any]:
    """
    Compute every rule suggestion the user's ledger supports.

    Returns the suggestion list plus the sampling context, so the caller can be
    honest about *why* the list is empty — "no data yet" and "your rules already
    match your data" are different answers and the UI must not conflate them.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    result = await db.execute(
        select(CompletedTrade).where(and_(
            CompletedTrade.broker_account_id == broker_account_id,
            CompletedTrade.exit_time >= cutoff,
        ))
    )
    trades = list(result.scalars().all())
    sessions = _group_by_session(trades)

    context = {
        "window_days": window_days,
        "trades": len(trades),
        "sessions": len(sessions),
        "min_sessions": MIN_SESSIONS,
        "min_trades": MIN_TRADES,
    }

    if len(sessions) < MIN_SESSIONS:
        return {
            "suggestions": [],
            "status": "insufficient_data",
            "reason": (
                f"{len(sessions)} of {MIN_SESSIONS} trading days recorded. "
                "Rules derived from fewer sessions would be guesswork."
            ),
            "context": context,
        }

    multi_leg = uses_multi_leg(trades)
    context["multi_leg_detected"] = multi_leg

    suggestions: List[Suggestion] = []

    # Count-based rules are withheld for spread traders — see uses_multi_leg.
    if not multi_leg:
        s = suggest_daily_trade_limit(sessions, current_rules.get("daily_trade_limit"))
        if s:
            suggestions.append(s)

    for builder, key in (
        (suggest_daily_loss_limit, "daily_loss_limit"),
        (suggest_max_consecutive_losses, "max_consecutive_losses"),
    ):
        try:
            s = builder(sessions, current_rules.get(key))
            if s:
                suggestions.append(s)
        except Exception as e:  # one bad builder must not empty the whole list
            logger.warning(f"[rule_suggestions] {key} failed: {e}")

    withheld = []
    if multi_leg:
        withheld.append({
            "field": "daily_trade_limit",
            "reason": (
                "You trade multi-leg structures. Each leg is currently counted as a "
                "separate trade, so a trade-count limit derived from this data would "
                "be too low to be useful."
            ),
        })

    return {
        "suggestions": [s.as_dict() for s in suggestions],
        "status": "ok" if suggestions else "no_change_needed",
        "reason": None if suggestions else (
            "Your current rules already match what your trading data supports."
        ),
        "withheld": withheld,
        "context": context,
    }
