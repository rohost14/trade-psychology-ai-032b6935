"""
Entry-time evaluation of the rules a trader can breach the moment they enter.

E3. These are the checks whose condition is fully known at entry — arithmetic
against a limit the trader wrote, or a clock reading — so waiting for the
position to close only makes the answer later, never better.

Everything here is a pure function. The severity ladder in particular is shared
with the exit-time detector rather than restated: two copies of "80% is caution,
100% is danger, 120% is critical" is exactly the drift that produced the
pattern-name and severity bugs elsewhere in this codebase.

Deliberately NOT here — and this is the substance of E3 rather than an omission:

  **opening_5min_trap was RETIRED 2026-08-30 (Pattern 21).** This note is kept
  because its reasoning generalises and was, in the end, the reason the detector
  went. It said: the raw condition is "entered in the first ten minutes", which
  is a very common and entirely innocent thing to do, so the exit-time detector
  refuses to fire on that alone — "Only fires on LOSING trades — a profitable
  opening trade could be a deliberate strategy". Firing it at entry would
  reintroduce the noise its author removed, so it stayed at exit.

  That outcome gate is exactly what retired it. If the behaviour is innocent and
  only the result distinguishes a firing, the result is what is being flagged:
  it discarded 42% of window entries for having made money, and the window
  measured 39.4% win against 39.5% for the rest of the day. The generalisable
  rule for E3 stands — a detector that must read an OUTCOME cannot move to
  entry — and a detector that can ONLY separate cases by outcome should be
  looked at hard. See docs/patterns/21-session_windows/.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


# ---------------------------------------------------------------------------
# The constitution ladder — one definition
# ---------------------------------------------------------------------------

def constitution_ladder(
    ratio: float,
    approaching: float = 0.80,
    severe: float = 1.20,
) -> Optional[str]:
    """
    How serious is being at `ratio` of your own limit?

    Mirrors BehaviorEngine._detect_constitution_violation exactly. `critical`
    at 120% is the severity that reaches an accountability partner, so the two
    paths agreeing is not cosmetic.
    """
    if ratio >= severe:
        return "critical"
    if ratio >= 1.0:
        return "danger"
    if ratio >= approaching:
        return "caution"
    return None


# ---------------------------------------------------------------------------
# Rules that are pure arithmetic at entry
# ---------------------------------------------------------------------------

def evaluate_trade_limit(
    trades_today: int,
    limit: Optional[int],
    approaching: float = 0.80,
    severe: float = 1.20,
) -> Optional[Dict[str, Any]]:
    """
    Have they used up their self-imposed trade budget for the day?

    Known in full at entry: this entry is the Nth of the day and the limit is a
    number they wrote down. Told at exit, the trade is already on.
    """
    if not limit or limit <= 0 or trades_today <= 0:
        return None
    ratio = trades_today / float(limit)
    severity = constitution_ladder(ratio, approaching, severe)
    if not severity:
        return None
    verb = "breached" if ratio >= 1.0 else "approaching"
    return {
        "rule": "daily_trade_limit",
        "severity": severity,
        "message": (
            f"Your daily trade limit {verb}: {trades_today} of {int(limit)} trades — "
            f"this position is OPEN."
        ),
        "limit": int(limit),
        "current": trades_today,
        "ratio": round(ratio, 2),
    }


def evaluate_loss_limit(
    session_pnl: float,
    limit: Optional[float],
    approaching: float = 0.80,
    severe: float = 1.20,
) -> Optional[Dict[str, Any]]:
    """
    Are they entering a new position while already at their loss limit?

    Uses realized session P&L, the same input the exit-time rule uses — P&L is
    raw and realized everywhere in this product.
    """
    if not limit or limit <= 0 or session_pnl >= 0:
        return None
    loss = abs(float(session_pnl))
    ratio = loss / float(limit)
    severity = constitution_ladder(ratio, approaching, severe)
    if not severity:
        return None
    verb = "breached" if ratio >= 1.0 else "approaching"
    return {
        "rule": "daily_loss_limit",
        "severity": severity,
        "message": (
            f"Your daily loss limit {verb}: ₹{loss:,.0f} of ₹{float(limit):,.0f} "
            f"({ratio * 100:.0f}%) — and you have just opened another position."
        ),
        "limit": float(limit),
        "current": round(loss, 2),
        "ratio": round(ratio, 2),
    }


# ---------------------------------------------------------------------------
# End-of-session MIS entries
# ---------------------------------------------------------------------------
# Exchange-specific square-off, matching the exit-time detector. A flat 15:00
# cutoff once meant every evening MIS entry on MCX — which trades to 23:30 —
# was scored as end-of-session panic, so this must stay exchange-aware.

def squareoff_window(exchange: Optional[str], on_day: datetime) -> Tuple[datetime, str]:
    """(when the panic window starts, the square-off time as text) in IST."""
    exch = (exchange or "").upper()
    if exch in ("MCX", "CDS", "BCD"):
        from app.core.exchange_constants import get_close_time
        close_t = get_close_time(exch)
        squareoff_min = close_t.hour * 60 + close_t.minute - 5
        panic_start_min = squareoff_min - 25
    elif exch in ("NFO", "BFO"):
        squareoff_min = 15 * 60 + 25
        panic_start_min = 15 * 60
    else:
        squareoff_min = 15 * 60 + 15
        panic_start_min = 15 * 60

    panic_start = on_day.replace(
        hour=panic_start_min // 60, minute=panic_start_min % 60,
        second=0, microsecond=0,
    )
    return panic_start, f"{squareoff_min // 60:02d}:{squareoff_min % 60:02d}"


def evaluate_mis_panic(
    entry_ist: datetime,
    exchange: Optional[str],
    product: Optional[str],
    late_mis_count: int,
    caution_count: int = 2,
    danger_count: int = 3,
) -> Optional[Dict[str, Any]]:
    """
    Repeated MIS entries in the run-up to auto-square-off.

    The trigger is a count of late entries, which is fully known at entry — and
    this is the detector where lateness matters most, because the alert's whole
    content is "there are N minutes left before this is closed for you". After
    the position closed, that sentence has no purchase.

    The exit-time version demotes to `info` when every late trade was profitable
    and the session is green. That demotion cannot be evaluated at entry for the
    position just opened, so this fires at the ordinary severity and the exit
    pass remains free to record the kinder reading.
    """
    if (product or "").upper() not in ("MIS", "INTRADAY"):
        return None
    panic_start, squareoff_str = squareoff_window(exchange, entry_ist)
    if entry_ist < panic_start:
        return None
    if late_mis_count < caution_count:
        return None

    minutes_left = int(
        (entry_ist.replace(
            hour=int(squareoff_str[:2]), minute=int(squareoff_str[3:]),
            second=0, microsecond=0,
        ) - entry_ist).total_seconds() / 60
    )
    severity = "danger" if late_mis_count >= danger_count else "caution"
    return {
        "severity": severity,
        "message": (
            f"{late_mis_count} MIS entries after {panic_start.strftime('%H:%M')} IST today. "
            f"{exchange or 'MIS'} auto-squares off at {squareoff_str} — "
            f"{max(minutes_left, 0)} minutes after this entry."
        ),
        "late_mis_count": late_mis_count,
        "squareoff": squareoff_str,
        "minutes_to_squareoff": max(minutes_left, 0),
    }


# ---------------------------------------------------------------------------
# Counting today's entries from the ledger
# ---------------------------------------------------------------------------

class _LedgerLeg:
    """Adapts a PositionLedger row to what count_structures reads."""

    __slots__ = ("tradingsymbol", "entry_time", "direction")

    def __init__(self, tradingsymbol: str, entry_time, fill_qty: int):
        self.tradingsymbol = tradingsymbol
        self.entry_time = entry_time
        self.direction = "LONG" if (fill_qty or 0) > 0 else "SHORT"


def count_entries_today(ledger_rows: Sequence[Any]) -> int:
    """
    How many trading decisions has this account opened today?

    Counted from opening ledger entries rather than closed rounds, because at
    entry time the position that matters has not closed. Structure-aware for the
    same reason the exit-time counters are: a four-leg condor is one decision,
    and counting its legs would put a spread trader over their own trade limit
    after two positions.
    """
    from app.services.fill_classification import POSITION_OPENING_FILLS
    from app.services.strategy_detector import count_structures

    legs = [
        _LedgerLeg(r.tradingsymbol, r.occurred_at, r.fill_qty)
        for r in ledger_rows
        if getattr(r, "entry_type", None) in POSITION_OPENING_FILLS
    ]
    return count_structures(legs)


# ── Repeated breach of the declared daily range ────────────────────────────
#
# TWO DIFFERENT CLAIMS, kept apart on purpose.
#
#   "You exceeded your daily limit"                  — a FACT about one day.
#       Emitted by `daily_overtrading` at the moment the count passes the
#       declared maximum. Needs no history and makes no interpretation.
#
#   "Repeatedly exceeding your limit may indicate overtrading"
#       — an OBSERVATION about a habit, and only defensible once there is
#       repetition to point at. That is what this function measures.
#
# It counts BREACH DAYS from the alerts the detector already wrote, rather than
# recomputing daily counts from trades. Two reasons: the detector's count is the
# one the trader was actually shown, so a second derivation could disagree with
# it; and one alert per breach day already exists, so counting them is exact.

#: How many of the recent active days must be breaches before the habit claim is
#: made, and how far back "recent" reaches.
#:
#: A PRODUCT DECISION, stated as one. It is not derived from any population and
#: it is not a statistical threshold - there is no evidence base for "three in
#: five means overtrading", and pretending otherwise would be the exact class of
#: unsourced claim this codebase has spent days removing. It is simply where we
#: draw the line between "a day that got away" and "a pattern", chosen to need
#: real repetition while still being reachable inside a working week.
REPEATED_BREACH_DAYS = 3
REPEATED_BREACH_WINDOW = 5


def breach_days_in_window(breach_dates, active_dates, window: int = REPEATED_BREACH_WINDOW):
    """
    How many of the last `window` ACTIVE days breached the declared maximum.

    `active_dates` is every day the trader traded; `breach_dates` the subset
    that breached. The window is over ACTIVE days, not calendar days, so a week
    off does not dilute the count and a trader who trades twice a month is
    judged on their own last five sessions rather than on the calendar.

    Returns (breaches_in_window, window_size). The caller decides what to say.
    """
    active = sorted({d for d in active_dates})
    if not active:
        return 0, 0
    recent = active[-window:]
    breached = {d for d in breach_dates}
    return sum(1 for d in recent if d in breached), len(recent)


def is_repeated_breach(breach_dates, active_dates,
                       threshold: int = REPEATED_BREACH_DAYS,
                       window: int = REPEATED_BREACH_WINDOW) -> bool:
    """
    Whether the habit claim is defensible yet.

    False until there are enough active days to fill the window. Calling three
    breaches in three sessions "repeated" would be true but useless - the
    trader has no normal for it to depart from, and the observation would fire
    on a trader's first week.
    """
    hits, size = breach_days_in_window(breach_dates, active_dates, window)
    if size < window:
        return False
    return hits >= threshold
