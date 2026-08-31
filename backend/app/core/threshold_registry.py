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

from dataclasses import dataclass, replace as _replace
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
    # RECLASSIFIED 2026-08-27, Pattern #7. This was PERSONAL_BASELINE resolving
    # from Source.HISTORY via `fomo_underlyings_per_window_p75` - and that
    # metric is produced by NOTHING. Not baseline_service, not
    # behavioral_baseline_service, and `_apply_history_v2` places no fomo key.
    # Every trader therefore got the fallback of 3, permanently, while the
    # registry described a personalisation the system does not perform. FALLBACK
    # is what it actually is: a stand-in until something better exists.
    #
    # This is a correction to the CLASSIFICATION, not a decision against
    # personalising breadth. If the metric is ever produced, this entry is where
    # that would be declared.
    _spec(key="fomo_symbols_in_window", kind=Kind.FALLBACK, fallback=3,
          meaning="distinct underlyings entered inside the rolling window, every context",
          provenance="unsourced. The Pattern #7 review established which of this detector's "
                     "constants were wrong and deliberately did not invent a replacement for "
                     "this one; 3 is unchanged and untested against any alternative"),

    # fomo_symbols_at_open (2), fomo_symbols_at_close (3) and
    # fomo_expiry_day_symbols (4) were DELETED with the Pattern #7 review. All
    # three carried the same unproduced-metric problem as the key above, and two
    # of them could not fire at all: across 142 expiry-day entries the maximum
    # breadth ever reached was 3 against a threshold of 4, and across 50
    # pre-close entries the maximum was 2 against a threshold of 3. The open
    # threshold of 2 produced 39% of the detector's output on its own. Every
    # context now uses fomo_symbols_in_window. See docs/patterns/07-fomo_entry/.

    # expiry_overtrading_caution_count / _danger_count / _caution_lots were
    # DELETED here 2026-08-27 with `expiry_day_overtrading`. All three were
    # declared Kind.PERSONAL_BASELINE against Source.HISTORY metrics
    # (expiry_day_trades_p75 / _p90, expiry_day_lots_p75) that NO code produced -
    # verified at 0 occurrences outside this file - so the ladder fell through to
    # the literals 5 / 8 / 10 permanently, for every trader. Declaring a value
    # personal when nothing can ever personalise it is a false statement in the
    # registry, and it is the same defect Pattern 7 found in fomo_underlyings_*.
    # The lots key was worse still: it was compared against a sum of CONTRACTS,
    # which made its clause unconditionally true.
    # See docs/patterns/09-expiry_day_overtrading/.

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

    # The two `overconfidence_win_streak_*` specs went with their detector on
    # 2026-08-30. Their reasoning is kept here because it applies to ANY future
    # streak threshold and is the point most likely to be re-litigated:
    # personalising a streak length gives the absurd result that a trader with
    # many streaks needs a LONGER streak before anyone mentions it. Streak
    # lengths are DEFINITIONAL, not PERSONAL_BASELINE.
    #
    # The two size multipliers that gated the same detector never had specs at
    # all - the same gap `early_exit_min_samples` had.
]


# ---------------------------------------------------------------------------
# Group D — clock and hold time. Rung 2 already does exactly this for
# rapid_reentry_min; these are the ones left behind.
# ---------------------------------------------------------------------------

_GROUP_D = [

    # rapid_flip_min DELETED 2026-08-28 with `direction_instability`. It was
    # declared PERSONAL_BASELINE against metric `flip_interval_p25`, which no
    # code produced - and the resolver never reads `spec.metric` anyway, so the
    # declaration wired nothing. That defect is registry-wide, not local to this
    # key: see docs/contracts/PERSONAL_BASELINE_AUDIT.md.


    # `opening_trap_quick_exit_min` went with its detector on 2026-08-30. Worth
    # recording why it never worked: it declared Source.SESSION with metric
    # `hold_minutes_p25`, and `_apply_session` computes a `holds` list then
    # blends ONLY `rapid_reentry_min`. The metric was computed and discarded, so
    # a PERSONAL_BASELINE sat permanently at its global fallback. Third instance
    # of that class after `winner_hold_p50` and `late_mis_entries_p75/p90`.

]


