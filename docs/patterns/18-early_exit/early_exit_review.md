# Pattern 18 — `early_exit`

**Review, 30 Aug 2026. Findings only. No code changed.**

Review-order 18. Source-list **#14**, recorded as *"IMPLEMENTED, evidence-only ·
**declared `trigger: session` but runs per trade**"*.

Measured against the real book — **175 sessions, 740 rounds** — running the real
detector in process.

---

## First: can we ever know an exit was "early"?

The question this detector exists to answer, and worth stating plainly because
it decides the verdict.

**Per trade: no. Not ever.** "Early" means *before the plan said to leave*, and
we observe neither the plan nor what the price did afterwards. A winner closed
at +₹800 that would have run to +₹4,000 and one that would have reversed look
identical in our data.

**Across trades: yes, and there is a standard, documented measure.** The
**disposition effect** — cutting winners early while letting losers run — is
measured exactly as this detector measures it: **average winner hold against
average loser hold**. It is long-established behavioural finance (Shefrin &
Statman 1985; Odean 1998, *"Are Investors Reluctant to Realize Their Losses?"*),
not something invented here.

So the detector's *concept* is right, and your instinct — *"maybe in analytics
we can add hold time of winning trade, hold time of losing trade"* — is the same
answer. **The problem is not the measure. It is the sample size it is computed
over**, and §Problems 2 shows that precisely.

One thing that would answer the question better and that we **cannot** do today,
recorded rather than proposed: **MFE / MAE** — how far the position went in your
favour after you left. That needs intraday price paths per position, which we do
not store.

---

## Current behaviour

Fires on a **winning** trade when, across the session so far:

```
winners >= 3  AND  losers >= 3                       (early_exit_min_samples)
avg_winner_hold < avg_loser_hold * 0.40              (early_exit_ratio)
avg_winner_hold < 60 min                             (early_exit_winner_max_min)
```

| | |
|---|---|
| registry | `nature=performance`, `disposition=analytics`, **`trigger=session`**, v2.0.0, `notification_level=0` |
| severity | **always `info`** — hardcoded |
| consumes | `session_trades`, `completed_trade`, `thresholds` |
| evidence | both averages, both counts, the ratio |
| confidence | none set |
| message | *"Today's pattern: winners held 5min avg, losers held 19min avg (3.4× longer). Winners are being closed faster than losers."* |

| threshold | value | classified? |
|---|---|---|
| `early_exit_ratio` | 0.40 | **`PERSONAL_BASELINE`**, maturity `NONE`. Provenance: *"ALREADY self-relative — it divides the trader by themselves. Only the 0.40 is a judgement, and that is detector-review evidence work"* |
| `early_exit_winner_max_min` | 60 | **`PERSONAL_BASELINE`**, `Source.HISTORY`, metric `winner_hold_p50`, maturity `TRADES_20` |
| `early_exit_min_samples` | 3 | **not in `THRESHOLD_SPECS`** |

---

## What is correct

**It measures the right thing, and it is the only thing measurable.** See above.

**It refuses to judge a single trade.** It requires ≥3 winners *and* ≥3 losers
before saying anything. Most detectors here have no sample gate at all; this one
was built knowing a single exit proves nothing.

**The message is purely factual.** It reports both averages, both counts and the
ratio, and stops. No claim about intent, no "you panicked", no "you left money
on the table". Compare `panic_exit`, retired for exactly the opposite.

**`early_exit_ratio` is genuinely self-relative** — it divides the trader by
themselves, which the design of record holds up as the model other thresholds
should follow.

**It is pure.** 44 lines, no database, no wall clock.

---

## Problems found

### 1. The disposition effect is not present in this book

| | n | mean hold | median |
|---|---|---|---|
| winners | 276 | **41.0 min** | 18 min |
| losers | 413 | **36.7 min** | 16 min |

**Ratio 1.12 — this trader holds winners *longer* than losers.** The detector's
subject is the opposite of what the book shows.

That is a fact about this trader, not proof the concept is wrong. But it means
every firing below is a session-level deviation from the trader's own contrary
habit.

### 2. At session sample sizes the measure is noise — shuffle null, p = 0.610

The three firings, and the samples they were computed from:

```
2025-08-14   winners n=3  avg  5.7min   losers n=4  avg 19.0min   ratio 3.4x
2025-08-14   winners n=4  avg  4.8min   losers n=7  avg 17.7min   ratio 3.7x
2025-12-24   winners n=5  avg 12.6min   losers n=3  avg 35.7min   ratio 2.8x
```

Three to five samples per side. Shuffling the win/loss labels **within each
qualifying session**, holding the hold-times fixed:

| | |
|---|---|
| sessions below 0.40 in the real labelling | **4 of 20** |
| p(shuffled ≥ observed), 20,000 runs | **0.610** |

**Indistinguishable from chance.** The same test that retired `size_escalation`.
This is not a threshold that needs tuning — at n=3 the ratio of two small means
is unstable by arithmetic, and no value of `early_exit_ratio` fixes that.

### 3. The sample gate excludes 89% of sessions, and raising it removes the detector

| `min_samples` | sessions qualifying |
|---|---|
| 2 | 53 / 175 (30%) |
| **3 (current)** | **20 / 175 (11%)** |
| 4 | 9 / 175 (5%) |
| 5 | 3 / 175 (2%) |

The gate is correct in principle and is the binding constraint in practice. But
the sample size needed for stability is **larger than an intraday session
provides** — so tightening it toward statistical validity tightens it toward
never firing.

`early_exit_min_samples` also has **no `THRESHOLD_SPECS` record**, unlike the
other two.

