# Threshold audit — all 109 constants

Findings only. Nothing here is fixed except the two items marked DONE.

The engine's architecture is sound; the numbers it runs on are mostly not
defended. Every alert a trader ever sees is decided by a value in
`backend/app/core/trading_defaults.py`, and that file had a docstring claiming
all of them were research-derived with "no arbitrary guesses". That claim was
false and is the most damaging thing in the file, because it told every reader
the values were settled and stopped anyone questioning them.

**109 constants — 98 in `COLD_START_DEFAULTS` plus 11 Tier-3 universal floors.
~14 carry a source. ~95 do not.**

---

## The pattern in what is sourced

Where a caution/danger pair exists, the caution value is usually sourced and
the danger value beside it is not:

| constant | value | source |
|---|---|---|
| `daily_trade_limit` | 7 | SEBI FY2023 — >6 trades/day → 94% loss probability |
| `daily_trade_danger` | 12 | none |
| `consecutive_loss_caution` | 3 | tilt onset, poker + trading research |
| `consecutive_loss_danger` | 5 | none |
| `revenge_window_caution_min` | 20 | Coates & Herbert, Cambridge 2008 — cortisol elevated 20–35 min |
| `revenge_window_danger_min` | 5 | none |
| `max_position_pct_caution` | 5.0 | Kelly at 45% win rate, half-Kelly ≈ 6% |
| `max_position_pct_danger` | 10.0 | none |
| `martingale_caution_multiplier` | 1.5 | SEBI — averaging down lost 3× more |
| `martingale_danger_multiplier` | 2.0 | none |
| `recovery_bet_caution_mul` | 2.0 | cited |
| `recovery_bet_danger_mul` | 3.0 | none |

Danger is the level that interrupts hardest, and it is the unsourced half of
every pair.

### A second, subtler problem: cited for the phenomenon, not the number

Several of the 14 "sourced" constants cite research that establishes the
behaviour exists, then attach a number the research does not contain:

- `profit_giveaway_min_peak` = 1500. Citation: "38% of retail intraday traders
  with a profitable session give back >50%". That justifies *detecting the
  pattern*. It says nothing about ₹1,500.
- `max_position_pct_caution` = 5.0. Citation derives ~6% (half-Kelly). The
  constant is 5.0.
- `martingale_caution_multiplier` = 1.5. Citation establishes averaging down is
  costly. The comment then asserts "Danger starts at 1.5×, not 1.8× (too
  late)" with nothing behind it.

So the true count of numbers traceable to a source is **lower than 14**.

### Constants that admit they are provisional

`signal_points_*` and `confidence_alert_gate` carry this comment verbatim:

> Relative importance → tunable values. **Starting points, not spec constants.**

Written as provisional, shipped, never revisited. They set the gate that
decides whether a revenge alert reaches the trader at all.

---

## The four buckets

### A — should be self-relative, currently absolute (the largest bucket)

These describe "big", "fast", or "a lot" and mean different things for a
₹20,000 account and a ₹10,00,000 one. The blend mechanism to fix them already
exists — `_blend()` in `get_thresholds()`, continuous, no activation cliff —
and **currently covers 4 keys out of 109**: `daily_trade_limit`,
`daily_trade_danger`, the two `burst_trades_per_30min_*`,
`revenge_window_caution_min`. `_typical_loss()` covers 2 more.

Everything below should route through one of those two and does not:

| constant | value | why it should be personal |
|---|---|---|
| `profit_giveaway_min_peak` | 1500 | a session peak worth protecting is relative to their typical session |
| `profit_giveaway_caution_pct` / `_danger_pct` | 0.50 / 0.70 | plausible as universal — verify, don't assume |
| `size_escalation_pct` | 30 | "30% is meaningful (not 50%)" — assertion |
| `martingale_caution_multiplier` / `_danger` | 1.5 / 2.0 | escalation is relative to their normal sizing spread |
| `recovery_bet_caution_mul` / `_danger_mul` | 2.0 / 3.0 | same |
| `overconfidence_size_mul_caution` / `_danger` | 1.3 / 2.0 | same |
| `overconfidence_win_streak_caution` / `_danger` | 3 / 5 | a 3-win streak is routine for a scalper, rare for 2 trades/day |
| `consecutive_loss_caution` / `_danger` | 3 / 5 | same |
| `expiry_overtrading_caution_count` / `_danger_count` | 5 / 8 | the `_mul` siblings ARE baseline-relative — the counts contradict them |
| `expiry_overtrading_caution_lots` | 10 | absolute lots across NIFTY and stock options is meaningless |
| `end_session_mis_caution_count` / `_danger_count` | 2 / 3 | |
| `fomo_symbols_in_window` | 3 | a diversified trader's normal is another's scatter |
| `fomo_symbols_at_open` / `fomo_expiry_day_symbols` | 2 / 4 | |
| `obsession_min_losses` / `_min_reentries` | 3 / 2 | |
| `early_exit_winner_max_min` | 60 | a scalper's winner is minutes; a positional trader's is hours |
| `revenge_min_loss_inr` | 500 | **partially fixed** — `_typical_loss` floor added |
| `profit_giveaway_min_erosion` | 500 | **partially fixed** — same |

**Hard limit, stated honestly:** this cannot become "all personal". A new user
has no history, and Kite supplies none (product constraint #1 — today-only
data, new accounts empty). A default must exist. The correct structure is
default → blend toward personal as evidence accumulates, which is exactly what
`_blend` does. The work is extending it, not deleting defaults.

### B — genuinely sourced; keep, but re-verify the number vs the phenomenon

`daily_trade_limit`, `burst_trades_per_15min`, `consecutive_loss_caution`,
`revenge_window_caution_min`, `max_position_pct_caution`,
`martingale_caution_multiplier`, `martingale_min_losses`,
`opening_trap_window_end_min`, `recovery_bet_caution_mul`,
`profit_giveaway_min_peak`, `early_exit_ratio`, `premium_avg_down_loss_pct`,
`iv_crush_proxy_hold_min`, `premium_destruction_pct`.

Action: for each, confirm the cited study actually contains the number, or
downgrade the comment to "phenomenon sourced, threshold chosen".

### C — arbitrary global machinery; cannot be fixed without outcome data

These belong to no single detector, so **pattern-by-pattern review will not
reach them**. They need calibration against labelled outcomes.

| group | constants |
|---|---|
| confidence stacking | `signal_points_critical/high/medium/low` (30/20/10/5), `confidence_alert_gate` (50) |
| behaviour score | `score_halflife_min` (90), `score_sev_mult_*` (0.5/1.0/1.5/2.0), `score_band_*` (30/60/80), `headline_other_weight` (0.15) |
| death spiral | `spiral_domain_min_severity`, `spiral_warning_domains` (2), `spiral_critical_domains` (3), `spiral_window_min` (180) |
| constitution ladder | `constitution_approaching_pct` (0.80), `constitution_severe_pct` (1.20) |
| notification | `alert_session_hard_cap` (8), `alert_bucket_minutes` (5), `alert_stale_push_min` (30), `entry_batch_window_sec` (5), `guardian_monthly_budget` (3) |
| baseline maturity | `baseline_target_sessions` (30), `baseline_target_trades` (100) |

**The blocker is real: 55 alerts, 0 outcomes.** Nothing can be fitted without
labels, and the product cannot ask for them — manual-input adoption is zero.
Capturing outcome signal *passively* is the prerequisite for this whole bucket.

### D — structural / definitional; fine as constants

Window definitions and safety rails, which are describing a market or a
mechanism rather than a judgement about a trader:

