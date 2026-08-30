# Pattern 19 — `winning_streak_overconfidence`

**Review, 30 Aug 2026. Findings only. No code changed.**

Review-order 19. Source-list **#15**, recorded as *"IMPLEMENTED, danger tier
never fired — 0 in 203 sessions"*.

Measured against the real book — **175 sessions, 740 rounds** — running the real
detector in process. Scripts: `docs/patterns/_measurement/p19_streak.py`,
`p19b.py`.

---

## Current behaviour

Fires on a completed trade when **both** halves hold:

```
A.  the last N session exits (ANY instrument) all won
B.  this position is >= M x the average size of prior trades

    danger   N = 5,  M = 2.0     (overconfidence_win_streak_danger / _size_mul_danger)
    caution  N = 3,  M = 1.3     (overconfidence_win_streak_caution / _size_mul_caution)
```

A 5-win streak whose size misses 2.0× falls through to the caution test.

| | |
|---|---|
| registry | `1.1.0`, `nature=emotional`, `disposition=alerting`, `trigger=exit`, `notification_level=1`, **`uses_baseline=True`** |
| severity | `danger` or `caution` — **never `info`** |
| consumes | `session_trades`, `completed_trade`, `thresholds`, `instrument_parser` |
| evidence | streak length, streak profit, baseline, current size, escalation %, underlying, and the full list of streak trades |
| confidence | **none set** — it inherits the engine's data-quality default (100/75/50) |
| also wired into | `danger_zone` **caution** set; `ENTRY_DECIDABLE`; the Reports label map |

**The size baseline has two different units, chosen silently.**

```python
_cross = len(prior_same) < 2
```

With fewer than two prior trades on the same underlying it compares **rupees of
notional**; otherwise it compares **contracts**. The same 1.3 and 2.0 multipliers
are applied to both.

| threshold | value | `THRESHOLD_SPECS`? |
|---|---|---|
| `overconfidence_win_streak_caution` | 3 | **DEFINITIONAL**, no maturity. *"three wins in a row is a definition, not a claim about what is normal"* |
| `overconfidence_win_streak_danger` | 5 | **DEFINITIONAL**. *"as above"* |
| `overconfidence_size_mul_caution` | 1.3 | **none** |
| `overconfidence_size_mul_danger` | 2.0 | **none** |

---

## What is correct

**It is pure.** No database, no wall clock, no `await`. Reads only the context it
is handed. Verified by inspection of all 122 lines.

**It withholds.** 28 trades met condition A with a usable baseline; it fired on
**6**. It declines on 79% of what it could judge — the opposite of the Pattern 9
failure, where a detector fired on 55 of 55.

**The `DEFINITIONAL` classification of the streak lengths is right, and the
provenance note is the best one in the registry.** Personalising a streak length
would mean a trader with many streaks needs a *longer* one before anyone
mentions it. That reasoning is sound and should survive this review whatever
else happens.

**F23 is correctly fixed here.** `if avg_baseline and ...` — a zero baseline is
treated as no baseline, not as a small one.

**F22 was correctly *not* applied here.** `test_f22_left_the_reachable_cross_branch_in_the_other_detector_alone`
pins the distinction: `size_escalation`'s `_cross` was dead, this one is
reachable. That test did its job.

**The copy makes no unsourced claim.** `PatternCopy` is *"Size up after wins /
Position size after a run of winning trades, against your session average /
Size raised because recent trades worked is size raised on a sample, not on an
edge."* Factual, no statistic. **This is NOT the `expiry_day_overtrading`
failure** — see Problem 5 for the distinction.

**It has tests** — 4 behavioural in `TestWinningStreakOverconfidence`, 2
structural in `test_f_cleanup_regressions`. `test_danger_at_five_wins_and_2x`
passes, so the danger tier is reachable *in principle*.

---

## Problems found

### 1. THE DECIDING TEST FAILS, AND THE DIRECTION IS BACKWARDS

The detector's claim is not "the trader had a winning run" and not "this
position is large". It is that **the run is why the size went up**. That is
directly measurable.

