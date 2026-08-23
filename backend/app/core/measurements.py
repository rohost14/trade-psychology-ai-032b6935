"""
Shared normalisation primitives — the denominators, in one place.

Every detector asks some version of "is this big?". The answer depends entirely
on what you divide by, and until now each detector chose for itself: one used a
flat rupee floor, another the session average, a third a fraction of declared
capital. Same question, three incompatible answers, none of them recorded.

This module owns the division. A `Measurement` carries the normalised value, the
denominator used, where that denominator came from, and how much to trust it —
so an alert can always be explained back to the arithmetic behind it.

NO THRESHOLDS LIVE HERE. These functions answer "how big, relative to what".
Whether that is *too* big is a threshold question, and thresholds live in
`threshold_registry` where each carries a Kind and a resolution path.

THREE KINDS OF DENOMINATOR, AND WHY COLD START IS SOLVED BY HAVING THREE

    account-relative   loss / account equity      needs equity
    trade-relative     loss / capital at risk     needs only this trade
    trader-relative    value / their own history  needs history

The document treats "we cannot measure the account" as though it left a new user
unprotected. It does not — because only the FIRST of these needs an account size.

  * A brand-new user with no margin data and no declared capital gets no
    ACCOUNT-relative safety, and that is correct: we cannot honestly say "you
    lost half your account" without knowing the account. Inventing a denominator
    would be worse than silence.

  * That same user still gets full TRADE-relative safety. "This position has lost
    80% of the premium you paid for it" needs nothing but the trade, is true on
    their first ever trade, and is exactly the objective-danger observation the
    document asks universal safety rules to make.

  * And full STRUCTURAL safety — "you added to a losing position" is a fact about
    a sequence and needs no numbers at all.

So the cold-start hierarchy is not a fallback chain ending in a guess. It is
three independent measurement families, of which two are always available. The
engine abstains from the one it genuinely cannot compute and keeps the other two.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from app.core.account_risk import AccountRisk, Quality
from app.core.baseline_rules import mad, median


@dataclass(frozen=True)
class Measurement:
    """
    A normalised quantity, and the arithmetic that produced it.

    `value is None` means unmeasurable — the caller must abstain from any claim
    that depends on it, exactly as with `AccountRisk.fraction`.
    """

    value: Optional[float]
    denominator: Optional[float]
    #: What we divided by, in words: "your opening balance", "the premium you
    #: paid", "your typical losing trade". Goes into alert copy verbatim.
    denominator_label: Optional[str]
    quality: Quality
    #: Sample size behind a trader-relative denominator. None for the others,
    #: which need no sample.
    sample_size: Optional[int] = None
    #: What KIND of denominator this is, where that matters. A ratio against a
    #: loss ceiling and the same ratio against posted margin are not comparable
    #: events, so a stored measurement that does not say which cannot be checked
    #: afterwards. See core/instrument_risk.
    denominator_kind: Optional[str] = None
    #: The instrument class the denominator came from, for the same reason.
    instrument_class: Optional[str] = None

    @property
    def is_measurable(self) -> bool:
        return self.value is not None

    def describe(self) -> str:
        if not self.is_measurable:
            return "not measurable"
        return f"{self.value:.2f}x {self.denominator_label}"


UNMEASURABLE = Measurement(None, None, None, Quality.UNKNOWN)


# ---------------------------------------------------------------------------
# Account-relative — needs equity, abstains without it
# ---------------------------------------------------------------------------

def loss_vs_account(loss: float, account: AccountRisk) -> Measurement:
    """
    How much of the account this cost, as a fraction.

    Abstains when the account size is unknown. This is the ONLY family that
    abstains at cold start, and the abstention is the honest outcome — a
    fabricated denominator would let us say "you lost 40% of your account" to
    someone whose account we cannot see.
    """
    frac = account.fraction(loss)
    if frac is None:
        return UNMEASURABLE
    return Measurement(
        value=frac,
        denominator=float(account.value),
        denominator_label=account.describe(),
        quality=account.quality,
    )


# ---------------------------------------------------------------------------
# Trade-relative — needs only the trade, so always available
# ---------------------------------------------------------------------------

def loss_vs_trade(loss: float, capital_at_risk: Optional[float]) -> Measurement:
    """
    How much of what was put at risk on THIS trade has been lost.

    Available on a trader's first ever trade. This is what protects a new user
    while the account-relative family is still abstaining.

    Prefer `loss_vs_risk_basis` where the instrument class is known: the bare
    number cannot say whether it was divided by a loss ceiling or by posted
    margin, and 80% of each is a different event.
    """
    if not capital_at_risk or capital_at_risk <= 0:
        return UNMEASURABLE
    return Measurement(
        value=abs(float(loss)) / float(capital_at_risk),
        denominator=float(capital_at_risk),
        denominator_label="the capital you put at risk on this trade",
        quality=Quality.GOOD,
    )


def loss_vs_risk_basis(loss: float, basis) -> Measurement:
    """
    The same ratio, carrying what it was divided by.

    Abstains when the basis is not comparable — a spread's denominator is known
    to be over-estimated, so the ratio would be understated in a known direction.
    A confident wrong answer is worse than none.

    `basis` is a `core.instrument_risk.RiskBasis`. Taken untyped to keep this
    module free of an import it would otherwise only need for an annotation.
    """
    if basis is None or not basis.amount or basis.amount <= 0:
        return UNMEASURABLE
    if not basis.is_comparable:
        return Measurement(None, None, None, Quality.UNKNOWN,
                           denominator_kind=basis.kind.value,
                           instrument_class=basis.instrument.value)
    return Measurement(
        value=abs(float(loss)) / float(basis.amount),
        denominator=float(basis.amount),
        denominator_label=basis.label,
        quality=Quality.GOOD,
        denominator_kind=basis.kind.value,
        instrument_class=basis.instrument.value,
    )


# ---------------------------------------------------------------------------
# Trader-relative — needs history, states how much it had
# ---------------------------------------------------------------------------

def _robust_ratio(value: float, history: Sequence[float], label: str,
                  min_sample: int) -> Measurement:
    """
    `value` as a multiple of the trader's own median, with sample size attached.

    Median rather than mean throughout, per the global baseline rules: one
    catastrophic observation must not redefine what is typical.

    `min_sample` is supplied by the CALLER, from the detector's declared
    maturity requirement. It is deliberately not a constant in this module —
    every numeric threshold belongs in the registry with a Kind, and a minimum
    sample buried here would be exactly the kind of unprovenanced number this
    architecture exists to eliminate.
    """
    clean = [abs(float(v)) for v in history if v is not None]
    if len(clean) < min_sample:
        return Measurement(None, None, None, Quality.UNKNOWN, sample_size=len(clean))
    m = median(clean)
    if not m or m <= 0:
        return Measurement(None, None, None, Quality.UNKNOWN, sample_size=len(clean))
    return Measurement(
        value=abs(float(value)) / m,
        denominator=m,
        denominator_label=label,
        quality=Quality.GOOD,
        sample_size=len(clean),
    )


def loss_vs_own_losses(loss: float, past_losses: Sequence[float],
                       min_sample: int) -> Measurement:
    """Is this loss large for this trader? The revenge-trade denominator."""
    return _robust_ratio(loss, past_losses, "your typical losing trade", min_sample)


def size_vs_own_sizes(size: float, past_sizes: Sequence[float],
                      min_sample: int) -> Measurement:
    """Is this position large for this trader? The sizing-detector denominator."""
    return _robust_ratio(size, past_sizes, "your typical position", min_sample)


def gap_vs_own_gaps(gap_minutes: float, past_gaps: Sequence[float],
                    min_sample: int) -> Measurement:
    """
    Is this re-entry fast for this trader?

    Note the direction: a SMALLER ratio means faster, so callers compare against
    a low percentile rather than a high one. Stated here because getting it
    backwards is silent and plausible.
    """
    return _robust_ratio(gap_minutes, past_gaps, "your typical gap between trades",
                         min_sample)


def dispersion(history: Sequence[float]) -> Optional[float]:
    """
    Median absolute deviation — how consistent is this trader.

    A trader at 6 +/- 1 trades a day and one at 6 +/- 9 have the same median and
    completely different normality. Currently nothing consumes dispersion; it is
    exposed because a percentile without it can call routine variance unusual.
    """
    clean = [abs(float(v)) for v in history if v is not None]
    return mad(clean) if clean else None
