# Reviews 25–27 — `time_of_day_bias`, `win_rate_collapse`, `strategy_breakdown`

**1 Sep 2026. INVESTIGATION ONLY. NO CODE CHANGED.**

> ## ⚠ SECTION 25 CONTAINS A FINDING THAT WAS WRONG — see `time_of_day_bias_design.md`
>
> This review states that `detected_patterns["time_patterns"]` **has no writer**
> and calls `time_of_day_bias` *"mis-wired / dead on arrival"*. **That is false.**
> `_store_learned_patterns` writes the whole dict at
> `ai_personalization_service.py:142`, on a nightly Celery beat, and the chain is
> live end to end. I grepped for `["time_patterns"] =` and a whole-dict
> assignment could not match it.
>
> **The corrected picture is more serious, not less:** the detector is live and
> firing today for traders with 30+ sessions, and the danger hours it fires on
> are **not stable** — no hour survives into the second half of the book, and
> chance reproduces the flagged count 31% of the time.
>
> **Verdicts 26 (KEEP AS-IS) and 27 (DEFER) are unaffected** and were confirmed
> independently.

Source-list #25, #26, #27. All three recorded as *"IMPLEMENTED, NEVER FIRED"* and
ON HOLD for the same stated reason. Reviewed in one pass because they share that
status — **each gets its own analysis and its own verdict**, and the combined
conclusion at the end answers whether they belong together at all.

Measured on the real book — **175 sessions, 740 rounds**.
Script: `docs/patterns/_measurement/p25b_performance_trio.py`.

**The zero was not accepted as an answer.** Each detector was run twice: once as
the engine sees it today, and once with its baseline **supplied from this book's
own history** — which is what a mature trader's profile would provide. The second
run is the real test. Still zero means the book; non-zero means the plumbing.

The three do not share one cause. **One is mis-wired, two are correctly gated.**

---

# 25. `time_of_day_bias`

## Current behaviour

```
danger_hours non-empty                              (from detected_patterns["time_patterns"])
baseline_sessions >= tod_bias_min_sessions (30)
entry hour ∈ danger_hours
```

| | |
|---|---|
| registry | `1.0.0`, `performance`, **`alerting`**, `trigger=exit`, **`notification_level=1`**, `uses_baseline=True` |
| severity | **`caution`**, hardcoded |
| consumes | `completed_trade`, `thresholds` |
| evidence | entry hour IST, historical win rate / trade count / avg P&L for that hour |
| confidence | **none set** |
| threshold | `tod_bias_min_sessions` = 30 |

`danger_hours` is produced by `ai_personalization_service._learn_time_patterns`:
**win rate < 35% with at least 5 trades in that hour.**

## What is correct

**Pure.** No database, no wall clock. Reads only the trade and its thresholds.

**The sample gate is real and unusually well chosen.** It requires **30 sessions
of history** before saying anything about a trader's hours — the largest maturity
requirement of any detector reviewed, and appropriate for a claim about a
recurring time pattern.

**It never invents a danger hour.** With no learned hours it returns `None`
rather than falling back to a "markets are bad at lunchtime" constant.

**The message is entirely factual and cites its own sample** — *"historically
your 12 PM hour runs a 30% win rate over 68 trades (avg −₹261)"*. Hour, rate,
count and average, no claim about intent.

**A real P0 defect in its input was already found and fixed**, and the comment
records it: `_learn_time_patterns` used `Trade.pnl`, which is always 0, so *"every
win_rate computed here defaulted to 50%, danger_hours never matched its <35%
filter, and time_of_day_bias was dead on arrival."* It now reads `CompletedTrade`.

## Problems found

### P1. It is MIS-WIRED, not selective. `time_patterns` has no writer.

`threshold_resolution` reads:

```python
dp = getattr(profile, "detected_patterns", None) or {}
hours = (dp.get("time_patterns") or {}).get("danger_hours") or []
```

**Nothing anywhere writes `detected_patterns["time_patterns"]`.** Every
reference in the codebase is a read — `personalization.py` (7 reads) and
`threshold_resolution.py` (1). Confirmed by grep for any assignment: none.

The producer runs. `learn_patterns` computes `time_patterns` nightly and returns
it inside `learned_patterns`. The nightly caller then does this:

```python
result = await ai_personalization_service.learn_patterns(...)
if result.get("insufficient_data"):
    logger.debug(...)
else:
    logger.info(f"[Personalization] {account.id}: patterns refreshed ...")
```

**It logs the result and discards it.** The only persistence inside
`learn_patterns` is on the *insufficient-data* branch, and it writes only
`existing["baseline"]`.

