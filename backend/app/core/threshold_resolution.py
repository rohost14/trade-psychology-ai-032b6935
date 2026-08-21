"""
Threshold resolution — where the number a detector compares against comes from.

Design: docs/THRESHOLD_RESOLUTION_DESIGN.md

A detector asking "is 5 losses in a row unusual?" needs a number. That number
should come from the most personal source available, and the system should be
able to say WHICH source, because "your limit" and "our starting guess" are
different claims and the product makes both.

The ladder, most personal first:

    1 HISTORY     your own past trades          ~20 sessions / ~100 trades
    2 SESSION     your own trades today         2-5 trades      (analytics only)
    3 DECLARED    a rule you set for yourself   day 1 if set
    4 CAPITAL     a ratio of your capital       day 1, zero input
    5 POPULATION  median of comparable users    once we have users  (not built)
    6 GLOBAL      a constant in this repo       always — last resort

`resolve_thresholds(profile, session_trades)` walks it and returns both the
values and, for every key, a `Resolved` record saying which rung answered and how
confident it is.

**What each rung currently covers.** Rung 1 reads a versioned baseline written
by one service (`baseline_service`); v1 shapes are still read so stored
baselines keep working until their next recompute. Rung 2
covers `panic_exit_min` and `rapid_reentry_min` only, both belonging to
`notification_level=0` detectors, so it cannot change alert volume; extending it
to a threshold that fires alerts needs a replay behind it. Rung 4 covers
`max_position_pct_*` and the three former rupee floors. Rung 5 is named but not
built — naming it is what makes its absence visible instead of silently falling
through to rung 6.

Everything else resolves at rung 6. On a cold-start profile that is 100% of
keys; with capital and declared rules known it is still the large majority.

Known defects it still preserves (the two-writer race that used to head this
list was fixed 2026-08-22):

  * universal floors are applied last, so they override a trader's own declared
    rule;
  * personalisation only ever loosens (`min`/`max` against the default), so a
    trader quieter than the default keeps the default.

Each is filed in the design doc with a proposed fix.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional


class Source(str, Enum):
    """Which rung of the ladder produced a value."""

    HISTORY = "history"        # rung 1 — the trader's own past trades
    SESSION = "session"        # rung 2 — the trader's own trades today (not yet built)
    DECLARED = "declared"      # rung 3 — a rule the trader set
    CAPITAL = "capital"        # rung 4 — a ratio of the trader's capital
    POPULATION = "population"  # rung 5 — comparable users (not yet built)
    GLOBAL = "global"          # rung 6 — a constant in this repo
    FLOOR = "floor"            # a universal floor overrode whatever was resolved
    FACT = "fact"              # not a threshold: a profile fact passed through


#: Rung number per source, for display and for asserting we are not regressing
#: (a key that used to resolve at rung 1 should not silently drop to rung 6).
RUNG = {
    Source.HISTORY: 1,
    Source.SESSION: 2,
    Source.DECLARED: 3,
    Source.CAPITAL: 4,
    Source.POPULATION: 5,
    Source.GLOBAL: 6,
    Source.FLOOR: 6,
    Source.FACT: 0,
}


@dataclass(frozen=True)
class Resolved:
    """One threshold, and where it came from."""

    value: Any
    source: Source
    #: 0..1. How much the personal evidence was trusted. 1.0 for a declared rule
    #: (a commitment is not an estimate); 0.0 for a bare global constant.
    confidence: float = 0.0
    #: Human-readable provenance, e.g. "P75 of your sessions (n=40)".
    detail: Optional[str] = None

    @property
    def rung(self) -> int:
        return RUNG[self.source]

    @property
    def is_personal(self) -> bool:
        """True when this value says something about THIS trader."""
        return self.source in (
            Source.HISTORY, Source.SESSION, Source.DECLARED, Source.CAPITAL
        )


class ThresholdSet:
    """
    The resolved thresholds plus their provenance.

    Behaves as the plain dict detectors already expect — `ts["daily_trade_limit"]`
    and `ts.get(k, default)` return the bare value — so nothing downstream has to
    change to adopt it.
    """

    __slots__ = ("values", "meta")

    def __init__(self, values: Dict[str, Any], meta: Dict[str, Resolved]):
        self.values = values
        self.meta = meta

    def __getitem__(self, key: str) -> Any:
        return self.values[key]

    def __contains__(self, key: str) -> bool:
        return key in self.values

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def items(self):
        return self.values.items()

    def keys(self):
        return self.values.keys()

    def explain(self, key: str) -> Optional[Resolved]:
        """Where did this threshold come from?"""
        return self.meta.get(key)

    def personal_keys(self) -> Dict[str, Resolved]:
        """Every threshold that says something about this trader specifically."""
        return {k: r for k, r in self.meta.items() if r.is_personal}


def resolve_thresholds(profile=None, session_trades=None) -> ThresholdSet:
    """
    Walk the ladder and return values + provenance.

    `session_trades` is today's closed trades, newest last. When supplied it
    enables rung 2 — comparisons against what this trader has done *today*,
    which is the rung that makes day one work. When omitted (every caller that
    has not been updated) rung 2 is skipped and nothing changes.
    """
    from app.core.trading_defaults import COLD_START_DEFAULTS, UNIVERSAL_FLOORS

    values: Dict[str, Any] = dict(COLD_START_DEFAULTS)
    meta: Dict[str, Resolved] = {
        k: Resolved(v, Source.GLOBAL, 0.0, "repo default")
        for k, v in COLD_START_DEFAULTS.items()
    }

    def put(key: str, value: Any, source: Source,
            confidence: float = 0.0, detail: Optional[str] = None) -> None:
        values[key] = value
        meta[key] = Resolved(value, source, confidence, detail)

    if profile is not None:
        _apply_history(profile, values, meta, put)
        _apply_declared(profile, values, put)
        _apply_profile_facts(profile, values, put)
    else:
        _apply_cold_start(put)

    # Rung 2 sits below history and above the repo constant: today's evidence is
    # more specific than a 90-day median, but a declared rule still outranks it.
    if session_trades:
        _apply_session(session_trades, values, put)

    # Universal floors, applied last — they win over every rung above, including
    # a rule the trader set for themselves. Preserved as-is; see module docstring.
    for key, floor in UNIVERSAL_FLOORS.items():
        if values.get(key, 0) < floor:
            put(key, floor, Source.FLOOR, 0.0,
                f"raised to universal floor {floor}")

    return ThresholdSet(values, meta)


# ---------------------------------------------------------------------------
# Rung 1 — the trader's own history
# ---------------------------------------------------------------------------

def _apply_history(profile, values: Dict[str, Any], meta: Dict[str, Resolved],
                   put: Callable) -> None:
    """
    Read the trader's own baseline.

    Branches on `version`, not on the shape. Two services used to write this same
    JSONB key in incompatible shapes and the reader sniffed for a `metrics` key
    to tell them apart — so which personalisation a trader got depended on which
    service wrote last. `baseline_service` is now the only writer and stamps
    `version: 2`; v1 is still read so stored baselines keep working until they
    are next recomputed.
    """
    baseline = (getattr(profile, "detected_patterns", None) or {}).get("baseline")
    if not isinstance(baseline, dict):
        return

    version = baseline.get("version")
    metrics = baseline.get("metrics")

    if version == 2 and isinstance(metrics, dict):
        _apply_history_v2(metrics, values, put)
        return

    if metrics and isinstance(metrics, dict):
        _apply_history_v1_metrics(metrics, values, put)
        return

    # Legacy flat shape — direct assignment, no confidence, no blend.
    #
    # The key list below DOES include revenge_window_caution_min, but a trader on
    # this path still keeps the global revenge window: the flat writer emits
    # `revenge_window_min`, a different key, so the lookup simply misses. Same
    # story for burst — it writes `burst_trades_per_15min` while this reads
    # `burst_trades_per_30min_caution`. Two of the five personalised values are
    # silently dropped on a name mismatch, with no error and no log.
    #
    # Faithfully reproduced; filed as H1 in docs/ENGINE_BACKLOG.md.
    n = baseline.get("session_count") or baseline.get("sessions_analyzed") or 0
    for key in ("daily_trade_limit", "burst_trades_per_30min_caution",
                "revenge_window_caution_min", "consecutive_loss_caution",
                "consecutive_loss_danger"):
        if baseline.get(key) is not None:
            put(key, baseline[key], Source.HISTORY, 1.0,
                f"personal baseline (n={n} sessions)")


def _blend(rec, default_val: float, derive=None):
    """
    effective = c*personal + (1-c)*default, with c = the metric's own confidence.

    Continuous, so there is no activation cliff and nobody has to be classified:
    three sessions barely move the number, forty decide it.
    """
    if not rec or rec.get("value") is None:
        return default_val, 0.0, None
    conf = float(rec.get("confidence") or 0)
    personal = float(rec["value"])
    if derive is not None:
        personal = derive(personal)
    blended = conf * personal + (1 - conf) * default_val
    pct = rec.get("percentile")
    what = f"p{pct:.0f} of your own" if pct else "your own median"
    return blended, conf, (
        f"{what} ({rec['value']}, n={rec.get('n', '?')}, confidence {conf:.2f})"
    )


def _apply_history_v2(metrics: Dict[str, Any], values: Dict[str, Any],
                      put: Callable) -> None:
    """
    Thresholds as points on the trader's own distribution.

    Every value here is a percentile of something this trader actually did, so
    there is no multiplier to defend. The v1 path had to invent them — `median x
    1.5` for the daily limit, `median / 4` for burst, `median x 0.5` for the
    revenge window — because the metrics it was given were averages rather than
    percentiles. Those three constants disappear with this path.
    """
    def place(key: str, metric_key: str, floor=None, cast=None, extra=None):
        v, c, d = _blend(metrics.get(metric_key), float(values[key]))
        if floor is not None:
            v = max(v, floor)
        v = cast(v) if cast else round(v, 1)
        put(key, v, Source.HISTORY if c else Source.GLOBAL, c, d)
        return c

    c = place("daily_trade_limit", "daily_trades_p75", cast=lambda x: int(round(x)))
    put("daily_trade_danger",
        max(values["daily_trade_limit"] + 1,
            int(round(values["daily_trade_limit"] * 1.5))),
        Source.HISTORY if c else Source.GLOBAL, c, "derived from daily_trade_limit")

    c = place("burst_trades_per_30min_caution", "burst_per_30min_p75",
              floor=3.0, cast=lambda x: int(round(x)))
    put("burst_trades_per_30min_danger",
        max(values["burst_trades_per_30min_caution"] + 2,
            int(round(values["burst_trades_per_30min_caution"] * 1.6))),
        Source.HISTORY if c else Source.GLOBAL, c,
        "derived from burst_trades_per_30min_caution")

    # The fast end of their own re-entry pace. v1 wrote this to
    # `revenge_window_min` while the reader looked for
    # `revenge_window_caution_min`, so it never arrived at all.
    place("revenge_window_caution_min", "reentry_after_loss_p25", floor=1.0)

    c = place("consecutive_loss_caution", "loss_streak_p60",
              floor=2.0, cast=lambda x: int(round(x)))
    v, c2, d = _blend(metrics.get("loss_streak_p85"),
                      float(values["consecutive_loss_danger"]))
    put("consecutive_loss_danger",
        max(values["consecutive_loss_caution"] + 1, int(round(v))),
        Source.HISTORY if c2 else Source.GLOBAL, c2, d)


def _apply_history_v1_metrics(metrics: Dict[str, Any], values: Dict[str, Any],
                              put: Callable) -> None:
    """
    The pre-versioning nested shape: averages plus invented multipliers.

    Kept only so baselines already stored keep resolving until their next
    recompute. Do not extend it.
    """
    v, c, d = _blend(metrics.get("avg_daily_trades"),
                     float(values["daily_trade_limit"]), lambda x: x * 1.5)
    put("daily_trade_limit", int(round(v)),
        Source.HISTORY if c else Source.GLOBAL, c, d)
    put("daily_trade_danger",
        max(values["daily_trade_limit"] + 1,
            int(round(values["daily_trade_limit"] * 1.5))),
        Source.HISTORY if c else Source.GLOBAL, c, "derived from daily_trade_limit")

    v, c, d = _blend(metrics.get("avg_daily_trades"),
                     float(values["burst_trades_per_30min_caution"]),
                     lambda x: max(3.0, x / 4))
    put("burst_trades_per_30min_caution", int(round(v)),
        Source.HISTORY if c else Source.GLOBAL, c, d)
    put("burst_trades_per_30min_danger",
        max(values["burst_trades_per_30min_caution"] + 2,
            int(round(values["burst_trades_per_30min_caution"] * 1.6))),
        Source.HISTORY if c else Source.GLOBAL, c,
        "derived from burst_trades_per_30min_caution")

    v, c, d = _blend(metrics.get("median_reentry_after_loss_min"),
                     float(values["revenge_window_caution_min"]),
                     lambda x: max(5.0, x * 0.5))
    put("revenge_window_caution_min", round(v, 1),
        Source.HISTORY if c else Source.GLOBAL, c, d)


# ---------------------------------------------------------------------------
# Rung 3 — rules the trader set for themselves
# ---------------------------------------------------------------------------

def _apply_declared(profile, values: Dict[str, Any], put: Callable) -> None:
    """
    A declared rule is a commitment, not an estimate, so confidence is 1.0.

    It is applied only where it is MORE restrictive than what is already
    resolved: a stale `daily_trade_limit=50` should not silently disable a
    detector. Preserved as-is, though it means a trader cannot deliberately
    loosen a limit the baseline tightened.
    """
    if getattr(profile, "daily_trade_limit", None):
        user_limit = int(profile.daily_trade_limit)
        if user_limit < values["daily_trade_limit"]:
            put("daily_trade_limit", user_limit, Source.DECLARED, 1.0,
                "your rule (tighter than resolved)")
        put("daily_trade_danger", int(values["daily_trade_limit"] * 1.5),
            Source.DECLARED, 1.0, "derived from daily_trade_limit")

    if getattr(profile, "cooldown_after_loss", None):
        user_cooldown = int(profile.cooldown_after_loss)
        if user_cooldown > values["revenge_window_caution_min"]:
            put("revenge_window_caution_min", user_cooldown, Source.DECLARED, 1.0,
                "your cooldown rule (longer than resolved)")
        put("revenge_window_min", user_cooldown, Source.DECLARED, 1.0,
            "your cooldown rule")


# ---------------------------------------------------------------------------
# Rung 4 + profile facts
# ---------------------------------------------------------------------------

def _apply_profile_facts(profile, values: Dict[str, Any], put: Callable) -> None:
    """Facts read straight off the profile, plus the one capital-derived pair."""
    for key in ("trading_capital", "daily_loss_limit", "max_position_size",
                "max_consecutive_losses"):
        put(key, getattr(profile, key, None), Source.FACT, 1.0, "declared")

    put("restricted_windows", getattr(profile, "restricted_windows", None) or [],
        Source.FACT, 1.0, "declared")
    put("user_daily_trade_limit", getattr(profile, "daily_trade_limit", None),
        Source.FACT, 1.0, "declared")
    put("user_cooldown_min", getattr(profile, "cooldown_after_loss", None),
        Source.FACT, 1.0, "declared")

    # An EMPTY learned value is not personal knowledge. Marking [] or None as
    # HISTORY made `personal_keys()` claim we knew something about a trader we
    # knew nothing about — the exact thing provenance exists to prevent, and the
    # Rules page would have rendered it as "your number".
    dp = getattr(profile, "detected_patterns", None) or {}
    hours = (dp.get("time_patterns") or {}).get("danger_hours") or []
    put("danger_hours", hours,
        Source.HISTORY if hours else Source.GLOBAL,
        1.0 if hours else 0.0,
        "learned danger hours" if hours else "none learned yet")

    bl = dp.get("baseline") or {}
    blm = bl.get("metrics") or {}
    put("baseline_sessions", bl.get("sessions_analyzed", 0), Source.FACT, 1.0, None)
    for key, metric in (("baseline_win_rate", "win_rate"),
                        ("baseline_profit_factor", "profit_factor")):
        val = blm.get(metric)
        put(key, val,
            Source.HISTORY if val is not None else Source.GLOBAL,
            1.0 if val is not None else 0.0,
            None if val is not None else "not computed yet")

    put("sl_percent_futures", getattr(profile, "sl_percent_futures", None) or 1.0,
        Source.FACT, 1.0, None)
    put("sl_percent_options", getattr(profile, "sl_percent_options", None) or 50.0,
        Source.FACT, 1.0, None)
    put("risk_tolerance", getattr(profile, "risk_tolerance", None) or "moderate",
        Source.FACT, 1.0, None)

    if values.get("max_position_size"):
        size = float(values["max_position_size"])
        put("max_position_pct_caution", size, Source.CAPITAL, 1.0,
            "your declared max position size")
        put("max_position_pct_danger", size * 2.0, Source.CAPITAL, 1.0,
            "2x your declared max position size")

    _apply_capital_ratios(values, put)


# ---------------------------------------------------------------------------
# Rung 2 — what this trader has done today
# ---------------------------------------------------------------------------

#: Trades needed before today's evidence is trusted completely. Deliberately
#: small: the point of this rung is that it works on day one. Below it the value
#: is shrunk toward the repo default rather than switched, so three trades nudge
#: and ten decide — there is no cliff and nobody has to be classified.
_SESSION_TARGET_N = 8

#: Fraction of the trader's own median used as the "unusually fast" line. Half
#: your normal hold is short for you whether your normal is three minutes or two
#: hours — which is the entire reason this rung exists and a fixed 5 minutes
#: cannot work for both.
_SESSION_FAST_FRACTION = 0.5


def _minutes(a, b) -> Optional[float]:
    if a is None or b is None:
        return None
    delta = (b - a).total_seconds() / 60.0
    return delta if delta >= 0 else None


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return None
    mid = n // 2
    return xs[mid] if n % 2 else (xs[mid - 1] + xs[mid]) / 2.0


def _apply_session(session_trades, values: Dict[str, Any], put: Callable) -> None:
    """
    Derive "unusually fast for you" from today's trades.

    This is what replaced the declared-style rung. Asking a trader whether they
    are a scalper produces a label that is wrong the week they trade differently
    and that nothing ever corrects. Measuring their median hold *today* is
    available just as early, cannot be wrong, and moves when they move.

    Applied only to thresholds owned by analytics-disposition detectors
    (`panic_exit`, `rapid_reentry`), which record evidence and never notify — so
    this rung cannot change alert volume. Extending it to alerting detectors is
    a separate change that needs a replay behind it.
    """
    holds, gaps = [], []
    ordered = [t for t in session_trades if getattr(t, "exit_time", None)]
    ordered.sort(key=lambda t: t.exit_time)

    for t in ordered:
        held = _minutes(getattr(t, "entry_time", None), t.exit_time)
        if held is not None:
            holds.append(held)

    for prev, nxt in zip(ordered, ordered[1:]):
        gap = _minutes(prev.exit_time, getattr(nxt, "entry_time", None))
        # Cap at one hour: a longer gap is a break, not a re-entry decision.
        if gap is not None and 0 < gap < 60:
            gaps.append(gap)

    _blend_session(values, put, "panic_exit_min", holds,
                   "your median hold today")
    _blend_session(values, put, "rapid_reentry_min", gaps,
                   "your median gap between trades today")


def _blend_session(values: Dict[str, Any], put: Callable, key: str,
                   samples, what: str) -> None:
    """Shrink today's evidence toward the repo default by sample size."""
    if len(samples) < 2:
        return
    med = _median(samples)
    if med is None or med <= 0:
        return

    default_val = float(values[key])
    personal = max(1.0, med * _SESSION_FAST_FRACTION)
    confidence = min(1.0, len(samples) / _SESSION_TARGET_N)
    blended = confidence * personal + (1 - confidence) * default_val

    put(key, round(blended, 1), Source.SESSION, confidence,
        f"{what} is {med:.0f}min (n={len(samples)}, confidence {confidence:.2f})")


