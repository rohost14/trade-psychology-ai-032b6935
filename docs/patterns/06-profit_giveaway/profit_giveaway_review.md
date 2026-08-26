# Pattern #6 — `profit_giveaway`

27 Aug 2026. **Review only. No code changed, no threshold added or retuned, no
detectors merged.**

**Verdict: MODIFY.** The subject is real and, unlike Pattern 5, it is a genuine
minority event rather than the ordinary arithmetic of a day. But the gate that
decides who hears about it excludes **more than twice the realized damage it
admits**, and the quantity carrying severity stops being a percentage of
anything once the session goes red.

---

## 1. What it is supposed to detect, and the mechanism

An intraday session that reached a profit high-water mark and then handed a
material share of it back. Registry copy: *"The trade taken after a session peak
is the one that decides whether the day is kept."*

The mechanism appealed to is the **house-money effect** (Thaler & Johnson) and
its mirror in the disposition literature: gains not yet booked are treated as
not-quite-real, so a trader risks them more freely than the same rupees in their
opening balance. Unlike Pattern 4's streak, this claim is not about a run being
a state — it is about a **specific, observable reference point** (the peak) and
what happens on the far side of it.

**That is a better-formed claim than the previous two patterns**, and the
evidence in §4 supports the subject even where it does not support the tiers.

## 2. What the implementation does, end to end

`behavior_engine.py:3063-3170`, 108 lines.

```
trades      = session_trades + completed_trade, sorted by exit_time  (>= 2 required)
peak_pnl    = ctx.facts.peak_pnl        # high-water mark of the REALIZED curve, floored at 0
running_pnl = ctx.facts.pnl
min_peak    = thresholds["profit_giveaway_min_peak"]      (1,500, or 3% of capital)
min_erosion = thresholds["profit_giveaway_min_erosion"]   (500, or 1% of capital)
min_erosion = max(min_erosion, self._typical_loss(ctx))   # trader's own median losing trade, needs >= 3
if peak_pnl < min_peak:      return None
erosion     = peak_pnl - running_pnl
if erosion  < min_erosion:   return None
erosion_pct = erosion / peak_pnl

if running_pnl < 0 and erosion_pct >= 1.0  -> danger   (green-to-red branch, sign_flip=True)
if erosion_pct >= danger_pct  (0.70)       -> danger
if erosion_pct >= caution_pct (0.50)       -> caution
```

| input | value | classification / source |
|---|---|---|
| `profit_giveaway_min_peak` | 1,500 | **capital-relative**: 3.0% of declared capital (`_CAPITAL_RATIOS`), falling back to ₹1,500 |
| `profit_giveaway_min_erosion` | 500 | **capital-relative**: 1.0% of capital; then raised to the trader's own median losing trade when ≥ 3 losses are on record |
| `profit_giveaway_caution_pct` | 0.50 | inline default, **no source comment** |
| `profit_giveaway_danger_pct` | 0.70 | inline default, **no source comment** |
| the `1.0` sign-flip test | inline literal | **no key, no classification, no test** |

**Rules / onboarding:** none. No declared value reaches this detector — there is
no "protect my gains" rule in the constitution, and nothing in the onboarding
wizard maps here. **This is the first reviewed pattern with no user-declared
input available at all**, which materially changes what Pattern 4's and Pattern
5's resolutions can be copied onto.

**Severity** caution/danger · **notification level 2** → danger pushes ·
**confidence** not set by the detector, so it inherits the data-quality default
· **evidence/abstention** none — returns a `DetectedEvent`, not a
`DetectorResult` · **dedup** 2h (`_DEDUP_HOURS`) with `_WORSEN_METRIC =
"erosion_pct"` re-arming at +20% · **not** in `_STRATEGY_SUPPRESSED` · **no**
constitution pairing · **no** consolidation family.

## 3. Performance and purity — **KEEP AS-IS**

No `await`, no `db.`, no `select(` in the body. Ran 912 times in this review
with no database connection. It reads `ctx.facts`, which `_load_context` has
already computed, plus one sort of the session's trades. Negligible.

