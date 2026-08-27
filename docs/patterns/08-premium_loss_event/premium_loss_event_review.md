# Pattern #8 — `premium_loss_event`

27 Aug 2026. **Review only. No code changed, no threshold added or retuned, no
detectors merged.**

This also closes the mandated review of `premium_loss_caution_pct`, which sits in
`safety_bounds.MANDATORY_REVIEW` flagged as *"documented as firing routinely
without behavioural failure."*

**Verdict: KEEP AS-IS.** The first detector in this series to survive its
evidence intact. Its thresholds select the trades that actually cost this trader
money, its severity ladder tracks magnitude, and the flag that sent it to
mandatory review is **not supported by measurement** — it fires on 6% of the
population, not routinely.

Two things I asserted before measuring were wrong, and are corrected in §2.

---

## 1. What it is supposed to detect, and the mechanism

A **long option that has lost a large share of the premium paid**. Registry
copy: *"Beyond a point the position needs a move it was never sized for. Time is
on the other side."*

This is the first reviewed pattern whose claim is **not about ordering or
timing**. It is a statement about the *state of a position*: a long option's
entire downside is the premium, decay runs against the holder, and past some
fraction of premium gone the position needs a move larger than the one it was
bought for. That is arithmetic about optionality, not a psychological claim —
and it is classified `nature="risk"`, not `emotional`, consistently.

**The permutation nulls used for Patterns 4, 6 and 7 do not apply here**, and
saying so is part of the review: there is no sequencing claim to destroy. The
questions that do apply are whether the thresholds select anything, whether the
severity ladder means anything, and whether the trader can act.

## 2. Two corrections to my own framing

**It is not the only source of `critical`.** `constitution_violation` and
`death_spiral` both emit `critical` too. The REVIEW STATUS table in
`00-shared/BEHAVIOURAL_PATTERNS.md` says *"only source of critical"* and I
repeated it when queuing this review. Verified by inspecting every detector's
source: three can produce it.

**It is not guardian-eligible.** `guardian_eligible=True` is set on
`session_meltdown` and `constitution_violation` only, with `death_spiral`
special-cased at `trade_tasks.py:1752`. **`premium_loss_event`'s criticals never
reach an accountability partner.** Its `notification_level` is 3, below the 4
carried by the two guardian-eligible detectors.

So it is the loudest thing that stays *between the product and the trader* — not
the loudest thing the product does.

## 3. What the implementation does, end to end

`behavior_engine.py:2634-2721`, 88 lines.

```
guard        instrument_type in (CE, PE) AND direction == LONG
loss_pct     from stored pnl_pct, else (exit-entry)/entry
cap          loss_pct > 100  ->  clamp to 100 + WARN   (see §5)
floor        loss_pct <= 0   ->  None
levels       caution 40, danger 60, critical 80   (% of premium)
expiry       all three levels +15pp on the instrument's own expiry day
severity     >= critical -> critical;  >= danger -> danger;  >= caution -> caution
repeat       another LONG option today already past `danger` promotes danger -> critical
flag         duration < 30 min  ->  fast_collapse (context only, never severity)
```

| input | value | classification |
|---|---|---|
| `premium_loss_caution_pct` | 40 | **`UNIVERSAL_SAFETY`**, `MANDATORY_REVIEW` |
| `premium_loss_danger_pct` | 60 | `UNIVERSAL_SAFETY` |
| `premium_loss_critical_pct` | 80 | `UNIVERSAL_SAFETY` |
| `premium_loss_expiry_shift_pct` | 15 | **unclassified** |
| `premium_loss_fast_hold_min` | 30 | **unclassified** |

`UNIVERSAL_SAFETY` means never personalised — a trader's habits must not raise
the bar on objective danger. **That classification is correct here** and the
registry says why in a comment worth keeping: *"KIND IS NOT VALUE… a wrong
number of the right kind is still the right kind."*

**Rules / onboarding:** none reach this detector, and none should — the whole
point of `UNIVERSAL_SAFETY` is that it is not the trader's to loosen.

**Severity** caution / danger / **critical**. **Confidence** not set by the
detector. **Evidence/abstention** none — returns a `DetectedEvent`.
**`_WORSEN_METRIC` = `loss_pct`**, which is monotonic within one position.
**Not** in `_STRATEGY_SUPPRESSED`, no constitution pairing, no consolidation
family.

### There are two producers, and only one is actionable

