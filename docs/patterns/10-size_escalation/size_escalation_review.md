# Pattern #10 — `size_escalation` · review

27 Aug 2026. Detector `1.1.0`, `behavior_engine.py:1388`. Measured against the
corrected book: **189 sessions, 912 positions**. Replay reference: **30 alerts /
30 days** of 203 sessions. In-process detections before dedup/consolidation: **42**.

**No code changed. Findings only.**

---

## 1. What it is supposed to detect, and the mechanism

**Intended behaviour:** a trader whose position size drifts upward across
consecutive trades *while those trades are losing* — sizing up to recover rather
than sizing to an edge.

**The mechanism it assumes:** loss-chasing / escalation of commitment. After a
loss the trader raises stake to make the loss back in one trade, so the *sequence*
of sizes carries information the individual sizes do not. This is the same
mechanism `martingale_behaviour` claims, in a weaker form — martingale asserts a
doubling *progression*, this asserts a *drift*.

The registry copy states it plainly: *"Quantity across consecutive trades on the
same underlying while losing… Larger size on an instrument that is already losing
compounds the drawdown rather than recovering it."*

**The claim is entirely about ordering.** That makes it directly testable by
permutation, which is the decisive test below.

---

## 2. What the implementation does, end to end

```
gate     len(ctx.session_trades) >= 3

branch A same underlying as ct, last 3 by exit_time, sizes = total_quantity
         if NOT strictly increasing -> fall through to B
branch B last 3 trades of the session regardless of instrument,
         sizes = _notional(t) = |total_quantity| * avg_entry_price   (rupees)
         cross = True

gate     sizes[0] < sizes[1] < sizes[2]           strictly increasing
gate     losses_before = count(p < 0 for p in pnls[:2]) >= 1
gate     (sizes[2] - sizes[0]) / sizes[0] * 100 >= size_escalation_pct   (30)

emit     severity "caution", always. confidence None (derived).
         notification_level 1. disposition alerting, trigger exit.
```

| value | where | status |
|---|---|---|
| `size_escalation_pct` = 30 | `trading_defaults.py:135` | **absent from `threshold_registry.py` entirely** — no `Kind`, no `Source`, no provenance, no `MANDATORY_REVIEW` entry |
| window = 3 trades | inline literal | no key, no provenance |
| `pnls[:2]`, `>= 1` loss | inline literal | no key, no provenance |
| strictly increasing | inline | definitional to the claim |
| severity `caution` | inline, fixed | never escalates |

**User Rules / onboarding: not used.** The trader declares a max position size in
onboarding, and `BehaviourLead.tsx:55` even tells them *"Set a max position size"*
as the response to this alert — but **no declared rule reaches this detector**. It
reads only `size_escalation_pct` from `ctx.thresholds`.

**Consolidation:** it is the *last* member of the `"sizing after losses"` family,
behind `martingale_behaviour` and `post_loss_recovery_bet`, so on a trade where a
stronger member fires it is folded. **Dedup:** keys on `pattern_type` alone, 24 h,
no `_WORSEN_METRIC` re-arm.

**Purity: confirmed.** No DB, no Redis, no network, no clock. `_notional` and
`parse_symbol` are pure. Safely replayable.

---

## 3. Are the values justified?

**No, and one of them is not even registered.**

`size_escalation_pct` never entered the threshold registry, so it has no declared
`Kind` and no provenance. Its only justification is the comment beside it:

> *"30% consistent increase after losses is meaningful signal (not 50%). It
> compounds: 3 trades at +30% each = 2.2× original size."*

**The comment describes a different computation than the code.** The code is
`(sizes[2] - sizes[0]) / sizes[0]`, a single first-to-third increase. 30% there
means the third trade is **1.3×** the first — not 2.2×. The compounding argument
would require +30% *per step*, which the code never checks.

The window (3), the loss test (`pnls[:2]`, `>= 1`), and the fixed `caution` are
inline literals with no key, no derivation and no test pinning them.

Threshold sensitivity says the number barely matters:

