# Pattern 14 — `panic_exit`

**Review, 29 Aug 2026. CLOSED — RETIRED.**

Review-order 14. Source-list **#6**, recorded as *"IMPLEMENTED, evidence-only ·
depends on `exit_order_types`, absent in replay"* — so, like Pattern 12, it had
no firing history until now.

Measured by [`p14_panic.py`](../_measurement/p14_panic.py) against the real book
— **175 sessions, 740 completed rounds** — running the real detector in process.

---

## What it was

Two conditions:

```python
hold_min < panic_exit_min (5)  AND  realized_pnl < 0
```

plus a skip when the exit was an SL execution. `severity="info"`,
`disposition=analytics`, v2.0.0. **"Panic" was inferred entirely from "short and
losing".**

---

## Why it was retired

### The deciding test — it selected OUTCOME, not behaviour

It fired on short **losses** and never on short **wins**:

| | n | win rate |
|---|---|---|
| held **< 5 min** | 180 | **38.3%** |
| held **≥ 5 min** | 560 | **39.8%** |

**Short holds perform the same as long holds.** A fast exit is not a worse
decision for this trader. The detector fired on the losing 60% and **ignored 69
identical-behaviour trades purely because they made money**.

That is the same shape that retired `size_escalation`: the claimed discriminator
does not discriminate.

### It was flagging ordinary behaviour

A sub-5-minute hold is **24% of everything this trader does** (180 of 740).
Median hold is 15 minutes, p25 is 5. Fast exits are their style, not an
aberration. It fired **108 times across 77 of 175 sessions** — 44% of all
trading days.

### It was flagging the trader's *best* losses

Median flagged loss **₹308**. **69% of firings were under ₹500.** The trades it
called panic were their cheapest — plausibly good risk management labelled a
psychological failure.

Short losses averaged **−₹473** against **−₹1,053** for longer ones, p = 0.000.
**That comparison is confounded** — a longer hold has more time to accumulate
loss, so it is partly arithmetic, as with `profit_giveaway`. Recorded, not relied
on. **The win-rate result carries the argument alone.**

### The message made three unsupported claims in one sentence

> `NIFTY2540323200PE: closed after 5min at ₹562 loss — no stop-loss order, quick manual exit.`

- *"no stop-loss order"* — the Pattern 12 defect verbatim, unverifiable
- *"quick manual exit"* — "manual" is equally unknowable without an order type
- ***"panic"*** — the event name itself is the inference

### Why not rename it to `rapid_loss_exit`

It would fix the wording and keep the defect. Still short losses only, still
ignoring the 69 wins. A neutral name on a biased selection is a tidier version
of the same error.

---

## What is NOT retired

**The fast exit as a neutral fact.** Hold time is on every `CompletedTrade` and
analytics can read it freely. What is retired is treating a short losing hold as
a *behavioural finding*.

---

## Dependency sweep

| surface | finding | action |
|---|---|---|
| `_STRATEGY_SUPPRESSED` | not a member | none |
| `_FAMILIES` | in no family | none |
| `_COMPOSITES` / `death_spiral` | not a member | none |
| `ENTRY_DECIDABLE` | excluded by design (needs the outcome) | comment updated |
| `_STOP_ORDER_TYPES` | **shared with `no_stoploss`, which is NOT retired** | kept; pinned by a test |
| `panic_exit_min` | read only by this detector and rung 2 | removed from registry, defaults, floors |
| **rung 2 session blend** | **shared with `rapid_reentry_min`** | **kept**; only the `panic_exit_min` call removed |
| `PATTERN_COPY` | entry removed, per every prior retirement | removed |
| frontend routing map | vocabulary contract forbids names the engine cannot emit | removed |
| frontend display map | stored rows must still render a name | **kept**, with a comment |
| `AlertDetailSheet`, `BehaviourLead`, `BehaviourCostCard` | render historical rows | **kept** |

**No blocker found.** Nothing else depended on it.

---

## Tests

**Deleted with their subject** (`_detect_panic_exit` no longer exists, so they
could only fail on an `AttributeError`): `test_panic_exit_detected`,
`test_no_panic_exit_on_profitable_quick_trade`, `test_no_panic_exit_on_slow_loss`.

**Retargeted, not deleted** — 8 tests in `test_threshold_resolution.py`. They
exercise the **rung-2 session blend**, which survives via `rapid_reentry_min`;
`panic_exit_min` was only their vehicle. One parametrised case had to change
shape: the hold-based version had a 240-minute "positional" row, and gaps are
capped at 60 minutes on purpose (*"a longer gap is a break, not a re-entry
decision"*), so a 4-hour gap yields no samples. 50 minutes is the widest
meaningful case.

**Updated:** four retirement suites' count assertions (23→22, 29→28), and the
INFO-visibility detector list (4→3).

**Added:** `test_panic_exit_retired.py` — 11 tests holding the retirement:
the method is gone, the registry and vocabulary do not name it, no spec points
at the deleted method, the counts are right, the threshold is gone and unread,
**the session rung survived**, **the other three analytics detectors are
untouched**, **`_STOP_ORDER_TYPES` survived for `no_stoploss`**, and historical
rows still render.

**Characterization baseline:** one scenario changed — `panic_exit` gone from
`two_unrelated_underlyings`, nothing added.

---

## Verdict — **RETIRED**

Counts: **22 detectors, 28 pattern types.**

Not renamed, because the name was not the defect. Not deferred, because unlike
Pattern 13 the evidence here is sufficient: n=180 with a clean, unconfounded
comparison showing the behaviour it names is indistinguishable from the
behaviour it ignores.

**One caveat, stated plainly:** this is one book and one trader. The
38.3%/39.8% result is about *this* trader's style. A future book where short
holds genuinely underperform would be grounds to revisit the concept — but not
this implementation, which would still be selecting on outcome.
