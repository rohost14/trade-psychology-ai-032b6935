"""
What happened AFTER an alert — observed from trades, never asked.

Every threshold in this product is currently a judgement. Calibrating one needs
labelled outcomes, and the manual label already exists — `risk_alerts.outcome`
∈ ('stopped', 'took_anyway', 'not_useful'), migration 069 — with an adoption
rate of zero. 55 alerts, 0 outcomes. Asking is not going to start working.

So the outcome is inferred from what the trader did next, which is recorded
anyway. Nothing here needs a tap, a form, or a notification response.

WHAT THIS IS NOT
----------------
It does not overwrite `risk_alerts.outcome`. That column means "the trader told
us", and an inferred value written into it would destroy the distinction
between a fact and a guess. These observations are computed on demand and
returned; nothing is persisted. They are cheap (a session holds a handful of
alerts) and always recomputable, which also means a change to the inference
rules re-labels history instead of leaving two generations of labels in a
table.

THE TRAP, STATED FIRST
----------------------
Alerts fire when a position CLOSES, so most of them land late in the session.
"The trader stopped after the alert" is then a statement about the market
closing, not about the alert working. Any naive version of this file produces a
dataset where most alerts look heeded, and that dataset is worse than none.

So "stopped" is only claimed when stopping was a choice: there was still
meaningful session left AND the trader had been active. Otherwise the outcome
is NO_OPPORTUNITY and it is excluded from rate calculations rather than counted
as a success.

WHAT THE LABELS MEAN
--------------------
Two different questions, deliberately separated, because they have different
uses and mixing them is how you get a metric nobody can act on:

  heeded/ignored  — did the trader's behaviour change?  (product question)
  warranted       — did the behaviour keep costing money? (calibration question)

`warranted` is the one that can calibrate a threshold, and it does not depend
on the trader reacting at all. An alert can be ignored and still be correct.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field, asdict
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

IST = timezone(timedelta(hours=5, minutes=30))

#: NSE cash/F&O close. Session end must be the MARKET's close, never the last
#: trade of the day: derived from the trades, the final alert of every session
#: would show zero minutes remaining and the guard below would fire on almost
#: all of them — over-correcting into the opposite bad dataset, one where
#: nothing is ever decidable.
MARKET_CLOSE_IST = time(15, 30)

#: Minutes of session that must remain after an alert before "they stopped"
#: is a claim about the trader rather than about the closing bell. NFO squares
#: off intraday positions from ~15:20, so an alert at 15:10 leaves no room.
MIN_REMAINING_MIN = 45

#: An alert on a trader who was going to stop anyway says nothing. Require that
#: they had been trading at a pace where continuing was the default.
MIN_TRADES_BEFORE = 2

# Outcome vocabulary. Deliberately not the same words as the manual column —
# these are observations, and using 'stopped' for both would invite someone to
# merge the two into one field later.
HEEDED = "heeded"                   # behaviour changed: stopped, or the pattern did not recur
IGNORED = "ignored"                 # same pattern fired again in the same session
NO_OPPORTUNITY = "no_opportunity"   # session ended too soon to tell — EXCLUDE from rates
UNDETERMINED = "undetermined"       # not enough data


@dataclass
class Observation:
    alert_id: str
    pattern_type: str
    severity: str
    detected_at: datetime

    # ── Behaviour change (the product question) ──────────────────────────
    behaviour: str = UNDETERMINED
    trades_after: int = 0
    minutes_to_next_entry: Optional[float] = None
    minutes_remaining_in_session: Optional[float] = None
    pattern_repeated: bool = False

    # ── Cost (the calibration question) ──────────────────────────────────
    #: None when the alert is the last thing that happened — absence of
    #: evidence, recorded as such rather than as a zero.
    warranted: Optional[bool] = None
    trigger_pnl: Optional[float] = None
    pnl_after: Optional[float] = None
    escalated_after: Optional[bool] = None

    notes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["detected_at"] = self.detected_at.isoformat() if self.detected_at else None
        return d


def _entry(t: Any) -> Optional[datetime]:
    return getattr(t, "entry_time", None) or (t.get("entry_time") if isinstance(t, dict) else None)


def _exit(t: Any) -> Optional[datetime]:
    return getattr(t, "exit_time", None) or (t.get("exit_time") if isinstance(t, dict) else None)


def _pnl(t: Any) -> float:
    v = getattr(t, "realized_pnl", None)
    if v is None and isinstance(t, dict):
        v = t.get("realized_pnl", t.get("pnl"))
    return float(v or 0)


def _notional(t: Any) -> float:
    qty = getattr(t, "total_quantity", None)
    price = getattr(t, "avg_entry_price", None)
    if isinstance(t, dict):
        qty = t.get("total_quantity", t.get("qty")) if qty is None else qty
        price = t.get("avg_entry_price", t.get("entry")) if price is None else price
    return abs(float(qty or 0)) * float(price or 0)


def observe_session(
    alerts: Sequence[Any],
    trades: Sequence[Any],
    session_end: Optional[datetime] = None,
) -> List[Observation]:
    """
    Label every alert in one session from the trades around it.

    `alerts` need `.id`, `.pattern_type`, `.severity`, `.detected_at` (or the
    same keys in a dict); `trades` need entry/exit times and realized P&L.
    Both ORM rows and plain dicts work, so the same code labels live alerts and
    a replayed tradebook — the replay is the only place a year of them exists.
    """
    def _a(alert, key, default=None):
        if isinstance(alert, dict):
            return alert.get(key, default)
        return getattr(alert, key, default)

    closed = sorted(
        [t for t in trades if _entry(t) and _exit(t)],
        key=lambda t: _exit(t),
    )
    if session_end is None and closed:
        last_ist = max(_exit(t) for t in closed).astimezone(IST)
        session_end = datetime.combine(
            last_ist.date(), MARKET_CLOSE_IST, tzinfo=IST)

    # The trader's own pace, for judging whether a gap is a pause or normal.
    gaps = []
    for prev, nxt in zip(closed, closed[1:]):
        if _exit(prev) and _entry(nxt):
            g = (_entry(nxt) - _exit(prev)).total_seconds() / 60
            if g >= 0:
                gaps.append(g)
    median_gap = statistics.median(gaps) if gaps else None

    fired_after: Dict[str, List[datetime]] = {}
    for al in alerts:
        fired_after.setdefault(str(_a(al, "pattern_type")), []).append(_a(al, "detected_at"))

    out: List[Observation] = []
    for al in alerts:
        at = _a(al, "detected_at")
        pattern = str(_a(al, "pattern_type"))
        obs = Observation(
            alert_id=str(_a(al, "id", "")),
            pattern_type=pattern,
            severity=str(_a(al, "severity", "")),
            detected_at=at,
        )
        if at is None:
            obs.notes.append("no detected_at")
            out.append(obs)
            continue

        before = [t for t in closed if _exit(t) and _exit(t) <= at]
        after = [t for t in closed if _entry(t) and _entry(t) > at]
        obs.trades_after = len(after)
        obs.trigger_pnl = _pnl(before[-1]) if before else None

        if session_end:
            obs.minutes_remaining_in_session = round(
                (session_end - at).total_seconds() / 60, 1)
        if after:
            obs.minutes_to_next_entry = round(
                (_entry(after[0]) - at).total_seconds() / 60, 1)

        # ── Did the same pattern fire again afterwards? ───────────────────
        obs.pattern_repeated = any(
            other and other > at for other in fired_after.get(pattern, [])
        )

        # ── Behaviour label ───────────────────────────────────────────────
        # Order matters. A repeat is positive evidence the alert did not land
        # and is trustworthy whenever it happens, so it is checked before the
        # no-opportunity guard — a pattern that recurred obviously had the
        # opportunity to recur.
        if obs.pattern_repeated:
            obs.behaviour = IGNORED
        elif len(before) < MIN_TRADES_BEFORE:
            obs.behaviour = NO_OPPORTUNITY
            obs.notes.append(
                f"only {len(before)} trade(s) before the alert — no established pace")
        elif (obs.minutes_remaining_in_session is not None
              and obs.minutes_remaining_in_session < MIN_REMAINING_MIN
              and not after):
            # The single most important guard in this file. Alerts fire when a
            # position closes, so they cluster near the end of the day; without
            # this, "they stopped" mostly means "the market did".
            obs.behaviour = NO_OPPORTUNITY
            obs.notes.append(
                f"only {obs.minutes_remaining_in_session:.0f}min of session left — "
                f"stopping was not a choice")
        elif not after:
            obs.behaviour = HEEDED
            obs.notes.append("no further entries with session remaining")
        elif median_gap and obs.minutes_to_next_entry is not None \
                and obs.minutes_to_next_entry >= median_gap * 2:
            obs.behaviour = HEEDED
            obs.notes.append(
                f"next entry {obs.minutes_to_next_entry:.0f}min vs "
                f"{median_gap:.0f}min median — paced down")
        else:
            obs.behaviour = IGNORED

        # ── Cost label — independent of whether the trader reacted ────────
        if after:
            obs.pnl_after = round(sum(_pnl(t) for t in after), 2)
            obs.warranted = obs.pnl_after < 0
            if before:
                obs.escalated_after = _notional(after[0]) > _notional(before[-1])
        else:
            # Nothing followed, so the behaviour had no chance to cost more.
            # NOT the same as "it cost nothing" — left None so it is excluded
            # rather than counted as a correct silence.
            obs.notes.append("no trades after — cost label unavailable")

        out.append(obs)
    return out


def summarise(observations: Sequence[Observation]) -> Dict[str, Dict[str, Any]]:
    """
    Per-pattern rates, with the undecidable cases excluded rather than buried.

    `n_behaviour` and `n_cost` are different denominators on purpose — an alert
    can be usable for one question and not the other, and averaging over a
    single count would quietly mix them.
    """
    by: Dict[str, List[Observation]] = {}
    for o in observations:
        by.setdefault(o.pattern_type, []).append(o)

    out = {}
    for pattern, obs in sorted(by.items()):
        decidable = [o for o in obs if o.behaviour in (HEEDED, IGNORED)]
        costed = [o for o in obs if o.warranted is not None]
        out[pattern] = {
            "alerts": len(obs),
            "n_behaviour": len(decidable),
            "heeded": sum(1 for o in decidable if o.behaviour == HEEDED),
            "heeded_rate": (round(sum(1 for o in decidable if o.behaviour == HEEDED)
                                  / len(decidable), 3) if decidable else None),
            "n_cost": len(costed),
            "warranted": sum(1 for o in costed if o.warranted),
            "warranted_rate": (round(sum(1 for o in costed if o.warranted)
                                     / len(costed), 3) if costed else None),
            "no_opportunity": sum(1 for o in obs if o.behaviour == NO_OPPORTUNITY),
            "median_pnl_after": (round(statistics.median(
                [o.pnl_after for o in obs if o.pnl_after is not None]), 2)
                if any(o.pnl_after is not None for o in obs) else None),
        }
    return out
