# Pattern 23 — `post_loss_recovery_bet`

**Review, 1 Sep 2026. Findings only. NO CODE CHANGED.**

Review-order 23. Source-list **#21**, recorded as *"IMPLEMENTED, NOT TESTED —
zero test mentions, near-zero evidence"*.

Reviewed **alone**. It shares no mechanics with Pattern 21/22 — the "review them
together" line in the brief was carried over from that pair's template. One
detector, one verdict.

Measured against the real book — **175 sessions, 740 rounds** — running the real
detector in process. Script: `docs/patterns/_measurement/p23_recovery.py`.

---

## The behaviour it claims

> *"After 2+ consecutive losses, trader enters one significantly oversized
> position. 'I'll make it all back in one trade' — the most documented bias in
> retail trading. Different from martingale (progressive escalation) — this is a
> single outsized bet."*

That last sentence is a testable claim about **distinctness**, and §2 tests it.

---

## Current behaviour

Fires on a completed trade when all of:

```
1.  >= 3 trades in the session so far                      (session_trades, OCCURRED)
2.  >= 2 CONCLUDED priors on the SAME underlying           (concluded_before_entry)
3.  the last TWO of those both lost
4.  current qty >= M x the mean qty of the last THREE priors
        caution  M = 2.0     danger  M = 3.0
```

| | |
|---|---|
| registry | `1.1.0`, `nature=risk`, `disposition=alerting`, `trigger=exit`, `notification_level=2` |
| severity | `danger` ≥ 3.0×, `caution` ≥ 2.0× |
| consumes | `session_trades`, `concluded_before_entry`, `completed_trade`, `thresholds` |
| evidence | size ratio, current qty, avg recent qty, total prior loss, underlying, and the last three prior trades with symbol/qty/pnl/exit time |
| confidence | **none set** |

| threshold | value | `THRESHOLD_SPECS`? |
|---|---|---|
| `recovery_bet_caution_mul` | 2.0 | **none** |
| `recovery_bet_danger_mul` | 3.0 | **none** |

Copy: *"Recovery bet / A position materially larger than your average, entered
after a loss on the same underlying. / If this one also loses, the combined loss
exceeds everything it was meant to recover."*

---

## What is correct

**This is the strongest detector reviewed in this sequence, and it is worth
saying so plainly after ten retirements.**

### It is NOT selected on outcome

**4 of its 7 flagged trades WON.** It fires on the size decision regardless of
how the trade turned out.

That is the structural property `panic_exit`, `opening_5min_trap` and
`options_premium_avg_down` all lacked — each of them could only distinguish a
"bad" case from an ordinary one by looking at the result, and each was retired
for it. This one separates behaviour from result by construction.

### Its gates genuinely withhold

```
>= 3 session trades                       291
>= 2 CONCLUDED priors on same underlying    88
...last two both losses                     29
...and size >= 2.0x                          7
```

The size gate declines **22 of 29 (76%)** of trades that already satisfy the
loss condition.

### The multiplier is not decoration — measured against the actual distribution

Size ratio after two same-underlying losses, n = 29:

| p10 | p25 | median | p75 | p90 | max |
|---|---|---|---|---|---|
| 0.75 | 1.00 | **1.20** | 1.88 | 3.00 | 4.00 |

| gate | qualifying |
|---|---|
| ≥ 1.0× | 25 / 29 (86%) |
| ≥ 1.5× | 11 / 29 (38%) |
| **≥ 2.0×** | **7 / 29 (24%)** |
| ≥ 3.0× | 3 / 29 (10%) |

The typical post-loss trade is **1.20×**. The 2.0× line sits at roughly the p78
of that distribution — well above normal behaviour, not on top of it. Compare
`winning_streak_overconfidence`, whose gate sat where the distribution already
was.

### Both severity tiers are reachable

**caution 4, danger 3.** Contrast `winning_streak_overconfidence` (danger never
fired, 1 trade of 740 could reach it) and `end_of_session_mis_panic` (danger
never reached in 175 sessions).

### The claimed distinction from `martingale_behaviour` is REAL

| | |
|---|---|
| `martingale_behaviour` firings | 26 |
| `post_loss_recovery_bet` firings | 7 |
| both on the same trade | **3 (43%)** |
| **recovery_bet alone vs martingale** | **4 of 7** |

The docstring's claim — progressive escalation versus one outsized bet — holds
in the data. Four firings describe something martingale does not see:

```
2025-08-13  NIFTY2581424400PE
2025-09-02  NIFTY2590224700PE
2026-01-22  SENSEX2612282300CE
2026-02-04  SENSEX2620584000CE
```

### The copy is accurate, and conditional