**One spec inaccuracy:** `consumes=("session", "session_trades",
"completed_trade", "thresholds")` omits `facts`, which is where both of its
primary inputs actually come from. `consumes` is descriptive metadata (one test
reads it), so nothing breaks — but it is wrong.

## 4. Evidence — 189 sessions, 912 positions, corrected trade set

Measured at the cold-start defaults with capital ₹50,000, matching the replay.
Cross-checked against the stored 203-session replay: 48 alerts there, 38 by this
review's dedup simulation on 189 sessions — consistent given the session count
differs.

### 4a. The baseline first — is this the ordinary day?

**No, and this is the important difference from Pattern 5.**

- 112 of 189 sessions went green on the realized curve at all.
- 69 (37%) reached a peak ≥ ₹1,500 — the gate.
- Of those 69, **end-of-day** erosion from peak:

| erosion at close | 0-25% | 25-50% | 50-70% | 70-100% | >100% (ended red) |
|---|---|---|---|---|---|
| sessions | **40 (58%)** | 11 (16%) | 3 (4%) | 5 (7%) | 10 (14%) |

**18 of 69 eligible sessions (26%) end having given back ≥ 50% of their peak.**
A clear minority. Handing back half a built-up day is not what this trader
usually does, so naming it is not naming their normal. **The subject survives.**

### 4b. What it fires

| | |
|---|---|
| detections | **55**, on **20 of 189 sessions (11%)** |
| alerts after dedup | **~38**, mean **1.9 per affected day**, max 4 |
| severity | **41 danger / 14 caution** — danger dominates |
| green-to-red (sign-flip) firings | **25 of 55** |
| `_typical_loss` engaged | 23 of 55 |
| peak at firing | p25 ₹2,046 · p50 ₹2,380 · max ₹13,958 |
| erosion at firing | p25 ₹1,636 · p50 ₹2,894 · max ₹12,866 |

### 4c. The gate excludes more damage than it admits

`min_peak` gates on the size of the **peak**. For the percentage branch that is
coherent — you need a real peak to talk about giving back a share of it. For the
**green-to-red branch it is the wrong quantity**, because how far below zero the
session ends has nothing to do with how high it got first.

Sessions that went green and then ended red:

| bucket | sessions | went green then ended red | total ending P&L |
|---|---|---|---|
| **peak ≥ 1,500 — alerts fire** | 69 | 10 | **−₹29,751** |
| peak 500-1,499 — silent | 25 | 9 | −₹35,114 |
| peak < 500 — silent | 18 | 14 | −₹31,098 |

> **23 sessions went green and ended red while excluded by the gate, totalling
> −₹66,212 — more than twice the −₹29,751 the gate admits.**

The five worst, none of which produced an alert:

| day | peak | ended |
|---|---|---|
| 2025-11-25 | ₹806 | **−₹9,956** |
| 2026-01-23 | ₹1,238 | −₹8,234 |
| 2025-08-13 | ₹334 | −₹6,548 |
| 2026-01-05 | ₹1,064 | −₹6,226 |
| 2025-06-11 | ₹470 | −₹5,008 |

A day that touched +₹334 and closed at −₹6,548 is exactly the story this
detector exists to tell, and it is silent because the peak was small.

### 4d. `erosion_pct` stops being a percentage

Once `running_pnl < 0`, `erosion = peak − current` with `current` negative, so
`erosion_pct` exceeds 1.0 without bound.

**25 of 55 firings have `erosion_pct` > 100%** — min 1.07, median 1.73, **max
4.87**. At 4.87 the number is not "the share of the peak given back" (that
saturated at 100%); it is new loss divided by an old peak, a ratio between two
unrelated quantities.

This matters twice over:

1. It is the **severity key**. Above 1.0 the sign-flip branch takes over and is
   always danger, so `erosion_pct` is reported but decides nothing there — while
   still appearing in the alert context as though it were meaningful.
