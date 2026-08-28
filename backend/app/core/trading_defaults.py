"""
Trading Defaults Module — cold-start thresholds

READ THIS BEFORE TRUSTING A NUMBER IN THIS FILE.

This docstring used to claim every threshold was research-derived, with "no
arbitrary guesses". That was not true, and the claim did more damage than the
numbers: it told every reader the values were settled, so nobody questioned
them. An audit of all 109 constants found roughly 14 with a source attached
and roughly 95 without.

The distribution is not random. Where a pair exists, the CAUTION value is
usually sourced and the DANGER value beside it is not:

    daily_trade_limit        7   SEBI FY2023 (>6/day → 94% loss probability)
    daily_trade_danger      12   no source
    consecutive_loss_caution 3   tilt onset, poker + trading research
    consecutive_loss_danger  5   no source
    revenge_window_caution  20   Coates & Herbert, Cambridge 2008 (cortisol)
    revenge_window_danger    5   no source

Danger is the level that interrupts the trader hardest, and it is the
unsourced half. Several constants are openly provisional in their own comments
("starting points, not spec constants") and have never been revisited.

So: some values below ARE research-backed and say so in a comment naming the
study. Everything else is a judgement someone made once. Both kinds are marked.
An unmarked number is unsourced — treat it as a hypothesis, not a finding.

Sources that ARE used, where cited: SEBI FY2022/23/24 retail F&O studies; NSE
microstructure data; behavioural finance (Kahneman, Shefrin, Coates); cortisol
research applied to financial decision-making.

3-tier hierarchy:
  Tier 1: User-declared values in UserProfile (only 6 inputs, and only when
          they are TIGHTER than the current threshold)
  Tier 2: The cold-start defaults below, blended continuously toward the
          trader's own observed baseline as evidence accumulates. The blend
          currently covers 4 keys out of 109 — extending it is the open work.
  Tier 3: Universal floors (prevent absurd configs)

None of the pattern thresholds are surfaced in Settings UI. Users configure
only: capital, max_position_size, daily_loss_limit, daily_trade_limit,
sl_percent, cooldown_after_loss. That is deliberate — manual-input adoption on
this product is zero — and it is exactly why the defaults have to be either
sourced or self-relative. Nobody is going to correct them by hand.
"""

from typing import Optional, Dict, Any