| | n | P(size ≥ 1.3× baseline) |
|---|---|---|
| after a 3+ win run | 28 | **21.4%** |
| every other comparable trade | 263 | **30.4%** |

**Sizing up is LESS likely after a winning run than at any other time.**
Label-permutation null on the difference: **p = 0.890**.

And it is not a single noisy cut. Across run lengths:

| preceding win run | n | median ratio | mean ratio | P(≥1.3×) |
|---|---|---|---|---|
| 0 | 165 | 1.00 | 1.47 | 32.1% |
| 1 | 61 | 1.00 | 1.25 | 27.9% |
| 2 | 37 | 1.00 | 1.09 | 27.0% |
| 3 | 21 | 1.00 | 1.07 | 28.6% |
| 4 | 6 | 0.63 | 0.55 | **0.0%** |

**Spearman rho(run length, size ratio) = −0.076, p = 0.902.** The detector's
theory predicts a positive correlation.

### 2. The sizing response to a run DOES exist — pointing the other way

The mirror measurement, and the reason Problem 1 is a finding about the trader
rather than an absence of data:

| preceding LOSS run | n | median ratio | mean ratio | P(≥1.3×) |
|---|---|---|---|---|
| 0 | 131 | 0.94 | 1.12 | 26.0% |
| 1 | 74 | 0.99 | 1.06 | 28.4% |
| 2 | 36 | 0.93 | 1.18 | 30.6% |
| 3 | 30 | 1.00 | 1.29 | 40.0% |
| 4 | 13 | 1.33 | 5.53 | **53.8%** |

**This trader sizes up after LOSSES, monotonically, and sizes down after wins.**
The behaviour the detector was built to catch is real in this book — inverted.
**That inverted behaviour is `martingale_behaviour`'s subject, and it already
covers it.**

### 3. The shuffle null — p = 0.582

The standing test for an ordering claim, run against the real detector:

| | |
|---|---|
| real trade order | **6 firings** |
| shuffled order, 2,000 permutations | mean **6.2**, median 6, range 0–15 |
| p(shuffled ≥ real) | **0.582** |

Destroying the link between the run and the size changes nothing. The same test
retired `size_escalation` (p = 0.880) and `early_exit` (p = 0.610).

### 4. The danger tier is not "correctly silent" — it is unreachable on this book

Confirmed: **0 danger events in 175 sessions.** The reason matters.

| | |
|---|---|
| trades with a 5-win run behind them | **1 of 740** |
| ...and size ≥ 2.0× baseline | **0** |

The book's win rate is 39.5%. Under independence P(5 in a row) = 1.0%; observed
is 0.1%. **The gating condition is the rare one, and it is the half with no
evidence behind it.**

Meanwhile the *size* half of the danger tier was satisfied twice — firings at
ratio **2.22** and **2.65** — and both emitted `caution`, because the streak was
3 rather than 5. The tier that never fires is blocked by the condition that
does not predict anything.

### 5. The threshold comment states an unsourced statistic, and the values contradict it

```python
# "Hot hand fallacy": after 3 wins, retail traders increase size 40-80%.
```

`trading_defaults.py:244`. **No source anywhere in the repository.** Grep finds
this line and one paraphrase in the engine; no study, no dataset, no link.

**The distinction from `expiry_day_overtrading` matters and is in this
detector's favour: that one shipped its unsourced statistics to the trader.
This one does not — the alert copy carries no statistic.** It is a code comment
justifying a constant, not a claim made to a user.

But it is the *only* stated justification for 1.3 and 2.0, and **the values do
not match it.** A "40–80% increase" is 1.4× to 1.8×. The caution multiplier is
**1.3** — below the claimed range — and the danger multiplier is **2.0**, above
it. Neither endpoint of the cited range is a threshold.

**Neither multiplier has a `THRESHOLD_SPECS` record.** Same gap as
`early_exit_min_samples`.

### 6. Three of six alerts print rupees labelled "qty"

The message is written once and used by both branches:

```
({avg_baseline:.0f}→{current_qty} qty)
```

On the `cross` branch those are **notional rupees**. Real firings:

```
[cross] NIFTY position jumped 54% above your session average (4235→6525.0 qty).
[cross] NIFTY position jumped 122% above your session average (10556→23484.4935 qty).
[cross] BANKNIFTY position jumped 165% above your session average (8711→23119.5 qty).
```

**23,484.4935 "qty"** of a NIFTY option. Three of the six firings — half — show
a rupee figure with four decimal places labelled as a contract count. The
`context` block repeats it in `avg_baseline_qty` and `current_qty`.

**This is the exact defect the 24 Aug hygiene pass fixed in `size_escalation`**
(H0 finding #4: *"computed `cross` and never read it, so a rupee sequence prints
as qty"*). It was fixed there and left here.

Branch split across all eligible trades: **198 cross, 93 same** — so the rupee
branch is the majority path, not an edge case.

### 7. `uses_baseline=True` is false

The spec declares it. The detector reads no baseline — its "baseline" is an
average over today's session trades, computed inline. `uses_baseline` has **zero
readers** in the codebase, so nothing breaks; it is a declaration that is simply
untrue.

**Same class as `early_exit_winner_max_min` naming a metric nothing produces** —
already recorded in `PENDING_AND_TODO.md` as needing a contract test over the
declarations rather than a one-off correction. This is the second instance.

### 8. It has never sent a notification, and cannot

`NOTIFIABLE = {"danger", "critical"}` (`core/severity.py:28`). This detector has
emitted `caution` 6 times and `danger` never, so **in 175 sessions it has
produced zero notifications.**

It is not invisible — `caution` writes a `RiskAlert` and raises `danger_zone` to
CAUTION, which `rapid_reentry`'s `info` could not. So it reaches the Alerts
screen and the danger-zone banner. But its `notification_level=1` has never been
exercised.

### 9. It sets no confidence

Every returned event leaves `confidence` unset, so the engine substitutes a
**data-quality** default (GOOD 100 / PARTIAL 75 / UNKNOWN 50). The number a
trader-facing surface reads as this detector's confidence is a property of the
data pipeline, not of the evidence. `revenge_trade` uses
`confidence.from_observables` instead.

Consequence at entry time: it is in `ENTRY_DECIDABLE`, and `above_entry_floor`
requires ≥ 60. With GOOD data it clears at 100 — on the strength of the pipeline
alone. (`above_entry_floor` is read only by `summarise_entry_evaluation`, for
logging and replay reporting, so this is not a live gate today.)

---

## Evidence

| question | answer | strength |
|---|---|---|
| does it fire? | **6 events / 6 sessions** of 175, all `caution` | measured |
| has `danger` ever fired? | **no** — only 1 trade of 740 ever had a 5-win run, and it was under 2.0× | measured |
| does a winning run predict sizing up? | **no, the reverse** — 21.4% vs 30.4%, rho = −0.076 | measured, n=291 |
| is that monotone? | **yes** — 32.1% → 27.9% → 27.0% → 28.6% → 0.0% | measured |
| does the trader size up after LOSSES? | **yes, monotonically** — 26.0% → 53.8% | measured, n=284 |
| do the firings survive the shuffle null? | **no** — p = 0.582 | measured, 2,000 permutations |
| does it withhold? | **yes** — 22 of 28 (79%) | measured |
| is the message unit correct? | **no** — 3 of 6 print rupees as "qty" | measured |
| does it overlap? | **no** — fired ALONE on **6 of 6 (100%)** | measured |
| consequence? | **insufficient** — flagged mean −₹392 vs −₹162, p = 0.243; flagged won 66.7% vs 22.7% | measured, n=6 |
| is it pure? | **yes** | verified |
| are the multipliers sourced? | **no** — and they contradict the one comment that justifies them | verified |

**What the evidence cannot say.**

- **n is small.** 28 trades after a 3+ win run, 6 at run length 4, 1 at run
  length 5. The direction is consistent and monotone, but a 28-trade sample
  cannot exclude a modest real effect.
- **One trader.** Overconfidence after wins is genuine literature (Barber &
  Odean on overconfidence; Statman, Thorley & Vorkink on volume after returns).
  This book says *this* trader does the opposite. It does not say the concept is
  wrong for everyone. **Unlike `panic_exit`, whose subject failed on its own
  terms, this is a subject that is real in general and absent here.**
- **The 6 consequence trades decide nothing** and are not offered as a reason.

---

## Recommended behavioural contract

> **Subject.** Raising position size *because* a run of trades worked — size
> justified by a sample rather than by an edge.
>
> **Requires the run to predict the sizing.** Both halves occurring is not the
> pattern; traders have winning runs and traders vary size. If the size
> distribution after a run is indistinguishable from the size distribution at
> any other time, there is nothing to report.
>
> **One unit, named honestly.** Contracts or rupees, never a rupee figure
> labelled "qty".
>
> **Says nothing when the trader's actual response to a run is the opposite** —
> which, in this book, it is, and which `martingale_behaviour` already covers.

---

## Exact changes required

Three defects are unambiguous and hold whatever is decided about the detector:

1. **The `cross` branch prints rupees labelled "qty"**, in the message and in
   `context`. Half the firings and the majority path. Already fixed once in
   `size_escalation`.
2. **`uses_baseline=True` is false.** Second instance of an unchecked spec
   declaration; belongs with the `THRESHOLD_SPECS` contract-test item already in
   the pending register rather than as a one-off.
3. **`overconfidence_size_mul_caution` / `_danger` have no `THRESHOLD_SPECS`
   record**, and the comment that justifies them cites 40–80% while the values
   are 30% and 100%.

**No replacement multiplier is proposed.** The measurement says the gate is
aimed the wrong way, not that 1.3 is the wrong number, and inventing a value
would be fixing the wrong thing.

---

## Verdict — **DELETE**

**Not KEEP AS-IS.** Shuffle null p = 0.582 means the six firings carry no
information about ordering, the deciding test runs backwards and monotonically,
and half the alerts print a rupee figure as a contract count.

**Not MODIFY.** There is no threshold change that fixes it. The failure is not
calibration — the conditioning variable has the wrong sign. Tuning 1.3, or
lowering the danger streak to make that tier reachable, would produce more
firings of a rule whose premise this book contradicts.

**Not RESEARCH FURTHER.** The measurement that would settle it has been run:
size after a win run, size after a loss run, both across run lengths, plus the
shuffle null and a label permutation. More of this book will not change the
sign.

**Not DEFER.** Nothing is blocking. Unlike Pattern 16 the detector is live,
measurable and measured.

**DELETE**, with three things recorded so the deletion does not read as bigger
than it is:

- **The behaviour it names is covered, inverted, by `martingale_behaviour`** —
  which this trader actually does (P(size ≥1.3×) rises 26% → 54% with loss-run
  length). Nothing about this trader's sizing goes unwatched.
- **The concept is not retired permanently.** Overconfidence after wins is real
  literature. This is one trader's answer to *"is it present"*, not an answer to
  *"does the detector work when it is"* — the same qualification recorded for
  `direction_instability`'s Level 1.
- **100% unique coverage is the one argument against deleting** and should be
  stated plainly: it fired alone on 6 of 6, so those 6 alerts disappear rather
  than being absorbed. Six non-notifying `caution` alerts across 175 sessions,
  whose firings are indistinguishable from shuffled order.

The `DEFINITIONAL` classification of the streak lengths — *"personalising a
streak length gives the absurd result that a trader with many streaks needs a
longer streak before anyone mentions it"* — is the best provenance note in the
registry and should be preserved in the retirement record.

---

## Recorded, NOT fixed here

Per the standing instruction, these go to `PENDING_AND_TODO.md`:

- **An orphaned comment block in `trading_defaults.py:253-255`** — the *"Early
  exit (disposition effect)"* header and its two SEBI claims survive, but the
  three keys beneath them went with Pattern 18. **This is leftover from my own
  retirement commit `13755b4`**, not a pre-existing defect.
- The unsourced *"Hot hand fallacy: after 3 wins, retail traders increase size
  40-80%"* comment, if the detector somehow survives.
- The `uses_baseline` / `THRESHOLD_SPECS` declaration-checking contract test —
  now with two known instances.
