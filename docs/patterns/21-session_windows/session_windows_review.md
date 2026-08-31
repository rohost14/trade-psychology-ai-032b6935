# Pattern 21 — `opening_5min_trap` + `end_of_session_mis_panic`

**Review, 30 Aug 2026. Findings only. NO CODE CHANGED.**

Review-order 21. Source-list **#19** and **#20**. Reviewed together because they
share session-boundary mechanics — both compare a trade's **entry** against an
exchange session edge — and because they contradict each other on how that edge
is derived. **They are not assumed to be the same behaviour, and each gets its
own verdict.**

Measured against the real book — **175 sessions, 740 rounds** — running both
real detectors in process. Script: `docs/patterns/_measurement/p21_windows.py`.

---

## Observability limits — stated before any number

**1. The tradebook has no `product` column.** Header is
`symbol,isin,trade_date,exchange,segment,series,trade_type,auction,quantity,price,trade_id,order_id,order_execution_time,expiry_date`.

`end_of_session_mis_panic` gates on `product in ("MIS","INTRADAY")`, so **its
true firing rate is unknowable from this book.** Every number reported for it is
an **upper bound** under an all-MIS assumption. This is not a small caveat — it
is the reason for its verdict.

**2. The export's `exchange` is the underlying's (NSE/BSE), not the derivatives
segment.** Every row is `segment=FO`, so the engine sees NFO/BFO. **There is no
MCX or CDS in this book at all**, so `end_of_session_mis_panic`'s commodity
branch and `opening_5min_trap`'s hardcoded 09:15 are **both unexercised**. A
defect in either is latent, not observed.

---

# Part A — `opening_5min_trap`

## Current behaviour

Fires on a **LONG or SHORT CE/PE/FUT** trade entered within
`opening_trap_window_end_min` (**10**) minutes of **09:15 IST**, that **lost**,
and that additionally satisfies **either**:

```
A) duration <= opening_trap_quick_exit_min (15)    "quick reactive exit"
B) loss_pct >= opening_trap_large_loss_pct (30)    "large loss"
```

| | |
|---|---|
| registry | `2.0.0`, `nature=emotional`, **`disposition=analytics`**, `trigger=exit`, **`notification_level=0`** |
| severity | **hardcoded `info`** — never alerts, never notifies |
| consumes | `completed_trade`, `thresholds` only |
| evidence | entry time IST, minutes after open, duration, loss %, realised P&L, both trigger flags |
| confidence | none set |
| market open | **hardcoded** `entry_ist.replace(hour=9, minute=15)` |

| threshold | value | `THRESHOLD_SPECS`? |
|---|---|---|
| `opening_trap_window_end_min` | 10 | **none** |
| `opening_trap_quick_exit_min` | 15 | `PERSONAL_BASELINE`, `Source.SESSION`, metric `hold_minutes_p25` |
| `opening_trap_large_loss_pct` | 30 | **none** |

## What is correct

**It is pure.** No database, no wall clock, no `await`. Reads only the trade in
front of it and its thresholds — the only detector in this pair that does not
touch `session_trades`.

**It withholds.** Of the 19 losing window entries, **8 satisfy neither trigger
and are declined**. The gates do work.

**Both triggers are reachable and neither is redundant.** Quick-exit fires on 8,
large-loss on 3, and **0 satisfy both** — they select disjoint sets. Compare
`no_stoploss`, whose weekly-expiry branch was a measured no-op.

**A dead computed severity was already removed** (24 Aug hygiene pass) with a
comment explicitly deferring "should this alert at all" to this review.

**The copy carries no statistic about the trader.** `PatternCopy` is
*"Opening-minutes entry / Entries in the first minutes after open that closed
quickly at a loss, or lost heavily / Spreads are widest and option premiums
least settled while the market is still finding its level."*

## Problems found

### A1. THE DECIDING TEST FAILS — the window is not a worse place to trade

The detector's premise is that the opening window is hazardous. Directly
measurable:

| | n | win rate | mean | median |
|---|---|---|---|---|
| inside 09:15–09:25 | 33 | **39.4%** | **+₹99** | −₹112 |
| rest of day | 707 | **39.5%** | **−₹59** | −₹180 |

**Win rates differ by 0.1 percentage points.** On money the window is *better*
— +₹157 per trade — and a permutation test on that difference gives
**p = 0.274**, so it is not a real edge either. The honest statement is that the
opening window is **indistinguishable from the rest of the day** for this
trader, and certainly not worse.

### A2. It selects on OUTCOME, not on behaviour

```python
if pnl >= 0:
    return None   # "a profitable opening trade could be a deliberate strategy"
```

