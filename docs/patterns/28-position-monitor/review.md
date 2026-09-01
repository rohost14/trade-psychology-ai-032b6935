# Position-monitor review — `overexposure`, `portfolio_concentration`, `holding_loser`

**1 Sep 2026. REVIEW ONLY. NO PRODUCTION CODE CHANGED. Three separate verdicts.**

Harness: `p28_openbook.py`, **V1 PASSED** — 93 production fills replayed, 0
mismatches on `entry_type` / `quantity` / `avg_entry_price`. See
`harness_validation.md` for its five binding limits.

---

## 0. What the harness can and cannot establish — read this before any number

The instruction was to keep these apart, and it changes the verdicts.

| | |
|---|---|
| **Predicate reconstruction** | **YES for both.** The state machine is validated against production, and both predicates are pure functions of that state plus a price. Every abstention path, the F17 contract multiplier and the severity ladders are production's own code (`_exposure_value` is imported, not copied). |
| **Firing-rate validation** | **NO for both.** Both read `get_cached_ltp()` — a **live** price. The tradebook has fill prices only. Every count below values each position at its **own last fill price**. |

**What the substitution costs, per detector:**

* **`overexposure`** — evaluated at the instant of the opening fill, so the
  price is exact *for the symbol being filled*. But production has **no
  fallback**: without an LTP it returns `{"skipped": "no_ltp"}`. So the
  reconstruction models a branch production only reaches with a live feed, and
  the real firing rate also depends on **feed availability**, which the tradebook
  cannot speak to at all.
* **`portfolio_concentration`** — the substitution is **production's own
  documented fallback**: `_concentration_task` already does
  `ltp = float(pos.average_entry_price)` on a cache miss. So this reconstruction
  exercises a real production branch. It is also a **ratio**, so it is immune to
  market moves that lift the whole book, and only sensitive to *relative* drift
  between legs.

**Everything below is therefore a reconstruction of the decision, not an
observation of the firing rate.** Where a finding survives that distinction, it
is because it rests on **arithmetic** rather than on the price — and each such
finding says so explicitly.

**Sample:** 1,993 fills, **1,071 position-opening fills**, 912 completed rounds,
0 positions left open at the end of the book. Zero abstentions on contract
resolution (the book is NFO throughout), so the F17 abstention path is
**untested here** — a limit, not a result.

---

## 1. `overexposure` — the quantity is wrong for the claim it makes

### Current behaviour

Fires on a position-opening fill when
`notional / trading_capital > max_position_size × 1.5`, where the notional is
`_exposure_value()` = `price × |qty| × contract_multiplier`. Ladder: `caution`
1.5–2×, `danger` >2×, `critical` ≥30% of capital, **ALL-IN BET** ≥50%. A
`danger` recovery-bet / martingale / revenge event in the last 12h bumps
severity one level. `max_position_size` is opt-in and falls back to **10.0**.

### What is correct

The **F17 work is genuinely good**: `_exposure_value` applies the contract
multiplier and **abstains** when the instrument cannot be resolved, with a
docstring that records exactly why (`GOLDM ... a tenfold understatement`). The
emotional bump is a real cross-signal. The entry-time placement is right — the
copy says *"Raised while the position is open, because that is while it can
still be acted on"*, and that is the correct moment.

### Problem 1 — it fires on 100% of futures entries. ARITHMETIC, not price.

| instrument | evaluations | fired @ ₹1L | rate |
|---|---|---|---|
| CE | 763 | 82 | 10.7% |
| PE | 304 | 15 | 4.9% |
| **FUT** | **4** | **4** | **100.0%** |

The four futures entries, and their reconstructed exposure against ₹1L capital:

```
SOLARINDS26JANFUT   618.6%   Rs   618,600    50 @ 12372.0
CIPLA26JANFUT       575.0%   Rs   574,950   375 @  1533.2
CIPLA26JANFUT       573.8%   Rs   573,750   375 @  1530.0
CIPLA26JANFUT       572.6%   Rs   572,588   375 @  1526.9
```