# ---------------------------------------------------------------------------
# Tier 2: Research-backed cold-start defaults
#
# Every value documented with its research basis.
# Do NOT change these casually — they reflect Indian F&O market study.
# ---------------------------------------------------------------------------
COLD_START_DEFAULTS: Dict[str, Any] = {

    # ── Session / overtrading ─────────────────────────────────────────────
    # SEBI FY2023: traders with >6 trades/day had 94% loss probability.
    # >12/day approached 99%. Profitable traders averaged 2-4/day.
    'daily_trade_limit':                7,    # caution above this (session total)
    'daily_trade_danger':               12,   # danger above this

    # Burst: 5+ in 30 min = emotional escalation, 8+ = spiral
    'burst_trades_per_30min_caution':   5,
    'burst_trades_per_30min_danger':    8,

    # burst_trades_per_15min removed 2026-08-23. Its comment claimed "Used by
    # RiskDetector", which was archived; a check of every reader found none in
    # any detector - only two API endpoints displaying it. Both live burst
    # detectors use burst_trades_per_30min_caution/_danger above, so this
    # described a window nothing measured. The displays were repointed there.

    # ── Consecutive losses ────────────────────────────────────────────────
    # Tilt state begins after 3 losses (confirmed in poker+trading research).
    # After 5, near-universal emotional impairment.
    'consecutive_loss_caution':         3,
    'consecutive_loss_danger':          5,

    # ── Revenge trade ─────────────────────────────────────────────────────
    # Cortisol stays elevated for 20-35 min post-loss (Coates & Herbert, Cambridge 2008).
    # SEBI data: 73% of trades within 15 min of a loss are also losing trades.
    # The "loss recovery" impulse peaks at 3-8 min (immediate = danger).
    'revenge_window_caution_min':       20,   # entry within 20 min of loss = caution
    # Unified revenge window used by RiskDetector + BehavioralEvaluator.
    # Overridden by profile.cooldown_after_loss in get_thresholds().
    'revenge_window_min':               10,   # default: 10-min window
    # A rupee amount cannot be universal: Rs 500 is 1% of Rs 50,000 and 0.1% of
    # Rs 5,00,000. The RATIO is the thing that generalises, so when capital is
    # known this is derived from it (threshold_resolution, rung 4) and the
    # absolute value below is only the no-capital fallback. The percentage is
    # calibrated so a Rs 50,000 account resolves to the same 500 it had before.

    # ── Position sizing / excess exposure ────────────────────────────────
    # Kelly criterion for 45% win rate, 1.5:1 R:R → ~13% optimal, half-Kelly = 6%.
    # SEBI: profitable traders averaged 4-6% per trade; loss-makers averaged 20-50%.
    'max_position_pct_caution':         5.0,  # 5% capital-at-risk = caution
    'max_position_pct_danger':          10.0, # 10% capital-at-risk = danger

    # ── Session meltdown ─────────────────────────────────────────────────
    # Prospect theory: "break-even effect" / risky recovery seeking starts at ~50% loss.
    # Rational decision-making measurably declines after 40% of daily limit lost.
    # Professional trading desks: intervention at 50%, hard stop at 80%.
    'meltdown_caution_pct':             0.40, # 40% of daily loss limit = caution
    'meltdown_danger_pct':              0.75, # 75% of daily loss limit = danger

    # ── Panic exit ────────────────────────────────────────────────────────
    # 5 min is minimum time to assess an options position in volatile market.
    # 2 min (old) falsely flagged legitimate SL hits as panic.
    'panic_exit_min':                   5,    # hold < 5 min at loss = caution

    # ── Rapid re-entry (same symbol) ─────────────────────────────────────
    # Options pricing stabilisation after a move takes ~5 min.
    # Re-entering in < 5 min is almost never analytical — it's emotional.
    'rapid_reentry_min':                5,

    # rapid_flip_min and direction_confusion_window_min DELETED 2026-08-28 with
    # `direction_instability`. The 10-minute line was the detector's only
    # discriminator and it sorted backwards - trades inside it did BETTER than
    # the same transition outside it. See docs/patterns/11-direction_instability/.

    # ── Martingale / averaging down ───────────────────────────────────────
    # "Averaging down" is culturally normalised in India ("lower my average cost").
    # SEBI: traders who averaged down on losing options lost 3× more than those who didn't.
    # Danger starts at 1.5× (initial escalation), not 1.8× (too late).
    'martingale_caution_multiplier':    1.5,  # 1.5× size on consecutive losses = caution
    'martingale_danger_multiplier':     2.0,  # 2.0× (full double) = danger
    'martingale_min_losses':            2,    # at least 2 consecutive losses (not 3)

    # size_escalation_pct DELETED 2026-08-27 with `size_escalation`. It was never
    # in threshold_registry, so it had no Kind and no provenance - only the
    # comment above, which described +30% PER STEP compounding to 2.2x while the
    # code computed a single first-to-third ratio (30% => 1.3x). It decided
    # little either way: 0% gave 51 firings, 30% gave 42.

    # ── No stop-loss (long-held option loser) ─────────────────────────────
    # Primary gate is now exit_order_type (SL/SL-M = skip). Hold time is only a
    # secondary guard to exclude micro-scalps (< 5 min) where no formal SL is normal.
    'no_stoploss_hold_min':             5,    # minimum 5 min hold (exclude ultra-fast scalps)
    'no_stoploss_loss_pct_caution':     25,   # > 25% premium loss = caution
    'no_stoploss_loss_pct_danger':      50,   # > 50% premium loss = danger
    'no_stoploss_expiry_hold_min':      5,    # expiry day: same 5 min minimum
    'no_stoploss_expiry_loss_pct':      25,   # expiry day: same 25% loss threshold

    # -- Breadth across underlyings (fomo_entry) ---------------------------
    # Distinct UNDERLYINGS in a rolling window - strikes of the same underlying
    # count once, because two NIFTY strikes are a structure and not a scatter.
    #
    # BOTH NUMBERS BELOW ARE UNSOURCED. The Pattern #7 review (2026-08-27)
    # established which of this detector's constants were wrong; it did not
    # establish what the right ones are, so these two were deliberately left
    # untouched. Treat them as hypotheses, in the sense this file's header
    # describes: an unmarked number is a judgement someone made once.
    'fomo_window_min':                  30,   # rolling window. Unsourced; a round number.
    'fomo_symbols_in_window':           3,    # distinct underlyings. Unsourced.
    'fomo_open_window_min':             30,   # labels the opening stretch. Reported, never thresholded.
    'fomo_close_window_min':            30,   # labels the closing stretch. Reported, never thresholded.
    #
    # DELETED 2026-08-27 with the Pattern #7 review. All three are now read by
    # nothing, and every context uses fomo_symbols_in_window instead:
    #
    #   fomo_symbols_at_open     (2) - produced 29 of the detector's 74 firings,
    #        39% of all output, at 3.6:1 against the general threshold, on a
    #        state (two underlyings inside half an hour) occurring in 20% of all
    #        entries. It sat in safety_bounds.MANDATORY_REVIEW precisely for
    #        this; that review is now complete.
    #   fomo_symbols_at_close    (3) - UNREACHABLE. Across 50 pre-close entries
    #        the maximum breadth ever reached was 2. Its own comment asked for
    #        exactly this measurement.
    #   fomo_expiry_day_symbols  (4) - UNREACHABLE. Across 142 expiry-day
    #        entries the maximum was 3, once.
    #
    # No replacement was invented: a threshold above the highest value its
    # branch has ever produced is not conservative, it is absent.

    # ── Expiry day overtrading ────────────────────────────────────────────
    # On the instrument's own expiry date: heightened FOMO, 0DTE herding, vol spikes.
    # expiry_overtrading_{caution_count, danger_count, caution_lots} DELETED
    # 2026-08-27 with `expiry_day_overtrading`. Unlike the profit_giveaway keys
    # above these hold nothing up: they were not in _CAPITAL_RATIOS, had no
    # second reader, and their three registry metrics were produced by no code,
    # so the ladder always fell through to these literals anyway. The lots value
    # was compared against a sum of CONTRACTS, which made it unconditionally
    # true. See docs/patterns/09-expiry_day_overtrading/.
    # expiry_overtrading_{caution,danger}_mul removed 2026-08-13: declared as
    # multiples of the personal baseline, read by nothing. The detector uses the
    # _count and _lots thresholds above.

    # ── Opening 10-minute trap ────────────────────────────────────────────
    # 09:15-09:25 IST: widest spreads, most distorted option pricing of the day.
    # NSE data: 78% of retail opening-10-min derivative trades are unprofitable.
    'opening_trap_window_end_min':      10,   # minutes after 09:15 that the trap window closes (→ 09:25)
    'opening_trap_quick_exit_min':      15,   # hold ≤ this = "quick reactive exit" trigger
    'opening_trap_large_loss_pct':      30,   # loss ≥ this % of premium = "large loss" trigger

    # ── End-of-session MIS panic ──────────────────────────────────────────
    # MIS trades entered after 15:00 IST face auto-square-off at ~15:20.
    # 2 such trades = caution (pattern emerging), 3+ = danger (clear panic spiral).
    'end_session_mis_caution_count':     2,
    'end_session_mis_danger_count':      3,

    # ── Post-loss single large recovery bet ───────────────────────────────
    # After 2+ consecutive losses, a position 2× larger than recent average.
    # Different from martingale (progressive) — this is one outsized "make it back" bet.
    'recovery_bet_caution_mul':          2.0,  # 2× recent average size = caution
    'recovery_bet_danger_mul':           3.0,  # 3× recent average size = danger

    # ── Profit giveaway (peak P&L erosion) ────────────────────────────────
    # SEBI/NSE data: 38% of retail intraday traders with a profitable session give back
    # >50% of peak gains in a single subsequent trade. Most common at end of day.
    # Pattern: built significant profit → one trade erodes a large % of it.
    # Fires exactly once per threshold crossing (not on every subsequent loss).
    # Same reasoning as revenge_min_loss_inr: a rupee floor cannot be universal.
    # Derived from capital when known (threshold_resolution, rung 4); the
    # absolute values below are the no-capital fallback. Percentages calibrated
    # so a Rs 50,000 account resolves to the previous 1500 / 500.
    # RETAINED after profit_giveaway was retired (2026-08-27). These four keys
    # have NO detector reader any more, and they are deliberately kept:
    # `_CAPITAL_RATIOS` in threshold_resolution.py contains only this pair, so
    # deleting them empties rung 4 of the ladder - the mechanism that turns an
    # absolute rupee floor into a ratio of the trader's capital - and removes its
    # only remaining test vehicle (tests/test_threshold_resolution.py defines
    # CAPITAL_KEYS as exactly these two and says the property under test is the
    # conversion, not the key; the third, revenge_min_loss_inr, went in August).
    # They are also the two values a DECLARED give-back stop would need.
    'profit_giveaway_min_peak_pct_capital':    3.0,
    'profit_giveaway_min_erosion_pct_capital': 1.0,
    'profit_giveaway_min_peak':          1500,   # was 1000, briefly 5000. 5000 silenced it completely — 17 firings to zero against nine days of the behaviour in the same tradebook, which is worse than the noise it replaced. The self-relative erosion floor is the real fix; this only needs to exclude the trivial. Originally fired on days that ENDED GREEN. A ₹1,348 peak is one tick on a ₹15,000 option lot, not a session built and given back. Seventeen firings across 61 real sessions, the most common alert in the product, almost all on profitable days.
    'profit_giveaway_min_erosion':        500, # minimum absolute erosion to avoid noise (₹500)
    # profit_giveaway_caution_pct (0.50) and profit_giveaway_danger_pct (0.70)
    # both DELETED 2026-08-27 with the detector. They were purely severity tiers
    # - unsourced, sitting at no break in the distribution, and measured at
    # 1.1 SE against a ~1.4 floor - so unlike the four keys above they hold
    # nothing up.

    # ── Monthly vs weekly expiry: no_stoploss tighter thresholds ─────────
    # Monthly expiry: theta at maximum all day. Primary gate = exit order type;
    # hold/loss thresholds here are secondary guards only.
    'no_stoploss_monthly_hold_min':      5,
    'no_stoploss_monthly_loss_pct':      20,

    # ── Win streak overconfidence ─────────────────────────────────────────
    # "Hot hand fallacy": after 3 wins, retail traders increase size 40-80%.
    # Streak check: last N session trades (any instrument) all won.
    # Size check: same underlying only — cross-instrument lot sizes are not comparable.
    # No same-underlying baseline → no alert (can't assess size without history).
    'overconfidence_win_streak_caution':    3,   # 3 wins → check size (same underlying)
    'overconfidence_win_streak_danger':     5,   # 5 wins → check size (same underlying, higher threshold)
    'overconfidence_size_mul_caution':      1.3, # same-underlying size ≥ 1.3× session avg = caution
    'overconfidence_size_mul_danger':       2.0, # same-underlying size ≥ 2.0× session avg = danger

    # ── Early exit (disposition effect / cutting winners) ─────────────────
    # SEBI FY2022: retail sold winning positions 2.7× faster than losing positions.
    # Disposition effect is 2-3× stronger in Indian retail vs institutional.
    'early_exit_ratio':                 0.40, # winner hold < 40% of loser hold
    'early_exit_winner_max_min':        60,   # avg winner hold must be < 60 min absolute (covers classic 25-40 min winner / 2-4 hr loser disposition pattern)
    'early_exit_min_samples':           3,    # need 3+ winners AND 3+ losers for signal

    # ── Options behavioral patterns ───────────────────────────────────────
    # Direction confusion: CE→PE flip on same underlying within 10 min.
    # Legitimate directional change requires analysis — < 10 min is confusion, not analysis.

    # Premium averaging down: re-entry on same options underlying after ≥20% loss.
    # SEBI data: traders who averaged down on losing options lost 3× more.
    # 20% floor to exclude scratch trades that hit SL cleanly.
    'premium_avg_down_loss_pct':        20,   # prior options position must have lost ≥20%

    # iv_crush_proxy_{hold_min,loss_pct} removed 2026-08-13: the iv_crush_behavior
    # detector was merged into premium_loss_event, and these were left behind
    # reading to nothing. premium_loss_{caution,danger,critical}_pct replace them.

    # confidence_alert_gate lived here until 2026-08-24, under a header about
    # signal points whose four constants had already gone with the revenge
    # rewrite. Its comment claimed alerts below 50 confidence were recorded but
    # not shown; that had exactly one reader for its whole life - revenge_trade's
    # deleted points score - and zero when it was removed. Keeping a constant
    # that describes behaviour the engine does not have is worse than the gap.
    # See docs/contracts/confidence_alert_gate_CLOSED.md. Global confidence
    # suppression remains DEFERRED and is deliberately NOT reintroduced here.

    # ── Premium loss event (merged iv_crush + premium_destruction) ───────
    # Levels are % of premium lost. Expiry day shifts all levels up — deep
    # OTM near expiry loses 40% routinely without any behavioral failure.
    'premium_loss_caution_pct':        40,
    'premium_loss_danger_pct':         60,
    'premium_loss_critical_pct':       80,
    # UNSOURCED, both of them, and left unchanged by the Pattern #8 review
    # (2026-08-27) which found nothing wrong with the bands above and no basis
    # for moving these two either.
    #
    # The expiry shift's DIRECTION is well argued - a deep OTM option near expiry
    # loses 40% of its premium routinely, so the same percentage means less - and
    # it engaged on 12 of the detector's 48 firings in the reference book. The
    # MAGNITUDE of 15pp has no stated derivation.
    'premium_loss_expiry_shift_pct':   15,   # UNSOURCED. Direction argued, size not.
    # Context flag only: it sets `fast_collapse` in the evidence and never
    # touches severity, so the cost of it being wrong is one wrong word in a
    # message. Engaged on 5 of 48.
    'premium_loss_fast_hold_min':      30,   # UNSOURCED. Never affects severity.

    # ── Same symbol obsession (doc 4 P27) ────────────────────────────────
    'obsession_min_losses':             3,   # 3+ losses on one underlying today
    # obsession_min_reentries was here until 2026-08-24. It could never
    # bind: losses is a subset of the attempts, so losses >= 3 implies
    # attempts >= 3 implies reentries >= 2. Minimum attempts observed
    # across the whole reference book: 3.

    # ── Time-of-day bias (doc 4 P28) ─────────────────────────────────────
    'tod_bias_min_sessions':           30,   # need 30 sessions of history

    # ── Behavioral scores — REMOVED 2026-08-13 ───────────────────────────
    # score_halflife_min, the four score_sev_mult_*, the three score_band_*
    # and headline_other_weight went with the driver scores they fed.
    # docs/GLOBALS_DERIVATION.md measured all three groups against a year of
    # real trades: the half-life outlived the signal ~3×, the severity
    # multiplier had the wrong sign, and no band was ever rendered.

    # ── Death spiral (Engine v2 Phase 5, master §1D.2 FINAL) ─────────────
    # Levels are STATE-based, never raw counts:
    #   warning  = behavior deteriorating (2+ domains active)
    #   danger   = + capital at meaningful risk (risk domain has danger+)
    #   critical = 3+ independent domains + CONTINUED ESCALATION (trader still
    #              opening trades after the discipline/risk breach) within the
    #              compression window
    'spiral_domain_min_severity':      'danger',  # a domain "deteriorates" on danger+
    'spiral_warning_domains':          2,
    'spiral_critical_domains':         3,
    'spiral_window_min':               180,   # time compression: domains must fire within 3h
    'guardian_monthly_budget':         3,     # hard cap on guardian sends per month (§1B.8)

    # ── Baseline confidence targets (Engine v2 Phase 3, master §1B.4) ────
    # Confidence = min(1, n / target). Session-level metrics mature with
    # SESSIONS; trade-level with TRADES (per-metric confidence, Q23).
    'baseline_target_sessions':         30,
    'baseline_target_trades':           100,

    # ── Constitution violation ladder (Engine v2 Phase 2, master §1C.4) ──
    # Level 1 "approaching" at 80% of a rule → caution
    # Level 2 "breached"   at 100%           → danger
    # Level 3 "severe"     at 120%           → critical (guardian-eligible)
    'constitution_approaching_pct':     0.80,
    'constitution_severe_pct':          1.20,

    # ── Alert consolidation (P-02, formerly inline in trade_tasks) ───────
    'alert_session_hard_cap':           8,   # max notified alerts per session (fatigue guard)
    'alert_bucket_minutes':             5,   # same pattern re-notification bucket

    # entry_batch_window_sec removed 2026-08-13: the entry-time coalescing it
    # configured was never implemented, so the constant described behaviour the
    # code does not have. Reinstate it with the feature, not before.

    # ── Notification staleness (Engine v2 Phase 0, master Q12) ───────────
    # Push/WhatsApp only fire for alerts whose triggering trade is recent.
    # Bulk-synced historical trades (detected_at = trade time, hours old)
    # produce analytics/in-app rows only — a 5:05pm push about a 2:20pm trade
    # makes users think the app is broken. Past-session trades are always
    # older than this window, so they are auto-suppressed too.
    'alert_stale_push_min':            30,   # no push if trade older than 30 min

    # premium_destruction_pct removed 2026-08-13: the premium_destruction
    # detector was merged into premium_loss_event and this threshold was left
    # behind, read by nothing. premium_loss_danger_pct (60) is its successor.
}