| | fires | on | dedup |
|---|---|---|---|
| `_detect_premium_loss_event` | at **exit**, on a CompletedTrade | a position that is **already closed** | pattern-type, 24h |
| `live_checks.evaluate_live_premium_loss` via `position_monitor_tasks:912` | on the **60-second beat**, on an open position | **unrealised** loss, while it can still be acted on | per-**symbol**, escalation-aware, 30 min |

The live variant mirrors the same 40/60/80 bands and the same expiry shift, and
deliberately omits the repeat rule because it needs completed trades. Its dedup
scope comment records a real bug it fixed: pattern-type alone meant *"with two
long options bleeding at once only the first ever alerted."*

**This matters for the verdict.** The exit-time detector reports a fact about a
position the trader has already closed. §6 measures what that means.

## 4. Performance and purity — **KEEP AS-IS**

No `await`, no `db.`, no `select(` — confirmed by source inspection and by
running it 912 times with no database connection. One pass over
`ctx.session_trades` for the repeat count. Negligible.

## 5. Evidence — 189 sessions, 912 positions

**Long options are 888 of 912 positions (97%)**, so this detector sees almost
the entire book. That is unusual and worth stating: most detectors here operate
on a slice.

### 5a. The MANDATORY_REVIEW flag is not supported

The flag says the caution level *"fires routinely without behavioural failure."*
Measured across all 888 long options:

| premium outcome | positions | share |
|---|---|---|
| in profit | 357 | 40.2% |
| lost 0-20% | 389 | 43.8% |
| lost 20-40% | 85 | 9.6% |
| **lost 40-60% (caution)** | **31** | **3.5%** |
| **lost 60-80% (danger)** | **16** | **1.8%** |
| **lost 80-100% (critical)** | **10** | **1.1%** |

> **Only 6% of this trader's long options lose 40% or more of premium.** The
> caution level is not routine; it is the top 6% of outcomes.

**The flag should be cleared, not acted on.** It was recorded as a documented
concern rather than a measured one, and this is the measurement.

### 5b. What it fires

**48 detections on 39 of 189 sessions (21%)** — 5% of the long options it can
see. Severity **29 caution / 9 danger / 10 critical**.

### 5c. It finds the money — and this is the finding

| | |
|---|---|
| book | 912 positions, net **−₹141,494**, gross loss **−₹690,545** |
| the 48 flagged trades | **−₹238,623** |
| share of all money lost | **35%** |
| share of positions | **5%** |
| of the 48 single worst positions by money (−₹287,008) | it captures **83%** |

> **Five percent of positions carrying thirty-five percent of everything lost.**

This is the opposite of Patterns 5, 6 and 7, each of which flagged trades that
won *more often* than the trader's baseline. **It is the first detector reviewed
whose flagged set is the expensive one.**

### 5d. The severity ladder tracks magnitude

| severity | n | total | median loss | median % of premium |
|---|---|---|---|---|
| caution | 29 | −₹120,909 | −₹3,011 | 54.4% |
| danger | 9 | −₹34,093 | −₹3,218 | 70.6% |
| **critical** | **10** | **−₹83,620** | **−₹5,670** | **85.5%** |

The critical band's median loss is **1.9× the caution band's**. Every previous
pattern in this series had a severity tier that ranked nothing; this one ranks
money.

### 5e. The modifiers

| modifier | engages |
|---|---|
| expiry-day +15pp shift | **12 of 48** |
| `fast_collapse` flag (hold < 30 min) | 5 of 48 — context only, never severity |
| repeat rule (`repeat_count >= 1`) | **5 of 48** |
| …**promoted danger → critical** | **2** |

The two promotions: `NIFTY2590924950CE` at 85.5% against an expiry-shifted
critical level of 95, and `NIFTY25D2326000PE` at 75.6% against 80. **So 2 of the
10 criticals come from the repeat rule rather than from magnitude** — a fifth of
the loudest severity the detector can emit is produced by a rule with no stated
source.

*Measurement note, and a correction to my own first pass: my harness initially
left `pnl_pct` unset, and the repeat rule reads prior trades' `pnl_pct`, so it
measured 0 engagements. `pnl_pct` **is** populated in production at
CompletedTrade creation (`position_ledger_service.py:692`), so I repopulated it
and re-ran. The figures above are from the corrected run. The rule is not dead.*

### 5f. The >100% cap

