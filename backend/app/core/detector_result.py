"""
The detector contract — what a detector returns, and which layer said it.

WHAT THIS ADDS OVER `DetectedEvent`

`DetectedEvent` carries a severity and a message. It cannot express three things
the architecture now requires:

  1. **Which layer produced this.** A universal-safety finding and a personal-
     deviation finding are different claims about the world. Collapsed into one
     severity, "normal is not safe" becomes a rule nobody can enforce at runtime
     — a personal baseline could quietly suppress an objective danger and nothing
     would notice.
  2. **That the detector could not tell.** `Optional[DetectedEvent]` makes `None`
     mean both "did not happen" and "cannot see", which is how three detectors
     stayed silent for 203 sessions with nobody able to say which it was.
  3. **The measurements behind the verdict**, so the alert is reconstructible
     from stored evidence rather than from prose.

`DetectorResult` wraps `DetectedEvent` rather than replacing it. Nothing is
migrated here; the existing return type keeps working untouched.

SEVERITY AND CONFIDENCE ARE ORTHOGONAL

Severity is potential harm if the behaviour is real. Confidence is certainty
that it was identified correctly. A 95%-confident low-harm re-entry is mild; a
60%-confident potentially account-ending exposure is not. Anything that derives
one from the other has conflated them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.core.account_risk import Quality
from app.core.evidence import Evidence, Insufficiency, Verdict
from app.core.measurements import Measurement


class Layer(str, Enum):
    """
    Which of the two systems produced this finding.

    The distinction is load-bearing, not descriptive: SAFETY findings may never
    be suppressed by anything learned from the trader, because a habit is not a
    licence. `violates_kind` enforces the same rule on thresholds; this enforces
    it on results.
    """

    SAFETY = "safety"      # objectively dangerous; does not learn, cannot be muted by habit
    PERSONAL = "personal"  # unusual for this trader; meaningless without their history


@dataclass(frozen=True)
class DetectorResult:
    """A detector's full answer: verdict, layer, and the arithmetic behind it."""

    detector: str
    evidence: Evidence
    layer: Optional[Layer] = None
    severity: Optional[str] = None
    #: 0-100. Certainty of identification, NEVER derived from severity.
    confidence: Optional[float] = None
    data_quality: Quality = Quality.GOOD
    #: The normalised values the verdict rests on, keyed by what they measure.
    measurements: Dict[str, Measurement] = field(default_factory=dict)
    message: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)

    @property
    def fired(self) -> bool:
        return self.evidence.verdict is Verdict.POSITIVE

    @property
    def abstained(self) -> bool:
        return self.evidence.is_abstained

    @property
    def is_safety(self) -> bool:
        return self.layer is Layer.SAFETY

    def explain(self) -> List[str]:
        """
        The measurements as human-readable lines.

        Explainability is not a rendering concern: if a result cannot describe
        itself from what it measured, it should not be shown to a trader.
        """
        out = []
        for name, m in self.measurements.items():
            if m.is_measurable:
                out.append(f"{name}: {m.describe()}")
        return out


def abstained(detector: str, reason: Insufficiency, detail: str = None,
              **basis) -> DetectorResult:
    """A detector declining to judge. Not a finding, and never an alert."""
    from app.core.evidence import abstain
    return DetectorResult(detector=detector, evidence=abstain(reason, detail, **basis))


def not_detected(detector: str, detail: str = None) -> DetectorResult:
    """
    The behaviour did not occur, and the detector could see well enough to say so.

    Distinct from abstaining. This one IS a finding: it is what makes a clean
    session distinguishable from an unmonitored one.
    """
    from app.core.evidence import negative
    return DetectorResult(detector=detector, evidence=negative(detail))


# ---------------------------------------------------------------------------
# Episode interface — DEFINED, NOT IMPLEMENTED
# ---------------------------------------------------------------------------

class EpisodeRole(str, Enum):
    """
    How a single detection relates to a longer behavioural sequence.

    An "episode" is a run of related detections that belong to one behavioural
    event rather than several — the loss, the fast re-entry, the doubled size and
    the second loss are four detections of one episode, and a trader should be
    told once about the episode rather than four times about its parts.

    DEFINED HERE, DELIBERATELY NOT BUILT. The interface exists so detectors can
    declare their role from the start and consolidation can group on it later,
    without a migration. Building the state machine now would add ordering,
    persistence and expiry problems for a benefit nothing has yet measured — and
    the existing `_consolidate` already folds duplicate descriptions of one
    behaviour, which covers the common case.

    The open question, recorded rather than answered: an episode needs a lifetime,
    and the honest boundary is probably the session — but a position held
    overnight makes that wrong. That is the design problem to solve before this is
    implemented, and it is why it is not implemented now.
    """

    NONE = "none"            # standalone; belongs to no sequence
    TRIGGER = "trigger"      # the event that starts one (e.g. a meaningful loss)
    ESCALATION = "escalation"  # continues and worsens it (size up, re-entry)
    TERMINAL = "terminal"    # the sequence resolved (stopped, or squared off)


@dataclass(frozen=True)
class EpisodeHint:
    """
    A detector's declaration of how its finding fits a sequence.

    Attached to a result; consumed by nothing today. Consolidation will group on
    `key` when episodes are built — `key` is intended to be a stable identifier
    for the behavioural thread (e.g. underlying + session), NOT a database id, so
    it can be computed without persistence.
    """

    role: EpisodeRole = EpisodeRole.NONE
    key: Optional[str] = None
    #: Ordering within the episode, where the detector can say. Sequence matters:
    #: escalation after a trigger means something that the same two detections in
    #: the opposite order do not.
    sequence: Optional[int] = None
