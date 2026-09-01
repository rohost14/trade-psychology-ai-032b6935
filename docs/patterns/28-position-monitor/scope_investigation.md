# Position-monitor group — scope investigation

**1 Sep 2026. SCOPE ONLY. NO CODE CHANGES. NOTHING REVIEWED YET.**

Two questions to settle before the review starts, plus the instrument problem.

---

## 1. `capital_mismatch` — HOUSEKEEPING. Keep it separate.

Traced end to end. **It never reads a position, a trade, an order, a fill or any
P&L.**

| | |
|---|---|
| producer | `maintenance_tasks.check_capital_reality` |
| wiring | **a real Celery beat**, `celery_app.py:219` — unlike every member of the trio |
| inputs | `UserProfile.trading_capital` (declared) vs the latest `MarginSnapshot` (`equity_available + equity_used`) |
| trigger | declared > **1.5×** actual, for **3 consecutive daily checks** (Redis streak key, 14-day TTL) |
| dedup | one alert per 7 days |
| severity | `caution`, fixed — no ladder |
| message | *"Your rules assume ₹X capital, but your account shows about ₹Y … Update your capital in My Rules."* |

Its own registry copy states the subject plainly: *"The trading capital declared
in your rules against what your account can actually deploy."* The action it asks
for is **edit a settings field**. Nothing about a trading decision.

### It is UPSTREAM of the trio, not parallel to it

This is the relationship that matters, and it is the reason "the engine groups
their names" is not a reason to review them together.

```
capital_mismatch  ->  is `trading_capital` correct?
                            |
                            v
overexposure / excess_exposure  ->  position ÷ trading_capital > limit?
```

Both exposure detectors **divide by** `trading_capital`. `capital_mismatch`
asks whether that denominator is real. It is a **precondition for the trio's
correctness**, which is a dependency, not an overlap. Reviewing it inside the
same pass would mix "is this behaviour worth alerting on" with "is this settings
field stale" — two different questions with two different kinds of evidence.

### The codebase already decided this, and pinned it

`behavior_scores_service._ALIAS_NATURE` deliberately **omits** `capital_mismatch`
while listing `overexposure`, `portfolio_concentration` and `holding_loser` as
`"risk"`. `tests/test_f_cleanup_regressions.py:126`
(`test_f21_capital_mismatch_is_excluded_from_death_spiral_on_purpose`) pins it as
*"a housekeeping nudge from maintenance_tasks"*. That finding was reached
independently, and this trace agrees with it.

**The consolidation group is not evidence of kinship.** `behavior_engine.py:889`
groups it under *"the position is too big"* for **presentation** — so the trader
does not receive four messages saying overlapping things. Sharing a consolidation
bucket is a UI decision, not a claim that the four measure the same subject.

> **VERDICT: excluded from the review group.** It belongs in the consolidated
> pending pass, as housekeeping. Recorded there with the dependency noted, so
> whoever touches `trading_capital` sees that two detectors divide by it.

---

## 2. `excess_exposure` — INCLUDE. And the reason is stronger than "same concept".

**The two detectors divide DIFFERENT QUANTITIES by the same capital and compare
against thresholds derived from the same field.**

| | `excess_exposure` | `overexposure` |
|---|---|---|
| pipeline | `BehaviorEngine`, per `CompletedTrade` | position monitor, per opening fill |
| moment | **EXIT** — the round is closed | **ENTRY** — the position is open |
| quantity | `quantities_for_trade(...).capital_requirement` — **SPAN MARGIN** | `_exposure_value()` — **NOTIONAL** (`price × qty × multiplier`) |
| abstains? | yes — `if not rq.usable_for_capital_rules` | yes — `if not reliable` (contract unresolved) |
| thresholds | `max_position_pct_caution` 5 / `max_position_pct_danger` 10, or `max_position_size` ×1 / ×2 | `max_position_size` ×1.5 / ×2, plus absolute 30% (`critical`) and 50% (ALL-IN) |
| escalation | none | emotional bump — a `danger` recovery-bet / martingale / revenge event in the last 12h raises severity one level |

`_exposure_value`'s own docstring is explicit: *"Deliberately NOT a margin
figure. These callers measure market exposure against capital, which is their
design."*

**That is a defensible design choice stated once and never reconciled with the
other detector.** For a long option the two roughly agree — premium paid is both
the notional and the margin. **For a futures or short-option position they differ
by an order of magnitude**, because margin is a fraction of notional. The same
position can be 4% of capital by one detector and 40% by the other, and both
present to the trader as "your position is too large against your capital".

This is exactly the **three quantities, never one** rule from the margin layer —
entry value / P&L / capital requirement. Neither detector can be judged in
isolation, because the question *"which quantity should a position-size rule
use?"* has one answer and two implementations.

### Its deferral does not block this

Pattern 16 deferred `excess_exposure` pending **live broker-margin validation**.
That blocks one specific claim — whether its margin figure is accurate in
absolute terms against a real Kite account. It does **not** block the comparative
question, which needs no live margin at all: the two detectors' quantities can be
computed side by side on the reference book and their disagreement measured
directly.

> **VERDICT: include it in the analytical pass**, scoped to the comparative
> question. **The absolute margin-accuracy validation stays deferred** and must
> not be quietly closed by this review.

---

## 3. Review group — confirmed

