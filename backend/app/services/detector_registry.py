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
    #: WHEN the engine invokes this detector. `entry` runs on the fill, from
    #: the entry-batch flush; `exit` runs when a position closes, from the
    #: per-CompletedTrade loop. Those are the only two dispatch paths that
    #: exist, and `TRIGGERS` below is enforced at import.
    #:
    #: `session` used to be a third value here and was SILENTLY IGNORED — the
    #: engine branches on `entry` and runs everything else, so a detector
    #: declaring `session` ran on the exit path anyway. It was not a dispatch
    #: value at all: it answered a different question, "what is this
    #: detector's subject", which is now `scope`. See that field.
    trigger: str                    # entry | exit
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
    #: WHAT this detector's subject is, which is independent of when it runs.
    #: `trade` judges the CompletedTrade in hand; `session` judges the day as a
    #: whole and merely happens to be evaluated at a close, because a close is
    #: when session state is next known. Splitting this out of `trigger` is
    #: what makes the dispatch field enforceable — see `trigger`.
    #:
    #: This field is DESCRIPTIVE. Nothing branches on it, and nothing should
    #: until an EOD evaluation path exists; a session-scoped detector reaching
    #: the same verdict several times as a session progresses is the current
    #: and intended behaviour.
    scope: str = "trade"            # trade | session
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
    # RETIRED 2026-08-27 - `size_escalation`. Its claim was that the ORDER of
    # position sizes carries information. Against 200 permutations of each
    # session's trade order, using this detector's own code, the real order fired
    # LESS than chance (42 vs 49.7, ratio 0.85, p = 0.880), and its gate selects
    # at the rate three random numbers are increasing (16.9% vs 16.7%). 37 of 42
    # alerts named an instrument absent from the three trades they showed, and
    # only 7 of 42 contained the trade that raised them. Dangerous sizing is NOT
    # retired: martingale_behaviour and post_loss_recovery_bet keep the claim
    # with the current trade as the subject. See docs/patterns/10-size_escalation/.
    DetectorSpec("rapid_reentry", "_detect_rapid_reentry",
                 "2.0.0", "emotional", "analytics", "exit", 0),
    # `panic_exit` RETIRED 2026-08-29. Short holds won at 38.3% against 39.8%
    # for longer ones, so it selected the losing half of an ordinary habit -
    # outcome, not behaviour. See docs/patterns/14-panic_exit/.
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
    # RETIRED 2026-08-28 - `direction_instability` (which had absorbed v1's
    # rapid_flip and options_direction_confusion). It could not separate an
    # emotional reversal from a change of view: its only discriminator was a
    # 10-minute clock, and the clock sorted backwards. Flagged flips won 56.2%
    # for +Rs 276 against 41.7% and -Rs 73 for the same transition beyond the
    # window, the position being exited was -Rs 284 at 31% win, and
    # rest-of-session AFTER a flip was +Rs 953 against -Rs 112 matched
    # (p = 0.095) where the premise predicts deterioration. Fast reversals on
    # this book are loss-cutting. revenge_trade already fired on 10 of the 18.
    # NOT retired permanently: Level 1 (same-symbol LONG<->SHORT) was untestable
    # here - 911 LONG against 1 SHORT - and would be live for a futures trader.
    # See docs/patterns/11-direction_instability/.
    # `excess_exposure` RETIRED 2026-09-01. There is no universal exposure
    # threshold any more and none replaced it: single-position exposure is a
    # breach of the trader's OWN declared limit, which `constitution_violation`'s
    # max_trade_risk rule already owns with the same quantity and its own dedup
    # key. See docs/patterns/28-position-monitor/.
    DetectorSpec("session_meltdown", "_detect_session_meltdown",
                 "1.0.0", "risk", "alerting", "exit", 4, guardian_eligible=True,
                 uses_constitution=True,
                 consumes=("session", "completed_trade", "thresholds")),
    # 2.0.0: one threshold for every context (Pattern #7 review, 2026-08-27).
    # The expiry and pre-close thresholds could not fire on the reference book
    # and the market-open threshold of 2 produced 39% of all firings on its own.
    DetectorSpec("fomo_entry", "_detect_fomo_entry",
                 "2.0.0", "emotional", "alerting", "exit", 1),
    DetectorSpec("no_stoploss", "_detect_no_stoploss",
                 "1.0.0", "risk", "alerting", "exit", 2,
                 consumes=("completed_trade", "exit_order_types", "thresholds")),
    # `early_exit` RETIRED 2026-08-30. The disposition-effect measure was
    # right; computing it over one session was not (shuffle null p = 0.610
    # at 3-5 samples a side). baseline_service still computes it over the
    # full history. See docs/patterns/18-early_exit/.
    # `winning_streak_overconfidence` RETIRED 2026-08-30. The concept is real
    # literature; the conditioning variable had the wrong sign on this book.
    # Sizing up was LESS likely after a 3+ win run (21.4% vs 30.4%), monotone
    # across run lengths, rho = -0.076. The trader sizes up after LOSSES
    # instead, which `martingale_behaviour` covers. Shuffle null p = 0.582.
    # Its `uses_baseline=True` was false - it read no baseline.
    # See docs/patterns/19-winning_streak_overconfidence/.
    # `options_premium_avg_down` RETIRED 2026-08-30. It was not an average-down:
    # 0 of 44 firings involved an open position, because its "prior losers" were
    # CLOSED rounds on the same UNDERLYING, not the same contract. Its copy
    # described `adding_to_adverse_position`, which already covers option
    # premium averaging on 100% of its 64 firings. Real subject was re-entry
    # after a loss - `same_symbol_obsession` saw 70%, `revenge_trade` 48%.
    # See docs/patterns/20-options_premium_avg_down/.
    # 3.0.0 (2026-08-27): Pattern #8 stopped being a behaviour detector and
    # became a real-time RISK-STATE detector. The alerting half moved onto the
    # tick path (`services/live_risk_state.py`), which raises a band crossing
    # while the position is still open and something can be done about it. What
    # remains HERE runs on a closed position, so it is analytics: it records what
    # the position finished at and feeds the daily report, and never alerts.
    #
    # `nature="risk"` was always right - a large premium loss is a market
    # outcome, not a behavioural failure - and the disposition now agrees with it.
    DetectorSpec("premium_loss_event", "_detect_premium_loss_event",
                 "3.0.0", "risk", "analytics", "exit", 0),
    # RETIRED 2026-08-27 - `expiry_day_overtrading`. It never withheld: of the
    # 55 positions it could judge in the 189-session book it fired on 55 and
    # stayed silent on 0, because `today_lots` summed CONTRACTS against a
    # threshold of 10 and a NIFTY lot is 75 - the only reachable clause was
    # unconditionally true. Both trader-facing sentences were unsourced and
    # measured false: the claimed ">85% loss rate in the last 2 hours of expiry"
    # is 53.8% at 14:00+ against a book-wide ~60%, and "each additional trade
    # reduces your edge" measured r = +0.260 (p = 0.056), the opposite sign. The
    # reversal repeats at day level (r = +0.107) and expiry-active sessions are
    # this trader's better sessions (51.1% green against 38.9%). Fixing the units
    # would have moved the pass rate 100% -> 58% without creating a finding, so
    # they were not fixed. Expiry-day-ness stays as a MODIFIER inside
    # premium_loss_event, no_stoploss and fomo_entry, which is where it works.
    # See docs/patterns/09-expiry_day_overtrading/.
    # `opening_5min_trap` RETIRED 2026-08-30. The opening window was not a worse
    # place to trade: win 39.4% inside 09:15-09:25 against 39.5% for the rest of
    # the day, and BETTER on money (p = 0.274). It reached its finding by
    # discarding 42% of window entries for having made money - selection on
    # outcome, the shape that retired `panic_exit`. Not retired permanently:
    # spreads are real, but testing that needs per-fill spread data we do not
    # store. See docs/patterns/21-session_windows/.
    DetectorSpec("end_of_session_mis_panic", "_detect_end_of_session_mis_panic",
                 "2.0.0", "emotional", "alerting", "exit", 1),
    DetectorSpec("post_loss_recovery_bet", "_detect_post_loss_recovery_bet",
                 "1.1.0", "risk", "alerting", "exit", 2),
    # RETIRED 2026-08-27 - `profit_giveaway`. A drawdown from the session
    # high-water mark is arithmetic, not behaviour: the peak IS the maximum of
    # the running curve, so 181 of 189 sessions have one. Shuffling each
    # session's trades - same trades, same day, different order - produced MORE
    # firings than the real order (49 observed against 56.3 expected, ratio
    # 0.87) and an identical amount of money given back (Rs 624,839 against
    # Rs 616,891, ratio 1.01), so the trader's ordering contributed nothing.
    # Every mechanism it was premised on failed too: house money predicts risk
    # RISING after a peak and this trader's fell in 54% of sessions
    # (Rs 7,315 -> Rs 6,737 median); the break-even effect predicts that
    # crossing zero changes behaviour and it measured 0.6 SE against a ~1.4
    # floor. The median giveback puts 77% of its loss in one trade, which is
    # what a losing trade is.
    #
    # The measurement is kept and needs no detector: peak_pnl,
    # drawdown_from_peak and max_drawdown stay in session_facts with eleven
    # readers, and reports compute the giveback from the trades directly. If it
    # is ever to interrupt a session again it must be against a give-back stop
    # the trader DECLARES, which does not exist yet.
    # See docs/patterns/06-profit_giveaway/.
    # `cooldown_violation` RETIRED 2026-08-29. Its precondition never occurred
    # on the live path - no Celery task creates a Cooldown - and the behaviour
    # is fully covered by constitution_violation's `cooldown` rule, which uses
    # the trader's OWN declared value at danger (181 events against this
    # detector's 0). See docs/patterns/15-cooldown_violation/.
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
    # `time_of_day_bias` RETIRED 2026-09-01. The learned "danger hours" it
    # alerted on do not survive into a second time period - not one hour
    # flagged in the first half of the reference book is flagged in the
    # second, and chance reproduces the flagged count 31% of the time.
    # Insufficient evidence, NOT proof that time-of-day effects do not exist;
    # the nightly learning and its storage are kept untouched.
    # See docs/patterns/25-27-performance-trio/.
    # Phase 7: performance analytics (info-only, feed the Strategy driver)
    # trigger was "session" until 2026-09-03, which the engine ignored: it
    # skips `entry` and runs everything else, so this has ALWAYS run on the
    # exit path. The declaration now says so, and `scope` carries the fact it
    # was really trying to express — the subject is the session, not the trade.
    # No behaviour change; this detector runs exactly where it always did.
    DetectorSpec("win_rate_collapse", "_detect_win_rate_collapse",
                 "1.0.0", "performance", "analytics", "exit", 0,
                 uses_baseline=True, scope="session"),
    # `strategy_breakdown` RETIRED 2026-09-02. It required a win-rate collapse
    # AND a profit-factor collapse together, and on the reference book the
    # profit-factor half NEVER bound: 4 firings, the identical set to
    # `win_rate_collapse`, ZERO unique. A session that wins 11% of its trades
    # almost always has a wrecked profit factor, so the second condition
    # restated the first. `win_rate_collapse` keeps the subject and both
    # baselines.
)