| `size_escalation_pct` | 0 | 10 | 20 | **30** | 40 | 50 | 75 | 100 |
|---|---|---|---|---|---|---|---|---|
| firings | 51 | 49 | 48 | **42** | 41 | 39 | 31 | 27 |

Going from 0% to 30% removes 9 of 51. The real gate is `sizes[0] < sizes[1] <
sizes[2]`; the percentage trims the edge of a set that is already selected.

---

## 4. Replay and real-data testing

### It fires at the chance rate for its own gate

Three distinct sizes are strictly increasing **1 time in 6 (16.7%)** by chance.
Measured over every 3-trade window in the book by notional:

```
69 of 408 windows strictly increasing  =  16.9%
```

The gate that defines the pattern selects at exactly its chance rate.

### The shuffle null — the decisive test

The claim is about *sequence*, so preserve every session's trades, sizes and P&L
and permute only the **order**, running the **real detector** inside the loop.

| | |
|---|---|
| observed, real order | **42** |
| shuffled, mean of 200 permutations | **49.7** |
| 95% range | [36, 65] |
| ratio observed / expected | **0.85** |
| p(shuffled ≥ observed) | **0.880** |

**The real order produces fewer firings than chance ordering.** The sequence —
which is the entire premise — carries nothing. This is the same result that
retired Pattern 4 and Pattern 6.

### The "while losing" condition excludes nothing

`losses_before = sum(1 for p in pnls[:2] if p < 0) >= 1` — only the **first two**
of the three trades, and **one** loss suffices.

- book-wide loss rate **58.4%** → P(≥1 loss in 2 trades) ≈ **82.7%**
- among the 42 firings: 2 losses **25**, exactly 1 loss **17**, **zero losses 0**
- the **third** trade — unchecked by the code — was a loss in only 24 of 42

So the qualifier that makes the alert say *"while losing"* is satisfied by four
sessions in five before anything about the trader is considered, and the code
never looks at whether the trade *at the top of the escalation* lost.

### It predicts nothing

| | n | win rate | mean P&L |
|---|---|---|---|
| the trade a firing is raised on | 42 | 42.9% | **+₹10** |
| other trades at index ≥ 3 (same eligibility) | 366 | 41.8% | −₹60 |

Difference **+₹69/trade, p = 0.797**. The flagged trade is very slightly *better*.

Rest-of-session after the first firing of a day: **+₹677** (n=36) against
**−₹499** for sessions that never fired (n=82). Direction is opposite to the
detector's premise, though not significant.

### False positives — the alert names an instrument that is not in its own evidence

**37 of 42 firings (88%) use branch B**, the cross-instrument notional path. The
message headline is `ct_underlying` — the underlying of the *current* trade —
while the three trades shown are whatever the session's previous three were:

```
ICICIGI: position size increased across 3 consecutive trades while losing —
         ₹2,984→₹3,491→₹9,700 (TCS25APR2900PE / TCS25APR3500CE / HUDCO25APR230CE).

NIFTY:   position size increased across 3 consecutive trades while losing —
         ₹4,688→₹6,365→₹7,438 (JINDALSTEL25APR900CE / CHAMBLFERT25APR700CE / CHOLAFIN25APR…).
```

ICICIGI is not one of the three trades. Neither is NIFTY in the third example.
**In 37 of 42 firings the headline underlying is not the underlying of the
sequence shown.** The registry copy compounds this by promising *"Quantity across
consecutive trades on the same underlying"* — which describes branch A, used in
**5 of 42** firings.

### The triggering trade is not in its own alert

`prior` is built from `ctx.session_trades`, which **excludes `ct`**. The alert
fires on trade N and describes trades N−3, N−2, N−1.

