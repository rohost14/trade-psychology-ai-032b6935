# Patterns 1 and 2 — close-out

24 Aug 2026. **Both COMPLETE.** No thresholds, severity, architecture or other
detectors were changed in this pass.

---

## The two contracts, final

| | **Pattern 1 — `martingale_behaviour`** | **Pattern 2 — `adding_to_adverse_position`** |
|---|---|---|
| **behaviour** | escalating risk across successive **attempts** after losses | increasing an **already-open** position that is moving against you |
| previous position is | **closed** | **open** |
| size must increase | **yes — it is the definition** | **no** — same-size and smaller adds both count |
| unit | a completed position among several | a fill inside one open position |
| reads | `ctx.session_trades` (CompletedTrades) | `ctx.position_fills` (PositionLedger) |
| trigger | `exit` | `entry` — fires on the `INCREASE` fill |
| version | 2.0.0 | 2.0.0 |

**They are not merged and neither is deleted.** They may both fire, and when
they do that is two true statements about one session rather than duplication —
the trader added to an open loser *and* escalated across attempts. Proven by
`tests/test_adverse_add_lifecycle.py::TestTheTwoBehavioursAreDistinct`, four
cases: same-size adverse adds are Pattern 2 only; a closed loss then a bigger
trade is Pattern 1 only; an adverse add that also grows is both; a favourable
add is neither.

## 1. Integration test — the real path, nothing stubbed

`tests/test_adverse_add_integration.py`. Fills go through
`process_webhook_trade` — the same Celery task the live webhook dispatches —
then PositionLedger, the Redis coalescing window, and the entry-batch flush. No
monkeypatching anywhere.

It exists because unit tests cannot answer the question that matters, and that
is not hypothetical: the task originally read the `positions` table, which the
fill pipeline does not populate, and **every unit test passed while the detector
produced nothing on real fills.**

Two cases, both green:

- the NIFTY ladder — 75 @59, then +75 at 50, 42.70, 34.35 — produces an alert
  carrying `at_fill: true`
- the same shape with the price going the trader's way produces **nothing**

The test commits (the fill task runs in its own session in another thread and
cannot see uncommitted fixtures) and deletes what it committed in a `finally`,
because the shared `db` fixture rolls back and a rollback cannot undo a commit.

**And separately, the full replay now fires it end to end**, which it did not
before the `positions` dependency was removed:

```
2025-11-25 [danger]   NIFTY25NOV26000CE   2 adds, 15% down to 22% down
2025-11-25 [critical] NIFTY25NOV26000CE   3 adds, 15% down to 32% down
2025-06-12 [danger]   ASIANPAINT25JUN...  5 adds, 6% down to 34% down
2026-01-29 [critical] SENSEX26JAN82000CE  4 adds, 9% down to 18% down
```

## 2. Evidence limitations — what is NOT proven

### Instrument coverage is synthetic outside long options

The tradebook is **727 LONG against 15 SHORT**, with 16 equity rows and 2
futures. **Every one of the 64 adverse-add positions in it is a long option**,
and 28 of the 31 martingale escalations are too.

Both patterns are therefore proven **synthetically** for short options, futures
and equity, and have **no real case** to validate against:

- Pattern 2: 8 symmetry cases, each long/short pair returning identical numbers
- Pattern 1: `TestMartingaleAcrossInstrumentClasses`, 8 parametrised classes
  plus three asserting a short is measured on **margin, never the premium
  received**

The formulas are direction-symmetric by construction and the exposure model is
shared and tested. That is not the same as having seen one.

### The replay harness starts each day flat

Found during this close-out. `_replay_day_once` resets between days, so a
position carried overnight has no `OPEN` row and its closing SELL is classified
as an opening SHORT.

Concretely, `LT25AUG3800CE` was bought 2025-08-11 and sold 2025-08-12. Replaying
only 2025-08-12, the ledger read the SELL as opening a short, the later BUY as an
adverse add, and Pattern 2 fired. **The detector was correct on what it was
told; the harness told it something false.**

This cannot happen in production — `position_ledger` is append-only and
continuous across days, so a carried position keeps its real `OPEN`. It matters
only for interpreting replay output, and it means **any replay firing on a
carried-over position should be checked before it is believed.**

### The post-win control is negative for both

Reported, not buried. Escalating after two losses is **no more likely than after
two wins** at every multiple from 1.25× up (23.5% vs 28.2% at 1.5×). And this
trader adds after roughly a 10% move in *either* direction — 10.6% when adverse,
10.4% when favourable.

Neither detector makes a predictive claim. Both report a fact: nine of the 31
martingale firings are on profitable trades, and one of the deepest
averaging-down ladders in the book finished **+₹5,719**. That is correct — the
behaviour happened either way.

### Not decided, deliberately

- **No dead band** on Pattern 2's trigger: a 0.01% adverse add reports, at the
  lowest severity. A floor would be the invented threshold the evidence pass
  rejected. Tick size is recorded as the principled alternative.
- **Cross-strike sequences stay out.** 53 occurrences on 30 days, excluded
  because strike progression on its own is not evidence of anything. Open as a
  research item on post-loss rotation, with no rule proposed.
- **Alert volume on repeated adds.** A long ladder can produce several alerts —
  ASIANPAINT produced four, because the 30-minute dedup window expires between
  fills that are hours apart. Whether that is right is a severity question, and
  severity was explicitly out of scope here.
- **Neither pattern is in a consolidation family**, so both can fire alongside
  `size_escalation` and `same_symbol_obsession`. Families change other
  detectors' behaviour, which this pass was not allowed to do. Decide at
  `size_escalation`'s review.

## 3. Status

| | Pattern 1 | Pattern 2 |
|---|---|---|
| implementation | ✅ v2.0.0 | ✅ v2.0.0 |
| unit tests | 20 | 65 |
| integration through the real path | n/a — exit-time, covered by replay | ✅ 4 cases |
| replay | ✅ 31 firings / 26 days | ✅ fires end to end |
| instrument classes | synthetic outside long options | synthetic outside long options |

**Suite: 1,166 passing.**

Both patterns are **COMPLETE**. Pattern 3 has not been started.