*"If this one also loses, the combined loss exceeds everything it was meant to
recover."* That is **arithmetic under a stated hypothetical**, not a prediction
and not a statistic. It carries no unsourced claim — the first detector in five
reviews of which that is true. §P5 shows why the conditional framing matters.

### The shuffle null points the right way — the first one that does

| | |
|---|---|
| real trade order | **7 firings** |
| shuffled order, 2,000 permutations | mean **4.0**, median 4, range 0–11 |
| p(shuffled ≥ real) | **0.088** |

Not significant at 0.05, and n = 7. But every previous detector tested this way
fired *at or below* chance — `size_escalation` 0.880, `early_exit` 0.610,
`winning_streak_overconfidence` 0.582. This is the first where the real ordering
produces **more** firings than shuffled order, which is what the theory predicts.

### It is pure, and its known defects were already fixed

No database, no wall clock, no `await`. F22 removed a genuinely unreachable
cross-underlying branch. It was migrated to `concluded_before_entry` at the
temporal fix (`b1f78fe`) with its firing set unchanged at 7 — its unguarded
shape had been latent rather than active.

---

## Problems found

### P1. There is no floor on the prior loss, and a sibling detector has one

Nothing requires the losses being "recovered" to be material. The seven firings'
total prior loss:

```
Rs 477   478   739   1,361   1,751   1,990   5,212
```

**Two of seven follow prior losses totalling under ₹500.** In context: **42% of
this book's 434 losing rounds are under ₹500** and the median loss is ₹628, so
"two losses" is a very low bar.

`revenge_trade` has `revenge_min_loss_inr = 500` for exactly this reason. This
detector has no equivalent.

**The consequence is precise:** the SIZE observation stays true — a 4.0× position
is a 4.0× position — but the **recovery framing** does not fit. "Make it all
back in one trade" after losing ₹478 describes a bet, not a recovery. The
message leads with *"After 2 SENSEX losses (₹478 total)"*, which invites the
trader to weigh a number that is not worth weighing.

**No floor value is proposed here.** Adopting `revenge_trade`'s 500 would be
importing a constant, not deriving one, and the brief forbids inventing
replacements.

### P2. The size baseline mixes a winner into a "post-loss" average

The loss test reads `prior[-2:]`; the size average reads `prior[-3:]`.

**3 of 7 firings had a WIN as the third-from-last prior.** So "your recent
NIFTY average" is, in those cases, partly the size of a trade that worked. The
two windows are one element apart for no stated reason.

This does not invalidate a firing — the ratio is still a real comparison against
recent size — but the alert says *"after 2 losses … your recent average"* and
the average is not a post-loss one.

### P3. Neither multiplier has a `THRESHOLD_SPECS` record

`recovery_bet_caution_mul` and `recovery_bet_danger_mul` exist only in
`COLD_START_DEFAULTS` with an inline comment. No `Kind`, no provenance, no
maturity — so nothing records whether they are definitional, policy or
judgement.

Unlike the last four reviews, **the values themselves measure well** (§What is
correct). The gap is bookkeeping, not calibration.

### P4. Overlap is very high — its uniqueness is against martingale, not the engine

| co-firing detector | n | share |
|---|---|---|
| `same_symbol_obsession` | 6 | 86% |
| `revenge_trade` | 5 | 71% |
| `adding_to_adverse_position` | 2 | 29% |
| **fired with nothing else at all** | **0** | **0%** |

Every one of the seven is already visible to at least one other detector. Its
contribution is a *different reading* of trades others also flag — specifically
the size dimension that `same_symbol_obsession` and `revenge_trade` do not
measure — rather than coverage nothing else has.

That is a weaker claim than "unique coverage" but not an empty one: at
`notification_level=2` it is the size statement, and 4 of 7 are invisible to the
other size detector.

### P5. Consequence runs opposite to the alert's implication — and cannot judge it

| | n | win rate | mean | median |
|---|---|---|---|---|
| flagged | 7 | **57.1%** | **+₹344** | +₹543 |
| everything else | 733 | 39.3% | −₹55 | −₹176 |

**The recovery bets worked.** Permutation p = 0.224, so this is not a real edge
either — but it is certainly not evidence of harm.

**This does not refute the detector, and the copy is why.** *"IF this one also
loses…"* is conditional; a winning sample leaves it untouched. And by the design
of record, rest-of-session P&L **ranks** detectors and cannot judge the product —
the alert's job is to make an automatic action deliberate, not to predict.

But it must be said in both directions: **the consequence measure cannot support
this detector either.** A trader shown a `danger` alert on a trade that then made
₹1,320 has been told something true about size and nothing true about outcome.

### P6. The copy says one loss; the code requires two

*"entered after a loss on the same underlying"* — singular. The gate is
`all(p < 0 for p in prior[-2:])`. Minor, but the copy understates the condition.

### P7. n = 7