Of 33 window entries, **14 (42%) are discarded for having made money before any
behaviour is examined.** The trader who entered at 09:17 and made ₹800 did the
same thing as the one who entered at 09:17 and lost ₹800.

**This is exactly the shape that retired `panic_exit`** — flagging the losing
half of an ordinary habit and calling the habit the problem. The in-code comment
even names the reasoning ("could be a deliberate strategy"), which concedes that
the *behaviour* is not distinguishable and only the *result* is.

### A3. Three different windows: the name, the threshold, and the copy

| source | window |
|---|---|
| detector **name** — `opening_5min_trap` | **5 min** |
| `opening_trap_window_end_min` | **10 min** |
| shipped message — *"The 09:15–09:25 window…"* | **10 min** |

The threshold and the copy agree; **the name does not**, and the name is what
every doc, tracker and conversation has called it. Entries within each:

```
 5 min of 09:15 : 15
10 min of 09:15 : 33      <- what actually fires
15 min of 09:15 : 70
```

The name overstates precision by half.

### A4. Market open is hardcoded 09:15 — latent, and contradicted by its partner

```python
market_open = entry_ist.replace(hour=9, minute=15, second=0, microsecond=0)
```

This is the 24 Aug H0 DEFER item. **`end_of_session_mis_panic`, the other half
of this review, derives its boundary from `exchange_constants.get_close_time`
for exactly this reason** — and its own comment records that a flat boundary
produced "hours of false alerts a day for commodity traders". The same class of
defect sits unfixed in its sibling.

**Unexercised on this book** — there is no MCX here, and NFO/BFO both open
09:15. So it is a real defect with **zero observed instances**, and this book
cannot test it.

### A5. Its one personalised threshold can never personalise

`opening_trap_quick_exit_min` declares `Source.SESSION`, `metric="hold_minutes_p25"`.
`_apply_session` in `threshold_resolution.py` computes a `holds` list — and then
blends **only `rapid_reentry_min`**:

```python
_blend_session(values, put, "rapid_reentry_min", gaps,
               "your median gap between trades today")
```

`holds` is computed and discarded. The threshold sits at its 15-minute fallback
permanently while declaring itself personalised.

**Third instance of this class**, after `early_exit_winner_max_min`
(`winner_hold_p50`, never produced) and `winning_streak_overconfidence`'s false
`uses_baseline=True`. The other two thresholds have **no spec at all**.

### A6. The shipped message asserts a mechanism the detector never measures

> *"The 09:15–09:25 window has the widest bid-ask spreads of the day as gaps
> resolve and order books stabilise."*

**Fairly stated: this is a market-microstructure claim, not a fabricated
statistic about the trader** — opening price discovery genuinely does carry
wider spreads, and it is not the `expiry_day_overtrading` failure. But **we have
no spread data**, the detector measures realised P&L and hold time, and §A1 shows
the outcome it does measure is *not* worse in that window. So the alert explains
its finding with a mechanism it did not observe and that its own evidence does
not support.

### A7. It is evidence with no reader

`severity="info"` hardcoded, `disposition="analytics"`, `notification_level=0`.
By the closed INFO/evidence rule it creates no `RiskAlert`, does not touch
`danger_zone`, and reaches no trader-facing surface. **11 events in 175 sessions,
seen by nobody.**

This is the `rapid_reentry` situation from Pattern 13 — **but the two differ on
the point that matters.** `rapid_reentry` was KEPT because its window *was*
genuinely selective (17.7% of same-symbol post-loss re-entries against a 20.7-min
median gap); only its consumer was missing. Here the window is **not** selective
on anything measured.

---

# Part B — `end_of_session_mis_panic`

## Current behaviour

Fires on an **MIS/INTRADAY** trade entered at or after a per-exchange
`panic_start`, counting all MIS entries from that point today:

| exchange | panic_start | square-off |
|---|---|---|
| NFO / BFO | 15:00 | 15:25 |
| NSE / BSE equity | 15:00 | 15:15 |
| MCX / CDS / BCD | `close − 25 min` (derived) | `close − 5 min` (derived) |

`panic_count >= 3` → **danger**; `>= 2` → **caution**. If every late entry is
profitable *and* the session is green, danger degrades to `info` and caution
returns `None` — "deliberate late scalping, not panic".

| | |
|---|---|
| registry | `2.0.0`, `nature=emotional`, **`disposition=alerting`**, `trigger=exit`, **`notification_level=1`** |
| severity | `danger` / `caution` / `info` |
| consumes | `completed_trade`, `session_trades`, `session.session_pnl`, `thresholds` |
| evidence | entry time IST, panic count, minutes to square-off, square-off time |
| confidence | none set |