# ---------------------------------------------------------------------------
# Tier 3: Universal floors
# Never fire alerts below these, regardless of user settings.
# ---------------------------------------------------------------------------
# Removed 2026-08-24 as dead machinery, after revenge_trade's pattern review:
#   revenge_min_loss_inr / revenge_min_loss_pct_capital
#       A minimum-loss gate resolving to 1% of capital. It SUPPRESSED rather than
#       protected: the larger the account, the larger a loss had to be before the
#       detector would look at it at all - 8 alerts at Rs 50,000 and zero at
#       Rs 5,00,000 on the same tradebook. Deleted with the gate, not replaced.
#   revenge_window_danger_min
#       The frozen A x B matrix has no danger sub-tier on the reaction axis, so
#       nothing reads it. Its MANDATORY_REVIEW entry is kept so the reason it was
#       ever questioned survives the constant.
#   signal_points_critical / high / medium / low
#       Weights summed into a confidence score inside one detector - the
#       behaviour score in miniature. Deleted with that arithmetic.
# None of the seven had a production reader when removed.


UNIVERSAL_FLOORS: Dict[str, Any] = {
    'burst_trades_per_30min_caution':   3,    # Never alert for < 3 trades in 30 min
    'revenge_window_caution_min':       2,    # Minimum 2-min caution window
    'revenge_window_min':               1,    # Unified window floor: minimum 1 min
    'consecutive_loss_caution':         3,    # At least 3 losses before any alert
    'panic_exit_min':                   1,    # Minimum 1 min
    'rapid_reentry_min':                1,    # Minimum 1 min
    'no_stoploss_hold_min':             5,    # Minimum 5 min (primary gate is now exit order type)
    'no_stoploss_loss_pct_caution':     15,   # Minimum 15% loss to trigger
}


