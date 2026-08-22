"""
Abstention — letting a detector say "I don't know" instead of guessing.

THE PROBLEM THIS SOLVES

A detector that must return something will invent something. `revenge_trade`
does exactly that today: it wants the trader's typical loss, needs three losses
to compute one, and when it has fewer falls back to a flat ₹500 — inventing a
threshold at precisely the moment it knows least. The alert that follows looks
identical to one backed by forty sessions of evidence.

That is the failure this module exists to prevent. Not knowing is a legitimate
answer, and the engine has to be able to give it.

WHAT ABSTENTION IS NOT

It is not "return no alert". A detector can decline to judge for two completely
different reasons:

    the behaviour did not occur          -> NEGATIVE   (a finding)
    we cannot tell whether it occurred   -> ABSTAINED  (not a finding)

Collapsing those is how a blind detector looks like a clean trader. Over the
203-session replay three detectors never fired once, and nothing in the system
could distinguish "this trader never did it" from "this detector cannot see".
`Evidence` keeps them apart.

HOW A DETECTOR DECIDES

Each detector declares its OWN sufficiency — there is no global "baseline ready"
flag, because the requirements differ per metric. Hold-time needs a handful of
trades; a daily-count baseline needs sessions; a time-of-day pattern needs weeks.
`require()` is the helper for expressing that inline.

MIGRATION POSTURE

Building the mechanism does not switch any detector onto it. Each one adopts
abstention at its own review, where we can say what its evidence bar should be
and check the effect on a replay. Until then behaviour is unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class Verdict(str, Enum):
    """What a detector concluded, including the option of concluding nothing."""

    POSITIVE = "positive"    # the behaviour occurred
    NEGATIVE = "negative"    # it did not — a real finding
    ABSTAINED = "abstained"  # we cannot tell; NOT a finding


class Insufficiency(str, Enum):
    """Why a detector could not judge. Kept separate so it is measurable."""

    NO_BASELINE = "no_baseline"          # not enough history for this metric
    MISSING_INPUT = "missing_input"      # a required field was absent
    STALE_INPUT = "stale_input"          # present but too old to trust
    BAD_QUALITY = "bad_quality"          # data quality below the detector's bar
    NOT_APPLICABLE = "not_applicable"    # the pattern cannot apply to this trade


@dataclass(frozen=True)
class Evidence:
    """
    A detector's conclusion plus what it was based on.

    `verdict` is the honest three-way answer. `basis` carries the numbers that
    justify it, so an alert stays explainable from stored evidence rather than
    from a score — every claim we make to a trader should be reconstructible.
    """

    verdict: Verdict
    reason: Optional[Insufficiency] = None
    detail: Optional[str] = None
    basis: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_abstained(self) -> bool:
        return self.verdict is Verdict.ABSTAINED

    @property
    def can_alert(self) -> bool:
        return self.verdict is Verdict.POSITIVE

    def __bool__(self) -> bool:
        """
        Deliberately NOT defined as truthiness of "did it fire".

        `if evidence:` reads as "did the behaviour occur" but would silently
        treat ABSTAINED as NEGATIVE, which is the exact conflation this module
        exists to prevent. Callers must ask explicitly.
        """
        raise TypeError(
            "Evidence has no truth value - check .can_alert or .is_abstained "
            "explicitly. Treating abstention as 'no' is the bug this type "
            "exists to prevent."
        )


def positive(detail: str = None, **basis) -> Evidence:
    return Evidence(Verdict.POSITIVE, None, detail, basis)


def negative(detail: str = None, **basis) -> Evidence:
    """The behaviour did not occur, and we could see clearly enough to say so."""
    return Evidence(Verdict.NEGATIVE, None, detail, basis)


def abstain(reason: Insufficiency, detail: str = None, **basis) -> Evidence:
    """We cannot tell. Not a finding, and must never be counted as a clean run."""
    return Evidence(Verdict.ABSTAINED, reason, detail, basis)


def require(
    condition: bool,
    reason: Insufficiency,
    detail: str = None,
    **basis,
) -> Optional[Evidence]:
    """
    Guard clause for a detector's own sufficiency bar.

        insufficient = require(len(losses) >= 3, Insufficiency.NO_BASELINE,
                               "need 3 losses to estimate a typical loss",
                               have=len(losses))
        if insufficient:
            return insufficient

    Returns None when the requirement is met, so the detector reads top-down as
    a list of things it needs before it is entitled to an opinion.
    """
    if condition:
        return None
    return abstain(reason, detail, **basis)