**Only 7 of 42 alerts contain the trade that triggered them.** A trader who has
just closed a position is shown three earlier ones and told their size is rising.
This is the same defect already recorded against `martingale_behaviour` (*"the
displayed sequence includes the current trade; the `max_ratio` that decides
severity does not"*) — here it runs the other way.

### Observability limits

- `size_sequence` holds **lots on branch A and rupees on branch B**, distinguished
  only by the `cross_instrument` flag. A reader that ignores the flag renders
  rupees as quantity.
- Severity is fixed `caution`, so escalation is unobservable.
- `confidence` is never set by this detector.
- **Not tested:** whether declared max-position-size would separate anything, and
  whether escalation measured *per step* rather than first-to-third behaves
  differently. Both would need new code, which this review does not propose.

---

## 5. Overlap, and whether the alert is meaningful

From the 203-session replay artifact — 30 alerts on 30 days:

```
it was the ONLY alert that day                          4 of 30
a STRONGER member of its own family also fired that day 14 of 30
co-firing: martingale_behaviour 14 · adding_to_adverse_position 11 · fomo_entry 9
           death_spiral 9 · same_symbol_obsession 8 · expiry_day_overtrading 7 …
```

Family consolidation is **per trade**, not per day, so on those 14 days the trader
receives *"you are doubling down"* **and** *"your size is rising"* — the family
ordering was written precisely to prevent that, and it does not, because the two
fire on different trades in the same session.

**Is the alert meaningful?** As written, no. It names an instrument that is absent
from its evidence, shows three trades that exclude the one that triggered it,
qualifies itself with a condition true 83% of the time, and selects at its own
chance rate.

---

## 6. Performance and purity

**Clean.** No DB, no Redis, no network, no clock, no `datetime.now`. Two
`parse_symbol` calls per prior trade — pure string parsing. Cost is O(session
length) per completed trade. Nothing to fix here.

---

## Current behaviour

Fires on a completed trade when the three trades *before* it were strictly
increasing in size — quantity if they share the current trade's underlying (5 of
42 firings), otherwise notional rupees across any instruments (37 of 42) — and at
least one of the first two lost, and the third is ≥ 30% larger than the first.
Always `caution`. Folded when a stronger family member fires on the same trade.

## What is correct

- **The detector is pure**, cheap, and safely replayable.
- **`_notional` is the right comparable across instruments.** Quantity is not: 50
  NIFTY against 2000 IndusTower says nothing. The reasoning recorded beside it is
  sound.
- **The cross-instrument fallback fixed a real bug.** The earlier version returned
  before branch B could run, so it saw nothing across 61 sessions.
- **Family ranking is right in principle** — `martingale_behaviour` first,
  `size_escalation` last, "the specific one is the harder claim to make".
- **`caution` is the honest ceiling** for a drift claim; it never escalates itself
  into `danger`.

## Problems found

1. **The ordering premise fails.** Shuffle null: 42 observed vs 49.7 expected,
   ratio 0.85, **p = 0.880**. The real sequence fires *less* than chance.
2. **The gate selects at its chance rate** — 16.9% of 3-trade windows are
   strictly increasing against 16.7% expected.
3. **The alert names an instrument absent from its own evidence** — 37 of 42.
4. **The triggering trade is not in its own alert** — only 7 of 42 contain it.
5. **"While losing" is not a condition** — satisfied 83% of the time by base
   rate; the trade at the top of the escalation is never checked.
6. **`size_escalation_pct` is not in the threshold registry**, and the comment
   justifying 30 describes per-step compounding the code does not compute.
7. **No predictive value** — +₹69/trade at p = 0.797, sign favouring the flagged
   trade.
8. **Family consolidation is per-trade**, so 14 of 30 days still carry both this
   and `martingale_behaviour`.
9. **`size_sequence` mixes units** (lots / rupees) behind a flag.

## Evidence

Permutation tests, 200 order-shuffles for the null and 20,000 resamples for the
P&L comparisons, seed 7. All figures above; the decisive ones are the shuffle
null (**ratio 0.85, p = 0.880**), the chance-rate gate (**16.9% vs 16.7%**), and
the outcome test (**p = 0.797**).

**Limits:** one trader, 189 sessions, 42 firings. The outcome tests are
underpowered on their own. What makes the finding safe is that the shuffle null
does not depend on outcomes at all — it tests the detector's own premise using
the detector's own code, and that premise fails independently of P&L.

