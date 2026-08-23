"""
Is a personal metric ready to be used? Three states, answered in one place.

WHY THIS IS SHARED

"Do I have enough of this trader's history to say what is normal for them" gets
asked by every detector that uses a personal baseline, and today it is answered
by each caller or not at all: `measurements` takes a `min_sample` from whoever
calls it, `_pct_metric` records a confidence and gates nothing, and the registry
has a `Maturity` enum that nothing consults.

That is the shape the nine competing definitions of a session fact had before
they were collapsed. The question is the same everywhere, so the answer belongs
in one place.

WHY THREE STATES AND NOT TWO

Collapsing "we have some of your history but not enough" into "we have none" is
how a fallback gets presented as personal. They lead to the same action — use the
declared fallback — but they are different claims about the trader, and the copy
that follows must differ:

    MATURE       we know this about you
    IMMATURE     we are still learning this about you
    UNAVAILABLE  we do not know this about you

WHAT IS NOT HERE

No numbers. `required` is supplied by the caller from the metric's own declared
maturity, and that requirement is unresolved for every metric today (M1). A
metric with no declared requirement resolves to UNAVAILABLE rather than being
assumed ready — the same rule the rest of this engine follows: when the decision
has not been made, abstain rather than guess.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from app.core.evidence import Insufficiency


class MaturityState(str, Enum):
    MATURE = "mature"            # enough observations; the metric may be used
    IMMATURE = "immature"        # some observations, not enough; use the fallback
    UNAVAILABLE = "unavailable"  # no metric, or no requirement declared


@dataclass(frozen=True)
class Assessment:
    """The state, the counts behind it, and why — so an alert can say which."""

    state: MaturityState
    observed: int
    required: Optional[int]
    #: The reason to record when a caller abstains on this metric. None when mature.
    reason: Optional[Insufficiency] = None

    @property
    def is_usable(self) -> bool:
        return self.state is MaturityState.MATURE

    @property
    def is_personalised(self) -> bool:
        """
        Whether a value derived from this metric may be described to the trader
        as theirs. False for both non-mature states, which is the point: a
        fallback must never be presented as personal.
        """
        return self.state is MaturityState.MATURE

    def describe(self) -> str:
        if self.state is MaturityState.MATURE:
            return f"from {self.observed} of your own observations"
        if self.state is MaturityState.IMMATURE:
            return (f"still learning: {self.observed} of "
                    f"{self.required} observations needed")
        return "not enough of your history to say"


def assess(metric: Optional[Dict[str, Any]], required: Optional[int]) -> Assessment:
    """
    Judge one baseline metric record against its declared requirement.

    `metric` is the record `baseline_service` stores — it carries `n`, the number
    of observations behind it. `required` comes from the metric's declared
    maturity and is None while that decision is unmade.
    """
    observed = 0
    if metric:
        try:
            observed = int(metric.get("n") or 0)
        except (TypeError, ValueError):
            observed = 0

    if not metric or observed <= 0:
        return Assessment(MaturityState.UNAVAILABLE, observed, required,
                          Insufficiency.NO_BASELINE)

    if required is None:
        # The metric exists but nobody has said how much is enough. Refusing to
        # judge is the honest answer; assuming it is ready would be inventing the
        # requirement at the moment of use, which is worse than leaving it unset.
        return Assessment(MaturityState.UNAVAILABLE, observed, None,
                          Insufficiency.NO_BASELINE)

    if observed < required:
        return Assessment(MaturityState.IMMATURE, observed, required,
                          Insufficiency.NO_BASELINE)

    return Assessment(MaturityState.MATURE, observed, required)
