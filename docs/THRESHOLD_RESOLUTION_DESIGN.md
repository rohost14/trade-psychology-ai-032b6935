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
| 5 | **Population posterior** | once we have users | median of comparable users |
| 6 | **Global constant** | always | last resort, explicitly labelled |

Rungs 2, 4 and 5 do not exist today. Rung 6 is doing their work.

### Why there is no "declared style" rung

An earlier draft had one: ask the trader whether they are a scalper / intraday /
swing / positional and price the hold-time and pace thresholds from it. That was
wrong and is removed.

**A declared category is an identity label, not a behavioural fact.** Someone who
selects "scalper" may take four trades next week; a "positional" trader may take
fifteen in a day. Behaviour is situational and moves with the market. Worse, a
wrong label is never corrected, because nothing ever measures "scalperness" —
so it would silently mis-price every hold-time threshold for the life of the
account.

The same objection retires `experience_level` as a detection input: two years
can be good and five can be bad, so it is a poor proxy for skill.

What replaces it is rung 2. Median hold time *today* is directly observable from
the trades themselves, needs no declaration, and moves when the trader moves.

**Governing rule for anything we ask a user:**

> Ask only for numbers we will later measure and replace. Never for categories,
> because a category never gets displaced.

**Rung 3 is never displaced.** A declared limit is a commitment, not an
estimate. Data may show a trader routinely exceeds their own limit — that is a
finding to show them, never a reason to quietly raise the limit.

**Rungs 1, 5 and 6 blend rather than switch**, by the shrinkage already
implemented: `effective = c*personal + (1-c)*prior`, `c = min(1, n/target)`.
No cliff, and no need to classify anyone.

---

## 3. Cold start, concretely

What we know about a user on the morning they sign up, with zero trades:

- capital (fetched from the broker on login)
- declared limits, if they completed onboarding
- their stated normal trade count, if they answered

That is enough to set a usable, *personal* threshold for most detectors on day
one. Worked through:

| detector | day 1 source | matures to |
|---|---|---|
| `session_meltdown` | rung 3/4 — % of declared or capital-derived loss limit | unchanged (already correct) |
| `profit_giveaway` | rung 2 — % of **your own peak today**, needs no history at all | unchanged |
| `martingale` | rung 2 — multiple of **your previous trade** (2 trades) | personal typical size |
| `size_escalation` | rung 2 — vs your session average (3-5 trades) | rung 1 |
| `revenge_trade` | rung 6 prior, then rung 2 — vs **your own gaps this session** (3-5 trades) | rung 1: P25 of your own gaps |
| `consecutive_loss` | rung 4 — scaled to capital | rung 1: P60/P85 of your streaks |
| `daily_trade_limit` | rung 3 if declared, else stated normal count, else rung 5 | rung 1: P75 of your sessions |
| `panic_exit` / `early_exit` | rung 2 — vs **your own median hold this session** | rung 1 |

Nothing on this list needs 90 days. The longest is ~20 sessions, and only to
*refine* a threshold that was already personal on day one.

Note what changed when the declared-style rung was removed: the hold-time and
pace detectors moved from "a label the trader picked once" to "what the trader
actually did in the last few trades". That is strictly better — it is available
just as early, it cannot be wrong, and it tracks a trader whose behaviour shifts.

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

### 4f. Signal stacking — EXTEND, do not delete (5)

`signal_points_critical/high/medium/low` 30/20/10/5, `confidence_alert_gate` 50.

An earlier draft called these inert and proposed deleting them. That was a
misreading, corrected here. Inside `revenge_trade` they are fully live and are
**the only false-positive suppression mechanism in the engine**:

```
base                                 30   meaningful loss + re-entry inside window
+ fast re-entry (<= danger window)  +20
+ same exact symbol                 +20   (or +10 for same underlying only)
+ position >= 1.5x the losing trade +20
+ session already red               +10
gate = 50 -> below this the event becomes "info": recorded, never alerts
```

Base alone is 30, under the gate. So "you traded 18 minutes after a loss" does
not alert without corroboration. Deleting these constants would make
`revenge_trade` — the highest-volume detector — fire on timing alone.