`fomo_window_min` (30), `fomo_open_window_min` / `fomo_close_window_min` (30),
`opening_trap_window_end_min` (10 — an NSE microstructure fact),
`direction_confusion_window_min` (10), `spiral_window_min` (180),
`tod_bias_min_sessions` (30), plus all **11 Tier-3 universal floors**, which
exist precisely to be absolute and are correct as such.

---

## Separate finding: the confidence axis barely exists

The design is two axes — severity (cost) and confidence (certainty), kept
independent on purpose. In practice:

**Signal stacking is implemented in exactly ONE detector: `revenge_trade`.**

The other 24 behavioural detectors leave `confidence=None`, which resolves to
`DATA_QUALITY_CONFIDENCE` — `GOOD` = 100.0 on any live postback. So for 24 of
27 detectors, "confidence" measures whether the *data* was clean, never whether
the *behaviour* occurred, and `confidence_alert_gate` (50) can never fire for
them.

This is intentional (`master §1.3`: "for arithmetic detectors, confidence ≈
data quality") and defensible for a pure arithmetic check. But it means the
second axis — the thing that makes the design better than a threshold list —
is load-bearing for one detector out of twenty-seven. Either more detectors
should stack signals, or the architecture should stop being described as
two-axis.

---

## `alert_session_hard_cap` — verified, works, two defects

`backend/app/tasks/trade_tasks.py:1451`. Confirmed firing during the year
replay (`session alert cap reached (8/8)`).

**It is a notification-layer cap, not an engine cap.** `RiskAlert` rows are
written regardless; only delivery is withheld. So **the replay report
over-states what a trader would actually receive** — the 11 alerts on
2025-06-19 and 18 on 2025-09-16 are rows, and at most 8 would have notified.
Worth correcting in how we read those days.

Two defects:

1. **A critical alert after the cap is silently dropped.** On hitting the cap
   the function `return []` for the whole batch, with no severity check. The
   ninth alert of a session is the *most* likely to matter — that is what a
   deteriorating session looks like. A severity floor (critical always
   notifies) is the obvious fix.

2. **The cap keys off wall-clock today, not the trade's session.**
   `today_ist = datetime.now(pytz.timezone("Asia/Kolkata")).date()`, while the
   alert belongs to `completed_trade.exit_time`. These diverge for postbacks
   arriving after midnight IST and for bulk syncs / backfills, where alerts get
   counted against the wrong day's budget.

Also noted in the code's own docstring: the counter measures *saved* rows, not
*delivered* ones, because `delivered_push_at` / `delivered_whatsapp_at` are
never written. It errs quiet, which is the safe direction, but it is the wrong
signal.

---

## DONE in this pass

**1. The docstring.** Rewritten to state the real provenance, name the
caution/danger asymmetry, and tell the reader that an unmarked number is a
hypothesis. Left as the first thing anyone reads.

**2. The double-count in `revenge_trade` signal stacking.** `same_symbol`
implies `same_underlying`, and both were scored — `+20` then `+10` — so one
observation stated twice earned 30 points. Additive stacking assumes
independent evidence; nested signals violate that and inflate confidence past
the gate. The tiers are now exclusive: exact contract → high (20), same
underlying different strike → medium (10).

Effect: the exact-re-entry case is unchanged after the 100 cap. The
different-strike case drops 100 → 90, and a marginal case (slow re-entry, same
underlying, no size increase, session green) moves 50 → 40 and stops alerting.
That is a real behaviour change and should be measured on the next replay
rather than assumed correct.

`session_pnl < 0` (+10) is *correlated* with "you just took a loss" but not
implied by it — you can lose a trade and still be net green. Left alone,
flagged here.

32 engine tests pass.

---

## Recommended order

1. Passive outcome capture — unblocks bucket C, which nothing else can touch.
2. Extend `_blend` / `_typical_loss` across bucket A, pattern by pattern.
3. Re-verify bucket B citations; downgrade comments that overclaim.
4. Fix the two `alert_session_hard_cap` defects.
5. Decide the confidence axis: extend stacking, or stop calling it two-axis.
