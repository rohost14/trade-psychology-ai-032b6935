"""
What every threshold IS — declared once, so nothing arbitrary can slip back in.

`threshold_resolution` answers "where did this number come from *this time*".
This module answers the prior question: "what sort of number is this allowed to
be, and what could it resolve from if we had the evidence".

WHY A REGISTRY RATHER THAN COMMENTS

Comments drift. `burst_trades_per_15min` carried the comment "Used by
RiskDetector" for months after RiskDetector was archived, and nothing caught it
because a comment cannot be asserted. A spec can: every entry declares its
`Kind`, and `violates_kind()` rejects an illegal resolution at test time.

WHAT `metric` DOES NOT MEAN

A spec naming a metric does NOT mean that constant should become personal. It
means personalisation is *available* for it. Whether personalising actually
makes a detector more accurate is a question for that detector's review, decided
with evidence — 20 constants classified `personal_baseline` is not 20 constants
that should be switched on. Several will be better left universal.

`personalise=False` on every entry is deliberate: this migration builds the path
and changes no behaviour. Each detector flips its own at review, behind a replay.

MATURITY

Per-metric, never global. Hold-time needs a handful of trades; a daily-count
distribution needs sessions; a time-of-day pattern needs weeks. A single
"baseline ready" flag would be wrong for all three.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from app.core.threshold_resolution import Kind, Source


class Sensitivity(str, Enum):
    """
    Which way this threshold's number points.

    Required before any bound can be enforced on it, and deliberately not
    guessable: for `consecutive_loss_caution` a bigger number means the detector
    speaks LESS (more losses required), while for `revenge_window_caution_min` a
    bigger number means it speaks MORE (a wider window catches more re-entries).

    `UNIVERSAL_FLOORS` applies one `<` comparison to both shapes, which is why it
    reads as a noise floor on some keys and a sensitivity floor on others. A
    bound that does not know its own direction cannot be enforced, so an
    unclassified threshold gets no bound rather than a guessed one.
    """

    UNKNOWN = "unknown"                    # not yet decided — no bound enforceable
    HIGHER_IS_LOOSER = "higher_is_looser"  # counts, streaks, percentages
    HIGHER_IS_STRICTER = "higher_is_stricter"  # windows, durations


class Maturity(str, Enum):
    """What must accumulate before a metric may be trusted."""

    NONE = "none"                  # needs no history at all
    SESSION = "session"            # a handful of trades today (rung 2)
    TRADES_20 = "trades_20"        # ~20 observations of the thing itself
    SESSIONS_20 = "sessions_20"    # ~20 trading days
    SESSIONS_60 = "sessions_60"    # a long-window distribution


@dataclass(frozen=True)
class ThresholdSpec:
    """One threshold, fully declared."""

    key: str
    kind: Kind
    #: What it resolves to today, and what it falls back to forever if the
    #: personal path is unavailable or never enabled.
    fallback: Any
    #: Plain-English statement of what the number means.
    meaning: str
    #: Rung that would answer if personalisation were enabled. None = never.
    resolution_source: Optional[Source] = None
    #: Baseline metric that would supply it.
    metric: Optional[str] = None
    #: Percentile of that metric, where applicable.
    percentile: Optional[float] = None
    maturity: Maturity = Maturity.NONE
    #: OFF for every entry in this migration. Behaviour is unchanged by design.
    personalise: bool = False
    #: Flagged in the G4 inventory as an unsupported judgement. Its detector
    #: review is mandatory, not optional.
    review_required: bool = False
    #: Why this classification, in one line. Provenance for the decision itself.
    provenance: str = ""
    #: Which way the number points. Without it, no bound can be enforced.
    sensitivity: Sensitivity = Sensitivity.UNKNOWN
    #: The point past which personal history may not push this threshold, in the
    #: direction that makes the detector quieter.
    #:
    #: DELIBERATELY None ON EVERY ENTRY. The mechanism is the architecture; the
    #: number is a claim about a specific behaviour and has to be justified
    #: against that detector's evidence during its review. Filling these in as a
    #: batch would recreate exactly the problem this whole exercise exists to
    #: undo - a wall of numbers nobody can defend individually.
    safety_bound: Optional[float] = None
    #: Why that bound, in one line. Required whenever safety_bound is set; a
    #: bound without a justification is an arbitrary constant wearing a new name.
    bound_provenance: str = ""


def _spec(**kw) -> ThresholdSpec:
    return ThresholdSpec(**kw)


# ---------------------------------------------------------------------------
# Group C — absolute counts. The genuine gap: "how many is too many" is a
# question the trader's own distribution answers better than a fixed number.
# ---------------------------------------------------------------------------

_GROUP_C = [
    _spec(key="fomo_symbols_in_window", kind=Kind.PERSONAL_BASELINE, fallback=3,
          meaning="distinct underlyings entered inside a 30-minute window",
          resolution_source=Source.HISTORY, metric="fomo_underlyings_per_window_p75",
          percentile=75, maturity=Maturity.SESSIONS_20,
          provenance="a scatter of 3 is ordinary for a basket trader and extreme for a single-index trader"),

    _spec(key="fomo_symbols_at_open", kind=Kind.PERSONAL_BASELINE, fallback=2,
          meaning="distinct underlyings in the opening 30 minutes",
          resolution_source=Source.HISTORY, metric="fomo_underlyings_at_open_p75",
          percentile=75, maturity=Maturity.SESSIONS_20, review_required=True,
          provenance="FLAGGED: measured ~4:1 over-firing; 2 is the tightest value in the "
                     "detector and is justified by an assertion about traders in general"),

    _spec(key="fomo_symbols_at_close", kind=Kind.PERSONAL_BASELINE, fallback=3,
          meaning="distinct underlyings in the closing 30 minutes",
          resolution_source=Source.HISTORY, metric="fomo_underlyings_at_close_p75",
          percentile=75, maturity=Maturity.SESSIONS_20,
          provenance="separated from the open threshold 2026-08-22; a pre-close scramble is "
                     "plausible but unmeasured"),

    _spec(key="fomo_expiry_day_symbols", kind=Kind.PERSONAL_BASELINE, fallback=4,
          meaning="distinct underlyings on the instrument's expiry day",
          resolution_source=Source.HISTORY, metric="fomo_underlyings_expiry_p75",
          percentile=75, maturity=Maturity.SESSIONS_20,
          provenance="expiry behaviour differs enough from ordinary days to need its own distribution"),

    _spec(key="expiry_overtrading_caution_count", kind=Kind.PERSONAL_BASELINE, fallback=5,
          meaning="trades on one underlying on its expiry day",
          resolution_source=Source.HISTORY, metric="expiry_day_trades_p75",
          percentile=75, maturity=Maturity.SESSIONS_20,
          provenance="an expiry-day specialist and an occasional participant are not comparable"),

    _spec(key="expiry_overtrading_danger_count", kind=Kind.PERSONAL_BASELINE, fallback=8,
          meaning="trades on one underlying on expiry, danger level",
          resolution_source=Source.HISTORY, metric="expiry_day_trades_p90",
          percentile=90, maturity=Maturity.SESSIONS_20,
          provenance="upper tail of the same distribution as the caution line"),

    _spec(key="expiry_overtrading_caution_lots", kind=Kind.PERSONAL_BASELINE, fallback=10,
          meaning="lots traded on one underlying on expiry",
          resolution_source=Source.HISTORY, metric="expiry_day_lots_p75",
          percentile=75, maturity=Maturity.SESSIONS_20,
          provenance="lot counts are not comparable across instruments or account sizes"),

    _spec(key="end_session_mis_caution_count", kind=Kind.PERSONAL_BASELINE, fallback=2,
          meaning="MIS entries after 15:00 IST, facing auto-square-off",
          resolution_source=Source.HISTORY, metric="late_mis_entries_p75",
          percentile=75, maturity=Maturity.SESSIONS_20,
          provenance="some traders work the close deliberately; for others it is panic"),

    _spec(key="end_session_mis_danger_count", kind=Kind.PERSONAL_BASELINE, fallback=3,
          meaning="late MIS entries, danger level",
          resolution_source=Source.HISTORY, metric="late_mis_entries_p90",
          percentile=90, maturity=Maturity.SESSIONS_20,
          provenance="upper tail of the same distribution"),

    # Definitional despite being counts — see the inventory. Personalising a
    # streak length gives the absurd result that a trader with many streaks
    # needs a LONGER streak before anyone mentions it.
    _spec(key="overconfidence_win_streak_caution", kind=Kind.DEFINITIONAL, fallback=3,
          meaning="consecutive winning trades before size is checked",
          provenance="three wins in a row is a definition, not a claim about what is normal"),

    _spec(key="overconfidence_win_streak_danger", kind=Kind.DEFINITIONAL, fallback=5,
          meaning="consecutive wins, higher bar",
          provenance="as above"),
]


# ---------------------------------------------------------------------------
# Group D — clock and hold time. Rung 2 already does exactly this for
# panic_exit_min and rapid_reentry_min; these are the ones left behind.
# ---------------------------------------------------------------------------

_GROUP_D = [
    _spec(key="revenge_window_danger_min", kind=Kind.PERSONAL_BASELINE, fallback=5,
          meaning="re-entry inside this many minutes of a loss is danger",
          resolution_source=Source.HISTORY, metric="reentry_after_loss_p10",
          percentile=10, maturity=Maturity.TRADES_20, review_required=True,
          provenance="FLAGGED: its caution twin already resolves from the trader's own p25 "
                     "re-entry gap while this stayed fixed - one detector measuring its two "
                     "lines two different ways"),

    _spec(key="rapid_flip_min", kind=Kind.PERSONAL_BASELINE, fallback=10,
          meaning="direction reversal on the same symbol inside this many minutes",
          resolution_source=Source.SESSION, metric="flip_interval_p25",
          percentile=25, maturity=Maturity.SESSION,
          provenance="a scalper reverses in seconds as a matter of course"),

    _spec(key="early_exit_winner_max_min", kind=Kind.PERSONAL_BASELINE, fallback=60,
          meaning="a winner held less than this counts as cut short",
          resolution_source=Source.HISTORY, metric="winner_hold_p50",
          percentile=50, maturity=Maturity.TRADES_20,
          provenance="60 minutes is a long hold for one trader and a scratch for another"),

    _spec(key="opening_trap_quick_exit_min", kind=Kind.PERSONAL_BASELINE, fallback=15,
          meaning="an exit within this many minutes is a reactive exit",
          resolution_source=Source.SESSION, metric="hold_minutes_p25",
          percentile=25, maturity=Maturity.SESSION,
          provenance="same reasoning as panic_exit_min, which rung 2 already personalises"),

    _spec(key="early_exit_ratio", kind=Kind.PERSONAL_BASELINE, fallback=0.40,
          meaning="winner hold as a fraction of loser hold",
          provenance="ALREADY self-relative - it divides the trader by themselves. Only the "
                     "0.40 is a judgement, and that is detector-review evidence work"),
]


THRESHOLD_SPECS: Dict[str, ThresholdSpec] = {
    s.key: s for s in (_GROUP_C + _GROUP_D)
}

#: Flagged in the G4 inventory as unsupported judgements. Detector review is
#: mandatory for these, not discretionary.
MANDATORY_REVIEW = frozenset({
    "fomo_symbols_at_open",
    "revenge_window_danger_min",
    "premium_loss_caution_pct",   # documented as firing routinely without behavioural failure
    "burst_trades_per_15min",     # retired 2026-08-23; kept here so the reason survives
})


def spec_for(key: str) -> Optional[ThresholdSpec]:
    return THRESHOLD_SPECS.get(key)


def kind_for(key: str) -> Kind:
    """
    A threshold's declared kind, defaulting to FALLBACK.

    FALLBACK is deliberately the default: an unclassified constant should look
    unclassified rather than pass silently as something considered.
    """
    s = THRESHOLD_SPECS.get(key)
    return s.kind if s else Kind.FALLBACK


def personalisable_keys() -> Dict[str, ThresholdSpec]:
    """Specs that name a metric — i.e. where a personal path could be built."""
    return {k: s for k, s in THRESHOLD_SPECS.items() if s.metric}