| in | | out |
|---|---|---|
| `overexposure` | | `capital_mismatch` → pending pass, housekeeping |
| `portfolio_concentration` | | `death_spiral` → last, it counts the others |
| `holding_loser` | | |
| `excess_exposure` *(comparative only)* | | |

---

## 4. Wiring — the docs name the wrong entry point

**Recorded because it nearly produced a false finding in this trace.** A search
for callers of the Celery task names returns nothing, which looks exactly like
the `cooldown_violation` shape — a detector whose precondition never occurs.
**It is not.** The tasks are live; the wrappers are not.

| what the docs say | what the code does |
|---|---|
| `celery_app.py:246` — *"`check_position_overexposure` — immediately after every COMPLETE fill"* | that task has **no caller** |
| `position_monitor_tasks.py:6` — same claim | same |

The live path:

```
trade_tasks.py, on a fill where _fill_entry_type in _POSITION_OPENING_FILLS
  -> entry_batch_service coalescing window (E1)
     -> flush_entry_batch -> _flush_entry_batch
        -> _concentration_task(account)
        -> _overexposure_task(account, symbol)   per symbol
  -> or, if the batch enqueue fails, the SAME two called INLINE
     (trade_tasks.py:855, 859)
  -> check_holding_loser_scheduled.apply_async(countdown=1800)   [the one real task dispatch]
```

So all three fire in production. They are reached through the **inner async
functions**, not the task wrappers. `check_position_overexposure` and
`check_portfolio_concentration` are unused shells.

### A second, divergent `overexposure` exists — and it carries the F17 bug

`monitor_open_positions._check_position` (line 207) computes:

```python
position_value = current_price * abs(qty)      # no contract multiplier
```

against `_overexposure_task`'s F17-corrected `_exposure_value()`, whose docstring
records exactly why that is wrong: *"GOLDM is one lot of 100 grams quoted per 10
grams, so one lot at 155,999 is 15,59,990 of exposure and not 1,55,999 — a
tenfold understatement."* The legacy version also has **no abstention** and **no
severity ladder** — one flat `caution`.

**It is dead**: `monitor_open_positions` is not in the beat schedule and the
file's own header calls it *"kept for reference"*. Confirmed — no caller anywhere
in `app/` or `tests/`. **Not live-harmful, and not fixed here.** Recorded because
a second implementation of a pattern name is how the two threshold resolvers
drifted, and because the review must not measure the wrong one.

---

## 5. The instrument — the CSV replay does NOT apply, and it does not apply UNEVENLY

The closed-round harness that carried the last twelve reviews reconstructs
`CompletedTrade` rounds from the tradebook. **These three fire on OPEN positions,
priced from the Redis LTP cache that KiteTicker fills.** The tradebook has entry
and exit prices and nothing in between.

**Forcing the CSV methodology onto them would produce false zeros** — the same
artefact that made `time_of_day_bias` look like it had never fired.

### What each one actually needs

| pattern | needs | available from the tradebook? |
|---|---|---|
| `overexposure` | open-position book at an **opening fill**, valued at LTP | **YES, with a caveat.** It fires *at* the opening fill, and at that instant LTP ≈ the fill price, which the tradebook has. Drift is bounded by the coalescing window |
| `portfolio_concentration` | **all** open positions at that instant, grouped by underlying, valued | **YES, same caveat.** `build_with_fills` already reconstructs the fill sequence; the open book falls out of it |
| `holding_loser` | unrealized P&L at **T+30, +60, +90 …** minutes on a still-open position | **NO.** This needs the intraday price path, and we store no candles — `zerodha_service` has no `historical_data` call |

So the group **splits on measurability**, and that must be stated rather than
papered over.

### Proposed instrument — an OPEN-POSITION-BOOK harness, not a closed-round one

A new harness that walks the fill sequence chronologically and maintains the
**open book** after every fill: symbol, signed qty, average entry, entry time.
At each fill classified as position-opening it evaluates the real
`_overexposure_task` / `_concentration_task` predicates against that book. This
reuses `build_with_fills` and `instrument_master.resolve`, so the contract
multiplier and the abstention path are exercised exactly as production does.

**It must be validated before it is trusted** — the standing harness rule. If it
returns zero for a detector known to fire, the harness is wrong, not the
detector.

### `holding_loser` — say what the evidence can and cannot be

**Not measurable as specified.** What *can* be established without a price path:

* the **hold-duration distribution** on positions that ended down, from real
  entry and exit times — so the 30-minute gate can be judged against how long
  positions are actually held;
* an **upper bound** on firings — a position that closed *up* may still have been
  down 0.5% at the 30-minute mark, so the reachable set is "every position held
  ≥ 30 min", which brackets the true rate from above;
* whether the **0.5% loss floor** is selective at all, given F&O premium
  volatility.

**What cannot be established** is the firing rate, the false-positive rate, or
whether flagged positions did worse. Those need either historical candles or
production `RiskAlert` rows.

**INSUFFICIENT EVIDENCE, and it will be reported as insufficient** rather than
substituting a proxy that answers a different question — the `early_exit` and
`opening_5min_trap` failure mode.

---

## 6. What this investigation did NOT do

No code changed. Nothing reviewed. No threshold judged. The two defects found
while tracing — the wrong entry point in the docs, and the dead multiplier-less
`_check_position` — are **recorded, not fixed**, and belong to the review or the
pending pass, not to a scope question.