**Zero occurrences** when `loss_pct` is computed from average prices. The cap
guards the *stored* `pnl_pct` path, where the defect it describes actually
lives. It is a defensive guard against bad data, it logs a warning, and it
reports the true rupee loss while refusing to print an impossible percentage.
**That is the correct handling** and the comment explaining it is exactly the
kind this codebase should have more of.

### 5g. Observability limits, and the timing problem

**Hold time of flagged trades: p25 169 min, p50 1,341 min, p75 4,400 min.**

> The median flagged position was held **22 hours** — overnight — and the upper
> quartile **three days**.

These are not intraday collapses. And the exit-time detector fires **after the
position is closed**, so on the median flagged trade the alert describes
something that finished a day or more ago and cannot be acted on.

The live variant is what makes this defensible: it fires on the same bands while
the position is open. **The exit path is a record; the live path is the alert.**
Nothing in the review contradicts that split — but the exit path is what carries
`notification_level=3`, and its message is written in the present tense
(*"85% of premium lost"*) for a position that no longer exists.

## 6. Overlap and whether the alert is meaningful

**Fired alone on 9 of its 39 alert-days — 23%, the highest solo rate of any
pattern reviewed so far** (`fomo_entry` 4/29, `daily_overtrading` 2/49,
`profit_giveaway` 0/20).

| co-fires with | days | share |
|---|---|---|
| `adding_to_adverse_position` | 16 | 41% |
| `options_premium_avg_down` | 13 | 33% |
| `martingale_behaviour` · `death_spiral` · `consecutive_loss_streak` (retired) | 10 each | 26% |
| `expiry_day_overtrading` | 9 | 23% |

The `options_premium_avg_down` overlap is the one worth noting for the families
review: both are statements about a long option going wrong, from different
angles.

**Is it meaningful?** Yes, on the evidence: it names 35% of the trader's losses
from 5% of their positions, its tiers rank money, and it says something no other
detector says. The qualifier is §5g — at exit it names something already over.

## 7. Are the values justified?

| value | justified? |
|---|---|
| `premium_loss_caution_pct` 40 | **Yes, by measurement.** Top 6% of long-option outcomes; the flag claiming it fires routinely is refuted. |
| `premium_loss_danger_pct` 60 | **Yes.** 2.9% of the population, median loss −₹3,218. |
| `premium_loss_critical_pct` 80 | **Yes.** 1.1% of the population, median loss −₹5,670, 1.9× the caution band. |
| `UNIVERSAL_SAFETY` classification | **Correct.** A trader's habits must not raise the bar on how much of a premium is gone. |
| `premium_loss_expiry_shift_pct` 15 | **Unclassified, unsourced**, but the *direction* is right and well argued — deep OTM near expiry loses 40% routinely. Engages on 12 of 48. The magnitude of the shift has no stated basis. |
| `premium_loss_fast_hold_min` 30 | **Unclassified, unsourced.** Context flag only, never touches severity, so the cost of it being wrong is a wrong word in a message. |
| the repeat rule (`>= 1` prior past danger) | **No stated source**, and it produces 2 of 10 criticals. The threshold is 1, which is the smallest non-trivial number available; nothing records why. |

**Research note.** That a long option's downside is bounded by the premium and
that theta runs against the holder are properties of the instrument, not claims
about traders — no citation is needed and none is missing. What is *not*
established anywhere is why the boundaries sit at 40, 60 and 80 rather than
elsewhere. They are round numbers. **On this book they happen to select well**,
which is evidence they are not badly wrong, not evidence that they are right.

## 8. Verdict — **KEEP AS-IS**

Not MODIFY: nothing measured here is wrong. The thresholds select the top 6% of
outcomes, capture 35% of all money lost from 5% of positions, and the severity
ladder tracks magnitude — the first in this series to do so. The mandatory-review
flag is refuted rather than confirmed.

Not DELETE, RESEARCH FURTHER or DEFER: the evidence is sufficient and it is
favourable.

The open items in §9 are **recorded, not required**. None of them is a defect I
can demonstrate on this book, and changing a `UNIVERSAL_SAFETY` band that
currently selects well, on one trader's data, would be exactly the kind of
unforced retune this series exists to prevent.

---

## Current behaviour

Fires on long options only, at 40 / 60 / 80 percent of premium lost, shifted
+15pp on the instrument's own expiry day, with a repeat rule promoting danger to
critical when another long option already passed danger the same day. 48
detections on 39 of 189 sessions; 29 caution, 9 danger, 10 critical. A separate
live variant applies the same bands to open positions on a 60-second beat.

