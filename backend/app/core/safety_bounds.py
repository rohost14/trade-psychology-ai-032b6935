"""
The bound on insensitivity — "normal is not safe", as machinery.

WHAT WAS MISSING

`UNIVERSAL_FLOORS` can say *never alert below three losses*. It cannot say
*always alert by eight, whatever this trader's history says*. Those are opposite
guarantees and only the first existed, so nothing bounded how quiet a personal
baseline could make a detector.

That gap is the whole content of the invariant. A trader's `daily_trade_limit`
resolves to the 75th percentile of their own daily trade counts, so the trader
who overtrades every day has a high limit and a quiet detector — the detector
goes silent for exactly the person it exists for. `cap_adaptation` slows that
drift by capping movement per recompute; it does not bound the level, and five
periods of 20% compounds to about 2.5x.

TWO GUARANTEES, NOT ONE

    floor    (UNIVERSAL_FLOORS)  the detector may not become MORE sensitive than this
    bound    (this module)       the detector may not become LESS sensitive than this

They point in opposite directions and both are needed. A floor stops noise; a
bound stops silence.

WHY DIRECTION HAS TO BE DECLARED

For `consecutive_loss_caution` a bigger number is looser — more losses are
required before anything is said. For `revenge_window_caution_min` a bigger
number is stricter — a wider window catches more re-entries. `UNIVERSAL_FLOORS`
applies one `<` to both, which is why it reads as a noise floor on some keys and
a sensitivity floor on others.

So a bound is only enforceable on a threshold whose `Sensitivity` is declared. An
undeclared one gets NO bound rather than a guessed one: a bound applied in the
wrong direction would silently invert the guarantee, which is worse than having
none.

WHY THERE ARE NO NUMBERS IN THIS FILE

Every `safety_bound` in the registry is `None`, on purpose. The bound is an
architectural constraint; each value is a claim about one specific behaviour and
has to be justified against that detector's own evidence when it is reviewed.
Filling them in as a batch would rebuild the wall of undefendable constants this
work exists to dismantle — pointing the other way, but just as arbitrary.

So: the mechanism is live from today and guards an empty set by design. It
changes no behaviour until a detector review adds the first bound, with its
reason, in the same commit that argues for it.
"""
from __future__ import annotations

import logging
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)


def bound_for(key: str) -> Tuple[Optional[float], str]:
    """
    The bound declared for this threshold, and the reason given for it.

    `(None, "")` when no bound is declared — which is every threshold today.
    """
    from app.core.threshold_registry import THRESHOLD_SPECS

    spec = THRESHOLD_SPECS.get(key)
    if spec is None or spec.safety_bound is None:
        return None, ""
    return float(spec.safety_bound), spec.bound_provenance


def clamp_to_bound(key: str, value: Any) -> Tuple[Any, Optional[str]]:
    """
    Pull `value` back to the safety bound if it has crossed it.

    Returns the value to use and, when it was clamped, a human-readable reason.
    The reason is not decoration: an alert that fires because a bound held must
    be able to say so, or the trader is told "your limit" about a number that is
    not theirs.

    Refuses to act on a threshold whose direction is undeclared, because a bound
    applied the wrong way silently inverts the guarantee it exists to provide.
    """
    bound, why = bound_for(key)
    if bound is None:
        return value, None

    from app.core.threshold_registry import THRESHOLD_SPECS, Sensitivity

    spec = THRESHOLD_SPECS.get(key)
    direction = spec.sensitivity if spec else Sensitivity.UNKNOWN

    if direction is Sensitivity.UNKNOWN:
        logger.warning(
            "[safety_bounds] %s declares a bound but no direction; not enforced. "
            "A bound applied the wrong way inverts the guarantee.", key
        )
        return value, None

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return value, None

    if direction is Sensitivity.HIGHER_IS_LOOSER and numeric > bound:
        return bound, (
            f"held at the safety bound {bound:g} — your own history would have "
            f"put this at {numeric:g}. {why}".strip()
        )
    if direction is Sensitivity.HIGHER_IS_STRICTER and numeric < bound:
        return bound, (
            f"held at the safety bound {bound:g} — your own history would have "
            f"put this at {numeric:g}. {why}".strip()
        )
    return value, None


def is_safety(key: str) -> bool:
    """Is this threshold one whose Kind forbids learning it from the trader?"""
    from app.core.threshold_resolution import Kind
    from app.core.threshold_registry import kind_for

    return kind_for(key) is Kind.UNIVERSAL_SAFETY
