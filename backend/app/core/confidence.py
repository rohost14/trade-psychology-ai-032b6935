"""
How well could we see this? One definition, and no weights.

CONFIDENCE IS NOT SEVERITY

Severity is potential harm if the behaviour is real. Confidence is certainty that
it was identified correctly. A 95%-confident low-harm re-entry is mild; a
60%-confident potentially account-ending one is not. Anything deriving one from
the other has conflated them.

Severity is pattern-specific — it is a claim about harm from one particular
behaviour and cannot be computed generically. Confidence is not: "how well could
we see this" is the same question for every detector, which is why it belongs
here and severity does not.

WHY THE WEAKEST LINK, NOT A SUM

Seven call sites compute confidence differently today. One of them adds invented
points — 30 for a base case, 20 for this, 10 for that — across observations that
are not independent, producing a number nobody can defend. That is the behaviour
score in miniature, and every argument that retired the score applies to it.

The replacement is not a better weighting. It is to stop combining by arithmetic:

    confidence = the LOWEST confidence of any input the verdict rested on

If the trade's data quality was PARTIAL, no amount of mature baseline makes the
conclusion more certain than PARTIAL allows. Confidence is bounded by the worst
thing we had to rely on, which is what "how well could we see this" means. It is
the same reasoning as the lattice join used for evidence levels, in the opposite
direction and for the same purpose: no invented arithmetic mixing incommensurable
things.

WHERE THE NUMBERS COME FROM

Both existed already; neither is invented here.

  * `DATA_QUALITY_CONFIDENCE` — GOOD 100 / PARTIAL 75 / UNKNOWN 50 / INVALID 0,
    the mapping the engine has always used for arithmetic detectors.
  * a baseline metric's own `confidence` — observations over target, capped at 1,
    computed by `baseline_service`.

This module adds no constant of its own.
"""
from __future__ import annotations

from typing import Iterable, Optional


def from_data_quality(data_quality: Optional[str]) -> float:
    """The ceiling that the trade's own data quality places on any conclusion."""
    from app.services.behavior_engine import DATA_QUALITY_CONFIDENCE

    return float(DATA_QUALITY_CONFIDENCE.get((data_quality or "").upper(), 50.0))


def combine(*confidences: Optional[float]) -> Optional[float]:
    """
    The weakest link among everything the verdict rested on.

    `None` entries are ignored rather than treated as zero: an input that was not
    consulted says nothing about certainty, while an input that was consulted and
    was poor says a great deal. Returns None when nothing was supplied, which the
    caller must treat as "cannot state a confidence" rather than as zero.
    """
    present = [float(c) for c in confidences if c is not None]
    if not present:
        return None
    return round(min(present), 1)


def from_observables(
    data_quality: Optional[str] = None,
    sample_confidences: Iterable[Optional[float]] = (),
    inputs_parsed: bool = True,
) -> Optional[float]:
    """
    Confidence for one detection, from what could actually be observed.

    `sample_confidences` are the baseline metrics' own confidences, already
    computed and stored, on a 0..1 scale — passed in by the detector for exactly
    the metrics its verdict used. A verdict that used no personal metric passes
    none, and is then bounded only by data quality, which is correct: a purely
    structural observation is as certain as the data it was read from.

    `inputs_parsed` is the one boolean: when a symbol could not be parsed the
    detector reasoned on a weaker footing than it believed. It maps to the same
    UNKNOWN level the data-quality vocabulary already uses rather than to a new
    number.
    """
    parts = [from_data_quality(data_quality)]
    for c in sample_confidences:
        if c is not None:
            parts.append(float(c) * 100.0)
    if not inputs_parsed:
        parts.append(from_data_quality("UNKNOWN"))
    return combine(*parts)
