# Pattern #4 — `consecutive_loss_streak`

25 Aug 2026. **Review only. No code changed, no threshold added or retuned, no
detectors merged.**

**Verdict: MODIFY.** The detector is the most frequent alert in the engine, and
its trigger is a coin flip. What information it carries is in a branch that
never fires for a trader who has not declared a daily loss limit — which is
every new user.

---

## 1. What it is supposed to detect

An unbroken run of losing trades inside one session. The registry copy: *"After
several losses in a row the next decision carries the weight of the previous
ones instead of standing on its own."*

The mechanism appealed to is real and well documented — **tilt / escalation after
a run of losses**, and Coval & Shumway's finding that CBOT traders who lose in
the morning take more risk in the afternoon. The claim is that a *run* is a
different psychological state from the same number of losses scattered through a
session.

**That claim is testable, and it is the thing this review tested.**

## 2. What the implementation does

`behavior_engine.py:914-984`, 71 lines.

1. Streak comes from `ctx.facts.consecutive_losses` — the canonical session
   fact, not a local count. Correct, and a genuine improvement over the three
   places that used to count it separately.
2. Sums the absolute P&L of the last *streak* trades.
3. `streak >= consecutive_loss_danger` (5) → **danger**.
4. Else `streak >= caution` (3) **and** `total_loss >= daily_loss_limit × 0.5`
   → **danger**, tagged `escalated_by: loss_size`.
5. Else `streak >= caution` (3) → **caution**.

| input | value | classification | notes |
|---|---|---|---|
| `consecutive_loss_caution` | 3 | `fallback` | |
| `consecutive_loss_danger` | 5 | **unclassified** | |
| `daily_loss_limit` | **user-declared** | user value | **None when not declared — no fallback** |
| the `0.5` | inline literal | **no key, no classification, no test** | flagged in the hygiene pass, still open |

**Severity** caution/danger. **Confidence** not set. **Evidence/abstention**
none — returns a `DetectedEvent`. **Notification level 2** → danger is a push.
**In `_STRATEGY_SUPPRESSED`**; suppressed by the constitution
`max_consecutive_losses` rule. **In no consolidation family.**

## 3. Are the values justified?

Answered by §4 rather than by argument. In short: **the counts are not**, and the
one value that is defensible — the trader's own declared limit — is absent for
anyone who has not set it.

## 4. Evidence — 189 sessions, 912 positions, corrected trade set

**106 firings across 58 days** (78 alerts after dedup — the largest single
source in the engine). Severity 85 caution / 21 danger. Streak at firing:
`{3: 62, 4: 23, 5: 11, 6: 5, 7: 4, 8: 1}`.

### 4a. The trigger is chance. Exactly chance.

Win rate 39.9%. Shuffling each session's outcomes 2,000 times at that rate,
preserving session lengths:

| run length | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| **observed** | 135 | 81 | 42 | 12 | 7 | 2 | 2 | 2 |
| **chance** | 146.4 | 73.9 | 36.4 | 17.3 | 7.4 | 3.1 | 1.5 | 0.6 |

And the summary figure:

> **Sessions containing a 3+ loss run: observed 63. Expected by chance 63.0.
> Of 189.**

Not close — identical. A three-loss run in this book is precisely what a 39.9%
win rate produces on its own. The danger tier at 5 is the same story: 7 observed
against 7.4 expected.

This is the second time this measurement has been run — the first was during the
revenge research, on the contaminated 742-position set. It holds on the corrected
912-position set with an independent win rate.

**What this does and does not mean.** It does not mean the trader is calm during
a losing run. It means **the run itself is not evidence of anything** — it does
not indicate a changed state, because a coin produces them at the same rate. Any
severity derived from the count is derived from noise.

### 4b. The one informative branch never fires

The loss-size escalation — *"if the run has already eaten half the limit the
trader set for themselves"* — is the only part of this detector not based on a
count. Money lost is not a coin flip.

**It fired 0 times in 106**, because `daily_loss_limit` is `None` when the trader
has not declared one, and `resolve_thresholds` provides **no fallback** for it
(unlike `session_meltdown`, which derives 5% of capital when the limit is
absent).

And when a limit *is* declared, the branch's behaviour swings wildly:

| declared daily limit | firings that would escalate to danger |
|---|---|
| ₹25,000 | **2** of 106 |
| ₹10,000 | 14 |
| ₹5,000 | 46 |
| ₹2,500 | **77** of 106 |

