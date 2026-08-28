# Pattern #11 — `direction_instability` · review

28 Aug 2026. Detector `2.0.0`, `behavior_engine.py:1871`. Measured against the
corrected book: **189 sessions, 912 positions**. Replay: **10 alerts / 9 days**
of 203 sessions; **18 raw detections** before dedup.

**No code changed. Findings only.**

---

## 1. What it is meant to detect, and the mechanism

A **directional flip** — betting the market goes the other way, minutes after
betting it went this way. A Phase-4 merge of two v1 detectors, `rapid_flip` and
`options_direction_confusion`.

**Mechanism assumed:** the trader is reacting to price rather than acting on a
view. If a position goes against you and you immediately take the opposite side,
the second trade is a response to the first trade's outcome, not an independent
judgement. Registry copy: *"Reversing repeatedly usually tracks the price rather
than a view about it."*

The claim is about the **sequence of instrument choices**, which makes it
testable by permuting that sequence.

---

## 2. What the implementation does

```
gate    ct.entry_time exists
        strategy legs suppressed (_STRATEGY_SUPPRESSED)

find    the most recent prior closed trade that this trade flips against:
  L1 "exact"      same tradingsymbol, opposite direction, gap < rapid_flip_min
  L2 "underlying" CE<->PE, same underlying, BOTH LONG,
                  gap < direction_confusion_window_min
        gap = ct.entry_time - prior.exit_time   (negative gaps excluded)

count   session_flips = flips across every adjacent pair in the session
sev     danger if session_flips >= 3, else caution
```

| value | where | status |
|---|---|---|
| `rapid_flip_min` = 10 | `trading_defaults.py:122` | in registry as **`PERSONAL_BASELINE` / `Source.SESSION`**, metric `flip_interval_p25` |
| `direction_confusion_window_min` = 10 | `trading_defaults.py:264` | **not in `threshold_registry` at all** |
| `session_flips >= 3` → danger | inline literal | no key, no provenance |

**User Rules / onboarding: not used**, and nothing here suggests they should be.

**Severity** is the only escalation: `caution`, → `danger` at 3 session flips.
**Confidence** is never set. **Dedup** keys on `pattern_type` alone, 24 h, no
`_WORSEN_METRIC` re-arm — so 18 raw detections become 10 alerts.

**Not in any consolidation family**, though it sits next to *"going back to the
same trade"* (`same_symbol_obsession`, `revenge_trade`, `rapid_reentry`).

---

## 3. Are the values justified?

**Partly, and one registry declaration is false.**

- **`rapid_flip_min` is declared personal and can never become personal.**
  Its metric `flip_interval_p25` is **produced by no code** — 0 occurrences
  outside the registry. The ladder always falls through to the hardcoded 10, for
  every trader, permanently. Same defect as Pattern 7's `fomo_underlyings_*`,
  Pattern 9's `expiry_day_trades_*` and Pattern 10's unregistered threshold.
  Its stated provenance — *"a scalper reverses in seconds as a matter of
  course"* — is a good reason to personalise and an accurate description of an
  intention that was never wired up.
- **`direction_confusion_window_min` is not in the registry at all**, so it has
  no `Kind` and no provenance.