Everything above rests on seven firings across 175 sessions. The shuffle null at
n = 7 is weak evidence however it falls. **This detector is not validated by
this book — it is not refuted by it**, and those are different statements.

---

## Evidence

| question | answer | strength |
|---|---|---|
| does it fire? | **7 events / 7 sessions** of 175; caution 4, danger 3 | measured |
| are both tiers reachable? | **yes** | measured |
| does it withhold? | **yes** — size gate declines 22 of 29 (76%) | measured |
| is the 2.0× gate above normal behaviour? | **yes** — median post-loss ratio 1.20, only 24% reach 2.0× | measured, n=29 |
| is it selected on outcome? | **no** — 4 of 7 flagged trades won | measured |
| is it distinct from `martingale_behaviour`? | **yes** — 4 of 7 fire alone against it | measured |
| does the real order beat chance? | **directionally** — 7 vs shuffled mean 4.0, p = 0.088 | measured, 2,000 perms |
| unique coverage across all detectors? | **none** — 0 of 7 fire alone | measured |
| is there a floor on the prior loss? | **no** — 2 of 7 follow < ₹500 total | measured |
| consequence | flagged won 57.1%, +₹344 mean, p = 0.224 | measured, n=7 |
| is it pure? | **yes** | verified |
| does the copy match the code? | **yes**, except "a loss" vs two | verified |
| do the thresholds have provenance? | **no spec record for either** | verified |

**What the evidence cannot say.** At n = 7 nothing here is established. The
structural properties — no outcome selection, real withholding, a gate above the
distribution, both tiers live, a genuine distinction from martingale — are
properties of the *code* and are solid. The behavioural claim is neither
confirmed nor contradicted.

---

## Recommended behavioural contract

> **Subject.** One position materially larger than the trader's recent size on
> that underlying, entered after that underlying has already lost — the "make it
> back in one" shape, as distinct from a progressive ladder.
>
> **Judged on the decision, never the result.** It must fire identically whether
> the bet wins or loses. It does.
>
> **The losses being recovered must be material.** A large position after a
> trivial loss is a sizing observation, not a recovery bet, and should not be
> described as one.
>
> **The baseline it compares against should be the sizes that preceded the
> losses**, and the window used for the average should be the window used for
> the loss test.
>
> **Says nothing about what the trade will do.** The copy's conditional framing
> is correct and should survive any change.

---

## Exact changes required

**None that can be made without inventing a value**, which is why the verdict is
KEEP AS-IS rather than MODIFY. Recorded for the consolidated pass:

1. **No loss floor** (P1). `revenge_trade`'s `revenge_min_loss_inr = 500` is the
   nearest precedent, but importing it is a product decision, not a measurement
   result. **The measurement that would settle it does not exist in this
   book** — 7 firings cannot locate a floor.
2. **The `prior[-2:]` / `prior[-3:]` window mismatch** (P2). Aligning them is a
   one-line change that alters firing, so it needs its own before/after.
3. **Neither multiplier has a `THRESHOLD_SPECS` record** (P3). Bookkeeping;
   belongs with the contract-test item already pending, now at seven known
   instances across the sequence.
4. **Copy says "a loss", code requires two** (P6).

---

## Verdict — **KEEP AS-IS**

**The first KEEP AS-IS since Pattern 13**, and it is earned on structure rather
than on outcome evidence.

**Not DELETE.** Every property that condemned the last four retirements is
absent here. It does not select on outcome — 4 of 7 flagged trades won. Its
gates withhold 76%. Its threshold sits well above the behaviour's normal
distribution rather than on top of it. Both severity tiers are reachable. Its
claimed distinction from `martingale_behaviour` is real and measured at 4 of 7.
Its copy is accurate, conditional, and free of invented statistics. The shuffle
null is the first in this sequence to point the way the theory predicts.

**Not MODIFY.** The one substantive defect — no loss floor — cannot be fixed
without choosing a number, and neither this book nor the brief supports choosing
one. The other three are bookkeeping or need their own before/after.

**Not RESEARCH FURTHER.** More analysis of *this* book will not help: the
constraint is n = 7, not method. What would settle it is more firings, which
means more data, not more measurement.

**Not DEFER.** Nothing blocks it. It is live, measurable, measured, and behaving
as designed.

**Stated plainly, because it cuts both ways:** at n = 7 this detector is **not
validated** — it is **not refuted**, and its structure is sound. That is a
weaker endorsement than "it works", and the difference should not be lost.
Its unique contribution across the whole engine is zero — all 7 firings are
already visible to something else — so what it adds is the *size* reading at
`notification_level=2`, not coverage. If a future pass finds that reading is not
worth a separate alert, that is a consolidation question, and it should be
decided on the reading, not on these seven rows.
