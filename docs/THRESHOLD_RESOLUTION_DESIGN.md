# How a threshold gets its value — design

Design proposal, 21 Aug 2026. Nothing here is implemented.

Answers one question: **where does the number a detector compares against come
from, for a user who signed up this morning and for a user with a year of
history, without hardcoding a claim about "traders" into either case.**

Companions: `docs/BEHAVIOUR_SYSTEM_DESIGN.md` (what an alert is for),
`docs/ARCHITECTURE_REVIEW_2026-08.md` (what exists today and what is broken).

---

## 1. The problem with what exists

Today a threshold comes from two places: a hardcoded default, or the trader's
own 90-day history. There is nothing in between, so a new user gets numbers
invented for an imaginary average trader and keeps them for three months. That
is a retention problem before it is an accuracy problem.

Three things make this worse than it needs to be:

1. **90 days is not required by the behaviours.** It is required by the query
   window `compute_baseline` happens to use. Most of these patterns are
   comparisons against the trader's own *recent* or *current-session* behaviour
   and need a handful of trades, not a quarter.
2. **Onboarding already collects the answers and the engine discards them.**
   `trading_style`, `experience_level` and `known_patterns` have **zero**
   references in the engine or in threshold resolution. `risk_tolerance` reaches
   only the AI coach's prose.
3. **A quarter of the constants are already ratio-based and work on day one.**
   The pattern is proven inside this codebase; it was just never finished.

---

## 2. The resolution ladder

`resolve(metric, ctx)` walks these top-down and returns the first rung that can
answer, with `{value, source, confidence}` attached so the answer is inspectable.

| # | rung | available from | nature |
|---|---|---|---|
| 1 | **Your own history** | ~20 sessions / ~100 trades | percentile of your distribution |
| 2 | **Your own recent + session-so-far** | **2-5 trades** | self-relative comparison |
| 3 | **Your declared rules** | day 1 if set | commitment - authoritative, never overridden |
| 4 | **Your capital** | **day 1, zero input** (fetched) | ratio of capital |
| 5 | **Your declared style/experience** | **day 1 if onboarded** | structural prior |
| 6 | **Population posterior** | once we have users | median of comparable users |
| 7 | **Global constant** | always | last resort, explicitly labelled |

Rungs 2, 4, 5 and 6 do not exist today. Rung 7 is doing their work.

**Rung 3 is never displaced.** A declared limit is a commitment, not an
estimate. Data may show a trader routinely exceeds their own limit — that is a
finding to show them, never a reason to quietly raise the limit.

**Rungs 1 and 5-7 blend rather than switch**, by the shrinkage already
implemented: `effective = c*personal + (1-c)*prior`, `c = min(1, n/target)`.
No cliff, and no need to classify anyone.

---

## 3. Cold start, concretely

What we know about a user on the morning they sign up, with zero trades:

- capital (fetched from the broker on login)
- declared limits, if they completed onboarding
- declared style and experience, if they completed onboarding
- which patterns they say they already have

That is enough to set a usable, *personal* threshold for most detectors on day
one. Worked through:

| detector | day 1 source | matures to |
|---|---|---|
| `session_meltdown` | rung 3/4 — % of declared or capital-derived loss limit | unchanged (already correct) |
| `profit_giveaway` | rung 2 — % of **your own peak today**, needs no history at all | unchanged |
| `martingale` | rung 2 — multiple of **your previous trade** (2 trades) | personal typical size |
| `size_escalation` | rung 2 — vs your session average (3-5 trades) | rung 1 |
| `revenge_trade` | rung 5 — style sets the window (a scalper's 5 min is not a swing trader's 5 min) | rung 1: P25 of your own gaps |
| `consecutive_loss` | rung 4/5 — scaled to capital and style | rung 1: P60/P85 of your streaks |
| `daily_trade_limit` | rung 5/6 — style prior, then population median for your band | rung 1: P75 of your sessions |
| `panic_exit` / `early_exit` | rung 5 — hold-time expectations differ by style by design | rung 1 |

Nothing on this list needs 90 days. The longest is ~20 sessions, and only to
*refine* a threshold that was already personal on day one.

---

## 4. The 94 constants — disposition of every one

83 in `COLD_START_DEFAULTS` + 11 in `UNIVERSAL_FLOORS`.

### 4a. Already ratio-based — keep as they are (~20)

These express a fraction of something personal and already work on day one.
**They are the model for everything else.**

`max_position_pct_caution/danger` (% capital) · `meltdown_caution/danger_pct`
(% of *your* loss limit) · `constitution_approaching/severe_pct` (% of *your*
rule) · `profit_giveaway_caution/danger_pct` (% of *your* peak today) ·
`martingale_caution/danger_multiplier` (x *your* last trade) ·
`overconfidence_size_mul_caution/danger` · `recovery_bet_caution/danger_mul` ·
`size_escalation_pct` · `early_exit_ratio` · `no_stoploss_loss_pct_*` ·
`premium_loss_*_pct` · `premium_avg_down_loss_pct` ·
`opening_trap_large_loss_pct`

### 4b. Absolute rupees — the clearest defects (3)

| constant | now | should be |
|---|---|---|
| `revenge_min_loss_inr` | 500 | % of capital, or % of your typical loss (already half-done inline) |
| `profit_giveaway_min_peak` | 1500 | % of capital |
| `profit_giveaway_min_erosion` | 500 | % of capital |