2. It is the **`_WORSEN_METRIC`**, re-arming the alert whenever it grows 20%. A
   sinking session therefore re-fires against an unbounded number.

### 4e. Volume: the same story told several times

Mean 1.9 alerts per affected day; 5 of 20 days produce 3 or 4.

**2025-11-20, seven detections against one peak of ₹2,046:**

| pos | severity | peak | now | erosion |
|---|---|---|---|---|
| 4 | caution | ₹2,046 | ₹1,012 | 51% |
| 5 | **danger** | ₹2,046 | ₹52 | 97% |
| 6 | **danger** | ₹2,046 | −₹848 | 141% (flip) |
| 7 | **danger** | ₹2,046 | −₹2,098 | 203% (flip) |
| 8 | **danger** | ₹2,046 | −₹462 | 123% (flip) |
| 9 | caution | ₹2,046 | ₹825 | 60% |
| 10 | **danger** | ₹2,046 | ₹165 | 92% |

Four survive dedup. **The session ended at +₹165 — green.** Severity oscillates
because `erosion_pct` is a function of `current_pnl`, which moves both ways;
2 of 20 days show severity going back down mid-session.

**The code comment is also wrong.** It says: *"DB-level dedup … (checks last 24h
for same pattern_type) prevents this from firing more than once per session."*
The window for this pattern is **2 hours**, not 24 (`_DEDUP_HOURS`), and
`_WORSEN_METRIC` deliberately re-arms it. It fires up to four times per session,
measured.

### 4f. Days that end green

**24 of 55 firings — 10 of 20 alert-days — are on sessions that closed
profitable.** Median close on those: **+₹620**, max +₹4,843. **12 of the 24 are
danger**, i.e. a push notification.

Whether this is a false positive depends on the contract, and the review must be
fair about it: **at the moment it fired, the statement was true** — the trader
had given back that share of their peak. The design of record says an alert's
job is to convert an automatic action into a deliberate one, not to predict, and
by that standard firing on a true present fact is correct.

But `trading_defaults.py` records that this detector was retuned *because* it
"originally fired on days that ENDED GREEN". **On the corrected book it still
does, on half its alert-days.** Either the retune did not achieve its stated
goal, or the goal was wrong. That contradiction needs resolving in the contract,
not in a threshold.

### 4g. The tiers are not behaviourally validated

Splitting the 55 firings at the median `erosion_pct` and asking whether the
trader stopped: **25.9% vs 39.3%, +13.4pp, 1.1 SE** — below the ~1.4 SE floor
this series uses.

And applying the Pattern 5 control: observed P(stopped) across all firings is
**32.7%** against a **position-matched expectation of 27.6%** from session
lengths alone. Most of the apparent effect is again where in the session the
alert lands.

**So 50% and 70% rank firings but do not separate behaviour.** No break supports
them either — the distribution runs 7 / 7 / 7 / 2 / 6 firings across the
50-100% deciles, with the only wide gaps in the unbounded >100% tail.

### 4h. Observability limitation — the peak is realized-only

`peak_pnl` is the high-water mark of the **realized** curve and moves only when a
position closes. A trader who was up ₹10,000 unrealized and closed the position
at +₹2,000 has a recorded peak of ₹2,000: the giveback that actually happened —
and that they actually felt — is invisible.

This is not a defect in the detector; it is the boundary of what the engine can
see per closed trade. **It means "you were up ₹X today" is only ever true at
trade boundaries**, and the alert states it as though it were the day's true
high. Worth saying plainly in the contract.

## 5. Overlap and whether the alert is meaningful

**`profit_giveaway` fired alone on 0 of its 20 days.**

| co-fires with | days | share |
|---|---|---|
| `death_spiral` | 16 | **80%** |
| `consecutive_loss_streak` (now retired) | 12 | 60% |
| `adding_to_adverse_position` | 11 | 55% |
| `daily_overtrading` | 8 | 40% |
| `premium_loss_event` · `martingale_behaviour` · `fomo_entry` | 6 each | 30% |