# ---------------------------------------------------------------------------
# Group E — the thresholds that are ACTUALLY personalised today.
#
# Added 2026-08-28. These four were personalised for months and the registry
# described none of them: three carried Kind.FALLBACK as an artifact of being
# auto-generated from _FLOOR_DIRECTIONS, and `daily_trade_limit` was not in the
# registry at all, so `kind_for()` returned FALLBACK by default.
#
# Nothing here changes a value or a resolution. `violates_kind` permits every
# source these keys already use under PERSONAL_BASELINE exactly as it did under
# FALLBACK — verified before the change and pinned by
# test_registry_classification_matches_reality.
#
# `personalise` stays False here, and that is correct rather than a compromise.
# The flag governs the REGISTRY-DRIVEN path — "each detector flips its own at
# review, behind a replay" — and that path is genuinely not enabled for these
# keys. They are personalised by hand-written `place()` calls in
# `_apply_history_v2` that predate the registry and do not consult it. Setting
# the flag True would swap one false statement for another.
#
# So the registry now records what these thresholds ARE (a personal baseline,
# from this metric, at this percentile) while `personalise=False` records that
# the declared path is not what supplies them. Making the registry actually drive
# resolution is a larger change with its own replay; it is written up in
# docs/contracts/PERSONAL_BASELINE_AUDIT.md rather than attempted here.
# ---------------------------------------------------------------------------

_GROUP_E = [
    _spec(key="daily_trade_limit", kind=Kind.PERSONAL_BASELINE, fallback=7,
          meaning="trades in a day before the count is worth naming",
          resolution_source=Source.HISTORY, metric="daily_trades_p75",
          percentile=75, maturity=Maturity.SESSIONS_20,
          sensitivity=Sensitivity.HIGHER_IS_LOOSER,
          provenance="wired by hand in _apply_history_v2; a declared rule outranks it"),

    _spec(key="burst_trades_per_30min_caution", kind=Kind.PERSONAL_BASELINE,
          fallback=5,
          meaning="trades in 30 minutes before a burst is worth naming",
          resolution_source=Source.HISTORY, metric="burst_per_30min_p75",
          percentile=75, maturity=Maturity.SESSIONS_20,
          sensitivity=Sensitivity.HIGHER_IS_LOOSER,
          provenance="wired by hand in _apply_history_v2"),

    _spec(key="revenge_window_caution_min", kind=Kind.PERSONAL_BASELINE,
          fallback=20,
          meaning="minutes after a loss still counted as a reaction",
          resolution_source=Source.HISTORY, metric="reentry_after_loss_p25",
          percentile=25, maturity=Maturity.SESSIONS_20,
          sensitivity=Sensitivity.HIGHER_IS_STRICTER,
          provenance="wired by hand in _apply_history_v2; floored at 1 minute"),

    _spec(key="consecutive_loss_caution", kind=Kind.PERSONAL_BASELINE,
          fallback=3,
          meaning="losses in a row before the streak is worth naming",
          resolution_source=Source.HISTORY, metric="loss_streak_p60",
          percentile=60, maturity=Maturity.SESSIONS_20,
          sensitivity=Sensitivity.HIGHER_IS_LOOSER,
          provenance="wired by hand in _apply_history_v2"),
]


THRESHOLD_SPECS: Dict[str, ThresholdSpec] = {
    s.key: s for s in (_GROUP_C + _GROUP_D + _GROUP_E)
}

# ---------------------------------------------------------------------------
# F1 - the thresholds that are universal safety
# ---------------------------------------------------------------------------
#
# Until now `violates_kind` was enforced at resolution time and guarded NOTHING,
# because no threshold was classified `universal_safety`. The rule was machinery
# protecting an empty set.
#
# WHAT QUALIFIES, AND WHAT DELIBERATELY DOES NOT
#
# A universal-safety threshold states objective harm - a magnitude of loss or
# exposure that is dangerous whoever the trader is. It must never be learned from
# the person it protects, because their habits cannot make an objectively
# dangerous event safe.
#
# The seven thresholds personal history actually moves today - daily trade limit
# and danger, burst caution and danger, the re-entry window, loss-streak caution
# and danger - are NOT here, and that is deliberate rather than an oversight.
# They describe a trader's tempo, not objective harm. "Six losses in a row" is a
# streak, and whether it hurt depends entirely on the size of the six. Classifying
# them universal_safety would forbid the personalisation that is the whole point
# of a baseline, and would be the opposite error to the one being fixed.
#
# What IS here measures magnitude:
#
#   position size as a fraction of the account  - account-relative exposure
#   loss as a fraction of premium paid          - trade-relative loss
#   loss with no stop in place                  - trade-relative loss
#
# CAPITAL IS STILL ALLOWED
#
# `violates_kind` forbids HISTORY, SESSION and POPULATION. It permits CAPITAL,
# which is right and necessary: account-relative safety needs an account size,
# and capital comes off the broker rather than out of the trader's habits.
#
# NEUTRAL TODAY, BY VERIFICATION NOT BY HOPE
#
# Rung 1 moves seven keys and none is below. Rung 2 moves exactly one,
# `rapid_reentry_min`, and it is not below. POPULATION is
# unused. So the guard now refuses resolutions that do not currently occur - it
# is a lock on a door nobody is yet trying to open, which is when a lock should
# be fitted.
#
# KIND IS NOT VALUE
#
# `premium_loss_caution_pct` WAS in MANDATORY_REVIEW because its VALUE was
# disputed - it was said to fire routinely without behavioural failure. Measured
# in the Pattern #8 review (2026-08-27) that is not true, and the flag was
# cleared: 6% of long options lose 40%+ of premium, and the 48 trades the
# detector flags carry 35% of every rupee the book lost.
#
# The reasoning the note was written to make survives the flag being cleared and
# is the more important half: its Kind was settled either way. It is a claim
# about objective loss magnitude, and a wrong number of the right kind is still
# the right kind.
_UNIVERSAL_SAFETY = {
    "max_position_pct_caution": (5.0, Sensitivity.HIGHER_IS_LOOSER,
                                 "percent of the account in one position"),
    "max_position_pct_danger": (10.0, Sensitivity.HIGHER_IS_LOOSER,
                                "percent of the account in one position"),
    "premium_loss_caution_pct": (40, Sensitivity.HIGHER_IS_LOOSER,
                                 "percent of the premium paid that has been lost"),
    "premium_loss_danger_pct": (60, Sensitivity.HIGHER_IS_LOOSER,
                                "percent of the premium paid that has been lost"),
    "premium_loss_critical_pct": (80, Sensitivity.HIGHER_IS_LOOSER,
                                  "percent of the premium paid that has been lost"),
    "no_stoploss_loss_pct_danger": (50, Sensitivity.HIGHER_IS_LOOSER,
                                    "percent lost with no stop in place"),
}