| threshold | value | `THRESHOLD_SPECS`? |
|---|---|---|
| `end_session_mis_caution_count` | 2 | `PERSONAL_BASELINE`, `Source.HISTORY`, metric `late_mis_entries_p75`, `SESSIONS_20` |
| `end_session_mis_danger_count` | 3 | same, `late_mis_entries_p90` |

## What is correct

**The exchange-aware boundary is genuinely good work, and is the best part of
either detector.** Its comment records the bug it fixed: a flat 15:00
`panic_start` meant that on MCX — which trades to 23:30 — *every* evening MIS
entry from 15:00 was scored as end-of-session panic. That is a real defect
correctly identified and correctly repaired, and it derives from
`exchange_constants` rather than a second hardcoded constant.

**It is pure.** No database, no wall clock.

**Its subject is real and mechanically checkable.** Unlike "was that exit
early", "did you enter MIS 20 minutes before forced square-off" is a fact, not
an inference.

**The `all_late_profitable` guard is a genuine attempt not to punish a working
strategy**, and it binds — 1 session on this book.

**The message states the broker fact plainly** — *"Zerodha auto-squares NFO at
15:25"* — with no claim about the trader's state of mind.

## Problems found

### B1. It cannot be validated on this book at all

The tradebook has no `product` column. Its very first gate is
`ct.product not in ("MIS","INTRADAY") → return None`, and the harness must
assume all-MIS to proceed. Everything below is therefore an **upper bound**:

| | upper bound |
|---|---|
| entries at/after 15:00 | **13 of 740 (1.8%)** |
| firings | **1**, `caution`, in 1 session of 175 |

**This is the finding, not a caveat around it.** A detector whose primary gate
is invisible to the only dataset we have cannot be judged on that dataset.

### B2. The danger tier is unreachable on this book

Late entries per session:

```
164 sessions with 0
  9 sessions with 1
  2 sessions with 2
  0 sessions with 3+
```

`danger_count = 3` was **never reached in 175 sessions**, even under the
all-MIS assumption that maximally inflates the count. Same shape as
`winning_streak_overconfidence`'s danger tier — and there the answer turned out
to be "unreachable", not "correctly silent".

### B3. The direction is right but the sample cannot support it

| | n | win rate | mean | median |
|---|---|---|---|---|
| entries ≥ 15:00 | 13 | **23.1%** | **−₹423** | −₹380 |
| rest of day | 727 | 39.8% | −₹45 | −₹175 |

Late entries do look worse — and unlike `opening_5min_trap`, the effect points
the way the detector claims. But **n = 13** and a permutation test gives
**p = 0.185**. That is insufficient, and saying so is the honest answer.

### B4. Half its copy is contradicted by the holds

> *"There is very little time for the position to work, and the exit is not
> yours to choose."*

| | |
|---|---|
| median hold of a late entry | **2 min** |
| mean | 6 min |
| exited at/after 15:20 (near square-off) | **4 of 13** |

**Nine of thirteen were closed by the trader, fast, long before square-off.**
"The exit is not yours to choose" is false for most of them. The first half of
the sentence stands; the second does not.

### B5. Both thresholds declare a baseline metric that does not exist

`late_mis_entries_p75` and `late_mis_entries_p90` appear **nowhere in the
codebase** outside these two spec declarations. `baseline_service` does not
produce them. Both thresholds are permanently at their 2/3 fallbacks while
declaring themselves `PERSONAL_BASELINE`, `Source.HISTORY`, `SESSIONS_20`.

**Fourth and fifth instances of the unchecked-declaration class**, and the
strongest argument yet for the contract test already sitting in the pending
register.

### B6. Its count is OCCURRED, which is correct — and worth recording as checked

```python
panic_trades = [t for t in ctx.session_trades
                if t.product in ("MIS","INTRADAY")
                and t.entry_time.astimezone(IST) >= panic_start]
```

No upper bound on `t.entry_time`, so a trade entered after this one can be
counted. **That is correct here** — this is a count of what happened, the
OCCURRED relation, and by the time the engine fires at this trade's exit those
entries have occurred. Verified against the temporal contract rather than
assumed; measured at 1 → 0 under CONCLUDED, which is the wrong relation for a
count.

---

## Evidence

