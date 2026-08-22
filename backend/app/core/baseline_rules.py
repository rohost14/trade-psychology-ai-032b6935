"""
Global rules for what a baseline may learn.

These apply to EVERY metric and EVERY detector. They are here rather than in
`baseline_service` because they are policy, not statistics, and because the next
person adding a metric must not have to rediscover them.

THE GOVERNING PRINCIPLE

    Normal is not safe.

A trader's history defines what is normal FOR THEM. It must never define what is
safe. If someone habitually risks 15% of their account, the engine must not
learn that 15% is therefore fine — it must keep saying so, every time, for as
long as they keep doing it. Personal baselines exist to suppress false positives
about *unusualness*, never to raise the bar on objective danger.

This is the specific way a self-relative system fails, and it fails silently:
the detector goes quiet exactly for the trader who needs it most.

WHAT FOLLOWS FROM THAT

1. **Robust statistics only.** Median, MAD, percentiles. Never the mean — one
   ₹25,000 loss among ten ₹500 losses moves a mean to ₹2,950 and a median not at
   all. Trading distributions are skewed and fat-tailed by nature.

2. **Two windows, not one.** A long-term baseline answers "what does this trader
   normally do"; a recent one answers "what have they been doing lately". Their
   DIVERGENCE is itself a finding — "your position sizes have doubled this
   month" is a better alert than any single trade can produce, and a single
   rolling window cannot express it.

3. **Capped adaptation.** A baseline may move only so far per period. Without a
   cap, a bad fortnight silently becomes the new normal — the trader escalates,
   the baseline follows, and nothing ever fires again.

4. **Confirmed harmful sequences do not train.** The clearest case is re-entry
   gaps: revenge sequences are fast by definition, so learning from them drags
   "normal" downward until nothing looks fast. A detector's own positives must
   not feed the baseline it is measured against.

5. **Extremes are excluded from the update, not from the record.** An outlier is
   evidence about a day; it is not evidence about a habit.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

#: A baseline may move at most this fraction of its current value per recompute.
#: Deliberately slow. The cost of adapting late is a few stale alerts; the cost
#: of adapting fast is that escalation redefines normal and the detector dies.
MAX_ADAPTATION_PER_PERIOD = 0.20

#: Long window: "what does this trader normally do".
LONG_WINDOW_SESSIONS = 60

#: Recent window: "what have they been doing lately". Short enough to move.
RECENT_WINDOW_TRADES = 20

#: Recent must differ from long-term by more than this before divergence is
#: worth reporting — below it, it is noise.
DIVERGENCE_REPORT_RATIO = 1.5

#: Values beyond this many MADs from the median are excluded from baseline
#: UPDATES. They remain in the trade record and can still trigger detectors;
#: they simply do not get to redefine what is typical.
OUTLIER_MAD_MULTIPLE = 5.0


def median(values: Sequence[float]) -> Optional[float]:
    return statistics.median(values) if values else None


def mad(values: Sequence[float]) -> Optional[float]:
    """
    Median absolute deviation — the robust answer to "how spread out is this".

    Preferred over standard deviation throughout: stddev is defined around the
    mean and inherits its sensitivity to exactly the outliers that trading data
    is full of.
    """
    if not values:
        return None
    m = statistics.median(values)
    return statistics.median([abs(v - m) for v in values])


def percentile(values: Sequence[float], p: float) -> Optional[float]:
    """Nearest-rank percentile. Honest for the small samples we actually have."""
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round(p / 100.0 * len(ordered))))
    return float(ordered[idx])


def is_outlier(value: float, values: Sequence[float]) -> bool:
    """
    Should this value be excluded from a baseline UPDATE?

    Not "should it be ignored". A ₹25,000 loss on a book of ₹500 losses is the
    most important thing that happened that day — it just says nothing about
    what is typical.
    """
    m = median(values)
    d = mad(values)
    if m is None or not d:
        return False
    return abs(value - m) > OUTLIER_MAD_MULTIPLE * d


def clean_for_learning(
    values: Sequence[float],
    excluded_indices: Sequence[int] = (),
) -> List[float]:
    """
    The subset of observations a baseline is allowed to learn from.

    `excluded_indices` is how a caller removes trades belonging to confirmed
    harmful sequences — rule 4. The detector that fired must not feed the
    baseline it will next be judged against.
    """
    kept = [v for i, v in enumerate(values) if i not in set(excluded_indices)]
    if len(kept) < 4:
        # Too few to identify an outlier without the outlier defining the
        # distribution. Take them as they are.
        return kept
    return [v for v in kept if not is_outlier(v, kept)]


def cap_adaptation(previous: Optional[float], proposed: float) -> float:
    """
    Limit how far a baseline may move in one step (rule 3).

    Without this, a trader who escalates for a fortnight has simply taught the
    system that escalation is normal.
    """
    if previous is None or previous <= 0:
        return proposed
    ceiling = previous * (1 + MAX_ADAPTATION_PER_PERIOD)
    floor = previous * (1 - MAX_ADAPTATION_PER_PERIOD)
    return max(floor, min(ceiling, proposed))


@dataclass(frozen=True)
class Divergence:
    """Recent behaviour measured against long-term behaviour (rule 2)."""

    long_term: Optional[float]
    recent: Optional[float]
    ratio: Optional[float]
    is_notable: bool
    direction: Optional[str]   # "escalating" | "moderating"

    def describe(self) -> Optional[str]:
        if not self.is_notable or self.ratio is None:
            return None
        if self.direction == "escalating":
            return f"recently {self.ratio:.1f}x your longer-term normal"
        return f"recently {1 / self.ratio:.1f}x below your longer-term normal"


def divergence(long_values: Sequence[float], recent_values: Sequence[float]) -> Divergence:
    """
    Compare the two windows.

    This is what catches the trader whose "normal" is itself drifting. A single
    rolling window cannot: by the time it has adapted, there is nothing left to
    compare against.
    """
    lt = median(clean_for_learning(long_values))
    rc = median(clean_for_learning(recent_values))
    if not lt or not rc or lt <= 0:
        return Divergence(lt, rc, None, False, None)
    ratio = rc / lt
    notable = ratio >= DIVERGENCE_REPORT_RATIO or ratio <= 1 / DIVERGENCE_REPORT_RATIO
    return Divergence(lt, rc, ratio, notable,
                      "escalating" if ratio > 1 else "moderating")


def safety_floor_is_immune(source_kind: str) -> bool:
    """
    Rule 0, stated as code so it can be asserted rather than remembered.

    A threshold classified as universal safety must never resolve from a
    personal baseline. Personalisation may make the engine MORE sensitive; it
    may never make an objectively dangerous event invisible.
    """
    return source_kind == "universal_safety"