- **The 10-minute value is unsourced** but, unlike Pattern 10's threshold, it
  **does real work** — see Evidence. Its comment (*"legitimate 5-min reversals
  exist… true emotional whipsaw = under 10 min"*) is an assertion, not a
  derivation.
- **`session_flips >= 3` → danger** has no key and no derivation. It fired once.

---

## 4. Replay and real-data testing

### It fires rarely, and only on one of its two branches

```
18 raw detections on 11 of 189 sessions   ->   10 alerts on 9 days after dedup
severity : caution 17, danger 1
level    : L2 (CE<->PE) 18,  L1 (exact reversal) 0
gap      : min 0.2m, median 4.4m, max 9.7m
```

**Level 1 never fires, and cannot.** This trader's book is **911 LONG against 1
SHORT**; there are **zero** same-symbol opposite-direction pairs at *any* gap.
An options buyer does not reverse a symbol, they close it and buy the other side
— which is Level 2.

**This is a limit of the evidence, not a fault in the detector.** Level 1 is the
live branch for a futures trader or an option seller. Deleting it because one
options-buyer's book cannot reach it would be overfitting.

### The sequence null — the decisive test, and it does not settle the question

Time slots stay exactly where they are; only **which trade occupies each slot**
is permuted, so the session's instrument mix, timing and P&L are all preserved
and only the ordering of instrument choices is destroyed. The real detector runs
inside the loop.

| | |
|---|---|
| observed, real order | **18** |
| shuffled, mean of 300 permutations | **14.8** |
| 95% range | [10, 19] |
| ratio observed / expected | **1.21** |
| p(shuffled ≥ observed) | **0.187** |

**This is a materially different result from Patterns 4, 6 and 10.** Those fired
at or *below* chance, with the sign against the hypothesis. This one is *above*
chance in the direction the detector claims — just not significantly, and at
n=18 it could not have been. The honest reading is **underpowered, not refuted**.

### No demonstrated consequence

| | n | win rate | mean P&L |
|---|---|---|---|
| the trade the flip alert fires on | 18 | 44.4% | −₹123 |
| every other trade after the session's first | 705 | 40.6% | −₹69 |

−₹54/trade at **p = 0.892**; win rate **+3.9pp better**, p = 0.815. **The flagged
trade is not worse than an ordinary one.**

### Does flipping follow losses?

The message appends *"after a loss on that view"*, and 12 of 18 firings follow a
losing trade — but that is close to the base rate of losing at all:

| | |
|---|---|
| P(next trade is a flip \| prior **lost**) | **2.9%** (9/312) |
| P(next trade is a flip \| prior **won**) | **1.3%** (3/223) |
| difference | +1.5pp, **p = 0.263** |

Directionally consistent with the emotional story, not significant, n=12 vs 3.

### The window does real work

| window | 2m | 5m | **10m** | 20m | 30m | 60m |
|---|---|---|---|---|---|---|
| firings | 7 | 10 | **18** | 23 | 28 | 42 |

Unlike Pattern 10's threshold — which trimmed the edge of a set already selected
— this value materially decides what fires. That does not make 10 *correct*, but
it does make it load-bearing rather than decorative.

### Overlap

```
10 alerts on 9 days
  it was the ONLY alert that day: 1 of 9
  co-firing: same_symbol_obsession 5 · adding_to_adverse_position 5
             options_premium_avg_down 4 · size_escalation 3 · martingale 3 ...
```

`same_symbol_obsession` co-fires on **5 of 9** days, which is expected —
flipping CE↔PE on one underlying *is* concentrating on that underlying. They are
not in a shared family, so both reach the trader.

### Observability limits

- **n = 18 firings, one trader, one trading style.** Every statistical test here
  is underpowered. Nothing in this review can confirm or refute the behaviour.
- **Level 1 is untested**, structurally, for the reason above.
- `session_flips` counts flips over adjacent pairs ordered by `exit_time`, while
  the flip search itself scans *all* recent priors. The two use slightly
  different neighbourhoods, so the count in the message and the trigger are not
  computed the same way. Not observed to matter at this volume.
- Confidence is never set.

---

## 5. Is the alert meaningful?

**As written, yes — and it is honest**, which distinguishes it from the last two
patterns reviewed.

- The message states **facts**: which instruments, the gap in minutes, whether
  the prior trade lost, how many flips this session. Every one is checkable.
- It carries **no invented statistic** — no "NSE data" claim, no fabricated
  percentage.
- The headline names the **right underlying**, and the trades shown are the ones
  the trigger used.
- Volume is low: 10 alerts across 203 sessions.

The registry copy's *"usually tracks the price rather than a view about it"* is a
mechanism assertion rather than a measured claim, hedged with "usually". It is
weaker than a fabricated statistic but is not evidenced here either.

---

## 6. Performance and purity

**Pure.** No DB, no Redis, no network, no clock — everything from `ctx`. Cost is
O(session²) in the worst case (`_is_flip` over priors, plus a session-wide
recount per trade), which at this book's session sizes is trivial. Correctly
included in `_STRATEGY_SUPPRESSED`, so straddle/strangle legs cannot false-fire —
and independently, a simultaneously-opened structure produces a negative gap and
is excluded anyway.

---

## Current behaviour

Fires when a completed trade reverses direction against a recent prior — same
symbol opposite direction (Level 1), or CE↔PE on one underlying with both legs
long (Level 2) — within 10 minutes. `caution`, escalating to `danger` at 3 flips
in a session. 18 raw detections → 10 alerts across 203 sessions.

## What is correct

- **Pure, cheap, strategy-suppressed.** The hedge-leg false-positive class is
  closed twice over.
- **The message is factual.** Instruments, gap, prior P&L, session count — all
  checkable, no invented statistics, correct underlying, and the evidence shown
  is the evidence used.
- **The two levels describe genuinely different acts** — reversing a symbol vs
  swapping side on an underlying — and merging them under one name was right.
- **The window is load-bearing**, not decorative.
- **Low volume**, and dedup collapses 18 detections to 10 alerts.
- **Negative gaps are excluded**, so simultaneous structures cannot register.

## Problems found

1. **`rapid_flip_min` is declared `PERSONAL_BASELINE` against a metric nothing
   produces** (`flip_interval_p25`, 0 producers). It can never personalise. A
   false statement in the registry — the fourth instance of this class.
2. **`direction_confusion_window_min` is not in the registry at all** — no
   `Kind`, no provenance, despite being one of the two values that decide
   everything.
3. **Level 1 has never fired and cannot on this book** — 911 LONG vs 1 SHORT.
   Untestable here; not evidence against it.
4. **No demonstrated consequence** — the flagged trade is not worse (p = 0.892),
   and its win rate is slightly *better*.
5. **`session_flips >= 3` → danger** is an inline literal with no key, no
   derivation and one firing.
6. **Not in a consolidation family** despite co-firing with
   `same_symbol_obsession` on 5 of 9 days, describing overlapping behaviour.

## Evidence

Permutation tests, 300 sequence-permutations for the null and 20,000 resamples
for the comparisons, seed 7. Full figures above. The three that matter:

- **sequence null: 18 observed vs 14.8 expected, ratio 1.21, p = 0.187**
- **outcome: −₹54/trade, p = 0.892; win rate +3.9pp, p = 0.815**
- **flip-after-loss: 2.9% vs 1.3%, +1.5pp, p = 0.263**

**The evidence is insufficient to decide this pattern, and I am saying so rather
than forcing a verdict.** With 18 firings in a year no test here can reach
significance. What can be said is that, unlike Patterns 4, 6 and 10, **nothing
points the wrong way** — the null leans mildly *toward* the detector's claim.

## Recommended behavioural contract

**Leave the behaviour alone. Fix the registry so it stops describing an
intention as a fact.**

The detector makes a modest, factual, low-volume claim and does not overstate it.
There is no evidence it is wrong and not enough to confirm it is right. Retiring
it would be acting on absence of evidence, which is the opposite of the standard
applied to Patterns 4, 6 and 10 — those were retired because measurement pointed
*against* them, not because it was quiet.

## Exact changes required, if any

**Two registry-truthfulness fixes. No behavioural change, no threshold change,
no new values.**

1. Reclassify `rapid_flip_min` from `Kind.PERSONAL_BASELINE` to `Kind.FALLBACK`
   until a producer for `flip_interval_p25` exists — exactly the treatment
   Pattern 7 gave `fomo_symbols_in_window`. Keep the provenance note; it records
   why personalising it would be worth doing.
2. Add a `_spec` for `direction_confusion_window_min` recording what it is, or
   record explicitly why it is absent.

Both are declarations. Neither changes a single firing, so **no replay is
required** to land them.

**Not recommended:** deleting Level 1 (untestable here, live for other trading
styles), retuning the 10-minute window (no basis to move it), adding a
consolidation family (a merge, which this review is not authorised to design),
or personalising anything.

## Verdict

**MODIFY — registry truthfulness only. The behaviour is KEEP AS-IS with the
evidence recorded as insufficient.**

This is the first pattern in this sequence that measurement does not condemn.
The sequence null runs **1.21× above chance (p = 0.187)** — weakly *for* the
detector, where Patterns 4, 6 and 10 all ran at or below chance with the sign
against them. Its alert is factual, carries no invented statistic, names the
right instrument, shows the evidence it used, and fires 10 times in 203 sessions.

What it does not have is a demonstrated consequence: the flagged trade is not
worse (p = 0.892). At n=18 that is a statement about the sample, not the
detector. **Revisit when there is more data or a second trader's book** — and if
this pattern is measured again, the sequence null is the test to repeat.

**Recorded for later reviews, not fixed here:**
- **The unproduced-baseline-metric defect is now four for four** —
  `fomo_underlyings_*` (P7), `expiry_day_trades_*` (P9), `size_escalation_pct`
  unregistered (P10), `flip_interval_p25` (P11). Worth one sweep across the whole
  registry rather than four more per-pattern fixes: any `PERSONAL_BASELINE` spec
  whose metric has no producer is currently a false declaration.
- `session_flips` and the flip trigger scan different neighbourhoods (adjacent
  pairs by `exit_time` vs all recent priors). Harmless at this volume.
- `direction_instability` and `same_symbol_obsession` co-fire on 5 of 9 days
  without a shared family.