So the P0 fix repaired the **input** to a computation whose **output** is thrown
away. `danger_hours` is permanently `[]`, gate 1 always fails, and the detector
cannot fire for any trader.

### P2. Supplied with its own data, it fires 81 times

Feeding the detector the danger hours this book would produce:

| | |
|---|---|
| as the engine sees it today | **0** |
| with learned `danger_hours` supplied | **81** |

This book would learn **two** danger hours:

| hour | trades | win rate | avg P&L |
|---|---|---|---|
| **12:00** | 68 | **29.9%** | −₹261 |
| **15:00** | 13 | **25.0%** | −₹423 |

Against a book-wide 39.5% win rate and −₹42 average.

**81 firings at `notification_level=1`, `alerting`, `caution`** is a substantial
volume — for context, the entire rest of the engine fires 457 times on this book.
Fixing the wiring without deciding that is not a safe change.

### P3. The hour signal has a multiple-comparisons problem nobody has addressed

Seven hours are tested; two are flagged. With 7 tests at a 35% cut on a 39.5%
base rate, finding one or two by chance is likely, and nothing in the producer or
the detector corrects for it.

The **15:00** hour is the weaker case: **n = 13**, which clears the producer's
`>= 5` gate but is a thin basis for telling a trader their 3 PM hour is
dangerous. **12:00 at n = 68** is a more serious candidate.

**No replacement threshold is proposed** — the `>= 5` and `< 35%` values are the
producer's, this review did not test them, and inventing better ones is exactly
what the brief forbids.

### P4. `uses_baseline=True` is true here — unlike two earlier cases

Worth recording positively: this detector genuinely consumes learned history,
unlike `winning_streak_overconfidence` (which declared it falsely) and
`early_exit`'s `winner_hold_p50` (which named a metric nothing produced).

## Evidence

| question | answer |
|---|---|
| does it fire? | **0**, always, for every trader |
| why? | **`detected_patterns["time_patterns"]` has no writer anywhere** |
| does the producer run? | **yes** — nightly, and its result is logged then discarded |
| would the data exist? | **yes** — this book yields 2 danger hours |
| firings if wired | **81** |
| is it pure? | yes |
| does the copy overstate? | no — it cites hour, rate, n and average |

## Observability limitations

None in the detector. The limitation is entirely upstream: a computed value that
is never persisted. **This is the third instance of that class in the review
sequence** — after `winner_hold_p50` and `late_mis_entries_p75/p90` — and the
first where the producer demonstrably runs and the result is dropped at the call
site rather than never computed.

## Recommended behavioural contract

> **Subject.** Hours of the day at which this trader has historically done
> materially worse, stated as a fact about their own record with the sample
> attached.
>
> **Requires a real sample per hour, and a correction for testing many hours.**
> Seven hours tested at one cut is seven chances to find noise.
>
> **Says nothing until the history exists** — the 30-session gate is right.

## Exact changes required

1. **Persist `time_patterns`.** The nightly caller must write
   `result["time_patterns"]` into `profile.detected_patterns` as it already does
   for `baseline`. One assignment.
2. **But not before P2 and P3 are settled** — the fix turns on 81 alerting
   events and rests on an uncorrected multiple-comparisons cut.

## Verdict — **WITHDRAWN.** See `time_of_day_bias_design.md`

The MODIFY verdict below rested on the wiring claim, which was wrong. There is
nothing to wire. The corrected question is whether a live `caution` alert should
be driven by a filter measured as chance-like and unstable across periods.

*(Original text retained below for the record.)*

### ~~Verdict — MODIFY, with the wiring fix explicitly gated~~

The defect is certain and the remedy is one line. The volume and the statistics
are not settled, and shipping the line alone would take a detector from silent to
81 alerts on evidence that has never been tested for significance.

**Not KEEP AS-IS** — a permanently dead alerting detector is not a working one.
**Not DELETE** — the subject is real, the data exists, and the only thing wrong
is an assignment that was never written.

---

# 26. `win_rate_collapse`

## Current behaviour

```
baseline_win_rate present AND confidence >= 0.5
>= 8 trades today (session_trades + current)
(baseline_wr − today_wr) / baseline_wr >= 0.40
```

| | |
|---|---|
| registry | `1.0.0`, `performance`, **`analytics`**, **`trigger=session`**, **`notification_level=0`** |
| severity | **`info`**, hardcoded |
| confidence | **set** — from the baseline's own confidence |
| message | *"Today's win rate 11% vs your 40% baseline (9 trades). Strategy or conditions, not psychology."* |

## What is correct

**Pure.** No database, no wall clock.