The 80% `death_spiral` overlap is expected — `death_spiral` is the L2
meta-detector that fires when several patterns coincide, so it is partly
*caused* by this one.

**Is the alert meaningful?** The facts are true and are not available elsewhere:
no other detector references the session's high-water mark. Alone among the
patterns reviewed so far, its message tells the trader something they cannot
read off the positions list — *when* the day turned. That is a real
contribution. What undermines it is volume, an unbounded severity key, and a
gate pointed at the wrong quantity.

## 6. Are the values justified?

| value | justified? |
|---|---|
| `min_peak` 1,500 / 3% of capital | **Coherent for the percentage branch, wrong for the sign-flip branch.** §4c: it silences −₹66,212 of green-to-red damage while admitting −₹29,751. |
| `min_erosion` 500 / 1% of capital, raised to the trader's median loss | **The best-founded value in this detector.** Self-relative by construction, engaged in 23 of 55 firings, and it is the mechanism that makes "real money" mean the same thing at any account size. |
| `caution_pct` 0.50 | **No source, no break in the distribution, 1.1 SE on behaviour.** Ranks, does not separate. |
| `danger_pct` 0.70 | Same, and it decides a push. |
| the `1.0` sign-flip literal | **No key, no classification, no test.** It is also redundant with `current_pnl < 0`: if current is negative and peak positive, `erosion_pct` is necessarily > 1.0, so the second half of that condition can never be false. |

**Research note:** the house-money effect is well documented for *unrealized*
gains within a position. I found no source — in this repo or in the literature I
can cite with confidence — that fixes a *session-level* giveback percentage at
which behaviour changes. The 50/70 split appears to be a judgement, and
`trading_defaults.py`'s own convention (unmarked = unsourced) says so.

## 7. Verdict — **MODIFY**

Not KEEP AS-IS: the gate excludes more than twice the damage it admits, and the
severity key is unbounded.

Not DELETE: the subject is real (26% of eligible sessions, a genuine minority),
the money is real, no other detector sees the session high-water mark, and the
mechanism is better formed than Patterns 4 or 5.

Not RESEARCH FURTHER: 189 sessions were enough to establish every finding above.
The one open question — what the sign-flip branch should gate on — is a contract
decision, not a measurement.

Not DEFER: unlike `overtrading_burst` (n = 13), this has 55 detections and 20
affected days. There is enough here to act on.

---

## Current behaviour

