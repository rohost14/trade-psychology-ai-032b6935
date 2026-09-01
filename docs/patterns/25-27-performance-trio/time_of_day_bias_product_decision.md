# `time_of_day_bias` — product design pass

**1 Sep 2026. DESIGN ONLY. NO CODE WRITTEN. NOTHING APPROVED.**

Accepted going in: **not a persistence bug.** The chain is live and the original
fix is withdrawn. The question is what, if anything, this signal should be.

---

## 1. Current product behaviour — THREE surfaces, not one

The learned `danger_hours` reaches the trader in three places. Any decision has
to cover all three, because demoting the detector alone would leave two of them
making the same claim.

### (a) The detector — `time_of_day_bias`

`alerting`, `notification_level=1`, `caution`. Message:

> *"Entered NIFTY…CE at 12:04 — historically your 12 PM hour runs a 30% win rate
> over 68 trades (avg −₹261)."*

**Cites its sample.** Hour, rate, n, average. The most honest of the three.

### (b) The dashboard — `PredictiveContextStrip.tsx`

Live, proactive, on the dashboard:

> **"Danger hour"** — *"You historically lose at 14:00. Trade smaller or wait it
> out."*

Three problems in one sentence:

* **It prescribes.** *"Trade smaller or wait it out"* is an instruction. The
  product's stated philosophy is *"Mirror, not blocker — show traders facts about
  their behaviour, not restrictions."*
* **It cites nothing.** No n, no win rate, no average. The detector's own message
  is strictly more honest than the dashboard's.
* **It uses browser-local time.** `new Date().getHours()` against IST-derived
  hours. For a trader outside IST the hour compared is simply the wrong one.

### (c) The API — `/api/personalization/insights` and `/time-patterns`

Return `danger_hours`, `danger_days`, `best_hours`, `best_days`,
`hourly_breakdown`, `daily_breakdown`. `danger_days` applies the **same
methodology** to weekdays, and has never been validated at all.

---

## 2. What the evidence supports

**That the phenomenon can be measured.** Hourly win rate and average P&L per hour
are computable from data we have, with real sample sizes, and the 90-day nightly
refresh works.

**That in this book, one hour looks bad in aggregate.** 12:00 — 68 trades, 29.9%
win rate against a 39.5% book rate, −₹261 average. Taken alone that is a real
observation about the past.

**That flagged trades did worse in aggregate.** 29.1% win against 40.8%, mean
−₹295 against −₹23. Directionally consistent.

That is the whole of it.

---

## 3. What the evidence does NOT support

### It does not support calling any hour "dangerous"

| period | hours flagged |
|---|---|
| full book | 12, 15 |
| first half | 11, 12, 15 |
| **second half** | **none** |
| **both halves** | **NONE** |

Quarters: `[9,11]`, `[11,12,15]`, `[12,13]`, `[]`. **Five hours, four quarters,
zero persistence.**

**p(chance flags ≥ 2 hours) = 0.314** under label shuffling — the real result is
the single most likely outcome under noise.

### It does not support the descriptive display either — and this is the new finding

The obvious fallback is "drop the classification, just show the numbers". **The
numbers are not stable either.**

| hour | n H1 | win H1 | n H2 | win H2 | shift |
|---|---|---|---|---|---|
| 9 | 89 | 38.2% | 121 | 39.7% | +1.5 |
| 10 | 109 | 39.4% | 99 | 42.4% | +3.0 |
| **11** | 53 | **28.3%** | 51 | **52.9%** | **+24.6** |
| **12** | 35 | **22.9%** | 33 | **36.4%** | **+13.5** |
| 13 | 48 | 39.6% | 41 | 34.1% | −5.4 |
| 14 | 18 | 50.0% | 30 | 60.0% | +10.0 |
| **15** | 11 | **18.2%** | 2 | **50.0%** | **+31.8** |

**Spearman rho between the two halves' hourly rankings = +0.071.** The hours that
look worst in the first half tell you essentially nothing about the second.

So *"in the last 90 days you traded 68 times at 12:00 and won 30%"* is a true
statement about the past — but presenting it as a **pattern**, in a product whose
purpose is to show traders their patterns, implies a persistence the data does
not have.

### It does not support the current sample gate

95% CI half-width on a win rate near 40%:

| n per hour | ±CI | can it separate 30% from 40%? |
|---|---|---|
| **5** *(the producer's gate)* | **±42.9pp** | **no** |
| 13 *(the 15:00 hour)* | ±26.6pp | no |
| 50 | ±13.6pp | no |
| 68 *(the 12:00 hour)* | ±11.6pp | **no** |
| 100 | ±9.6pp | yes |
| 200 | ±6.8pp | yes |

At **n = 5** the interval is **±43 points** — wider than the entire plausible
range of win rates. **Even 12:00's 68 trades cannot separate 29.9% from 39.5%.**

Only hours **9 and 10** (n = 210 and 208) carry enough data for a claim at all,
and neither is flagged.

---

## 4. Minimum sample and history — what the evidence will and will not fix

**The arithmetic is not a judgement:** roughly **n ≈ 100 trades in that hour** is
needed before a 10-point difference in win rate is distinguishable from noise.
That is a confidence-interval property, not a threshold I chose.

**Choosing the required precision IS a judgement, and I am not making it.**
Whether the product wants ±10pp, ±5pp or something else determines the gate, and
nothing in this book decides it.

**And a sample gate alone would not fix this.** Even at adequate n the ranks do
not persist between halves (rho = 0.071). A larger sample makes each estimate
tighter; it does not make an unstable phenomenon stable. **Any credible gate
would need a persistence test across periods, not just a count** — and I have no
evidence for what that test's parameters should be.

**Honest summary: the evidence does not support a minimum sample that would make
the current methodology sound.** It supports the conclusion that n ≥ 5 is far too
small, and it does not identify a larger number that would be enough.

---

## 5. Recommended product behaviour

**The classification must go.** *"Danger hour"* is not supportable in any surface,
at any severity, on this evidence.

Beyond that, two coherent positions. **I lean strongly to B.**

### A — descriptive statistics, no classification

Keep `hourly_breakdown` as an analytics surface: hour, trade count, win rate,
average P&L, **with the sample size always visible and no hour marked**. Delete
`danger_hours` / `best_hours` from every consumer.

*For:* the numbers are true about the past; a trader can look for themselves.
*Against:* rho = 0.071 means the display invites a pattern reading that is not
there, and a product whose whole promise is "show me my patterns" showing an
unstable one is a subtle lie of context.

### B — remove the hour signal from the product, keep the computation

Stop surfacing hour-of-day anywhere: retire `time_of_day_bias`, remove the
"Danger hour" strip item, and stop returning `danger_hours` / `best_hours` from
the API. Leave `_learn_time_patterns` computing and storing, so the data is
there if a future evidence pass can establish stability.

*For:* it is the only option consistent with the measurements. Nothing is shown
that the data cannot support, and nothing is thrown away.
*Against:* removes a feature that currently exists, on one trader's book.

**Why I lean B:** the difference between A and B is whether a trader can be shown
an unstable number in a context that implies stability. Every surface we have —
detector, dashboard strip, insights API — is a "here is your pattern" context.
There is no neutral place to put it, and A would require inventing one.

---

## 6. Exact implementation changes — if B is approved

| # | file | change |
|---|---|---|
| 1 | `behavior_engine.py` | retire `_detect_time_of_day_bias`, with the evidence in the retirement note |
| 2 | `detector_registry.py` | remove `DetectorSpec` + `PatternCopy`; keep the display name for stored rows |
| 3 | `trading_defaults.py` | remove `tod_bias_min_sessions` (30) |
| 4 | `threshold_resolution.py` | remove the `danger_hours` put (2 sites incl. cold start) |
| 5 | **`PredictiveContextStrip.tsx`** | remove the `danger_hour` item — **and this is the one that matters most**, because it prescribes and cites nothing |
| 6 | `api/personalization.py` | stop returning `danger_hours` / `best_hours` from `/insights` and `/time-patterns` |
| 7 | `AlertContext.tsx` | remove routing; keep display name |
| 8 | tests | retirement suite; counts 17 → 16 detectors, 23 → 22 pattern types |

**Untouched:** `_learn_time_patterns` keeps computing and storing; the nightly
beat, the 90-day window and `detected_patterns` persistence are all unchanged.

**Expected firing impact: zero on this book** — the detector already fires 0 in
replay for want of a profile. For real traders with 30+ sessions it removes the
81-equivalent alerts and the dashboard strip item.

---

## 7. Unresolved decisions — yours, not mine

1. **A or B.** The measurements support B; A is defensible if the product wants
   the data visible with heavy caveats.
2. **`danger_days` has never been validated.** Same methodology, weekdays instead
   of hours, five tests instead of seven, same `<35% / n≥5` filter. It feeds the
   same dashboard strip. **Whatever is decided for hours should almost certainly
   apply to days — but I have not measured days**, and I am not assuming.
3. **`best_hours` / `best_days`** are the mirror image, presumably with the same
   instability, also unmeasured.
4. **The `PredictiveContextStrip` browser-local-time bug** is a defect regardless
   of A or B — it compares IST-derived hours against `new Date().getHours()`.
   If A is chosen it must be fixed; if B, it disappears with the item.

---

## 8. Confirmations

**`win_rate_collapse` — untouched.** KEEP AS-IS stands. Nothing in this pass
reads, changes or implicates it.

**`strategy_breakdown` — untouched.** DEFER stands, with its unblock condition
unchanged: sessions where the win-rate and profit-factor conditions disagree.

**No other detector is implicated.** The only shared surface is
`detected_patterns`, and the `baseline` key that 26/27 depend on is written by a
different service on a different path.

---

## 9. Final recommendation

**Approve B — remove the hour signal from every trader-facing surface, keep the
computation.**

Not because the subject is uninteresting: time-of-day effects are real in
markets and plausible in traders. Because on the only book we have, **this
implementation cannot tell one from noise** — the classification does not survive
into a second period, chance reproduces it 31% of the time, the descriptive ranks
correlate at 0.071, and the sample gate is twenty times too small.

**And because the worst of the three surfaces is the one nobody reviewed.** The
detector at least shows its working. The dashboard says *"You historically lose
at 14:00. Trade smaller or wait it out"* — a prescription, with no evidence
attached, on the wrong clock, derived from a signal measured here as chance.
That sentence should not survive this pass whatever is decided about the
detector.

**If A is preferred instead**, the minimum I would want before shipping it: the
sample size shown beside every number, no hour marked or ranked, and the copy
saying what the data says — *"in the last 90 days"* — rather than
*"historically"*.
