# Pattern #1 — synthetic validation of the contract

24 Aug 2026. **No production code changed. No threshold, score, merge or delete.**
Third and final document before implementation, after
`adding_to_adverse_position_contract.md` and `_evidence.md`.

**Result: the contract is ready for implementation, with three additions
required.** One of them closes a real gap the testing found.

---

## 1. Test results

A reference measurement of the contract — a scratchpad walker, not a detector —
was run against 24 synthetic cases, alongside the **real** neighbouring detectors
on the equivalent completed-trade stream.

**24 of 24 pass.**

| # | case | report | ignore | abstain | ok |
|---|---|---|---|---|---|
| 1–2 | long / short **equity**, adverse add | 1 | 0 | 0 | PASS |
| 3–4 | long / short **futures**, adverse add | 1 | 0 | 0 | PASS |
| 5–6 | long **CE / PE**, premium falls | 1 | 0 | 0 | PASS |
| 7–8 | short **CE / PE**, premium rises | 1 | 0 | 0 | PASS |
| 9 | adverse add **smaller** than held | 1 | 0 | 0 | PASS |
| 10 | adverse add **same size** | 1 | 0 | 0 | PASS |
| 11 | adverse add **larger** than held | 1 | 0 | 0 | PASS |
| 12 | three **constant-size** adverse adds | 3 | 0 | 0 | PASS |
| 13 | three **increasing-size** adverse adds | 3 | 0 | 0 | PASS |
| 14–15 | add after a **favourable** move, long / short | 0 | 1 | 0 | PASS |
| 16 | add at exactly **break-even** | 0 | 1 | 0 | PASS |
| 17 | favourable add **then** adverse add | 1 | 1 | 0 | PASS |
| 18 | **partial exit** | 0 | 0 | 0 | PASS |
| 19 | partial exit **then re-add** while adverse | 1 | 0 | 0 | PASS |
| 20 | close, then **re-enter** | 0 | 0 | 0 | PASS |
| 21 | position **flips** through zero | 1 | 0 | 0 | PASS |
| 22 | single fill, never added | 0 | 0 | 0 | PASS |
| 23 | **spread leg**, adverse add | 0 | 0 | 1 | PASS |
| 24 | **hedged multi-leg**, repeated adverse adds | 0 | 0 | 2 | PASS |

### Directional symmetry — measured, not asserted

| instrument | long | short | |
|---|---|---|---|
| equity | +10.00% | +10.00% | **MATCH** |
| futures | +1.00% | +1.00% | **MATCH** |
| CE | +20.00% | +20.00% | **MATCH** |
| PE | +20.00% | +20.00% | **MATCH** |

### Exposure — from the existing `instrument_risk` model, unmodified

| case | before | after | |
|---|---|---|---|
| long equity | 10,000 | 19,000 | grew |
| short equity | 10,000 | 21,000 | grew |
| long futures | 216,000 | 429,840 | grew |
| short futures | 216,000 | 434,160 | grew |
| long CE | 3,750 | 6,750 | grew |
| short CE | **450** | **990** | grew — **margin, not the premium received** |
| spread leg | — | — | **abstained** |

The short-option row is the one that matters: exposure is `MARGIN_POSTED`, so
the number is nothing like the premium collected. Reusing the existing model gets
that right for free.

## 2. Edge cases and ambiguities

Four found. Two are settled by the tests; **two need a decision and are the
reason this document exists.**

### 2a. AMBIGUITY — no dead band on the sign

The trigger is the *sign* of the move, which has no minimum. A **0.01% adverse
add reports.** In the real book, 8 positions have a deepest adverse add under 3%,
three of them under 1.2% — those look like fills at essentially the same price,
not decisions to double down.

The obvious fix is a floor, and a floor is exactly the threshold this review
already rejected on evidence. The honest options:

1. **Report it, let severity be lowest.** Consistent — the sign is the sign.
2. **Use the instrument's tick size**, which is a market fact rather than a chosen
   number: a move smaller than one tick is not a move. Needs tick data we do not
   currently load.
3. Leave it open and see what the replay produces.

**Recommendation: option 1 for implementation, and record option 2 as the
principled version to revisit.** Do not invent a percentage floor.

### 2b. GAP — same underlying, different strike, while the first is still open

The contract keys on the **symbol**, so buying a *different strike* is a new
position, not an add. Measured on the real book:

| | occurrences | days |
|---|---|---|
| **same option type** (CE+CE / PE+PE), different strike | **53** | **30** |
| different type (CE+PE) — a straddle/strangle structure | 41 | 25 |

Examples of the first kind:

```
2025-05-13  SENSEX   open 83500CE  →  new 83000CE  →  new 82700CE
2025-04-07  BERGEPAINT open 510CE  →  new 520CE    →  new 530CE
2025-07-18  SENSEX   open 82400PE  →  new 81300PE
```

Moving to a cheaper strike as the trade goes against you is, behaviourally, the
same decision as averaging down. **It is covered by nothing today:** the contract
treats it as a new position, and `options_premium_avg_down` requires the prior
position to be **closed**.

**Recommendation: exclude it from this contract, state the exclusion explicitly,
and open it as its own research item.** Not because it is unimportant — 53 cases
on 30 days is more than the 64 in-position cases the contract does catch — but
because "the position moved against me" is not measurable across two different
strikes with different deltas. Including it would require a price model this
review has no evidence for. **Do not quietly extend the contract to cover it.**

### 2c. Settled — the abstention still carries a number

`risk_basis` returns an `amount` for a spread even though `is_comparable` is
False. The contract must state that on abstention the amount is **unusable**, and
that the abstention is **recorded as evidence** rather than silently dropped —
consistent with the project's abstention-as-first-class rule and with what
`revenge_trade` already does.

