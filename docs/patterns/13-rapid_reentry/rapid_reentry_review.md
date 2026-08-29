# Pattern 13 — `rapid_reentry`

**Review, 29 Aug 2026. Findings only. No code changed.**

Review-order 13. Source-list **#5** in
[`BEHAVIOURAL_PATTERNS.md`](../00-shared/BEHAVIOURAL_PATTERNS.md) — the
lowest-numbered unreviewed entry, taken in sequence — where it is recorded as
*"IMPLEMENTED, evidence-only · overlaps #2 by construction"*.

Measured by [`p13_reentry.py`](../_measurement/p13_reentry.py) against the real
book — **175 sessions, 740 completed rounds** — running the real detector in
process.

---

## Current behaviour

**What it is supposed to detect.** Going straight back into the instrument that
just lost. Registry copy: *"Re-entering the same instrument shortly after
closing it at a loss. The setup that just failed has not changed in those few
minutes. The re-entry is a second attempt at the same idea at a worse moment."*

**Mechanism, end to end.** On each completed trade it takes the session's prior
trades on the **same `tradingsymbol`**, picks the most recently exited one, and
fires when that trade was a **loss** and the gap from its exit to this entry is
`0 ≤ gap ≤ rapid_reentry_min`.

| | |
|---|---|
| registry | `nature=emotional`, `disposition=analytics`, `trigger=exit`, **v2.0.0** |
| severity | **always `info`** — hardcoded, never computed |
| threshold | `rapid_reentry_min` = **5** minutes |
| threshold kind | **`Kind.FALLBACK`**, `personalise=False`, `maturity=NONE`, `review_required=False` |
| provenance | *"direction read from the consumer; value unchanged (F2)"* |
| sensitivity | `HIGHER_IS_STRICTER` |
| floor | `1` minute (`trading_defaults.py:394`) |
| in `_STRATEGY_SUPPRESSED` | **yes** |
| in `ENTRY_DECIDABLE` | **yes** |
| family | *"going back to the same trade"* with `same_symbol_obsession`, `revenge_trade` |

**One personalisation path exists and is not the registry's.** Despite
`personalise=False`, `threshold_resolution._blend_session` shrinks the 5 toward
*"your median gap between trades today"*, using gaps under 60 minutes, applied
only to analytics-disposition detectors. Its own docstring gives the reason:
*"Asking a trader whether they are a scalper produces a label that is wrong the
week they trade differently."* This is a real, deliberate mechanism, not drift.

**Confidence / evidence.** No confidence is set. The event carries symbol, gap,
prior P&L, window, and both IST timestamps.

---

## What is correct

**The window is genuinely selective — it is not picking the base rate.** This is
the test that retired Pattern 9, and this detector passes it:

```
same-symbol re-entry gaps after a loss, n=79 (minutes)
  p10 2.2   p25 7.1   MEDIAN 20.7   p75 46.8   p90 80.0

  <=  1 min:   2 / 79  ( 2.5%)
  <=  3 min:   9 / 79  (11.4%)
  <=  5 min:  14 / 79  (17.7%)   <-- current
  <= 30 min:  54 / 79  (68.4%)
```

The trader's median gap is **20.7 minutes**. Five minutes selects the fastest
**17.7%**, not "most re-entries". The gate does real work.

**The funnel withholds heavily.** 740 rounds → 139 with a prior trade on the same
symbol → 79 where that trade lost → **14 fire**.

**It is pure.** 40 lines, reads only `ctx.completed_trade`, `ctx.session_trades`
and `ctx.thresholds`. No database access, no `await`, no imports in the body,
no I/O. Nothing to fix on performance.

**Its guards are deliberate and correct.** It fires only after a **loss** —
*"Re-entering quickly after a profit may be scalping — a valid strategy"* — and
matches on the exact `tradingsymbol`, not the underlying, so an option roll to a
different strike is not counted as going back to the same trade.

**The threshold is honestly classified.** `Kind.FALLBACK` with
`maturity=NONE` is exactly what a 5 with no research behind it should be. It
does not claim to be personalised or evidence-derived.

---

## Problems found

### 1. Nothing trader-facing consumes it. Verified against every reader.

`severity="info"` is hardcoded, and `behavior_engine.py:376` is explicit:
`if e.severity == "info" ... continue` — **an info event never becomes a
`RiskAlert`**. Every consumer then filters it out:

| consumer | why it never sees this detector |
|---|---|
| `danger_zone_service` — upgrades to **CAUTION** on `rapid_reentry` | reads `RiskAlert`; info never written there. **Dead branch** |
| `analytics.py` day-tag — tags a day **"revenge"** | query filters `BehaviorEvent.severity != "info"` |
| `behavior_summary` (the `/api/behavioral/` summary) | sourced from `RiskAlert` |
| `behavior_scores_service` (`death_spiral`) | requires severity ≥ `danger` |
| `analytics.py` session-log | filters `detector == "constitution_violation"` |
| `position_monitor_tasks` emotional bump | filters to three other detectors at danger+ |
| `admin/insights.py` | **no filter — the only reader that sees it, and it is an admin aggregate** |

So the detector writes a `BehaviorEvent` that **no trader-facing surface reads**.

**The `danger_zone_service` CAUTION branch is dead code** and should be recorded
as such — it is a consumer bug, not this detector's fault.