### 4. `trigger="session"` is declared and not honoured

The engine branches on `spec.trigger == "entry"` only. Everything else,
including `session`, falls through to the per-trade exit loop. So a session-level
finding is recomputed and re-emitted on **every winning trade after the
condition first holds** — 1.5 events per firing session here, max 2. The March
note is still live.

### 5. `early_exit_winner_max_min` can never personalise

It is declared `PERSONAL_BASELINE`, `Source.HISTORY`, `metric="winner_hold_p50"`,
`Maturity.TRADES_20`. **`winner_hold_p50` is never produced.** `baseline_service`
emits `avg_winner_hold_min`, `avg_loser_hold_min`, `median_reentry_after_loss_min`
and six others — no `winner_hold_p50` anywhere in the codebase.

So the threshold sits at its 60-minute fallback permanently while declaring
itself personalised. **Same class as the H1 key-name mismatch** already found and
fixed once in the baseline work.

Its ceiling also **excluded 0 of 3** firings here, so it is untested on this book
in either direction.

### 6. The right measurement already exists, over the right sample, and is unconsumed

`baseline_service` computes **`avg_winner_hold_min`** and **`avg_loser_hold_min`**
across the trader's full history, each with a confidence and a target sample
size. Over the book that is **276 winners and 413 losers** — not three and four.

**Nothing reads them.** Grep across `app/` and `src/`: produced by
`baseline_service`, referenced by `session_state`, consumed by no analytics
endpoint and no screen.

So the measure the detector approximates badly at session scope is already
computed well at history scope, and then discarded.

---

## Evidence

| question | answer | strength |
|---|---|---|
| is the disposition effect present? | **no** — winners 41.0 min vs losers 36.7 min, ratio 1.12 | measured, n=689 |
| does it fire? | **3 events / 2 sessions** in 175 | measured |
| are the firings real? | **no** — shuffle null **p = 0.610** | measured, 20k permutations |
| is the sample gate binding? | **yes** — 89% of sessions excluded at n=3 | measured |
| is `trigger=session` honoured? | **no** | verified |
| can `early_exit_winner_max_min` personalise? | **no** — its metric is never produced | verified |
| does the 60-min ceiling do work? | **excluded 0 of 3** — untested | measured |
| is it pure? | yes | verified |
| does it overlap? | all 3 firings co-fire with something else | measured |

**What the evidence cannot say:** whether a trader who *does* exhibit the
disposition effect would be served by this. The book contains the opposite
habit, so this is one trader's answer to "is it present", not to "does the
detector work when it is".

---

## Recommended behavioural contract

> **Subject.** The asymmetry between how long this trader holds winners and how
> long they hold losers. **Not** whether any individual exit was early — that is
> unobservable and must never be claimed.
>
> **Requires a sample large enough for the ratio of two means to be stable.** An
> intraday session does not provide one: at 3–5 trades per side the measure is
> indistinguishable from chance (p = 0.610). The trader's **history** does.
>
> **Reports, never interprets.** Both averages, both counts, the ratio. No claim
> about intent.
>
> **Says nothing when the sample is too small** — which, at session scope, is
> almost always.

---

## Exact changes required

**None safe to make at session scope**, because the problem is sample size, not
configuration. Three defects are unambiguous and independent of the verdict:

1. **`trigger="session"` is not honoured** — either the engine respects it or
   the spec should stop claiming it. Recorded; it affects other session-trigger
   detectors too, so it is **not** an `early_exit` fix.
2. **`early_exit_winner_max_min` declares a metric nothing produces.** Either
   `winner_hold_p50` gets produced or the spec should name
   `avg_winner_hold_min`, which exists. Until then it is a `PERSONAL_BASELINE`
   that is permanently global.
3. **`early_exit_min_samples` has no `THRESHOLD_SPECS` record.**

Recorded for later, **not** fixed here: `baseline_service`'s
`avg_winner_hold_min` / `avg_loser_hold_min` are computed and consumed by
nothing.

---

## Verdict — **MODIFY**, and the likely destination is retirement in favour of analytics

**Not KEEP AS-IS.** p = 0.610 means the three firings carry no information, and
a `PERSONAL_BASELINE` threshold that can never personalise is a defect whatever
else is decided.

**Not DELETE outright**, and this is where it differs from `panic_exit`. That one
was retired because its subject did not exist — short holds performed the same
as long ones. Here the **subject is real and documented**; what fails is the
scope it is computed at. Deleting the detector should not read as deleting the
question.

**Not RESEARCH FURTHER.** The evidence is sufficient: the measure is sound, the
session sample is not, and the history sample already exists.

**The modification, and the decision it needs from you.** Two coherent forms:

- **(a) Keep it session-scoped and honour `trigger=session`,** firing once per
  session rather than per winning trade, with a sample gate raised until the
  ratio is stable. The book says that gate lands at 4–5, which leaves **3–9
  qualifying sessions out of 175** — it would fire approximately never.
- **(b) Retire the detector and surface the history measure instead.**
  `baseline_service` already computes `avg_winner_hold_min` and
  `avg_loser_hold_min` over 276 and 413 trades, with confidence, and nothing
  reads them. This is your original instinct, and the sample size is the reason
  it is the right one.

**I recommend (b)** — but it is half a product decision, because it moves a
behavioural finding into an analytics surface that does not exist yet, and I am
not making that call unprompted. **(a) is honest but produces a detector that
fires roughly once a year.**

The three defects listed above should be fixed regardless of which form is
chosen, and two of them are not `early_exit`'s alone.