₹500 is 1% of ₹50,000 and 0.1% of ₹5,00,000. These cannot be universal.

### 4c. Absolute counts — move to rungs 1/2/5/6 (~22)

`daily_trade_limit` 7 · `daily_trade_danger` 12 · `burst_trades_per_30min_caution`
5 · `_danger` 8 · `burst_trades_per_15min` 6 · `consecutive_loss_caution` 3 ·
`_danger` 5 · `fomo_symbols_in_window` 3 · `fomo_symbols_at_open` 2 ·
`fomo_expiry_day_symbols` 4 · `expiry_overtrading_caution_count` 5 ·
`_danger_count` 8 · `_caution_lots` 10 · `end_session_mis_caution_count` 2 ·
`_danger_count` 3 · `overconfidence_win_streak_caution` 3 · `_danger` 5

Sub-group — **minimum-sample gates, keep global**: `martingale_min_losses` 2,
`early_exit_min_samples` 3, `obsession_min_losses` 3, `obsession_min_reentries`
2. These are definitional: you need two losses before "martingale" means
anything. They are not claims about the trader.

### 4d. Time windows — split (~17)

**Definitional (keep global)** — they define the measurement unit, not a
judgement: `fomo_window_min` 30 · `fomo_open/close_window_min` 30 ·
`spiral_window_min` 180 · `alert_bucket_minutes` 5 ·
`direction_confusion_window_min` 10 · `opening_trap_window_end_min` 10

**Judgemental (should be personal, rung 5 then 1)** — each asserts something
about how fast this trader normally acts: `panic_exit_min` 5 ·
`rapid_reentry_min` 5 · `rapid_flip_min` 10 · `revenge_window_caution/danger_min`
20/5 · `revenge_window_min` 10 · `early_exit_winner_max_min` 60 ·
`no_stoploss_hold_min` 5 · `premium_loss_fast_hold_min` 30 ·
`opening_trap_quick_exit_min` 15

A five-minute exit is panic for a positional trader and ordinary for a scalper.
`trading_style` answers this on day one and is currently discarded.

### 4e. Product policy — legitimately global (~11)

These are our decisions about the product, not claims about traders, and should
stay hardcoded and defended as product choices:

`alert_session_hard_cap` 8 · `guardian_monthly_budget` 3 ·
`alert_stale_push_min` 30 · `baseline_target_sessions` 30 ·
`baseline_target_trades` 100 · `tod_bias_min_sessions` 30 ·
`spiral_domain_min_severity` danger · `spiral_warning_domains` 2 ·
`spiral_critical_domains` 3

### 4f. Inert — decide explicitly (5)

`signal_points_critical/high/medium/low`, `confidence_alert_gate` 50. The
confidence axis is implemented in 1 detector of 27, so these are dead for the
other 26. Build the axis out or delete them; do not leave them looking live.

### 4g. UNIVERSAL_FLOORS — replace the mechanism (11)

The floors exist to stop absurd alerts (never interrupt over 2 trades). That
purpose is legitimate; **11 per-metric magic numbers are a crude proxy for it.**
The thing actually wanted is "do not interrupt more often than is useful", which
the interruption policy provides directly — transition-only, percentile-gated,
session budget. With that policy the floors are redundant.

They also currently override the trader's own declared rules, which sits badly
with the constitution's promise that your rules are yours.

---

## 5. Capital on login

Unlocks rung 4 for every user on day one with zero input.

**Constraint that must shape the implementation:** Kite rate-limits per API key,
and we run one platform app for all users (Model A), so the ~3 req/s ceiling is
shared across the entire base. 10k users spread over a day is fine. 100k users
clustered at 09:00-09:15 is roughly 55 req/s against a 3 req/s budget.

So: a throttled worker with a per-user daily cache, never an inline call in the
login handler. A stale-by-hours margin figure is perfectly adequate for setting
behavioural thresholds.

Once capital is known, statements that are true for **anyone** become available
without any history: losing 50% of capital in one session is critical for a
beginner and a professional alike, because it is a ratio.

---

## 6. The one-way ratchet — open decision

Personalisation currently only loosens:

```python
daily_trade_limit = max(your_P75, default_7)
```

A trader whose P75 is 3 keeps 7 and must more than double their normal day
before anything fires — which is precisely the signal "unusual for you" exists
to catch, suppressed.

Removing the `max()` makes thresholds genuinely personal in both directions and
increases alert volume for quiet traders. This is the single biggest behavioural
change in the plan and needs an explicit decision, not a default.

---

## 7. Build order

1. `resolve(metric, ctx)` returning `{value, source, confidence}` — the ladder,
   with rung 7 as the fallback it should always have been.
2. Wire the onboarding fields already being collected — `trading_style` first,
   since it prices every hold-time and pace threshold on day one.
3. Convert 4b (3 rupee constants) and the ready parts of 4c to capital-relative.
4. Capital on login via a throttled worker.
5. One baseline writer: percentile derivation (service A) + confidence model
   (service B), matured on trades rather than calendar days.
6. Replace the floors with the interruption policy.
7. Population posterior (rung 6) — interface now, switch on when users exist.