# Event types emitted by a detector under a different name than its spec
# (version lookup only — never iterated).
ALIASES = {
    "daily_overtrading": "2.0.0",
    # `death_spiral` RETIRED 2026-09-02. It was a summary of alerts the trader
    # had already received, not a state: set-identical to a two-detector
    # conjunction, 69% of firings preceded by a danger alert already delivered,
    # 38.9% of sessions with one declared rule, and order-independent at the
    # only tiers that ever fired. Its display name stays in the frontend's
    # `formatPatternName` so stored rows still render.
    # Position-monitor (entry-time) patterns - Phase 6
    #
    # `overexposure` RETIRED 2026-09-02. Not on evidence about the behaviour -
    # the alias was already DEAD. `_overexposure_task` emits
    # pattern_type="constitution_violation" with rule="max_trade_risk", gates
    # on the trader's DECLARED limit and abstains when the capital requirement
    # is unavailable. Nothing had emitted "overexposure" since the exposure
    # hierarchy shipped (0602aa8); this map was the last thing keeping the name
    # in the vocabulary.
    #
    # `portfolio_concentration` RETIRED 2026-09-01 - it measured how few
    # positions were open, not concentration. A two-position book has a
    # 50% floor against a 40% cut and could never withhold.
    #
    # `holding_loser` RETIRED 2026-09-02 - a snapshot plus a stopwatch. Its
    # predicate never observed the loss CHANGING, and the winner/loser hold
    # substitute failed the persistence test: ratio 0.62 in the first half of
    # the book against 2.54 in the second, intraday 1.04 at shuffle p = 0.343,
    # median 0.98. Not replaced.
    # Housekeeping nudge from maintenance_tasks, not a behaviour detector — but
    # it IS written to risk_alerts.pattern_type, so it is part of the vocabulary
    # and the contract test found it missing from this map.
    "capital_mismatch": "1.0.0",
}