## Recommended behavioural contract

**Size escalation as currently defined — a monotone rise over a fixed 3-trade
window — is not a behaviour. It is the 1-in-6 arithmetic of three numbers.**

If sizing after losses is to be alerted on, the engine already has the stronger
form: `martingale_behaviour` asserts a *doubling progression* and
`post_loss_recovery_bet` asserts *one oversized bet after losses*. Both make a
harder claim than "three numbers went up", and both are ranked above this one for
that reason.

The one version of this claim that would be defensible and is not implemented is
**against the trader's declared max position size** — a commitment, not an
inference. That is `constitution_violation`'s territory, and the frontend already
tells the trader to *"Set a max position size"* in response to this alert. It is
not proposed here.

## Exact changes required, if any

**None yet — this is a review.** Two options, for decision:

### Option A — RETIRE (recommended)

Precedent: Patterns 4 and 6, both retired on the same null. Delete the detector,
its `DetectorSpec`, its `PatternCopy`, `size_escalation_pct`, and drop it from
the `"sizing after losses"` family (leaving `martingale_behaviour` and
`post_loss_recovery_bet`, which are untouched). Keep `_notional` — martingale and
others read it. Keep every frontend label for stored rows. Expected replay delta
**−30 alerts**, plus a `death_spiral` fall as arithmetic on its 9 co-firing days.

### Option B — RESEARCH FURTHER before deciding

Only if you want the sizing-after-loss claim rescued rather than dropped. It would
have to be re-specified against something that is not chance — the trader's
declared max size, or escalation measured per step against their own baseline —
and re-tested against the same null. **This is new work, not a fix**, and nothing
in the current evidence suggests the rescued version would fire on this book.

Problems 3, 4, 6 and 9 (mislabelled headline, missing triggering trade,
unregistered threshold, mixed units) are **only worth fixing under Option B**.
Under Option A they disappear with the detector.

## Verdict

**DELETE — retire as a behavioural detector.** Option A.

The detector's entire claim is that the *order* of position sizes carries
information. Tested with its own code against 200 order-shuffles of the same
trades, the real order fires **less** than chance (42 vs 49.7, ratio 0.85,
**p = 0.880**), and its defining gate selects at exactly the 1-in-6 rate three
random numbers are increasing (16.9% vs 16.7%). Its "while losing" qualifier is
true 83% of the time by base rate and never checks the trade at the top of the
escalation. It predicts nothing (p = 0.797, sign favouring the flagged trade). And
as shipped it is wrong on its face: **37 of 42 alerts name an instrument that is
not among the three trades they show**, and only 7 of 42 include the trade that
triggered them.

Retiring it costs 30 alerts. The two stronger members of its own family —
`martingale_behaviour` and `post_loss_recovery_bet` — already own the defensible
version of this claim and are ranked above it for exactly that reason.

**Recorded for later reviews, not fixed here:**

- `demoData.ts:333` and `:1030` give `size_escalation` severities `critical` and
  `danger`; the detector only ever emits `caution`. The vocabulary contract checks
  that fixture severities are *in* the vocabulary, not that they match what the
  detector can emit. Same class as the guest-mode field-name bugs.
- **Family consolidation is per-trade, not per-session.** Two members of one
  family firing on different trades in a day both reach the trader. Affects the
  `"sizing after losses"` and `"going back to the same trade"` families
  generally, not just this pattern.
- `martingale_behaviour`'s displayed sequence includes the current trade while its
  deciding `max_ratio` does not — the mirror image of problem 4, already on the
  tracker and still open.

---

## Addendum — coverage-gap check (27 Aug, requested before deletion)

**Question:** if `size_escalation` goes, is any meaningful sizing behaviour left
uncovered by `martingale_behaviour`, `post_loss_recovery_bet`,
`adding_to_adverse_position` and `options_premium_avg_down`?

**Answer: no. The concept is covered. Retire.**

### What each of the four actually owns

