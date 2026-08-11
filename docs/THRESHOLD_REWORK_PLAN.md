# Threshold rework — plan

Written 11 Aug 2026, from replaying 744 real F&O trades across 61 sessions.

Nothing here is implemented. It changes product defaults, not tuning.

---

## The finding this rests on

`risk 1–2% of capital per trade` assumes **continuous position sizing** — you can
buy 37 shares. F&O has fixed lot sizes. You cannot buy 0.4 of a NIFTY lot.

On ₹50,000 capital, the shipped defaults give ₹500–1,000 per trade. One NIFTY
option lot costs ₹5,000–15,000. **The minimum tradeable unit is 10–30× the
limit.** Every trade breaches on contact, which is exactly what the first replay
produced: 212 rule violations in 61 sessions, 54% of all alerts.

The rule is equity risk-management orthodoxy applied to a market where it cannot
work. It is not a tuning error.

---

## What actually depends on capital

All 27 detectors, categorised.

**19 need no money figure at all.** Ratios, counts, clock:

| Kind | Detectors |
|---|---|
| Size vs your own previous size | `martingale_behaviour` `size_escalation` `post_loss_recovery_bet` `winning_streak_overconfidence` |
| Counts of trades or instruments | `consecutive_loss_streak` `overtrading_burst` `daily_overtrading` `same_symbol_obsession` `fomo_entry` `expiry_day_overtrading` |
| Clock and sequence | `rapid_reentry` `panic_exit` `early_exit` `opening_5min_trap` `end_of_session_mis_panic` `direction_instability` |
| % of the position itself | `profit_giveaway` `premium_loss_event` `options_premium_avg_down` |

These work identically at ₹30,000 and ₹30,00,000.

**3 self-calibrate from the trader's own history:** `time_of_day_bias`,
`win_rate_collapse`, `strategy_breakdown`. All three were silent across 61
sessions — worth checking whether they need more history than three months.

**5 genuinely need a number, and it should be the trader's:** `excess_exposure`,
`session_meltdown`, `constitution_violation`, `capital_mismatch`,
`portfolio_concentration`.

So removing the capital-derived defaults costs **nothing**. Nineteen keep
working, three self-calibrate, five become the trader's own numbers — which is a
stronger message anyway. "The rule you set" beats "our threshold, which you never
saw."

---

## The changes

### 1. Delete the capital-relative defaults

| Threshold | Now | After |
|---|---|---|
| `risk_pct` per trade | 1–2% of capital | none |
| `loss_pct` daily | 2% of capital | none |
| `excess_exposure` | % of capital | none |
| `profit_giveaway_min_peak` capital scaling | 0.2% of capital | removed |
| `max_position_pct_danger` | `max_position_size × 2` | derived only if the trader set the base |
| `session_meltdown` | % of the derived daily limit | only if the trader set a limit |

### 2. The constitution starts empty

No rules until the trader writes them. The five capital-dependent detectors stay
silent until then, and that is correct: **a mirror that has not been told what to
watch should not invent limits.**

Onboarding suggests values from the trader's own first weeks rather than a
matrix keyed to "beginner / intermediate / advanced".

### 3. Replace the two rupee floors with self-relative ones

`revenge_min_loss_inr` (₹500) and `profit_giveaway_min_erosion` (₹500) exist to
ignore scratches, and ₹500 is meaningful at ₹50,000 and noise at ₹10,00,000.

Replace with **median absolute P&L across the trader's recent trades**. A loss
matters if it is large for them. Needs no capital and no new data — the engine
already loads the session's trades.

### 4. profit_giveaway, restated

The ratio logic is already right: peak, then how much was handed back, at 50%
and 70%. Two tiers stay, for a reason that is not severity:

**50% fires, then 70% fires the same day → the trader did not stop.** The second
alert is a different fact, not a louder one, and it is only visible because there
are two tiers.

The floor becomes "did you give back a meaningful amount" (§3), not "is your
peak a share of capital".

Aggregate give-back behaviour — how often, average %, which days — belongs in
analytics, not in the alert.

### 5. winning_streak_overconfidence — the one still blind

`martingale_behaviour`, `size_escalation` and `post_loss_recovery_bet` were fixed
on 10 Aug to compare notional value across instruments. **`winning_streak_
overconfidence` has the identical restriction and was missed.** Same fix.

---

## What I cannot claim about the other detectors

Asked directly whether the remaining logic is sound, the honest answer is: **I do
not know, and the martingale case is why.**

That detector had correct code, 32 passing tests, and a wrong idea of the
behaviour — it assumed a trader who hammers one instrument. My scenarios were
written from the same assumption, so they could not catch it. It took real
trades.

The same class of flaw may exist elsewhere. What I have verified is that each
detector implements its stated logic. What I have not verified is whether the
stated logic describes what traders actually do. Those are different claims and
I have been conflating them.

**Proposed: an assumption audit.** For each of the 27, write down what it assumes
about the trader — same instrument, same product, trades close together, a
minimum session size — and check each assumption against the tradebook. That is
how martingale was found, done deliberately rather than by luck.

---

## Validation

A twelve-month tradebook, offered by the user, is the right test:

- ~250 sessions instead of 61 — enough for the rarely-firing detectors to show
  whether they are silent because the trader is clean or because they are blind
- Enough winning streaks to exercise `winning_streak_overconfidence`
- Enough history for the three self-calibrating detectors to have a baseline
- Seasonal variation, so thresholds are not tuned to one quarter's conditions

Order: implement §1–5, re-run the 3-month book to confirm nothing regressed,
then the 12-month book as the real test.

**One limit worth stating.** Every threshold decision so far comes from one
trader's data. It is far better than the judgement it replaced, and it is still
one trader. A second book from someone who trades differently would be worth
more than another year from the same person.