The other 26 detectors leave `confidence=None`, which resolves to
`DATA_QUALITY_CONFIDENCE["GOOD"] = 100`, so the gate always passes for them.
They do not participate; the mechanism is not broken for them.

This is the "certainty" axis of `docs/BEHAVIOUR_SYSTEM_DESIGN.md`, already built
once and never extended. Best candidates to extend to, by measured need:
`fomo_entry` (over-fires roughly 4:1), `same_symbol_obsession` (-20 lift),
`size_escalation`.

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

## 7. What onboarding should ask

Only what cannot be observed. Anything observable is measured, not asked.

| # | question | kind | status |
|---|---|---|---|
| 1 | Capital | fact — **fetched** from broker, shown to confirm | change: stop asking, start fetching |
| 2 | Daily loss limit (₹ or % of capital) | **commitment** | exists |
| 3 | Max trades per day you want to hold yourself to | **commitment** | exists |
| 4 | On a normal day, how many trades do you take? (band) | **number** — prior, displaced by measurement | **add**; surfaces in Rules beside #3 |
| 5 | Max consecutive losses before you stop | **commitment** | exists |
| 6 | Cooldown after a loss | **commitment** | exists |
| 7 | Accountability partner contact | fact, not inferable | exists |

Commitments (2, 3, 5, 6) are rung 3 and are **never displaced by data**. If the
trader routinely exceeds their own limit, that is a finding to show them — never
a reason to quietly raise the limit.

**Dropped:** `known_patterns` ("which of these do you struggle with?") has
**zero consumers anywhere in the codebase** — asked at onboarding, read by
nothing. Remove the question.

**Demoted, not removed:** `trading_style`, `experience_level`, `risk_tolerance`
are kept as profile/coach context (the AI coach uses them for prose) but must
never become detection inputs — see §2.

---

## 8. Build order

1. ~~**`resolve()` returning `{value, source, confidence}`**~~ — **DONE**
   (`app/core/threshold_resolution.py`). Pure refactor, parity-tested against
   the previous implementation across 7 profile shapes.
2. ~~Convert the 3 rupee constants to capital-relative~~ — **DONE**. Ratios
   calibrated so a ₹50,000 account resolves to exactly its previous 500 / 1500 /
   500; a ₹20,000 account now gets 200 / 600 / 200 and a ₹20,00,000 account
   20,000 / 60,000 / 20,000.
3. ~~Rung 2 — session-relative~~ — **DONE for analytics thresholds only.**
   `panic_exit_min` and `rapid_reentry_min` now come from the trader's own
   median hold and median gap today, shrunk toward the default by sample size
   (`n/8`, so two trades nudge and eight decide). Both belong to
   `notification_level=0` detectors, so **this cannot change alert volume** —
   which is why it was the right place to prove the mechanism.

   A scalper with 3-minute holds now gets `panic_exit_min` 1.5; a positional
   trader with 4-hour holds gets 120. One constant could never have served both,
   and this is measured rather than declared.

4. **Extend rung 2 to alerting thresholds** — `revenge_window_*`,
   `size_escalation`. This DOES change alert volume, so it needs a replay over
   the reference tradebook behind it, not just unit tests.
5. Capital on login via a throttled worker — makes rung 4 automatic rather than
   dependent on onboarding.
6. One baseline writer: percentile derivation (service A) + confidence model
   (service B), matured on trades rather than calendar days. Kills the
   two-shapes race.
7. Extend signal stacking to `fomo_entry`, `same_symbol_obsession`,
   `size_escalation`.
8. Replace the floors with the interruption policy.
9. Population posterior (rung 5) — interface now, switch on when users exist.

### What is deliberately still on the global rung

Everything that fires an alert. Rung 2 is scoped to analytics detectors on
purpose: it is a real behavioural change, and the honest way to introduce one is
where it cannot reach the trader, verify the mechanism, and only then extend it
to the thresholds that interrupt. `test_session_rung_only_touches_analytics_thresholds`
pins that boundary, so widening it has to be a deliberate act.