**A position cannot cost more capital than the account holds.** These are
contract values. A CIPLA futures lot requires roughly ₹75–90k of SPAN+exposure
margin, not ₹575k. The trader is told:

> *"CIPLA26JANFUT ₹574,950 exposure (575.0% of capital, your limit 10%)"*

**That sentence is arithmetically correct and substantively false as a statement
about capital.** Futures are margined at roughly 10–15% of notional, so *every*
futures position is several multiples of any retail capital by this measure.
The detector cannot distinguish a reckless futures position from a routine one.

**This finding does not depend on the price substitution.** Shift the price 10%
either way and 618% becomes 556% or 680% — still far past every rung.

### Problem 2 — the threshold sits on the median of its own distribution

Reconstructed exposure as a share of ₹1L capital:

| p50 | p90 | p99 | max |
|---|---|---|---|
| **14.1%** | 29.8% | 57.0% | 1237.2% |

The default trigger is `10 × 1.5 = 15%`. **The median entry sits 0.9 points below
the firing line.** A threshold that bisects the distribution it measures is not
selective — it is a coin-flip on position size.

### Problem 3 — it is mostly a function of self-reported capital

| capital | fired | rate | caution | danger | critical | ALL-IN |
|---|---|---|---|---|---|---|
| ₹50,000 | 495 | **46.2%** | 179 | 214 | 102 | 17 |
| ₹100,000 | 101 | 9.4% | 60 | 32 | 9 | 4 |
| ₹200,000 | 9 | 0.8% | 5 | 0 | 4 | 4 |
| ₹500,000 | 4 | 0.4% | 0 | 0 | 4 | 4 |
| ₹1,000,000 | 4 | **0.4%** | 0 | 0 | 4 | 4 |

**A 115× swing in firing rate across a plausible capital range**, on identical
trading. And `trading_capital` is **self-reported and known to go stale** — that
is precisely what `capital_mismatch` exists to nudge about. The detector's output
is dominated by a settings field, not by behaviour.

The four survivors at every capital level are the four futures entries.

### Overlap

This is the entry-time, notional half of the same question `excess_exposure`
answers at exit with **margin**. Per the scope decision, `excess_exposure` is not
reviewed here — but the comparison is unavoidable, because **the two divide
different quantities by the same capital against thresholds derived from the same
`max_position_size` field.** Fixing the quantity here is not a local change.

### Verdict — **MODIFY**, and it cannot ship alone

**The concept is sound and should not be retired.** It is the only entry-time
capital check, it fires while the position can still be acted on, and its
abstention discipline is correct. **The defect is the quantity, not the idea.**

**The required change is to divide capital requirement by capital, not notional
by capital** — the `quantities_for_trade(...).capital_requirement` path
`excess_exposure` already uses, with its `usable_for_capital_rules` abstention.

**But that change is blocked**, and I will not propose shipping it now:

1. It makes `overexposure` and `excess_exposure` the same measurement at two
   moments, which is a consolidation decision, not a bug fix.
2. `excess_exposure` is **deferred pending live broker-margin validation**, and
   that deferral is exactly about whether our margin figure can be trusted.
3. Changing the quantity invalidates the current thresholds — 10%/15%/30%/50%
   are notional-calibrated. New numbers would have to be **derived, not chosen**,
   and nothing in this book derives them.

**Recommended: accept MODIFY in principle, implement nothing until the margin
question is settled.** Record the futures finding as confirmed.

---

## 2. `portfolio_concentration` — it measures how few positions are open

### Current behaviour

On an opening fill, values every open position, groups by underlying, and alerts
on the top underlying's share: `caution` ≥40%, `danger` ≥60%, `critical` ≥80%.
Abstains on <2 positions, <2 underlyings, zero exposure, or any unresolved
contract — **abandoning the whole calculation rather than skewing it**, which is
the right call.

### What is correct

The abstention design is the best part of the detector: one unresolved leg makes
the share wrong for *every* leg, and it refuses rather than guesses. The
underlying-level grouping is the right unit — several strikes on one index is one
bet. The LTP fallback to `average_entry_price` is sensible.

### The finding — it cannot withhold on the most common case. ARITHMETIC.