## What is correct

- **The thresholds find the money.** 5% of positions, 35% of all losses, 83% of
  the worst 48 by value.
- **The severity ladder ranks magnitude** — critical's median loss is 1.9× caution's.
- **`UNIVERSAL_SAFETY` is the right classification**, and the registry's
  "KIND IS NOT VALUE" note is the right reasoning.
- **The >100% cap.** Logs, reports the true rupee figure, refuses to print an
  impossible percentage. Correct handling of bad input.
- **The expiry shift's direction** is right and argued from how options behave.
- **Long-only.** A short option receives premium; the loss is unbounded and a
  percentage of premium would be meaningless. The guard is correct.
- **Purity**, and the live/exit split, which puts the actionable check where it
  can be acted on.

## Problems found

1. **The exit-time path fires on closed positions with a median hold of 22
   hours**, in the present tense, for something already over.
2. **The repeat rule has no stated source** and produces 2 of 10 criticals.
3. **`premium_loss_expiry_shift_pct` (15) and `premium_loss_fast_hold_min` (30)
   are unclassified and unsourced.**
4. **The `MANDATORY_REVIEW` flag on `premium_loss_caution_pct` is wrong** — it
   should be cleared with the measurement recorded, not left implying an open
   concern.
5. **The tracker's claim that this is the "only source of `critical`" is false**
   — `constitution_violation` and `death_spiral` also emit it.
6. **40 / 60 / 80 are round numbers with no stated derivation.** They select
   well here; that is not the same as being derived.

## Evidence

§5 in full. Headlines: 888 long options of 912 positions; only 6% lose ≥40% of
premium; 48 detections / 39 days; 29/9/10 by severity; **−₹238,623 on flagged
trades = 35% of the book's −₹690,545 gross loss from 5% of positions**; critical
median loss −₹5,670 against caution's −₹3,011; expiry shift engages 12 times,
repeat rule 5 times promoting twice; zero >100% events from average prices;
median flagged hold 1,341 minutes; fired alone on 9 of 39 days.

## Recommended behavioural contract

> **`premium_loss_event` reports one fact: how much of the premium paid for a
> long option is gone.**
>
> - The **finding is the magnitude**, and it is a property of the instrument,
>   not a claim about the trader's state of mind. The copy is already correct on
>   this and must stay that way.
> - It is **`UNIVERSAL_SAFETY`**: the trader may not raise the bar on it, and no
>   personal baseline may quieten it.
> - **The live path is the alert; the exit path is the record.** Where the
>   position is already closed, the wording should not imply that anything can
>   still be done about it.
> - Severity must continue to follow **magnitude of premium lost**. Any rule
>   that promotes severity for another reason needs its own justification.

## Exact changes required, if any

**None required.** Four items are recorded for whoever wants them, in priority
order, and each is optional:

| # | item | why it is not required |
|---|---|---|
| 1 | Clear the `MANDATORY_REVIEW` flag on `premium_loss_caution_pct`, recording the 6% measurement | bookkeeping; the flag is stale, not harmful |
| 2 | Give the repeat rule a source, or a key and a test | it produces 2 of 10 criticals, but both were genuine large losses |
| 3 | Classify `premium_loss_expiry_shift_pct` and `premium_loss_fast_hold_min` | both are unsourced; one is context-only |
| 4 | Reword the exit-path message so it does not read as live | the live path already carries the actionable version |

**No threshold change is proposed.** 40 / 60 / 80 are unsourced round numbers
that select the top 6% of outcomes and 35% of the losses on the only book we
have. That is the strongest evidence any threshold in this series has had, and
it is not a reason to move them.

## What is NOT proposed

Changing any band. Personalising anything — the `UNIVERSAL_SAFETY` kind forbids
it and is correct. Merging with `options_premium_avg_down`. Adding a
consolidation family. Touching the live variant. Removing the >100% cap.

## Recorded for later reviews, not fixed here

- `options_premium_avg_down` overlaps on 33% of days and makes an adjacent claim
  about long options going wrong. **For the families review.**
- The REVIEW STATUS table's "only source of `critical`" note is wrong and should
  be corrected wherever it appears.
- `premium_loss_event` is `notification_level=3` and **not** guardian-eligible,
  while `session_meltdown` and `constitution_violation` are level 4 and are. Whether
  the loudest *magnitude* finding should be able to reach a guardian is a product
  question, untouched here.