### 2. Total overlap with its own family

The coverage test that retired Pattern 10:

| | |
|---|---|
| family (`same_symbol_obsession` / `revenge_trade`) sees it | **14 / 14 (100%)** |
| **fires alone** | **0 / 14 (0%)** |

`revenge_trade` fires on **every single one**. `same_symbol_obsession` on 43%.

**But that coverage is weaker than it looks.** Of the 14, `revenge_trade` returns
**`info` on 13** and `caution` on 1. So on 13 of 14 events, "covered" means
covered by another invisible record. Neither detector notifies. This is not the
Pattern 10 situation, where the covering detectors genuinely alerted.

### 3. The behavioural claim is unproven at this sample size

| | n | mean P&L | median | win rate |
|---|---|---|---|---|
| re-entry ≤ 5 min | 14 | **−₹497** | −₹742 | **14.3%** |
| re-entry > 5 min | 65 | −₹184 | −₹390 | 33.8% |

The direction matches the copy — the rapid re-entry does worse, and the win-rate
gap is large. **But the permutation test gives p = 0.508.** At n=14 this is
entirely consistent with chance.

**The evidence is insufficient to judge the behaviour, in either direction.**
It does not support the claim and it does not refute it.

### 4. The threshold has no research behind it — correctly labelled, still unjustified

`rapid_reentry_min = 5` is a `FALLBACK` whose provenance records only that its
*direction* was verified. Nothing establishes 5 rather than 3 or 10, and the
firing set is highly sensitive to it:

```
1 min ->  2      3 min ->  9      5 min -> 14      10 min -> 26
15 min -> 34    30 min -> 54
```

The count nearly **doubles** from 5 to 10 minutes. The session blend partly
answers this by measuring the trader's own median gap, which is the better
mechanism — but 5 remains the anchor it shrinks toward, and 5 is unsourced.

**Do not replace it.** There is no measurement here that would justify a
different number, and inventing one would be exactly the error this review
process exists to prevent.

---

## Evidence

| question | answer | strength |
|---|---|---|
| does it fire? | 14 events / 11 sessions in 175 | measured |
| does the window discriminate? | **yes** — 17.7% of candidates, against a 20.7 min median gap | measured, strong |
| does anything trader-facing read it? | **no** — every reader filters info or reads `RiskAlert` | verified against all 15 readers |
| is it covered by its family? | **100%**, but by an `info` event on 13 of 14 | measured |
| is the behaviour real? | direction right, **p = 0.508 at n=14** | **insufficient** |
| is it pure / cheap? | yes — 40 lines, zero DB | verified |
| is the threshold justified? | no; correctly labelled FALLBACK | verified |

---

## Recommended behavioural contract

> **Subject.** One decision: going back into the *exact instrument* that just
> lost, before the situation that produced the loss can have changed.
>
> **Fires when** the previous completed trade on the same `tradingsymbol` in
> this session was a loss, and the gap from its exit to this entry is within the
> re-entry window.
>
> **Does not fire** after a profit — that is scalping, not a second attempt —
> nor on a different strike or expiry of the same underlying, which is a
> different instrument and a different decision.
>
> **Claims nothing about outcome.** At n=14 the book cannot say whether these
> re-entries do worse. The event records that the decision was made quickly; it
> does not assert it was wrong.
>
> **Disposition: evidence.** It records, it does not notify. That is only
> coherent if something reads the evidence — today nothing trader-facing does.

---

## Exact changes required

**To the detector: none.** It is correct, pure, selective and honestly
classified.

Two defects belong to **consumers**, and are recorded rather than fixed:

1. **`danger_zone_service.py:310`** lists `rapid_reentry` in `caution_patterns`,
   but `_get_recent_alerts` reads `RiskAlert` and an info event never creates
   one. Dead branch. Fixing it is a `danger_zone` change, not a Pattern 13
   change — and "fixing" it by making the detector notify would be a product
   decision nobody has taken.
2. **The analytics-disposition question is cross-cutting.** `rapid_reentry`,
   `panic_exit`, `early_exit` and `opening_5min_trap` are all info-only. If
   nothing reads their evidence, the disposition is a write with no reader — for
   all four. That is one product decision, not four detector reviews.

---

## Verdict — **KEEP AS-IS**

The detector does the job it is specified to do, does it cheaply and purely, and
its one substantive gate is genuinely selective rather than a rubber stamp.

**Not DELETE.** The two arguments for deletion both fail on inspection. Total
family overlap is real, but the covering detector emits `info` on 13 of 14, so
deleting this removes a record without promoting anything. And the outcome test
is **p = 0.508** — deleting a correct detector on a non-significant result at
n=14 would be the mirror image of the error that got Patterns 9 and 10 retired
on strong evidence.

**Not MODIFY.** No measurement here justifies a different window, a different
severity, or different guards. Changing the threshold would be inventing a
value; changing the severity would be a product decision about whether this
should notify.

**Not RESEARCH FURTHER as a blocker.** More sessions would settle the outcome
question, but nothing depends on that answer today — the detector is cheap and
its output is already invisible.

**The one thing genuinely unresolved is not about this detector**: whether
analytics-disposition evidence should exist at all when no trader-facing surface
reads it. That question covers four detectors and belongs to the product, not to
Pattern 13.
