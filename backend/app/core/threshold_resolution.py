"""
Threshold resolution — where the number a detector compares against comes from.

Design: docs/THRESHOLD_RESOLUTION_DESIGN.md

A detector asking "is 5 losses in a row unusual?" needs a number. That number
should come from the most personal source available, and the system should be
able to say WHICH source, because "your limit" and "our starting guess" are
different claims and the product makes both.

The ladder, most personal first:

    1 HISTORY     your own past trades          ~20 sessions / ~100 trades
    2 SESSION     your own trades today         2-5 trades          (not yet built)
    3 DECLARED    a rule you set for yourself   day 1 if set
    4 CAPITAL     a ratio of your capital       day 1, zero input   (partly built)
    5 POPULATION  median of comparable users    once we have users  (not yet built)
    6 GLOBAL      a constant in this repo       always — last resort

`resolve_thresholds(profile)` walks it and returns both the values and, for every
key, a `Resolved` record saying which rung answered and how confident it is.

**This module is currently a pure refactor.** It reproduces the previous
`get_thresholds` byte-for-byte (see tests/test_threshold_resolution.py, which
pins six profile shapes against a golden capture taken before the change). The
only thing it adds is provenance. Rungs 2 and 5 are declared in the enum but not
yet implemented — naming them now is what makes their absence visible instead of
silently falling through to rung 6.

Known defects it deliberately preserves rather than quietly fixing, because a
refactor that also changes behaviour cannot be verified:

  * the two baseline shapes take different paths and produce different numbers
    (the legacy flat shape never reaches `revenge_window_caution_min` at all —
    it writes `revenge_window_min`, which is a different key);
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


def resolve_thresholds(profile=None) -> ThresholdSet:
    """
    Walk the ladder and return values + provenance.

    Values are identical to the previous `get_thresholds()` for every profile
    shape; only the provenance is new.
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
    Two incompatible baseline shapes exist and take different paths. Which one a
    trader gets depends on which service wrote last — a race, not a design.
    Reproduced here rather than fixed, so this refactor stays value-identical.
    """
    baseline = (getattr(profile, "detected_patterns", None) or {}).get("baseline")
    if not isinstance(baseline, dict):
        return

    metrics = baseline.get("metrics")

    if metrics and isinstance(metrics, dict):
        # Per-metric confidence blend: effective = c*personal + (1-c)*default.
        # No activation cliff — a trader with 3 sessions barely moves the needle.
        def blend(metric_key: str, derive, default_val: float):
            rec = metrics.get(metric_key)
            if not rec or rec.get("value") is None:
                return default_val, 0.0, None
            conf = float(rec.get("confidence") or 0)
            personal = derive(float(rec["value"]))
            blended = conf * personal + (1 - conf) * default_val
            return blended, conf, (
                f"{metric_key}={rec['value']} (n={rec.get('n', '?')}, "
                f"confidence {conf:.2f})"
            )

        v, c, d = blend("avg_daily_trades", lambda x: x * 1.5,
                        values["daily_trade_limit"])
        put("daily_trade_limit", int(round(v)),
            Source.HISTORY if c else Source.GLOBAL, c, d)
        put("daily_trade_danger",
            max(values["daily_trade_limit"] + 1,
                int(round(values["daily_trade_limit"] * 1.5))),
            Source.HISTORY if c else Source.GLOBAL, c, "derived from daily_trade_limit")

        v, c, d = blend("avg_daily_trades", lambda x: max(3.0, x / 4),
                        values["burst_trades_per_30min_caution"])
        put("burst_trades_per_30min_caution", int(round(v)),
            Source.HISTORY if c else Source.GLOBAL, c, d)
        put("burst_trades_per_30min_danger",
            max(values["burst_trades_per_30min_caution"] + 2,
                int(round(values["burst_trades_per_30min_caution"] * 1.6))),
            Source.HISTORY if c else Source.GLOBAL, c,
            "derived from burst_trades_per_30min_caution")

        v, c, d = blend("median_reentry_after_loss_min", lambda x: max(5.0, x * 0.5),
                        values["revenge_window_caution_min"])
        put("revenge_window_caution_min", round(v, 1),
            Source.HISTORY if c else Source.GLOBAL, c, d)
        return

    # Legacy flat shape — direct assignment, no confidence, no blend.
    # NOTE the key set: it does NOT include revenge_window_caution_min, so a
    # trader on this path keeps the global revenge window however fast they
    # actually re-enter. Faithfully reproduced; filed as a defect.
    n = baseline.get("session_count") or baseline.get("sessions_analyzed") or 0
    for key in ("daily_trade_limit", "burst_trades_per_30min_caution",
                "revenge_window_caution_min", "consecutive_loss_caution",
                "consecutive_loss_danger"):
        if baseline.get(key) is not None:
            put(key, baseline[key], Source.HISTORY, 1.0,
                f"personal baseline (n={n} sessions)")


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

    dp = getattr(profile, "detected_patterns", None) or {}
    put("danger_hours", (dp.get("time_patterns") or {}).get("danger_hours") or [],
        Source.HISTORY, 1.0, "learned danger hours")

    bl = dp.get("baseline") or {}
    blm = bl.get("metrics") or {}
    put("baseline_sessions", bl.get("sessions_analyzed", 0), Source.FACT, 1.0, None)
    put("baseline_win_rate", blm.get("win_rate"), Source.HISTORY, 1.0, None)
    put("baseline_profit_factor", blm.get("profit_factor"), Source.HISTORY, 1.0, None)

    put("sl_percent_futures", getattr(profile, "sl_percent_futures", None) or 1.0,
        Source.FACT, 1.0, None)
    put("sl_percent_options", getattr(profile, "sl_percent_options", None) or 50.0,
        Source.FACT, 1.0, None)
    put("risk_tolerance", getattr(profile, "risk_tolerance", None) or "moderate",
        Source.FACT, 1.0, None)

    # Rung 4, the only capital-derived pair that exists today. The design doc
    # proposes moving the three absolute-rupee constants here too.
    if values.get("max_position_size"):
        size = float(values["max_position_size"])
        put("max_position_pct_caution", size, Source.CAPITAL, 1.0,
            "your declared max position size")
        put("max_position_pct_danger", size * 2.0, Source.CAPITAL, 1.0,
            "2x your declared max position size")


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
