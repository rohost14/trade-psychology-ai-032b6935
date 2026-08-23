# Every hardcoded threshold, by what kind of number it is

24 Aug 2026. Reference for the 27 pattern reviews. **No values changed.**

The alphabetical list in `trading_defaults.py` hides the thing that matters:
**these are five different kinds of number, and only some of them should be
hardcoded at all.** Grouped by kind below, with the honest verdict for each.

---

## Type 1 — Definitional. Hardcoding is CORRECT.

Not calibration. These define what the word means; changing them changes the
phenomenon rather than the sensitivity.

| constant | value | note |
|---|---|---|
| `martingale_min_losses` | 2 | you cannot have a progression with one loss |
| `obsession_min_reentries` | 2 | a re-entry is not a pattern |
| `obsession_min_losses` | 3 | |
| `overconfidence_win_streak_caution` | 3 | classified `definitional` |
| `overconfidence_win_streak_danger` | 5 | classified `definitional` |
| `early_exit_min_samples` | 3 | statistical minimum, not a threshold |
| `spiral_warning_domains` / `_critical_domains` | 2 / 3 | see caveat below |

**Verdict: leave hardcoded.** The only argument is against "3 wins is a streak" —
defensible as a definition, arbitrary as a measurement. The spiral domain counts
sit awkwardly here: they *are* counting, which is a score with unit weights.

## Type 2 — Product policy. Hardcoding is CORRECT, classification is WRONG.

Nothing to do with trading. These are our decisions about how much to interrupt.

| constant | value |
|---|---|
| `alert_session_hard_cap` | 8 |
| `alert_bucket_minutes` | 5 |
| `alert_stale_push_min` | 30 |
| `guardian_monthly_budget` | 3 |
| `confidence_alert_gate` | 50 |

**Verdict: keep the values, fix the `Kind`.** All five are `fallback` today.
They are `product_policy`, and classifying them would stop anything ever
personalising them — which is right: a trader should not be able to learn their
way into more alerts.

## Type 3 — Time windows. Personal by nature.

"How long does the effect last." Genuinely different per trader — a scalper's
20 minutes is not a positional trader's.

| constant | value |
|---|---|
| `revenge_window_caution_min` / `_danger_min` / `_min` | 20 / 5 / 10 |
| `fomo_window_min`, `fomo_open_window_min`, `fomo_close_window_min` | 30 |
| `rapid_reentry_min`, `rapid_flip_min` | 5, 10 |
| `panic_exit_min` | 5 |
| `spiral_window_min` | 180 |
| `direction_confusion_window_min` | 10 |
| `opening_trap_window_end_min` / `_quick_exit_min` | 10 / 15 |
| `premium_loss_fast_hold_min` | 30 |
| `no_stoploss_hold_min` and variants | 5 |

**Verdict: personal percentile is better than any constant here** — the machinery
exists (`reentry_after_loss_p25` is exactly this), and the constant becomes the
declared fallback for an immature trader. This is the clearest case where we can
do better than hardcoding, and the three-state maturity model already handles the
cold-start cost.

## Type 4 — Magnitude ratios. The problematic class.

| constant | value | Kind |
|---|---|---|
| `premium_loss_caution_pct` / `_danger` / `_critical` | 40 / 60 / 80 | **universal_safety** |
| `no_stoploss_loss_pct_caution` / `_danger` | 25 / 50 | fallback / **universal_safety** |
| `no_stoploss_expiry_loss_pct`, `_monthly_loss_pct` | 25, 20 | fallback |
| `premium_avg_down_loss_pct` | 20 | fallback |
| `opening_trap_large_loss_pct` | 30 | fallback |
| `max_position_pct_caution` / `_danger` | 5 / 10 | **universal_safety** |
| `meltdown_caution_pct` / `_danger_pct` | 0.4 / 0.75 | fallback (of declared limit) |
| `profit_giveaway_caution_pct` / `_danger_pct` | 0.5 / 0.7 | fallback (of peak) |

**Verdict: this is the class the revenge review broke.** S2a was one of these and
no value in its range was defensible, because prospect theory is
reference-dependent — "a large loss" has no person-independent definition.

Two are structurally better than the rest: `meltdown_*` and
`profit_giveaway_*_pct` are fractions **of something the trader owns** (their
declared limit; their own session peak), so they scale by construction. The
premium-loss family divides by the premium, which is a property of the contract
rather than of the trader.

**The genuinely better alternative — instrument-derived, see §6.**

## Type 5 — Multipliers. Relative already, values still invented.

| constant | value |
|---|---|
| `martingale_caution_multiplier` / `_danger` | 1.5 / 2.0 |
| `overconfidence_size_mul_caution` / `_danger` | 1.3 / 2.0 |
| `recovery_bet_caution_mul` / `_danger_mul` | 2.0 / 3.0 |
| `size_escalation_pct` | 30 |
| `constitution_approaching_pct` / `_severe_pct` | 0.8 / 1.2 |

**Verdict: better than absolutes, still arbitrary.** These compare a trade to a
prior trade, so they scale with account size automatically — the failure mode
that killed `revenge_min_loss_inr` cannot happen here.

`revenge_trade` removed its multiplier entirely by using a **plain inequality**
("larger than the position that just lost"). Several of these could do the same,
and `constitution_*_pct` are policy about a declared limit, not trading numbers.

## Type 6 — Counts. Personal by nature.

`burst_trades_per_30min_*` 5/8 · `consecutive_loss_*` 3/5 · `daily_trade_limit`
7, `_danger` 12 · `fomo_symbols_*` 2/3/4 · `expiry_overtrading_*` 5/8/10 ·
`end_session_mis_*` 2/3

**Verdict: same as Type 3 — personal percentile beats a constant**, and the
ladder already moves seven of these from the trader's own history. The rest are
candidates for the same treatment at their reviews.

---

## Is hardcoding the best we have? Per type, no.

| type | hardcode? | better alternative | available today? |
|---|---|---|---|
| 1 definitional | **yes** | none needed | — |
| 2 product policy | **yes** | none — ours to decide | fix `Kind` only |
| 3 time windows | no | personal percentile | **yes**, machinery built |
| 4 magnitude ratios | no | §6 below | partly |
| 5 multipliers | mostly | plain inequality, or personal ratio | yes |
| 6 counts | no | personal percentile | **yes**, 7 already do |

### §6 — The alternative worth investigating for Type 4

A fixed premium-loss percentage is wrong for a reason that has nothing to do with
the trader: **it ignores the contract's own volatility.**

Losing 40% of the premium on a far-OTM weekly option is an ordinary hour — that
contract routinely moves that much. Losing 40% on a deep-ITM option is a serious
adverse move, because it should not move that fast.

Same number, two completely different events, and the difference is **observable
from the instrument** — moneyness, time to expiry, and the option's own typical
range. No user data, no maturity requirement, no cold-start cost.

That is the most promising direction I can see for Type 4, and it is the one
class where personalisation does not help much either, because the variation is
in the *contract*, not the trader.

**Not proposed as work.** It needs its own evidence, and it belongs to the review
of whichever detector reaches it first (`premium_loss_event`).

---

## Standing rule for all 27 reviews

Each detector's review removes **its own** inline magic numbers, as
`revenge_trade` removed its `1.5` and its `30/20/10/5`. Numbers are not cleaned
in bulk: a number is examined when the detector that reads it is examined, with
that detector's evidence and behind its replay.

Current state: **1 of 27 cleaned.** 56 of 86 constants remain unclassified
`fallback` — untouched and unexamined, exactly as before this work began.