**Its data source genuinely exists and is persisted.** `baseline_win_rate` comes
from `detected_patterns["baseline"]`, written by
`behavioral_baseline_service.compute_and_store` on the sync path (24-hour
throttle). Unlike §25 this chain is complete.

**It sets a real confidence** — derived from the baseline's own sample
confidence, not a data-quality proxy. Only a minority of detectors do this.

**The copy refuses the psychological reading**, deliberately: *"Strategy or
conditions, not psychology."* That is the detector declining to over-claim, and
the registry comment explains why — *"win rate is strategy-dependent; a 30% WR
trader with PF 2.3 is excellent"*.

**Its 0.40 threshold is documented as a deliberate severity choice**, not a
tuned one: *"severe tier only — mild tiers are pure variance."*

## Problems found

### P1. The zero is the harness, not the detector

| | |
|---|---|
| as the engine sees it today (no baseline) | **0** |
| with this book's own baseline supplied | **4** |

The replay has no profile, so `baseline_win_rate` is absent and gate 1 always
fails. **That is a property of the reference book, not of the detector.** A real
trader who has synced has the baseline.

### P2. It is genuinely selective — the funnel is steep and defensible

| gate | sessions |
|---|---|
| all sessions | 175 |
| **>= 8 trades** | **26** |
| ...and win-rate deterioration >= 40% | **2** |

The 8-trade gate removes 85% of sessions, and the 40% deterioration removes 92%
of what remains. On a 39.5% baseline, a 40% deterioration means a session below
**23.7%** — a genuinely bad day, not a wobble.

### P3. `trigger="session"` is declared and not honoured

The engine branches on `trigger == "entry"` only; `session` falls through to the
per-trade exit loop. **2 qualifying sessions produce 4 events**, one of which
repeats the same symbol.

**Already recorded in the pending register** from the `early_exit` review; noted
here as a second confirmed instance rather than a new finding.

### P4. Analytics with no reader

`info`, `disposition=analytics`, `notification_level=0`. By the closed INFO rule
it creates no `RiskAlert` and reaches no surface. Its registry comment says it
*"feeds the Strategy Health driver"* — **that driver does not consume it today**,
the same open question recorded for `rapid_reentry`.

### P5. INSUFFICIENT EVIDENCE on whether it is useful

Two qualifying sessions. That is not enough to say whether a trader shown this
would act differently, and rest-of-session P&L cannot judge it by the design of
record. **Stated as insufficient rather than resolved.**

## Evidence

| question | answer |
|---|---|
| does it fire? | **0** today; **4** with a baseline supplied |
| why 0? | the reference book has no profile — the input is real and persisted |
| is it selective? | **yes** — 175 → 26 → 2 sessions |
| is the data produced? | **yes**, `behavioral_baseline_service`, sync path |
| is it pure? | yes |
| does it set confidence? | **yes**, from the baseline's own |
| is it useful? | **INSUFFICIENT EVIDENCE** (n = 2 sessions) |

## Observability limitations

The reference book cannot exercise it, because a CSV tradebook carries no
profile and therefore no baseline. Everything above with a baseline is a
*simulation* using the book's own history as the baseline — defensible, but not
the same as a real trader's 90-day rolling figure.

## Recommended behavioural contract

> **Subject.** Today's win rate against this trader's own established baseline,
> at a sample where the comparison means something.
>
> **Reports, never interprets** — the current copy already refuses the
> psychological reading, and that should survive any change.
>
> **Says nothing without a confident baseline**, which it already does.

## Exact changes required

**None.** The two defects are shared, recorded, and not this detector's:
`trigger="session"` is an engine-level contract, and the missing Strategy Health
reader is a product question.

## Verdict — **KEEP AS-IS**

Correctly wired, correctly gated, honest copy, real confidence, and its silence
on this book is an artefact of the book rather than a fault. Its usefulness is
unproven and stated as such.

---

# 27. `strategy_breakdown`

## Current behaviour

Everything `win_rate_collapse` requires, **plus** a profit-factor condition:

```
baseline_win_rate AND baseline_profit_factor, both confidence >= 0.5
>= 8 trades today
wr_collapsed:  (base_wr − today_wr) / base_wr >= 0.40
pf_collapsed:  today_pf <= base_pf * 0.50
BOTH required
```

Same registry shape as §26: `analytics`, `trigger=session`, `notification_level=0`,
`info`, confidence set from the weaker of the two baselines.

## What is correct

**Pure.** Both inputs real and persisted.

**The rationale is statistically sound on its face** — two independent
degradation signals are stronger evidence than either alone, and the registry
comment says exactly that.

**It takes the weaker of the two confidences**, which is the right way to combine
them.