def get_thresholds(profile=None, session_trades=None) -> Dict[str, Any]:
    """
    Build the merged threshold dict every detector reads.

    Thin wrapper over `threshold_resolution.resolve_thresholds`, which walks the
    resolution ladder (own history > own session > declared rule > capital >
    population > repo constant) and records WHICH rung answered each key.

    This function returns only the values, so every existing caller is
    unaffected. Callers that need provenance — the Rules page, cold-start
    diagnostics — should use `resolve_thresholds()` and read `.explain(key)`.

    See docs/THRESHOLD_RESOLUTION_DESIGN.md.
    """
    from app.core.threshold_resolution import resolve_thresholds
    return resolve_thresholds(profile, session_trades=session_trades).values


def _get_thresholds_pre_ladder(profile=None) -> Dict[str, Any]:
    """
    The implementation as it stood before the resolution ladder.

    Kept ONLY as the parity oracle for tests/test_threshold_resolution.py, which
    asserts the ladder returns identical values for every profile shape. Delete
    once the ladder starts deliberately changing values (the capital-relative
    conversion), at which point a golden fixture replaces it.
    """
    result = dict(COLD_START_DEFAULTS)  # Start with Tier 2 research defaults

    if profile:
        # Tier 2 override: per-metric behavioral baseline (Engine v2 Phase 3).
        # Continuous confidence blend — no activation cliff (master §1B.4):
        #   effective = confidence × personal + (1 − confidence) × default
        # A trader with 3 sessions barely moves the needle; 40 sessions ≈ their
        # own numbers. Universal floors still apply at the end of this function.
        baseline = (getattr(profile, 'detected_patterns', None) or {}).get('baseline')
        metrics = (baseline or {}).get('metrics') if isinstance(baseline, dict) else None
        if metrics and isinstance(metrics, dict):

            def _blend(metric_key: str, derive, default_val: float) -> float:
                rec = metrics.get(metric_key)
                if not rec or rec.get('value') is None:
                    return default_val
                conf = float(rec.get('confidence') or 0)
                personal = derive(float(rec['value']))
                return conf * personal + (1 - conf) * default_val

            # Overtrading: your normal day × 1.5 = your caution line
            result['daily_trade_limit'] = int(round(_blend(
                'avg_daily_trades', lambda v: v * 1.5, result['daily_trade_limit'])))
            result['daily_trade_danger'] = max(
                result['daily_trade_limit'] + 1,
                int(round(result['daily_trade_limit'] * 1.5)),
            )
            # Burst: a quarter of your typical day inside 30 min = unusual
            result['burst_trades_per_30min_caution'] = int(round(_blend(
                'avg_daily_trades', lambda v: max(3.0, v / 4),
                result['burst_trades_per_30min_caution'])))
            result['burst_trades_per_30min_danger'] = max(
                result['burst_trades_per_30min_caution'] + 2,
                int(round(result['burst_trades_per_30min_caution'] * 1.6)),
            )
            # Revenge window: half your natural re-entry pace after a loss
            result['revenge_window_caution_min'] = round(_blend(
                'median_reentry_after_loss_min', lambda v: max(5.0, v * 0.5),
                result['revenge_window_caution_min']), 1)
        elif baseline and isinstance(baseline, dict):
            # Legacy flat-key baseline shape (pre-Phase 3) — direct values
            for key in (
                'daily_trade_limit', 'burst_trades_per_30min_caution',
                'revenge_window_caution_min', 'consecutive_loss_caution',
                'consecutive_loss_danger',
            ):
                if key in baseline and baseline[key] is not None:
                    result[key] = baseline[key]

        # Tier 1: user-declared overrides ONLY when more restrictive than current threshold.
        #
        # Rationale: users set these once and forget. A stale/wrong value (e.g.
        # daily_trade_limit=50, cooldown=0) would otherwise silently disable alerts.
        # When behavioral baseline exists, we trust the observed reality over self-report.
        # When no baseline (cold start), current == research default — user input is fine.
        #
        # Upper limits (lower = stricter):  use min(user, current)
        # Protection windows (higher = stricter): use max(user, current)
        #
        # Exception: capital & loss limits are factual inputs — always use as declared.
        if getattr(profile, 'daily_trade_limit', None):
            user_limit = int(profile.daily_trade_limit)
            # More restrictive = lower number; pick the tighter of user vs current
            result['daily_trade_limit'] = min(user_limit, result['daily_trade_limit'])
            result['daily_trade_danger'] = int(result['daily_trade_limit'] * 1.5)
        if getattr(profile, 'cooldown_after_loss', None):
            user_cooldown = int(profile.cooldown_after_loss)
            # More restrictive = longer cooldown; pick the longer of user vs current
            result['revenge_window_caution_min'] = max(
                user_cooldown, result['revenge_window_caution_min']
            )
            # Unified key used by RiskDetector + BehavioralEvaluator: honour user's declared cooldown directly
            result['revenge_window_min'] = user_cooldown

        # Capital-derived thresholds (always from profile, no style default)
        result['trading_capital']   = getattr(profile, 'trading_capital', None)
        result['daily_loss_limit']  = getattr(profile, 'daily_loss_limit', None)
        result['max_position_size'] = getattr(profile, 'max_position_size', None)
        # Constitution rules (Engine v2 Phase 2) — raw declared values
        result['max_consecutive_losses'] = getattr(profile, 'max_consecutive_losses', None)
        result['restricted_windows']     = getattr(profile, 'restricted_windows', None) or []
        result['user_daily_trade_limit'] = getattr(profile, 'daily_trade_limit', None)
        result['user_cooldown_min']      = getattr(profile, 'cooldown_after_loss', None)

        # Learned danger hours (Phase 4 time_of_day_bias): [{"hour": 13, ...}]
        dp = getattr(profile, 'detected_patterns', None) or {}
        tp = dp.get('time_patterns') or {}
        result['danger_hours'] = tp.get('danger_hours') or []
        _bl = dp.get('baseline') or {}
        result['baseline_sessions'] = _bl.get('sessions_analyzed', 0)
        _blm = _bl.get('metrics') or {}
        result['baseline_win_rate'] = _blm.get('win_rate')          # {value, confidence, n} | None
        result['baseline_profit_factor'] = _blm.get('profit_factor')
        result['sl_percent_futures'] = getattr(profile, 'sl_percent_futures', None) or 1.0
        result['sl_percent_options'] = getattr(profile, 'sl_percent_options', None) or 50.0
        result['risk_tolerance']    = getattr(profile, 'risk_tolerance', None) or 'moderate'

        # User-declared max_position_size maps to the caution threshold
        if result.get('max_position_size'):
            result['max_position_pct_caution'] = float(result['max_position_size'])
            result['max_position_pct_danger']  = float(result['max_position_size']) * 2.0

    else:
        # Cold start: no profile — capital fields are unknown
        result['trading_capital']    = None
        result['daily_loss_limit']   = None
        result['max_position_size']  = None
        result['max_consecutive_losses'] = None
        result['restricted_windows']     = []
        result['user_daily_trade_limit'] = None
        result['user_cooldown_min']      = None
        result['danger_hours']           = []
        result['baseline_sessions']      = 0
        result['baseline_win_rate']      = None
        result['baseline_profit_factor'] = None
        result['sl_percent_futures'] = 1.0
        result['sl_percent_options'] = 50.0
        result['risk_tolerance']     = 'moderate'

    # Apply Tier 3 universal floors — never go below these
    for key, floor in UNIVERSAL_FLOORS.items():
        if result.get(key, 0) < floor:
            result[key] = floor

    return result