### 2d. Settled by test — reductions, flips, re-entries

- A partial exit does not change average cost, so a later re-add is measured
  against the original average (case 19). Correct.
- A flip through zero starts a new position and resets the repetition counter
  (case 21). Correct.
- Close-then-re-enter is not an add (case 20). Correct.

## 3. Minimum required data

Everything needed already exists, is written in production, and is **already
indexed for exactly this query**:

```sql
-- migrations/043_performance_indexes.sql
CREATE INDEX idx_position_ledger_account_symbol
    ON position_ledger(broker_account_id, tradingsymbol, occurred_at);
```

| field | source | verified |
|---|---|---|
| signed fill quantity | `PositionLedger.fill_qty` | yes |
| fill price | `PositionLedger.fill_price` | yes |
| running position after the fill | `PositionLedger.position_qty_after` | yes — distinguishes an add from a partial exit |
| running average entry after the fill | `PositionLedger.avg_entry_price_after` | yes — no need to recompute |
| fill time | `PositionLedger.occurred_at` | yes — and it is the index's third column |
| instrument type, symbol | `CompletedTrade` | already in context |
| spread membership | `ctx.strategy_group` | already in context |

Written by `position_ledger_service.py` and driven from `trade_tasks.py`.

**What is missing is access, not data.** `EngineContext` carries none of it, no
detector reads `PositionLedger`, and nothing reads `num_entries`.

**One caveat for the replay gate:** `replay_tradebook.py` has zero direct
`apply_fill` calls — it drives the pipeline instead. Whether the replay populates
`position_ledger` must be confirmed **before** the replay can validate this
detector, otherwise the gate would pass on an empty table and prove nothing.

## 4. Overlap between the related detectors — measured

Each scenario run through the contract's measurement and the real detectors:

| scenario | contract | martingale | size_esc | opt_avg_down | same_symbol |
|---|---|---|---|---|---|
| 1 position, 3 adverse adds (constant size) | **REPORT ×3** | – | – | – | – |
| 3 separate positions, escalating, no adds | – | – | – | – | **danger** |
| 3 escalating positions **+** adverse adds in the last | **REPORT ×2** | – | – | – | **danger** |
| 1 position, adds only while in profit | – | – | – | – | – |
| 1 position held while down, never added | – | – | – | – | – |
| closed loss, then a new position, same underlying | – | – | – | **caution** | – |
| hedged spread leg, adverse adds | **ABSTAIN** | – | – | – | – |

**The boundaries are clean, and they are complementary rather than overlapping:**

- **Row 1 is the whole argument.** The behaviour happens inside one position and
  **every existing detector is silent**, because there is only one completed
  trade to compare.
- **Row 2 is the mirror image.** Three escalating separate positions with no
  adds: the contract is correctly silent and the completed-trade detectors are
  the ones with something to say.
- Pyramiding and hold-without-adding are silent on both sides — the desired
  answer, and hold-without-adding is `holding_loser`'s territory.
- Re-entry after a **closed** loss is `options_premium_avg_down`'s, and only its.

### A finding the boundary test turned up, recorded not fixed

**`martingale_behaviour` needs FOUR completed positions to fire, not three.**
Its guard is `len(ctx.session_trades) < 3`, and `session_trades` excludes the
current trade:

| completed positions | martingale | size_escalation |
|---|---|---|
| 2 | – | – |
| 3 | – | – |
| **4** | **danger** | caution |

The docstring and comments describe a three-trade comparison. This is a new
finding, it changes what fires, and it therefore belongs to
`martingale_behaviour`'s own scope decision — **not fixed here.**

### On whether these should eventually be one episode

The user's framing — adverse add as the core event, repetition as stronger
evidence, exposure growth stronger still, aggressive escalation as martingale-like
— is supported by the boundary map: the five sit on **one axis** (what the trader
did to an exposure that was going wrong) separated by **unit** (inside a position
vs across positions) and by **action** (adding vs holding).

**No merge is proposed and none is needed to implement this contract.** The
merge question becomes answerable once `martingale_behaviour`,
`size_escalation` and `options_premium_avg_down` have had their own reviews and
their scopes are settled. Recorded, deferred.

## 5. Is the contract ready?

**Yes, with three additions.** No change to the core definition, which survived
all 24 cases unmodified.

| # | addition | why |
|---|---|---|
| 1 | State that **exclusion is by symbol**: a different strike on the same underlying is *not* an add, even while the first position is open. Record the 53-case gap as its own research item | found by testing; currently covered by nothing, and covering it needs a price model this review has no evidence for |
| 2 | State that on abstention the exposure **amount is unusable**, and the abstention is **recorded as evidence**, not dropped | `risk_basis` returns a number even when `is_comparable` is False |
| 3 | State that the trigger has **no dead band** — any adverse move reports, at the lowest severity — and record tick size as the principled alternative to revisit | avoids inventing the percentage floor this review already rejected |

**Still not decided, deliberately:** severity structure. The evidence supports an
ordinal built from the sign, repetition and exposure growth, but *how* those
combine is not a counting exercise — counting is a weighted score with every
weight set to one, which this project has already rejected twice. That structure
needs its own design step, after implementation of the measurement and a replay.

**Prerequisite before any code:** fill access in `EngineContext`, which is a
context change plus one gated query, and needs approval on its own terms.

## Status

Contract validated. **24/24 synthetic cases pass, symmetry proven on four
instrument pairs, exposure correct including short options, boundaries measured
against the real detectors.** Three contract additions required. Nothing
implemented.