# ---------------------------------------------------------------------------
# Rung 4 — ratios of the trader's capital
# ---------------------------------------------------------------------------

#: threshold key -> (percentage key, what the number means)
#: Each of these was an absolute rupee amount, which cannot be universal:
#: Rs 500 is 1% of Rs 50,000 and 0.1% of Rs 5,00,000. Same money, different
#: event. The ratio is what generalises.
_CAPITAL_RATIOS = {
    "revenge_min_loss_inr": (
        "revenge_min_loss_pct_capital", "a loss big enough to react to"),
    "profit_giveaway_min_peak": (
        "profit_giveaway_min_peak_pct_capital", "a peak worth protecting"),
    "profit_giveaway_min_erosion": (
        "profit_giveaway_min_erosion_pct_capital", "a giveback worth naming"),
}


def _apply_capital_ratios(values: Dict[str, Any], put: Callable) -> None:
    """
    Re-derive the rupee floors from capital, when capital is known.

    Capital is available on day one with no trading history and no typing — it
    comes off the broker. So this rung is what makes a brand-new Rs 5,00,000
    account behave differently from a brand-new Rs 20,000 one, which the
    absolute constants could never do.

    When capital is unknown the absolute fallback stands, still marked GLOBAL,
    so the distinction between "scaled to you" and "our starting guess" survives
    into the UI rather than being flattened into one number.
    """
    capital = values.get("trading_capital")
    try:
        capital = float(capital) if capital is not None else 0.0
    except (TypeError, ValueError):
        capital = 0.0
    if capital <= 0:
        return

    for key, (pct_key, meaning) in _CAPITAL_RATIOS.items():
        pct = values.get(pct_key)
        if pct is None:
            continue
        derived = round(capital * float(pct) / 100.0, 2)
        put(key, derived, Source.CAPITAL, 1.0,
            f"{pct}% of your capital (₹{capital:,.0f}) — {meaning}")


def _apply_cold_start(put: Callable) -> None:
    """No profile at all — capital and rule fields are unknown, not defaulted."""
    for key in ("trading_capital", "daily_loss_limit", "max_position_size",
                "max_consecutive_losses", "user_daily_trade_limit",
                "user_cooldown_min", "baseline_win_rate", "baseline_profit_factor"):
        put(key, None, Source.GLOBAL, 0.0, "unknown — no profile")
    put("restricted_windows", [], Source.GLOBAL, 0.0, "unknown — no profile")
    put("danger_hours", [], Source.GLOBAL, 0.0, "unknown — no profile")
    put("baseline_sessions", 0, Source.GLOBAL, 0.0, "unknown — no profile")
    put("sl_percent_futures", 1.0, Source.GLOBAL, 0.0, "repo default")
    put("sl_percent_options", 50.0, Source.GLOBAL, 0.0, "repo default")
    put("risk_tolerance", "moderate", Source.GLOBAL, 0.0, "repo default")
