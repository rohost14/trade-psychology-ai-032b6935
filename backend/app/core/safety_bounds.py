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

    `(None, "")` when no bound is declared.

    UNIVERSAL_SAFETY IS ITS OWN BOUND (2026-08-28)
    ----------------------------------------------
    A `Kind.UNIVERSAL_SAFETY` threshold with no explicit `safety_bound` is
    bounded at its own universal value. This is definitional, not a new
    judgement, and it invents no number: the Kind means "objective danger; never
    personalised", so the universal value is by definition the loosest the
    threshold may become. Tightening below it stays allowed — a trader who
    declares a 3% position cap still gets alerts at 3%.

    It was added because the gap was reachable and proven. `_apply_profile_facts`
    maps a declared `max_position_size` onto `max_position_pct_caution` and
    `max_position_pct_danger` — both UNIVERSAL_SAFETY — via `Source.CAPITAL`,
    which `violates_kind` does not refuse because CAPITAL is not a *learned*
    source. Measured before the fix: declaring 40 moved the caution line from
    5.0 to 40.0 and danger from 10.0 to 80.0, so the detector that exists to say
    "this position is dangerously large" went quiet for exactly the traders
    taking the largest positions.

    The declared value is not lost: `max_position_size` is a `RULE_FIELD` in
    `constitution_service`, so it is still enforced as the trader's own rule by
    `constitution_violation`. What it may no longer do is move a universal
    safety line.

    An explicit `safety_bound` on a spec still wins, so a detector review can
    still set a different bound with its own reason.
    """
    from app.core.threshold_registry import THRESHOLD_SPECS, Kind

    spec = THRESHOLD_SPECS.get(key)
    if spec is None:
        return None, ""
    if spec.safety_bound is not None:
        return float(spec.safety_bound), spec.bound_provenance
    if spec.kind is Kind.UNIVERSAL_SAFETY and isinstance(spec.fallback, (int, float)):
        return float(spec.fallback), (
            "a universal-safety threshold is its own bound: it may be tightened "
            "for you, never loosened"
        )
    return None, ""


def clamp_to_bound(key: str, value: Any) -> Tuple[Any, Optional[str]]:
    """
    Pull `value` back to the safety bound if it has crossed it.

    Returns the value to use and, when it was clamped, a human-readable reason.
    The reason is not decoration: an alert that fires because a bound held must
    be able to say so, or the trader is told "your limit" about a number that is
    not theirs.

    Refuses to act on a threshold whose direction is undeclared, because a bound
    applied the wrong way silently inverts the guarantee it exists to provide.

    The reason says "this would otherwise have resolved to X", not "your own
    history would have put this at X". The clamped value does not always come
    from history — the case that prompted the UNIVERSAL_SAFETY self-bound came
    from a DECLARED rule via Source.CAPITAL — and a reason that names the wrong
    origin tells the trader something untrue about their own data.
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
            f"held at the safety bound {bound:g} — this would otherwise have "
            f"resolved to {numeric:g}. {why}".strip()
        )
    if direction is Sensitivity.HIGHER_IS_STRICTER and numeric < bound:
        return bound, (
            f"held at the safety bound {bound:g} — this would otherwise have "
            f"resolved to {numeric:g}. {why}".strip()
        )
    return value, None


def is_safety(key: str) -> bool:
    """Is this threshold one whose Kind forbids learning it from the trader?"""
    from app.core.threshold_resolution import Kind
    from app.core.threshold_registry import kind_for

    return kind_for(key) is Kind.UNIVERSAL_SAFETY