Total loss at firing: p25 ₹2,070 · p50 ₹3,232 · p75 ₹5,076 · max ₹12,866. On a
₹50,000 account a realistic 5% limit is ₹2,500, at which **73% of firings become
danger** — so the tier means something completely different for two traders with
different limits. That is arguably correct, since it is *their* number, but it
means the danger tier is not comparable across users and the `0.5` multiplying
it has never been justified.

### 4c. It re-fires as the run grows

106 detections for 58 days. A run of 5 fires at 3 (caution), is suppressed at 4
(same key, same severity, and no `_WORSEN_METRIC` entry), then fires again at 5
(danger). Two alerts per session maximum — the dedup is working, and 78 alerts
across 56 days is consistent with it.

### 4d. Observability

Nothing is missing. The streak, the P&L and the trader's declared limit are all
directly observable. **This detector has no data problem** — it has an evidence
problem.

## 5. Overlap and whether the alert is meaningful

On the same trade:

| detector | co-fires | survives consolidation? |
|---|---|---|
| `revenge_trade` | **44 of 106 (42%)** | **Yes** — different families |
| `martingale_behaviour` | 29 (27%) | **Yes** |
| `profit_giveaway` | 22 (21%) | **Yes** |
| `same_symbol_obsession` | 22 (21%) | **Yes** |

**It belongs to no consolidation family**, so all of these fire alongside it. On
a bad day the trader receives the streak alert *plus* whichever of the four also
triggered — and the streak alert is the one whose trigger is chance.

**Is the alert meaningful?** The *facts* are true: three losses happened and
₹3,232 was lost. But the alert's implied claim — that a run is a state worth
interrupting for — is not supported. And it is the engine's loudest voice: 78
alerts, more than any other pattern.

## 6. Performance and purity

**Pure.** No `await`, no `db.`, no `select(` in the body; ran 912 times in this
review with no database connection. One sort of the session's trades, then a
slice. Negligible. **KEEP AS-IS.**

## 7. Verdict — **MODIFY**

Not KEEP AS-IS: the engine's most frequent alert fires on a coin flip, and its
one informative branch is dead for any trader without a declared limit.

Not DELETE: the *loss* is real. ₹12,866 lost across a run is worth saying, and
the trader's own declared limit is the most defensible reference in this whole
engine — it is their number, not ours.

Not DEFER: the count-vs-chance result is measured, reproduced on two independent
trade sets, and needs no further evidence.

### Recommended behavioural contract

> **`consecutive_loss_streak` reports one fact: the money lost in an unbroken run
> of losing trades.**
>
> - The **run is the occasion, not the finding**. It marks where to look; it is
>   not itself evidence, because runs of this length occur at exactly the rate
>   chance produces.
> - The **finding is the money** — how much the run has cost, against the limit
>   the trader set for themselves. That is the only dimension here that is not a
>   coin flip.
> - It makes **no predictive claim**. A run does not indicate a changed state,
>   and this detector must not imply that it does.
> - Where the trader has declared no limit, the detector has nothing to
>   escalate on and should say less, not guess.

### Exact changes required — for approval, not implemented

| # | change | why |
|---|---|---|
| 1 | severity must not be driven by the **count** alone | 63 observed vs 63.0 expected — the count carries no information, so `danger` at 5 asserts something the data denies |
| 2 | decide what happens when `daily_loss_limit` is absent | the only informative branch is dead for every trader who has not declared one, which is the cold-start default |
| 3 | the `0.5` needs justification, a key and a test — or removal | inline literal, unclassified, untested, and it decides a push notification |
| 4 | copy must stop implying a run is a state | *"the next decision carries the weight of the previous ones"* is a claim about psychology that this book does not support |

**No replacement threshold is proposed.** What severity should key on instead —
absolute loss, loss against the declared limit, loss against capital — needs its
own evidence pass, and choosing one here would be inventing.

**Not proposed either:** adding it to a consolidation family, personalising the
counts, or deleting the detector. Each needs its own decision.

### Recorded for later reviews, not fixed here

- `consecutive_loss_danger` is unclassified in the threshold registry;
  `consecutive_loss_caution` is `fallback`. Classify when severity is settled.
- The detector is in no consolidation family while overlapping four others at
  21–42%. That is a families question, not a Pattern 4 question.
- `session_meltdown` derives a limit from capital when none is declared; this
  detector does not. Two detectors reading the same user value take different
  approaches to its absence — worth settling once, in whichever review reaches
  it first.
