"""
Detector Registry — Engine v2 Appendix A.1 / A.10.

One declarative record per detector. The engine iterates THIS list, not a
hardcoded method list. Adding a detector = one DetectorSpec + one method.

Fields
------
name                pattern_type written to BehaviorEvent.detector / RiskAlert.pattern_type
version             per-detector semver; bump on ANY logic change (A.2).
                    Alerts/events store max(detector version, ENGINE_VERSION).
nature              emotional | risk | discipline | performance   (master §1.1 Axis A)
disposition         alerting | analytics                          (master §1.1 Axis C)
                    Phase 4 flipped panic_exit/early_exit/opening_trap/
                    rapid_reentry to analytics (severity=info, evidence only).
trigger             exit | session   — when the detector can fire. All detectors
                    are exit-triggered today (engine runs per CompletedTrade);
                    'session' marks session-level patterns that will move to
                    EOD evaluation in Phase 4+. 'entry' arrives with Phase 6.
notification_level  0 analytics · 1 in-app · 2 push · 3 critical push · 4 guardian
                    (maximum level this detector may reach; routing still applies
                    severity × confidence — master §1B.7b)
guardian_eligible   may ever reach the guardian channel
consumes            state the detector reads (A.10 — primary state only, never
                    another detector, never derived scores)
uses_baseline / uses_constitution / uses_position_state
                    threshold-source dependencies (master §1.1 Axis B)

Dependency rule (A.10): no detector may consume another detector's output.
Detectors consume primary state + the trade event; meta-detectors (Phase 5
death spiral) consume BehaviorEvents.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Dict, NamedTuple, Tuple


class ReferenceFrame(str, Enum):
    """
    What a detector measures against.

    The distinction is the whole of "normal is not safe": only PERSONAL depends
    on the trader's own history, so only PERSONAL can be quietened by a trader
    whose history is bad. The other three keep working on a brand-new account and
    cannot be argued down by habit.

        ACCOUNT     impact relative to account equity - needs a denominator,
                    abstains without one
        TRADE       loss or risk relative to THIS position - needs only the trade,
                    so it works on someone's first ever one
        PERSONAL    deviation from this trader's own established behaviour -
                    meaningless without history, and the only frame a baseline
                    may move
        STRUCTURAL  objectively observable behaviour needing no baseline at all -
                    "you added to a losing position" is a fact about a sequence

    A detector may use more than one. Recording which is what makes it checkable
    that a PERSONAL frame has not been allowed to silence a STRUCTURAL claim.
    """

    ACCOUNT = "account"
    TRADE = "trade"
    PERSONAL = "personal"
    STRUCTURAL = "structural"


@dataclass(frozen=True)
class DetectorSpec:
    name: str
    method: str                     # BehaviorEngine method name
    version: str
    nature: str                     # emotional | risk | discipline | performance
    disposition: str                # alerting | analytics
    trigger: str                    # exit | session (entry arrives Phase 6)
    notification_level: int         # 0-4, max channel
    guardian_eligible: bool = False
    uses_baseline: bool = False
    uses_constitution: bool = False
    uses_position_state: bool = False
    consumes: Tuple[str, ...] = ("session_trades", "completed_trade", "thresholds")
    # Feature-flag DEFAULT mode (migration 068): off | shadow | canary | on.
    # A row in the detector_flags table overrides this at runtime. New or
    # reworked detectors ship as "shadow" here, then promote to "on" once shadow
    # parity holds — the safe detector-by-detector migration path.
    default_mode: str = "on"
    #: Which reference frame(s) this detector measures in. See ReferenceFrame.
    #:
    #: EMPTY ON EVERY ENTRY, deliberately. The frame is decided while reading the
    #: detector during its review, not guessed in a bulk annotation pass - a field
    #: filled in by guesswork is worse than an empty one, because it reads as a
    #: decision somebody made.
    frames: tuple = ()


# RETIRED 2026-08-26 — `consecutive_loss_streak`. It was the engine's most
# frequent alert and its trigger was chance: across 189 sessions, 63 contained a
# 3+ loss run against 63.0 expected from the trader's 39.9% win rate alone. A run
# of losses is what that win rate produces on its own, so the run is not evidence
# of a changed state and severity derived from the count was derived from noise.
# The behaviour worth alerting on — "you are approaching / have crossed the
# consecutive-loss limit YOU set" — is the `max_consecutive_losses` rule of
# `constitution_violation`, which reads the same canonical streak against the
# trader's own declared number instead of ours. See
# docs/patterns/04-consecutive_loss_streak/.
REGISTRY: Tuple[DetectorSpec, ...] = (
    # 3.0.0: rewritten to the frozen A x B contract 2026-08-23. First detector
    # to declare its reference frames and the first to return a DetectorResult.
    DetectorSpec("revenge_trade", "_detect_revenge_trade",
                 "3.0.0", "emotional", "alerting", "exit", 2,
                 uses_baseline=True, uses_constitution=True,
                 frames=(ReferenceFrame.ACCOUNT, ReferenceFrame.TRADE,
                         ReferenceFrame.PERSONAL, ReferenceFrame.STRUCTURAL)),
    # Emits overtrading_burst (30-min window) AND daily_overtrading (Phase 4
    # split) — version lookup for the alias lives in ALIASES below.
    #
    # `overtrading_burst` is DEFERRED as of the Pattern #5 review (2026-08-26)
    # and is deliberately UNCHANGED. 13 detections, 12 alerts, 10 of 189
    # sessions, and it never once fired alone — n is far too small to justify
    # moving its thresholds in either direction. Absence of evidence is not
    # evidence, so it was neither tuned nor removed. `daily_overtrading`, which
    # shares this method, WAS changed. See docs/patterns/05-overtrading/.
    DetectorSpec("overtrading_burst", "_detect_overtrading_burst",
                 "2.0.0", "emotional", "alerting", "exit", 2,
                 uses_baseline=True, uses_constitution=True),
    DetectorSpec("size_escalation", "_detect_size_escalation",
                 "1.1.0", "emotional", "alerting", "exit", 1),
    DetectorSpec("rapid_reentry", "_detect_rapid_reentry",
                 "2.0.0", "emotional", "analytics", "exit", 0),
    DetectorSpec("panic_exit", "_detect_panic_exit",
                 "2.0.0", "emotional", "analytics", "exit", 0,
                 consumes=("completed_trade", "exit_order_types", "thresholds")),
    # 2.0.0: Pattern #1 review, 2026-08-24. Escalation across ATTEMPTS after a
    # closed loss - not adding to an open one, which is
    # adding_to_adverse_position and reads a fill sequence this cannot see.
    # The step is now the one the trader took, the losses must be trailing
    # consecutive, and size is capital at risk rather than quantity in one
    # branch and notional in the other.
    DetectorSpec("martingale_behaviour", "_detect_martingale_behaviour",
                 "2.0.0", "risk", "alerting", "exit", 2,
                 frames=(ReferenceFrame.TRADE, ReferenceFrame.STRUCTURAL)),
    # 2.0.0: Pattern #1, 2026-08-24. The first detector to read a position's
    # FILL SEQUENCE rather than its aggregate - a CompletedTrade folds every
    # entry into one avg_entry_price, so an averaging-down ladder was invisible
    # to every other detector in this list.
    #
    # The FIRST detector with trigger="entry", and the first the exit loop skips.
    # It fires on the INCREASE fill itself: by the time a position closes, the
    # decision to add is long past - 50 -> 40 -> 30 -> close alerts after the
    # last one, when nothing can be done about it. Fired on the fill, the trader
    # is looking at the position they just added to.
    #
    # It needs no price feed: the fill price is a market print and the running
    # average comes from the ledger, so nothing here can be made wrong by a
    # stale tick.
    DetectorSpec("adding_to_adverse_position", "_detect_adding_to_adverse_position",
                 "2.0.0", "risk", "alerting", "entry", 2,
                 consumes=("completed_trade", "position_fills", "strategy_group"),
                 frames=(ReferenceFrame.TRADE, ReferenceFrame.STRUCTURAL)),
    DetectorSpec("direction_instability", "_detect_direction_instability",
                 "2.0.0", "emotional", "alerting", "exit", 1),
    DetectorSpec("excess_exposure", "_detect_excess_exposure",
                 "1.0.0", "risk", "alerting", "exit", 2,
                 uses_constitution=True),
    DetectorSpec("session_meltdown", "_detect_session_meltdown",
                 "1.0.0", "risk", "alerting", "exit", 4, guardian_eligible=True,
                 uses_constitution=True,
                 consumes=("session", "completed_trade", "thresholds")),
    DetectorSpec("fomo_entry", "_detect_fomo_entry",
                 "1.0.0", "emotional", "alerting", "exit", 1),
    DetectorSpec("no_stoploss", "_detect_no_stoploss",
                 "1.0.0", "risk", "alerting", "exit", 2,
                 consumes=("completed_trade", "exit_order_types", "thresholds")),
    DetectorSpec("early_exit", "_detect_early_exit",
                 "2.0.0", "performance", "analytics", "session", 0),
    DetectorSpec("winning_streak_overconfidence", "_detect_winning_streak_overconfidence",
                 "1.1.0", "emotional", "alerting", "exit", 1,
                 uses_baseline=True),
    DetectorSpec("options_premium_avg_down", "_detect_options_premium_avg_down",
                 "1.0.0", "emotional", "alerting", "exit", 1),
    DetectorSpec("premium_loss_event", "_detect_premium_loss_event",
                 "2.0.0", "risk", "alerting", "exit", 3),
    DetectorSpec("expiry_day_overtrading", "_detect_expiry_day_overtrading",
                 "1.0.0", "emotional", "alerting", "exit", 2,
                 uses_baseline=True),
    DetectorSpec("opening_5min_trap", "_detect_opening_5min_trap",
                 "2.0.0", "emotional", "analytics", "exit", 0),
    DetectorSpec("end_of_session_mis_panic", "_detect_end_of_session_mis_panic",
                 "2.0.0", "emotional", "alerting", "exit", 1),
    DetectorSpec("post_loss_recovery_bet", "_detect_post_loss_recovery_bet",
                 "1.1.0", "risk", "alerting", "exit", 2),
    DetectorSpec("profit_giveaway", "_detect_profit_giveaway",
                 "1.0.0", "emotional", "alerting", "exit", 2,
                 consumes=("session", "session_trades", "completed_trade", "thresholds")),
    # cooldown_violation: system-suggested cooldowns (Cooldown DB records),
    # analytics-only. Distinct from the constitution cooldown rule below.
    DetectorSpec("cooldown_violation", "_detect_cooldown_violation",
                 "1.0.0", "discipline", "analytics", "exit", 0,
                 uses_constitution=True,
                 consumes=("active_cooldowns", "completed_trade")),
    # Constitution violation (Phase 2, Q15): one pattern for every user-declared
    # rule — daily_loss, daily_trades, max_consecutive_losses, cooldown,
    # restricted_window, max_trade_risk. Ladder: 80% caution / 100% danger /
    # 120% critical (guardian-eligible). Returns a LIST (multi-rule breaches).
    DetectorSpec("constitution_violation", "_detect_constitution_violation",
                 "1.0.0", "discipline", "alerting", "exit", 4,
                 guardian_eligible=True, uses_constitution=True,
                 consumes=("session", "session_trades", "completed_trade", "thresholds")),
    # Phase 4 additions
    # 2.0.0: Pattern #3 review, 2026-08-24. Severity now reads the PEAK size
    # rather than the last, which stopped it oscillating danger/caution as an
    # episode grew, and obsession_min_reentries is gone - it could never bind.
    # Its unique contribution is persistence WITHOUT escalation: on 4 of the 20
    # episodes in the book no other detector fires at all.
    DetectorSpec("same_symbol_obsession", "_detect_same_symbol_obsession",
                 "2.0.0", "emotional", "alerting", "exit", 2,
                 frames=(ReferenceFrame.STRUCTURAL,)),
    DetectorSpec("time_of_day_bias", "_detect_time_of_day_bias",
                 "1.0.0", "performance", "alerting", "exit", 1,
                 uses_baseline=True),
    # Phase 7: performance analytics (info-only, feed the Strategy driver)
    DetectorSpec("win_rate_collapse", "_detect_win_rate_collapse",
                 "1.0.0", "performance", "analytics", "session", 0,
                 uses_baseline=True),
    DetectorSpec("strategy_breakdown", "_detect_strategy_breakdown",
                 "1.0.0", "performance", "analytics", "session", 0,
                 uses_baseline=True),
)

# Event types emitted by a detector under a different name than its spec
# (version lookup only — never iterated).
ALIASES = {
    "daily_overtrading": "2.0.0",
    # Meta-detector (L2, behavior_scores_service) — consumes BehaviorEvents,
    # never iterated with the L1 detectors.
    "death_spiral": "1.0.0",
    # Position-monitor (entry-time) patterns - Phase 6
    "overexposure": "2.0.0",
    "portfolio_concentration": "1.0.0",
    "holding_loser": "1.0.0",
    # Housekeeping nudge from maintenance_tasks, not a behaviour detector — but
    # it IS written to risk_alerts.pattern_type, so it is part of the vocabulary
    # and the contract test found it missing from this map.
    "capital_mismatch": "1.0.0",
}

# Fast lookups
BY_NAME = {spec.name: spec for spec in REGISTRY}


def spec_for(pattern_type: str) -> DetectorSpec | None:
    return BY_NAME.get(pattern_type)


# ---------------------------------------------------------------------------
# What each pattern MEANS — the single source of user-facing copy
# ---------------------------------------------------------------------------
# This lived in the frontend, in three separate `Record<string, string>` maps
# keyed on pattern name with no normalisation. Engine v2 renamed the detectors;
# the maps kept the v1 keys; the lookups silently returned undefined and React
# rendered nothing. Overtrading — the most common alert we raise — opened a
# detail panel with no facts, no explanation and no context, and there was no
# error anywhere because a missing key is not a failure in either language.
#
# Copy lives here, next to the name it describes, and test_pattern_contract
# fails if a pattern has no copy or copy has no pattern. A rename cannot
# silently orphan a renderer again.
#
# Rules for writing these:
#   observes    — what the detector actually looks at. Mechanical, checkable.
#   explanation — why it is worth noticing. Mechanism only.
#
# No statistics. The frontend previously shipped precise unsourced claims
# ("win rate on the 4th trade after 3 losses is typically below 30%") presented
# as measurement. Where a number belongs, it is the trader's own — see My Record.

class PatternCopy(NamedTuple):
    label: str
    observes: str
    explanation: str


PATTERN_COPY: Dict[str, PatternCopy] = {
    # ── Emotional ────────────────────────────────────────────────────────
    "revenge_trade": PatternCopy(
        "Trade straight after a loss",
        "How soon a new position follows a losing exit, and how its size compares to your average.",
        "A decision taken while the previous loss is still fresh is being made against that loss "
        "rather than on its own terms.",
    ),
    "rapid_reentry": PatternCopy(
        "Immediate re-entry",
        "Re-entering the same instrument shortly after closing it at a loss.",
        "The setup that just failed has not changed in those few minutes. The re-entry is a "
        "second attempt at the same idea at a worse moment.",
    ),
    "session_meltdown": PatternCopy(
        "Session breakdown",
        "Session P&L against your daily loss limit, together with the pace of trading.",
        "A session that is both deep in loss and accelerating is the shape a bad day takes before "
        "it becomes the worst one.",
    ),
    "post_loss_recovery_bet": PatternCopy(
        "Recovery bet",
        "A position materially larger than your average, entered after a loss on the same underlying.",
        "If this one also loses, the combined loss exceeds everything it was meant to recover.",
    ),
    "profit_giveaway": PatternCopy(
        "Gains given back",
        "Session P&L against its high-water mark for the day.",
        "The trade taken after a session peak is the one that decides whether the day is kept.",
    ),
    "panic_exit": PatternCopy(
        "Fast manual exit",
        "A quick manual close at a loss with no stop-loss order on record.",
        "May be a considered decision or a reaction. Worth reviewing against what you planned "
        "before entering.",
    ),
    "fomo_entry": PatternCopy(
        "Chasing several instruments",
        "Entries spread across multiple distinct underlyings inside a short window.",
        "Several unrelated instruments at once is usually chasing movement rather than acting on "
        "a view.",
    ),
    "winning_streak_overconfidence": PatternCopy(
        "Size up after wins",
        "Position size after a run of winning trades, against your session average.",
        "Size raised because recent trades worked is size raised on a sample, not on an edge.",
    ),

    # ── Risk / sizing ────────────────────────────────────────────────────
    "size_escalation": PatternCopy(
        "Rising position size",
        "Quantity across consecutive trades on the same underlying while losing.",
        "Larger size on an instrument that is already losing compounds the drawdown rather than "
        "recovering it.",
    ),
    "martingale_behaviour": PatternCopy(
        "Averaging down",
        "Position size increasing after consecutive losses on the same instrument.",
        "Each step raises the total at risk in the session, not just the cost of this trade.",
    ),
    "excess_exposure": PatternCopy(
        "Oversized exposure",
        "Capital at risk in a single position against the trading capital you declared.",
        "One position large enough to define the session removes the choice of how the session ends.",
    ),
    "no_stoploss": PatternCopy(
        "No stop-loss on record",
        "Whether a stop-loss order was on the position when it was exited.",
        "A pre-defined exit is decided before the position moves. Without one, the exit is decided "
        "while it is moving.",
    ),
    "adding_to_adverse_position": PatternCopy(
        "Added to a losing position",
        "Additions made to a position that had already moved against you, and how far "
        "against it had moved each time.",
        "The position that is already wrong is the one being made bigger. Each addition "
        "lowers the price at which it has to come back, and raises what it costs if it "
        "does not.",
    ),
    "options_premium_avg_down": PatternCopy(
        "Adding to a losing option",
        "Additional quantity on an option position already down on premium.",
        "Averaging down an option fights both direction and time decay.",
    ),
    "premium_loss_event": PatternCopy(
        "Premium destruction",
        "Percentage of the premium paid that has been lost on a long option.",
        "Beyond a point the position needs a move it was never sized for. Time is on the other side.",
    ),

    # ── Discipline / pace ────────────────────────────────────────────────
    "overtrading_burst": PatternCopy(
        "Burst of trades",
        "Positions opened inside a 30-minute window, counting a multi-leg structure as one.",
        "Trades taken minutes apart share one state of mind rather than separate assessments.",
    ),
    "expiry_day_overtrading": PatternCopy(
        "Expiry-day activity",
        "Trades and lots on an instrument expiring today.",
        "Expiry-day options move on time decay as much as direction, and the clock does not reverse.",
    ),
    "opening_5min_trap": PatternCopy(
        "Opening-minutes entry",
        "Entries in the first minutes after open that closed quickly at a loss, or lost heavily.",
        "Spreads are widest and option premiums least settled while the market is still finding its level.",
    ),
    "end_of_session_mis_panic": PatternCopy(
        "Late intraday entries",
        "MIS entries in the run-up to auto square-off.",
        "There is very little time for the position to work, and the exit is not yours to choose.",
    ),
    "cooldown_violation": PatternCopy(
        "Cooldown ignored",
        "Time between a losing exit and your next entry, against the cooldown you set.",
        "The cooldown exists to put distance between a loss and the next decision.",
    ),
    "constitution_violation": PatternCopy(
        "Rule breach",
        "Your own limits — loss cap, trade count, cooldown, no-trade windows, position size — "
        "against what you actually did.",
        "These are your numbers, written when the session was not running.",
    ),
    "same_symbol_obsession": PatternCopy(
        "Repeated same instrument",
        "Repeat trades on one underlying — any strike or expiry — and their combined result.",
        "Returning to the same instrument after losses on it is persistence with the instrument, "
        "not with the strategy.",
    ),
    "direction_instability": PatternCopy(
        "Direction flip-flop",
        "Switching between long and short on the same underlying in a short window.",
        "Reversing repeatedly usually tracks the price rather than a view about it.",
    ),
    "early_exit": PatternCopy(
        "Early exit",
        "Winning positions closed well short of your usual holding time.",
        "Winners cut short while losers run is the asymmetry that quietly caps a strategy.",
    ),

    # ── Performance (analytics) ──────────────────────────────────────────
    "win_rate_collapse": PatternCopy(
        "Win rate below baseline",
        "Today's win rate against your own longer-run baseline.",
        "A sharp drop against your own history is a change in conditions or in execution — worth "
        "knowing which.",
    ),
    "strategy_breakdown": PatternCopy(
        "Strategy underperforming",
        "Results grouped by the strategy structure you traded.",
        "Separates a losing day from a structure that has stopped working.",
    ),
    "time_of_day_bias": PatternCopy(
        "Time-of-day pattern",
        "Results grouped by the hour you entered.",
        "Most traders have hours that work and hours that do not. Yours are in your own record.",
    ),
}

#: Copy for the event types emitted under a name that is not a registry spec.
ALIAS_COPY: Dict[str, PatternCopy] = {
    # Copy rewritten 2026-08-26, Pattern #5. It used to say "past a certain
    # count the day stops being a series of decisions and becomes momentum" —
    # a claim about psychology the reference book contradicts on all three
    # observable markers (past the line the trader was slower, smaller and no
    # worse). The pattern now reports one thing that is true by construction:
    # you are at or past the number you set for yourself.
    "daily_overtrading": PatternCopy(
        "Past your trade limit",
        "Positions opened today against the daily trade limit you declared, counting a "
        "multi-leg structure as one.",
        "You set a limit on how many positions you take in a day. This is where you reached it.",
    ),
    "death_spiral": PatternCopy(
        "Multi-domain breakdown",
        "Several different behaviour patterns firing together in one session.",
        "One pattern is a moment. Several at once is a session that has stopped being managed.",
    ),
    "overexposure": PatternCopy(
        "Position too large",
        "The size of a position you have just opened against your capital.",
        "Raised while the position is open, because that is while it can still be acted on.",
    ),
    "portfolio_concentration": PatternCopy(
        "Concentrated exposure",
        "Share of your open exposure sitting in one underlying.",
        "Several positions in one underlying is one position wearing several names.",
    ),
    "holding_loser": PatternCopy(
        "Holding a loser",
        "How long an open position has been held while down.",
        "A position held well past the point it was working is being held for a reason that is no "
        "longer about the trade.",
    ),
    "capital_mismatch": PatternCopy(
        "Capital out of date",
        "The trading capital declared in your rules against what your account can actually deploy.",
        "Percent-of-capital rules are only as accurate as the capital figure behind them.",
    ),
}


def pattern_copy(pattern_type: str) -> PatternCopy | None:
    """User-facing copy for any emitted pattern type, registry spec or alias."""
    spec_copy = PATTERN_COPY.get(pattern_type)
    if spec_copy:
        return spec_copy
    return ALIAS_COPY.get(pattern_type)


def all_pattern_types() -> Tuple[str, ...]:
    """Every pattern type this system can emit — specs plus aliases."""
    return tuple(BY_NAME.keys()) + tuple(ALIASES.keys())