for _key, (_default, _direction, _meaning) in _UNIVERSAL_SAFETY.items():
    THRESHOLD_SPECS[_key] = ThresholdSpec(
        key=_key,
        kind=Kind.UNIVERSAL_SAFETY,
        fallback=_default,
        meaning=_meaning,
        sensitivity=_direction,
        provenance=(
            "objective magnitude of loss or exposure; may not be learned from "
            "the trader it protects (F1)"
        ),
    )

# ---------------------------------------------------------------------------
# Product policy - our decisions, never the trader's and never learned
# ---------------------------------------------------------------------------
#
# These say how much we are willing to interrupt someone. They are not claims
# about trading and no amount of a trader's history should move them: a trader
# must not be able to learn their way into a larger alert budget.
#
# Classified 2026-08-24. Values unchanged - only the Kind, which is what stops
# them ever resolving from HISTORY, SESSION or POPULATION via violates_kind.
_PRODUCT_POLICY = {
    "alert_session_hard_cap": (8, "alerts a trader may receive in one session"),
    "alert_bucket_minutes": (5, "window in which similar alerts are grouped"),
    "alert_stale_push_min": (30, "age past which a push notification is not worth sending"),
    "guardian_monthly_budget": (3, "guardian messages a month"),
}

# ── The constitution ladder ────────────────────────────────────────────────
#
# Classified 1 Sep 2026 (Pattern 24). VALUES UNCHANGED - 0.80 and 1.20 are
# exactly what shipped; only their Kind and provenance are recorded.
#
# These are the ONLY two numbers `constitution_violation` chooses. Every other
# input it reads is the trader's own declared rule, so these decide the one
# thing the product decides there: how close to your own line counts as a
# warning, and how far past it counts as severe.
#
# PRODUCT_POLICY, not a trading threshold and not personalisable. A trader must
# not be able to move the point at which breaking their own rule is reported -
# that would let the rule be softened without editing the rule, which is the
# thing `constitution_service`'s tighten-instant/loosen-409 gate exists to
# prevent. `violates_kind` enforces it: neither may resolve from HISTORY,
# SESSION or POPULATION.
_CONSTITUTION_LADDER = {
    "constitution_approaching_pct": (
        0.80, "share of your own limit at which a warning is raised"),
    "constitution_severe_pct": (
        1.20, "multiple of your own limit at which the breach is severe"),
}

for _key, (_default, _meaning) in _CONSTITUTION_LADDER.items():
    THRESHOLD_SPECS[_key] = ThresholdSpec(
        key=_key,
        kind=Kind.PRODUCT_POLICY,
        fallback=_default,
        meaning=_meaning,
        provenance=(
            "product policy on reporting a trader's OWN rule, not a claim about "
            "trading. The rule is theirs; only the run-up and the severity step "
            "are ours. Values unchanged from ship; classified at Pattern 24"),
    )


for _key, (_default, _meaning) in _PRODUCT_POLICY.items():
    THRESHOLD_SPECS[_key] = ThresholdSpec(
        key=_key,
        kind=Kind.PRODUCT_POLICY,
        fallback=_default,
        meaning=_meaning,
        provenance="product decision about interruption, not a trading threshold",
    )