| detector | subject | unit | trigger |
|---|---|---|---|
| `martingale_behaviour` v2.0.0 | **the current trade**, stepped from the previous closed one | **capital at risk** (`instrument_risk.risk_basis`) | ≥2 **trailing consecutive** losses, step ≥1.5× / 2.0× |
| `post_loss_recovery_bet` | **the current trade** vs mean of last 3 | qty within one underlying, notional across | last 2 same-underlying trades both losses, ≥2.0× / 3.0× |
| `adding_to_adverse_position` | one **open** position's fill sequence | — | added while the position moved against them. **Size deliberately excluded** — 95 of 96 adverse adds were under 1.5×, median 0.67× |
| `options_premium_avg_down` | re-entry on the same underlying long option | premium | prior loss on that underlying |

The first two own "sized up after losing" outright, and both do it the way this
detector does not: **the current trade is the subject**, the comparison is the
step the trader actually took, and martingale's unit is capital at risk rather
than a quantity/notional mix.

### Measured overlap is LOW — and that is not a reason to keep it

On the same trade `size_escalation` fires on (42 firings):

```
martingale_behaviour          2 / 42
post_loss_recovery_bet        1 / 42
options_premium_avg_down      8 / 42
covered by a sizing detector  3 / 42
covered by any of the four   10 / 42
```

Per session (36 sessions): a sizing detector fired somewhere in **21 of 36**, any
of the four in **26 of 36**.

**This corrects a claim in the body of this review.** The earlier draft leant on
redundancy — that martingale already says this. Measured, it mostly does not:
`size_escalation` selects a largely *different* set of trades. The reason to
retire is not that something else says the same thing. It is that **what it
uniquely selects is not a behaviour** — it fires *less* than shuffled trade order
(42 vs 49.7, p = 0.880) and its gate hits at the chance rate for three increasing
numbers (16.9% vs 16.7%). Low overlap with a real detector plus chance-level
selection means the non-overlapping firings are residue, not signal.

### The one genuine conceptual gap is empty in practice

A **slow ramp** is the only sizing shape that could evade all four: monotone
growth where every step is under martingale's 1.5× and the current trade stays
under post_loss_recovery's 2.0× of the recent mean, yet cumulative growth is
large. It is mathematically possible (1.45 × 1.45 = 2.1×).

Measured across 189 sessions / 912 positions, requiring monotone growth, every
step < 1.5×, cumulative ≥ 2.0×, current < 2× the window mean, and at least one
prior loss:

| window | occurrences in a full year |
|---|---|
| 3 trades | **0** |
| 4 trades | **1** |
| 5 trades | **1** |

**The gap exists on paper and not in the data.** There is nothing to build a
replacement detector for, and building one on one or two instances would be
inventing a pattern rather than finding one.

### Harness note — a self-correction

The first run of this check reported `martingale_behaviour` covering **0 of 42**
and was wrong. `martingale` v2.0.0 returns a `DetectorResult`, which wraps a
positive finding as well as a negative one; the check treated every
`DetectorResult` as a non-firing and silently zeroed it. Caught by validating
raw in-process detections against the replay's alert counts before using them:

```
martingale_behaviour        raw 48   replay 39   OK
post_loss_recovery_bet      raw  9   replay  5   OK
options_premium_avg_down    raw 60   replay 30   OK
adding_to_adverse_position  raw  0   replay 99   HARNESS LIMIT - needs position_fills
```

The correct predicate is `DetectorResult.fired` (`evidence.verdict is
Verdict.POSITIVE`). `adding_to_adverse_position` cannot be measured in this
harness at all — it reads a fill sequence the CSV reconstruction does not carry —
so its 0 above is a limit of the tool, not a finding. The replay shows it firing
99 times, and on 11 of the 30 `size_escalation` days, so true session coverage is
**higher** than the 26 of 36 reported here.

### Verdict of the coverage check

**Covered. Proceed with retirement.** `martingale_behaviour` and
`post_loss_recovery_bet` hold the defensible form of the claim; the shape only
`size_escalation` could have caught occurs twice in a year, both outside the
3-trade window it uses.