## Problems found

### P1. On this book it is EXACTLY `win_rate_collapse`. Zero unique firings.

| | firings |
|---|---|
| `win_rate_collapse` | 4 |
| `strategy_breakdown` | 4 |
| **identical firing sets** | **True** |
| **unique to `strategy_breakdown`** | **0** |

```
2025-08-13  NIFTY2581424400PE      both
2025-08-13  BAJFINANCE25AUG900CE   both
2025-09-16  NIFTY2591625150PE      both
2025-09-16  NIFTY2591625150PE      both
```

The profit-factor condition **never excluded anything**. Every session with a
40% win-rate collapse also had a profit factor at or below half the baseline —
which is unsurprising, since a session winning 11% of its trades will almost
always have a wrecked profit factor.

**The PF condition is not vacuous in isolation** — 6 of the 26 qualifying
sessions had PF collapse — but as the second half of an `AND` with the win-rate
condition, it added nothing.

### P2. The redundancy cannot be settled at n = 2

Two sessions is not enough to conclude that PF never excludes a WR collapse.
It is enough to say the second signal has **not yet earned its place**, and not
enough to remove it.

### P3. Shares §26's P3 and P4 exactly

`trigger="session"` unhonoured; `info` with no Strategy Health reader.

## Evidence

| question | answer |
|---|---|
| does it fire? | **0** today; **4** with baselines supplied |
| unique coverage vs `win_rate_collapse` | **0 of 4** |
| is the PF condition ever the binding one? | **no** on this book |
| is PF collapse itself rare? | no — 6 of 26 qualifying sessions |
| is it pure? | yes |
| is it distinct? | **INSUFFICIENT EVIDENCE** at n = 2 |

## Observability limitations

Same as §26, plus: distinguishing it from `win_rate_collapse` requires sessions
where the two conditions **disagree**, and this book contains none. That is what
is missing, and no amount of further analysis of these 175 sessions will supply
it.

## Recommended behavioural contract

> **Subject.** Two independent performance signals degrading together, which is
> stronger evidence than either alone.
>
> **Must be able to differ from its own first signal.** A detector whose second
> condition never binds is a copy of the first under another name, and should
> either be shown to differ or be folded into it.

## Exact changes required

**None yet.** Folding it into `win_rate_collapse` is the obvious consolidation
and it is **not** justified on 2 sessions — that would repeat the error of acting
on evidence too thin to carry the conclusion.

## Verdict — **DEFER**

**Not DELETE.** Its subject is sound and 100% overlap across 4 events on 2
sessions is not a finding that can carry a retirement. Both detectors are
`info`-only with no reader, so nothing is harmed by waiting.

**Not KEEP AS-IS** — "keep" would imply it has been shown to add something, and
it has not.

**Unblock condition:** enough sessions reaching the 8-trade gate to observe
whether the profit-factor condition ever excludes a win-rate collapse. On this
book only 26 sessions reach that gate and 2 pass; that is the constraint, and it
is data, not method.

---

# Combined conclusion — do these three belong together?

**No. Two of them do; the third does not.**

They were reviewed together because they share a *status* — "never fired" — and
that turned out to be the only thing they share. The status had **two different
causes**:

| | `time_of_day_bias` | `win_rate_collapse` + `strategy_breakdown` |
|---|---|---|
| why zero | **mis-wired** — its input has no writer | **the book has no profile** |
| input | `detected_patterns["time_patterns"]` — **never persisted** | `detected_patterns["baseline"]` — **persisted on the sync path** |
| disposition | **alerting**, `notification_level=1` | analytics, `notification_level=0` |
| trigger | `exit` (correct for it) | `session` (declared, not honoured) |
| firings if fed | **81** | 4 |
| verdict | **MODIFY** | **KEEP AS-IS** / **DEFER** |

**`time_of_day_bias` should not be maintained with the other two.** It is an
alerting detector with a plumbing defect, its own producer, its own statistical
question, and eighty-one times the volume. Grouping it with two silent analytics
detectors would bury exactly the finding that matters.

**`win_rate_collapse` and `strategy_breakdown` genuinely belong together** and
should be maintained as a pair: identical inputs, identical gates, identical
disposition, one is a strict superset of the other's condition, and on this book
identical output. Any future work on one is work on both — and the open question
about the second is precisely whether it should remain separate from the first.

**One shared finding worth carrying:** all three depend on learned history, and
two of the three chains were broken or unread at some point.
`detected_patterns` is written by two different services on two different paths,
read by three more, and has no test asserting which keys exist. That is the
common thread, and it is a plumbing question rather than a behavioural one.