# Fast lookups
#: The dispatch paths that exist. A spec declaring anything else is a bug the
#: engine cannot act on, and until 2026-09-03 it was absorbed silently — the
#: exit loop skips `entry` and runs the rest, so an unrecognised trigger meant
#: "run on exit" with nobody told. Validated at import so it cannot recur.
TRIGGERS = frozenset({"entry", "exit"})
#: Subjects. Descriptive; see DetectorSpec.scope.
SCOPES = frozenset({"trade", "session"})

for _spec in REGISTRY:
    if _spec.trigger not in TRIGGERS:
        raise ValueError(
            f"{_spec.name}: trigger={_spec.trigger!r} is not a dispatch path. "
            f"Expected one of {sorted(TRIGGERS)}. If you meant 'this detector "
            f"judges the whole session', that is scope='session'."
        )
    if _spec.scope not in SCOPES:
        raise ValueError(
            f"{_spec.name}: scope={_spec.scope!r} — expected one of {sorted(SCOPES)}."
        )
    # ANALYTICS IS EVIDENCE, NOT A CHANNEL.
    #
    # `disposition="analytics"` means the detector's output is a row — journal,
    # daily report, strategy view — not an interruption. The engine enforces
    # that at the alert gate; this enforces it at the DECLARATION, so a spec
    # cannot claim a notification channel it may never use and read as though
    # somebody had decided it should reach a trader.
    #
    # Until 2026-09-03 the rule held only because all three analytics detectors
    # happened to hardcode severity="info". That is a coincidence, not a
    # contract.
    if _spec.disposition == "analytics":
        if _spec.notification_level != 0:
            raise ValueError(
                f"{_spec.name}: disposition=analytics with "
                f"notification_level={_spec.notification_level}. Analytics is "
                f"evidence and never notifies; use disposition='alerting' if "
                f"this detector is meant to reach a trader."
            )
        if _spec.guardian_eligible:
            raise ValueError(
                f"{_spec.name}: disposition=analytics cannot be "
                f"guardian_eligible — the guardian channel is the loudest one "
                f"there is."
            )