# ---------------------------------------------------------------------------
# Capital-at-risk estimation (instrument-aware)
# ---------------------------------------------------------------------------

def estimate_capital_at_risk(
    instrument_type: Optional[str],
    tradingsymbol: str,
    direction: str,
    avg_entry_price: float,
    total_quantity: int,
) -> float:
    """
    Returns estimated Rs capital at risk for a completed trade.

    For options buyers (LONG CE/PE): exact — premium paid IS the capital at risk.
    For futures/options sellers: SPAN-approximated (conservative).
    Hedged positions will appear over-estimated — acceptable for safety alerts.
    """
    notional = float(avg_entry_price or 0) * int(total_quantity or 0)

    if instrument_type in ('CE', 'PE'):
        if direction == 'LONG':
            return notional  # Premium paid = exact capital at risk
        else:
            return _futures_span_margin(tradingsymbol, notional)

    elif instrument_type == 'FUT':
        return _futures_span_margin(tradingsymbol, notional)

    # EQ delivery or unknown — use notional (conservative)
    return notional


def _futures_span_margin(tradingsymbol: str, notional: float) -> float:
    """
    NSE-approximate SPAN margin percentages by underlying.
    Hedged positions (spreads) will over-estimate — acceptable.
    """
    sym = (tradingsymbol or '').upper()

    if sym.startswith('BANKNIFTY') or 'BANKEX' in sym:
        return notional * 0.15   # ~15% SPAN (higher volatility)

    if (
        (sym.startswith('NIFTY') and not sym.startswith('BANKNIFTY'))
        or sym.startswith('FINNIFTY')
        or sym.startswith('MIDCPNIFTY')
        or 'SENSEX' in sym
    ):
        return notional * 0.12   # ~12% SPAN for broad index futures

    return notional * 0.20  # Stock futures: conservative 20%