**With *n* open positions the top underlying's share is at least 1/n.** With
n = 2 that floor is **50%**, and the `caution` cut is **40%**. A two-position book
is therefore *mathematically incapable* of not firing.

Reconstructed, by number of open positions:

| n open | evaluations | fired | rate | min share seen | median |
|---|---|---|---|---|---|
| **2** | **206** | **206** | **100.0%** | **50.0%** | 63.1% |
| 3 | 99 | 80 | 80.8% | 34.5% | 47.0% |
| 4 | 22 | 12 | 54.5% | 28.6% | 41.6% |
| 5 | 3 | 0 | 0.0% | 27.3% | 35.1% |

By distinct underlyings, the same shape: **2 → 224/224 = 100.0%**, 3 → 77.6%,
4 → 44.4%, 5 → 0%.

* **Withhold rate on a 2-position book: 0.0%.**
* **69.1% of all firings (206 of 298) come from a 2-position book.**
* Firing rate falls **monotonically** as the book gets more diverse — which is
  the detector working backwards: it alerts hardest when there is least to
  measure.

Of 1,071 opening fills, **705 (65.8%) abstain as `single_position`** — this
trader usually holds one thing. So the population the detector judges is
overwhelmingly "exactly two positions", and on that population it always fires.

**This finding does not depend on the price substitution at all.** The 1/n floor
is arithmetic. Any prices whatsoever give a two-position book ≥50%.

**This is the `profit_giveaway` shape** (a drawdown from the session peak is
arithmetic) and the `expiry_day_overtrading` shape (it never withheld — 55 of 55).

### Is it just a mis-set threshold?

**No, and this is the reason for the verdict.** Raising the cut above 50% would
stop 2-position books firing automatically, but it would also make the measure
meaningless there: a 2-position book that is genuinely lopsided (95/5) and one
that is balanced (50/50) would both need to clear the same bar that only exists
because n = 2. **A concentration measure has to control for book size** — the
comparison is against what a diversified book *of that size* looks like, not
against a fixed percentage. That is new methodology, and this review will not
invent it.

### Verdict — **DELETE (retire)**

The trader-facing claim is *"NIFTY is 63% of your open exposure"*. On this book
that sentence is, 69% of the time, a restatement of *"you have two positions
open"*. It cannot withhold on the case it most often judges, it fires hardest on
the least diverse books, and the defect is structural rather than a threshold
that can be moved.

**NOT retired permanently.** Concentration risk is real and standard in
portfolio management. What is retired is a **fixed-percentage share test applied
to a 1–5 position book**. A size-adjusted measure could return, and would need
its own evidence — including a decision about whether a two-position F&O book is
a portfolio at all.

---

## 3. `holding_loser` — the subject is real, and the gate is in the wrong place

### Current behaviour

Scheduled 30 minutes after an opening fill, self-rescheduling up to
`MAX_HOLDING_LOSER_CHECKS = 8` cycles (**4 hours of coverage**). Fires `caution`
when the position is down ≥ `HOLDING_LOSER_MIN_LOSS_PCT` **0.5%** and has been
held ≥ `HOLDING_LOSER_MIN_DURATION` **30 minutes**.

### What CANNOT be established, stated plainly

**The firing rate, the false-positive rate and the outcome of flagged positions
are all unmeasurable.** The predicate needs unrealized P&L at T+30/60/90 minutes
on an open position. We store **no intraday price path** — `zerodha_service` has
no `historical_data` call — and the harness validation found a second gap: **the
ledger never sees an expiry**, so a position closed by expiry has no closing fill
and its hold time is unbounded.

**INSUFFICIENT EVIDENCE.** No proxy is substituted — that is the `early_exit` and
`opening_5min_trap` failure mode.

### What CAN be established — hold durations, and the upper bound

912 completed rounds:

| p10 | p25 | p50 | p75 | p90 | max |
|---|---|---|---|---|---|
| 2 min | 6 min | **23 min** | 120 min | 1,310 min | 30,245 min |