Fires when the realized session curve reaches a peak ≥ ₹1,500 (3% of capital)
and then gives back ≥ ₹500 (or the trader's own median losing trade) **and** ≥
50% of that peak; danger at 70%, or immediately if the session crosses into
loss. Re-fires as the giveback deepens. 55 detections → ~38 alerts on 20 of 189
sessions, 41 of 55 at danger.

## What is correct

- **The subject.** A genuine minority behaviour, not the ordinary day.
- **`min_erosion` raised to the trader's own median losing trade** — the
  best-founded value in the detector and the right pattern for the others.
- **The peak from `ctx.facts`**, one canonical definition rather than an inline
  recomputation.
- **Purity.** No DB access, negligible cost.
- **The green-to-red narrative as a distinct message.** "Your green day is now
  red" is a different sentence from "you gave back 70%", and it is right that it
  is not just a louder version of the same tier.
- **Uniqueness.** Nothing else in the engine references the session high-water
  mark.

## Problems found

1. **The `min_peak` gate silences the worst cases.** 23 green-to-red sessions,
   −₹66,212, excluded; −₹29,751 admitted. The gate measures the peak; the harm
   is in the depth of the fall.
2. **`erosion_pct` is unbounded** (max 4.87 observed) and is used as both
   severity key and re-arm metric.
3. **Alert volume:** 1.9 per affected day, up to 4, against a single peak.
4. **Severity oscillates** within a session (2 of 20 days) because `erosion_pct`
   tracks a `current_pnl` that moves both ways.
5. **Half the alert-days end green** — the exact failure the default's own
   comment says the retune addressed.
6. **The 50 / 70 tiers rank but do not separate behaviour** (1.1 SE, below the
   floor; position-matched control absorbs most of the rest).
7. **The code comment is factually wrong** — claims 24h dedup and once-per-
   session firing; it is 2h with a deliberate re-arm, measured at up to 4.
8. **The `1.0` sign-flip literal** has no key, no test, and its second condition
   is unreachable.
9. **`consumes` omits `facts`**, which is where both primary inputs come from.

## Evidence

§4 in full. Headline figures: 69 of 189 sessions eligible; 18 (26%) give back ≥
50% by close; 55 detections on 20 sessions; 41 danger / 14 caution; 25 sign-flip;
gate excludes −₹66,212 versus −₹29,751 admitted; `erosion_pct` max 4.87; 24 of
55 firings on days closing green (median +₹620); tier split 1.1 SE against a
1.4 floor and a 27.6% position-matched baseline.

## Recommended behavioural contract

> **`profit_giveaway` reports one fact: the session reached a high-water mark
> and a material part of it is gone.**
>
> - The **peak is the occasion and the reference**, not the finding. It is a
>   peak of the *realized* curve and the alert must not imply it was the day's
>   true high — unrealized gains are invisible to it.
> - The **finding is the money given back**, measured against what a loss is
>   worth to this trader. That is the dimension already self-relative and the
>   only one with support.
> - **Crossing from profit into loss is a different statement** from giving back
>   a share, and must not be gated on how large the profit was first.
> - It makes **no predictive claim**. A giveback in progress is not a forecast
>   that the day is lost — measured here, half the alert-days closed green — and
>   the copy must not imply otherwise.
> - **One episode, one peak, one alert** that may escalate but must not restate.

## Exact changes required — for approval, not implemented

| # | change | why |
|---|---|---|
| 1 | **The sign-flip branch must not be gated on `min_peak`.** Which quantity should gate it is a contract decision — `min_erosion` already applies and would admit every excluded case — but the peak-size gate is demonstrably the wrong one there. | §4c: −₹66,212 silenced |
| 2 | **Stop using `erosion_pct` as the re-arm metric.** Unbounded, and it re-arms hardest exactly where it is least meaningful. | §4d, §4e |
| 3 | **Severity must not oscillate downward within one session.** Whatever carries severity should be monotonic in the episode, as Pattern 3's `max(qty)` fix established. | §4e |
| 4 | **Resolve the ends-green contradiction in the contract, not the threshold.** Either the alert is a statement of present fact (then the default's comment is wrong and should be corrected) or it claims the day is lost (then it is wrong on half its days). | §4f |
| 5 | **The 50 / 70 tiers need justification or collapse to one severity.** No source, no break, 1.1 SE. | §4g, §6 |
| 6 | **Fix the false comment** about 24h dedup and once-per-session firing. | §4e |
| 7 | **Give the `1.0` literal a key and a test, or delete it** as unreachable. | §6 |
| 8 | Add `facts` to `consumes`. | §3 |

**No replacement threshold is proposed** and none should be chosen from this
book: the evidence says where the current values fail, not where correct ones
would sit.

## What is NOT proposed

Deleting the detector. Merging it with anything. Adding a consolidation family.
Personalising the percentages. Touching the capital-relative ratios (PARKED by
standing instruction). Changing `_typical_loss`. Any change to `session_facts`.

## Recorded for later reviews, not fixed here

- `profit_giveaway_caution_pct` and `profit_giveaway_danger_pct` are unclassified
  in the threshold registry while one of them decides a push.
- The realized-only peak (§4h) is an engine-wide observability boundary, not a
  Pattern 6 defect — it affects anything reasoning about intraday highs.
- `death_spiral` co-fires on 80% of this pattern's days by construction; whether
  the L2 meta-detector should count a pattern that is itself multi-firing is a
  death_spiral question.