| question | `opening_5min_trap` | `end_of_session_mis_panic` |
|---|---|---|
| does it fire? | **11 / 10 sessions** of 175 | **1 / 1 session** (upper bound) |
| is its window worse than the rest of the day? | **no** — 39.4% vs 39.5% win, p = 0.274 | **direction yes**, 23.1% vs 39.8%, but **p = 0.185, n = 13** |
| does it withhold? | yes — 8 of 19 losers | untestable |
| does it select on outcome? | **yes — 42% of window entries discarded for winning** | no |
| is the danger tier reachable? | n/a (info only) | **no — 0 sessions of 175 reached 3** |
| does it overlap? | fired **ALONE on 8 of 11** | n too small |
| can its thresholds personalise? | **no** — `hold_minutes_p25` never blended | **no** — `late_mis_entries_*` never produced |
| is the boundary derived? | **no — hardcoded 09:15** | **yes**, per exchange |
| is it pure? | yes | yes |
| does the copy match the evidence? | **no** (§A6) | **half** (§B4) |

**What the evidence cannot say.** For `opening_5min_trap`, n = 33 window entries
is small; the win-rate identity is striking but one trader's book cannot
establish that opening windows are harmless in general. For
`end_of_session_mis_panic`, **the dataset cannot see its primary gate at all** —
this is not a weak result, it is an absent one.

---

## Recommended behavioural contract

> **`opening_5min_trap`.** The subject would be: entries taken while price
> discovery is still resolving, where the *cost* is spread and premium
> instability rather than the direction of the trade. That requires observing
> **spread or premium behaviour** — which we do not store. Selecting the losing
> subset of window entries measures the market's direction, not the trader's
> decision, and cannot distinguish them.
>
> **`end_of_session_mis_panic`.** Entries taken so close to a forced square-off
> that the exit is the broker's and not the trader's. The boundary must come
> from the instrument's own exchange — it already does. The claim about the exit
> must be checked against the actual hold, not assumed from the entry time.
> Neither half can be validated without `product`.

---

## Exact changes required

**Defects that hold regardless of verdict, both recorded rather than fixed:**

1. **`opening_5min_trap`'s hardcoded 09:15** — its sibling in this same review
   derives the equivalent boundary properly. Latent, unexercised here.
2. **Three dead personalisation declarations** — `hold_minutes_p25` (computed
   and discarded), `late_mis_entries_p75`, `late_mis_entries_p90` (never
   produced). Belongs with the `THRESHOLD_SPECS` contract test already pending,
   now at five known instances.
3. **`opening_trap_window_end_min` and `opening_trap_large_loss_pct` have no
   spec record.**
4. **The detector name says 5 minutes; the code says 10.**

**No replacement threshold, window or boundary is proposed.** The measurements
say the opening window is not a worse place to trade for this trader and that
the late-entry effect cannot be established at n = 13 — neither of which is
fixed by a different number.

---

## Verdicts — one each

### `opening_5min_trap` — **DELETE**

**Not KEEP AS-IS.** Its premise is that the opening window is hazardous, and on
this book the window's win rate is **39.4% against 39.5%** — a 0.1pp difference
— while its money is *better*. It reaches that finding only by discarding 42% of
window entries for having made money, which is **selection on outcome, the exact
shape that retired `panic_exit`**. Its message explains the result with a
spread mechanism it never measures.

**Not MODIFY.** Widening or narrowing the window does not create a difference
that is not there; the 5/10/15-minute cuts all sit on the same undifferentiated
distribution. Removing the loss gate would make it fire on every opening entry
and judge nothing.

**Not RESEARCH FURTHER.** The measurement that decides it has been run. What
*would* change the answer — spread and premium-stability data per fill — is not
something we store, and is recorded rather than proposed.

**Not DEFER.** Nothing is blocking; it is live, measurable and measured.

**Distinguished from `rapid_reentry`, which was KEPT at Pattern 13** despite
also being info-with-no-reader: that detector's window was genuinely selective
and only its consumer was missing. This one's window is not selective on
anything we can measure. **The concept is not retired permanently** — opening
spreads are real, and a book with spread data could revisit it.

### `end_of_session_mis_panic` — **DEFER**

**Not DELETE, and this is the important distinction from its partner.** Its
subject is real and mechanically checkable, its exchange-aware boundary is
correct work that fixed a genuine MCX defect, and the effect it claims points
the **right way** on this book (23.1% vs 39.8% win rate) rather than the wrong
way. Deleting a detector whose evidence is merely *absent* would be the opposite
error from the last several retirements, where the evidence was *present and
contrary*.

**Not KEEP AS-IS.** Its danger tier has never been reachable, both its
thresholds declare metrics that do not exist, and half its copy is contradicted
by the holds it fires on.

**Blocked on data, not on judgement.** The tradebook has no `product` column, so
the detector's primary gate is invisible and every number here is an upper
bound. **It should be reviewed against product-bearing data** — live
`CompletedTrade` rows, which do carry `product` — in the same way Pattern 16
`excess_exposure` is deferred pending live broker margin.

Recorded alongside `excess_exposure` as the second detector deferred on a data
gap rather than a decision.