| gate | rounds | share |
|---|---|---|
| ≥ 30 min | **405** | 44.4% ← **upper bound on firings** |
| ≥ 60 min | 312 | 34.2% |
| ≥ 120 min | 228 | 25.0% |
| ≥ 240 min | 187 | 20.5% |

**The 30-minute gate is genuinely selective**: the median round closes in 23
minutes, so the gate excludes over half the book before the loss test is applied.
That is a real point in the detector's favour and it survives the price problem.

### The subject question — measured, and the answer is split

Does holding past the gate actually go worse? Round outcome by hold duration:

| | n | win rate | mean | median |
|---|---|---|---|---|
| < 30 min | 507 | 37.5% | −₹43 | −₹165 |
| **≥ 30 min** | 405 | **43.0%** | **−₹296** | −₹271 |

**Longer holds win MORE often and lose MORE money.** The win rate points the
*opposite* way to the detector's premise — the Pattern 19 direction check would
flag that — while the money points its way. That combination is a fat left tail,
which is the disposition effect's actual signature.

**And the tail is not where the detector looks:**

| hold | n | win rate | mean |
|---|---|---|---|
| 0–5 min | 187 | 38.5% | −₹45 |
| 5–15 | 179 | 40.8% | +₹14 |
| 15–30 | 141 | 31.9% | −₹112 |
| **30–60** | 93 | 39.8% | **+₹3** |
| **60–120** | 84 | 48.8% | −₹130 |
| **120–240** | 41 | **53.7%** | **+₹219** |
| 240–1440 | 114 | 40.4% | −₹192 |
| **1440+** | **73** | 38.4% | **−₹1,319** |

**Between 30 minutes and 4 hours — exactly the detector's coverage window —
outcomes are neutral to positive.** The 120–240 minute bucket is the *best* in
the book on both win rate and money. The damage is at **1,440+ minutes**:
overnight, mean **−₹1,319**, an order of magnitude worse than any other bucket.

**The detector's coverage stops at 4 hours. The harm starts at 24.**

Caveats, because this is round outcome and not the predicate: it measures how a
round *ended* by how long it was *held*, not whether it was down at T+30. Long
holds are also structurally different — overnight positions are NRML, not MIS —
so bucket 1440+ is partly a product difference, not purely a duration effect.

### Verdict — **RESEARCH FURTHER**

Not KEEP: the evidence says the coverage window misses the horizon where the
money is lost, and a detector aimed at the wrong horizon should not be blessed.

Not DELETE: the subject **exists** in this book on the money measure, the
30-minute gate is demonstrably selective, and the reason we cannot judge the
predicate is a **data gap**, not a failed test. Retiring on unmeasurability would
be treating insufficient evidence as evidence of absence.

**Unblock conditions, in order of value:**

1. **Production `RiskAlert` rows** — `holding_loser` is live and dispatched on
   every opening fill. Real firings would answer the rate directly, with no
   price path needed.
2. **An intraday price path** for the flagged positions, which is what the
   predicate genuinely requires.

**Do NOT tune the 30-minute gate or the 0.5% floor now**, and do not extend
`MAX_HOLDING_LOSER_CHECKS` to reach the overnight horizon on the strength of one
bucket of 73 rounds. Both would be choosing numbers from a measurement that
cannot see the predicate.

---

## 4. Summary

| pattern | verdict | rests on |
|---|---|---|
| `overexposure` | **MODIFY** — quantity is wrong; blocked on the margin decision | arithmetic (100% of futures), not the price substitution |
| `portfolio_concentration` | **DELETE (retire)** | arithmetic (the 1/n floor), not the price substitution |
| `holding_loser` | **RESEARCH FURTHER** | duration is measurable; the predicate is not |

**Neither of the two firm findings depends on the price substitution** — both
rest on properties that hold at any price. That is the only reason verdicts are
being offered at all on detectors whose real firing rate cannot be validated.

**Nothing here touches `excess_exposure`** beyond noting that it is the other
half of `overexposure`'s quantity question, or `capital_mismatch`, which stays
housekeeping — though this review sharpens why it matters: `overexposure`'s
firing rate swings 115× across a plausible capital range, and capital is exactly
the field `capital_mismatch` nudges about.