del _spec

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
    # Copy rewritten 2026-08-27, Pattern #7. It used to say several instruments
    # at once "is usually chasing movement rather than acting on a view" - a
    # claim about intent that the permutation null contradicts (ratio 0.94) and
    # that the win rate on flagged trades points against (45.9% vs a 39.9%
    # baseline). It now describes what was counted.
    "fomo_entry": PatternCopy(
        "Several underlyings at once",
        "Distinct underlyings entered inside a short window, counting strikes of the same "
        "underlying as one.",
        "Breadth is worth seeing on its own. It is not evidence about why the trades were taken.",
    ),

    # ── Risk / sizing ────────────────────────────────────────────────────
    # `size_escalation` copy removed 2026-08-27 with the detector. It promised
    # "on the same underlying", which described a branch used in 5 of 42 firings.
    "martingale_behaviour": PatternCopy(
        "Averaging down",
        "Position size increasing after consecutive losses on the same instrument.",
        "Each step raises the total at risk in the session, not just the cost of this trade.",
    ),
    # `excess_exposure` copy removed 2026-09-01 with the detector. Its display
    # name stays in AlertContext.formatPatternName so stored rows still render.
    # Copy rewritten 2026-08-27... see Pattern 12 review, 2026-08-29.
    #
    # It read "No stop-loss on record" / "Whether a stop-loss order was on the
    # position when it was exited." Neither was knowable: the detector reads the
    # EXIT FILL's order type, never the resting order book, so it could not say
    # whether a stop was ON the position. The copy asserted the absence of
    # something the engine had not looked at.
    #
    # What it CAN say is how far a loss was allowed to run before the position
    # was closed. That is what the copy now says.
    "no_stoploss": PatternCopy(
        "Large loss held to the exit",
        "How far a losing position was allowed to run before it was closed.",
        "An exit decided before a position moves is a different decision from one decided while "
        "it is moving.",
    ),
    "adding_to_adverse_position": PatternCopy(
        "Added to a losing position",
        "Additions made to a position that had already moved against you, and how far "
        "against it had moved each time.",
        "The position that is already wrong is the one being made bigger. Each addition "
        "lowers the price at which it has to come back, and raises what it costs if it "
        "does not.",
    ),
    # `options_premium_avg_down` copy removed 2026-08-30 with the detector. It
    # is worth recording WHAT it said, because the copy is why the detector
    # survived four earlier audits: "Adding to a losing option / Additional
    # quantity on an option position already down on premium." No part of that
    # was true of the code, and all of it is true of
    # `adding_to_adverse_position` below.
    # Copy rewritten 2026-08-27, Pattern #8. "Premium destruction" and "the
    # position needs a move it was never sized for" both read as a verdict on the
    # trade. This is a risk STATE - how much of the premium is gone - and the
    # evidence says nothing about how the trade was taken.
    "premium_loss_event": PatternCopy(
        "Premium lost",
        "Percentage of the premium paid that has been lost on a long option.",
        "A long option's whole downside is the premium. This is how much of it is gone.",
    ),

    # ── Discipline / pace ────────────────────────────────────────────────
    "overtrading_burst": PatternCopy(
        "Burst of trades",
        "Positions opened inside a 30-minute window, counting a multi-leg structure as one.",
        "Trades taken minutes apart share one state of mind rather than separate assessments.",
    ),
    # `expiry_day_overtrading` copy removed 2026-08-27 with the detector. The
    # copy here was never the problem - it carried no statistic. The two invented
    # ones lived in the detector's `message`, which this contract does not cover.
    # `opening_5min_trap` copy removed 2026-08-30 with the detector. Its
    # explanation - "Spreads are widest and option premiums least settled while
    # the market is still finding its level" - was a mechanism the detector
    # never measured, and the outcome it did measure was not worse inside that
    # window.
    "end_of_session_mis_panic": PatternCopy(
        "Late intraday entries",
        "MIS entries in the run-up to auto square-off.",
        "There is very little time for the position to work, and the exit is not yours to choose.",
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
    # `direction_instability` copy removed 2026-08-28 with the detector. Its
    # explanation - "reversing repeatedly usually tracks the price rather than a
    # view about it" - is the claim this trader's book contradicted.

    # ── Performance (analytics) ──────────────────────────────────────────
    "win_rate_collapse": PatternCopy(
        "Win rate below baseline",
        "Today's win rate against your own longer-run baseline.",
        "A sharp drop against your own history is a change in conditions or in execution — worth "
        "knowing which.",
    ),
    # `time_of_day_bias` copy removed 2026-09-01 with the detector. Its
    # display name stays in AlertContext.formatPatternName so stored rows
    # still render.
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
    # `overexposure`, `portfolio_concentration` and `holding_loser` copy removed
    # with their aliases (2026-09-01 / 2026-09-02). Their display names stay in
    # AlertContext.formatPatternName so stored rows still render.
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