#: Flagged in the G4 inventory as unsupported judgements. Detector review is
#: mandatory for these, not discretionary.
# ---------------------------------------------------------------------------
# UNIVERSAL_FLOORS, with the one thing they never declared: which way they point
# ---------------------------------------------------------------------------
#
# A floor is arithmetically the same operation either way - raise the value to
# the minimum - but it MEANS opposite things depending on the threshold's
# direction, and `trading_defaults` applies one `<` comparison to both without
# saying which is which:
#
#   HIGHER_IS_LOOSER   a bigger number is a quieter detector, so the floor is a
#                      NOISE floor: "never alert on fewer than three losses".
#   HIGHER_IS_STRICTER a bigger number is a louder detector, so the floor is a
#                      SENSITIVITY floor: "always look at least two minutes back".
#
# Four of the ten are noise floors and six are sensitivity floors. Nothing said
# so until now, which is why the same dict reads as a safety guarantee on some
# keys and as spam suppression on others.
#
# Every direction below was read from the consumer, not inferred from the name:
# a window compared with `gap <= window` widens as it grows, while a gate
# compared with `value < threshold: return None` narrows.
#
# Kind stays FALLBACK on every entry. Declaring direction changes no value and no
# resolution; classifying these as universal_safety is a separate decision (F1)
# with its own replay.
_FLOOR_DIRECTIONS = {
    # noise floors - a bigger number means the detector says less
    "burst_trades_per_30min_caution": (5, Sensitivity.HIGHER_IS_LOOSER,
                                       "trades in 30 minutes before a burst is worth naming"),
    "consecutive_loss_caution": (3, Sensitivity.HIGHER_IS_LOOSER,
                                 "losses in a row before the streak is worth naming"),
    "no_stoploss_hold_min": (5, Sensitivity.HIGHER_IS_LOOSER,
                             "minutes held before a missing stop is judged at all"),
    "no_stoploss_loss_pct_caution": (25, Sensitivity.HIGHER_IS_LOOSER,
                                     "percent lost before a missing stop is worth naming"),
    # sensitivity floors - a bigger number means the detector looks wider
    "revenge_window_caution_min": (20, Sensitivity.HIGHER_IS_STRICTER,
                                   "minutes after a loss still counted as a reaction"),
    "revenge_window_min": (10, Sensitivity.HIGHER_IS_STRICTER,
                           "unified re-entry window, set from a declared cooldown"),
    "rapid_reentry_min": (5, Sensitivity.HIGHER_IS_STRICTER,
                          "minutes within which a re-entry counts as rapid"),
}

for _key, (_default, _direction, _meaning) in _FLOOR_DIRECTIONS.items():
    _existing = THRESHOLD_SPECS.get(_key)
    if _existing is not None:
        # ALREADY CLASSIFIED. Add the direction and change nothing else.
        #
        # The first cut of this block rebuilt every entry with kind=FALLBACK and
        # silently downgraded two thresholds that were already personal_baseline.
        # No value moved, so a threshold-equality check showed nothing - the loss
        # was of classification, which is exactly what this registry exists to
        # hold. Declaring a direction must never overwrite a decision someone
        # else made.
        THRESHOLD_SPECS[_key] = _replace(_existing, sensitivity=_direction)
        continue
    THRESHOLD_SPECS[_key] = ThresholdSpec(
        key=_key,
        kind=Kind.FALLBACK,          # unclassified before, unclassified now
        fallback=_default,
        meaning=_meaning,
        sensitivity=_direction,
        provenance="direction read from the consumer; value unchanged (F2)",
    )

MANDATORY_REVIEW = frozenset({
    # Reviewed and DELETED 2026-08-27 (Pattern #7). The flag said "~4:1
    # over-firing"; measured, it was 29 of 74 firings at 3.6:1 against the
    # general threshold. Kept here so the reason survives the constant.
    "fomo_symbols_at_open",
    "revenge_window_danger_min",   # retired 2026-08-24; kept so the reason survives
    "burst_trades_per_15min",     # retired 2026-08-23; kept here so the reason survives
    #
    # premium_loss_caution_pct was here until 2026-08-27, flagged as "documented
    # as firing routinely without behavioural failure". Its Pattern #8 review
    # MEASURED that and the flag is refuted, so it is removed rather than kept:
    # across all 888 long options in the reference book only 6% lose 40% or more
    # of premium (40.2% finish in profit, 43.8% lose under a fifth, 9.6% lose a
    # fifth to two fifths). The caution level is the top 6% of outcomes, not a
    # routine event.
    #
    # The other three entries above stay because their constants were DELETED
    # and the reason has to outlive them. This one stays in the code, vindicated,
    # so an open-concern marker on it would be false. See
    # docs/patterns/08-premium_loss_event/.
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
