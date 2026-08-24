# Pattern #1 — production data path validation

24 Aug 2026. **No production code changed. No threshold, score, severity, merge
or delete.** Fourth and last document before implementation.

**Result: the data path is proven end to end. One `EngineContext` field and one
gated query are the entire production change.**

---

## 1. Is the fill data actually available? **Yes — proven, not inferred**

### The replay uses the live ingestion path

`replay_tradebook.py` injects through `alertlab/runner/inject.py`, which
dispatches **`process_webhook_trade`** — *the same Celery task the live webhook
dispatches*. There is no separate replay ingestion.

### Proven by running it

One replay day, 2025-11-25, 19 fills:

```
position_ledger rows written: 19
completed_trades written:      5
```

And the position the whole review has been about, reconstructed in full:

```
05:09:10  NIFTY25NOV26000CE  OPEN      +75 @ 59.00   pos_after  75   avg_after 59.00
05:12:49  NIFTY25NOV26000CE  INCREASE  +75 @ 50.00   pos_after 150   avg_after 54.50
05:16:50  NIFTY25NOV26000CE  INCREASE  +75 @ 42.70   pos_after 225   avg_after 50.57
05:24:55  NIFTY25NOV26000CE  INCREASE  +75 @ 34.35   pos_after 300   avg_after 46.51
05:25:46  NIFTY25NOV26000CE  INCREASE  +75 @ 30.50   pos_after 375   avg_after 43.31
06:53:20  NIFTY25NOV26000CE  CLOSE    -375 @ 19.75   pos_after   0
```

**This corrects my previous document**, which said the replay had no direct
`apply_fill` calls and that ledger population "must be confirmed". It is
confirmed, and the answer is yes. The replay gate can validate this detector.

### A better find than expected: the ledger already names the events

`entry_type` is not something the engine would have to infer:

| value | meaning |
|---|---|
| `OPEN` | first fill, position 0 → N |
| `INCREASE` | **adds to an existing position, same direction — this is the event** |
| `DECREASE` | partial close, position stays open |
| `CLOSE` | full close |
| `FLIP` | closes and opens the opposite direction |

Those map one-to-one onto the five events the contract's walker distinguishes.
The classification work is already done and stored.

## 2. Minimum `EngineContext` addition

One optional field, populated in `_load_context`, read by the detector:

```python
#: The fill sequence of the CURRENT position, oldest first. Empty when the
#: position had a single entry fill - which is 90% of them - so detectors that
#: need the sequence get it and everything else pays nothing.
position_fills: List[PositionFill] = field(default_factory=list)
```

`PositionFill` carries exactly what the contract needs and nothing else — every
field already stored, none computed:

| field | ledger column | contract use |
|---|---|---|
| `entry_type` | `entry_type` | OPEN / INCREASE / DECREASE / CLOSE / FLIP |
| `fill_qty` | `fill_qty` (signed) | direction of the fill, size of the add |
| `fill_price` | `fill_price` | the price the add was taken at |
| `position_qty_after` | `position_qty_after` | running position; separates an add from a partial exit |
| `avg_entry_price_after` | `avg_entry_price_after` | the reference the next move is measured from |
| `occurred_at` | `occurred_at` | ordering |

**Derived, not stored** — adverse movement (from `avg_entry_price_after` and
`fill_price` and the sign of `position_qty_after`) and exposure (from
`instrument_risk.risk_basis`, unchanged). No new model, no new column, no
migration.

### The query

```sql
SELECT ... FROM position_ledger
 WHERE broker_account_id = :account
   AND tradingsymbol     = :symbol
   AND occurred_at BETWEEN :entry_time AND :exit_time
 ORDER BY occurred_at
```

Served exactly by the index that already exists:

```sql
idx_position_ledger_account_symbol
    ON position_ledger(broker_account_id, tradingsymbol, occurred_at)
```

`migrations/043_performance_indexes.sql`. Account, symbol, time — the three
columns in the order the query uses them.

### No N+1

The engine runs **once per CompletedTrade**, and this is **one query inside that
one run**, gated on `num_entries > 1`. It is not a loop over trades and cannot
become one.

The alternative — one session-wide query grouped in memory — was measured and is
worse here, because the gate makes the per-position query nearly free:

| approach | queries per trade | measured |
|---|---|---|
| **per-position, gated on `num_entries > 1`** | **0.096** | ~11ms when it fires → **≈1.1ms amortised** |
| session-wide every trade, grouped in memory | 1.0 | 23.5ms for 19 rows |

## 3. Performance

| | n | mean | max |
|---|---|---|---|
| single-fill positions | 4 | 10.56ms | 11.24ms |
| multi-fill positions | 1 | 11.20ms | 11.20ms |

**Single-fill and multi-fill cost the same**, which is the point of the gate:
the 90.4% that are single-fill never issue the query at all.

**Honest reading of these numbers.** The lab database is remote, so ~10ms is
round-trip latency rather than query time — the index makes the work itself
trivial and the sample is 5 positions. What the measurement establishes is the
*shape*: one indexed lookup, constant in position size, skipped for nine trades
in ten. It does not establish a production latency figure, and should not be
quoted as one.

Against the four queries `_load_context` already issues, this adds roughly one
tenth of a query per trade.

## 4. Replay validation — the contract run over real ledger rows

The contract's walker was fed **production ledger rows** rather than synthetic
fills:

```
NIFTY25NOV26000CE
   REPORT#1  +15.3% adverse   exposure  4,425 →  8,175
   REPORT#2  +21.7% adverse   exposure  8,175 → 11,378
   REPORT#3  +32.1% adverse   exposure 11,378 → 13,954
   REPORT#4  +34.4% adverse   exposure 13,954 → 16,241

SUNPHARMA25DEC1900CE
   REPORT#1   +3.3% adverse   exposure  2,642 →  5,198
```

Four adverse adds on the position that lost **₹8,835** — the largest single loss
in the book — with exposure tracked from ₹4,425 to ₹16,241 through
`instrument_risk` unchanged.

**Both paths agree.** The raw-fill walk gave +15%, +22%, +32%, +34%; the ledger
walk gives +15.3%, +21.7%, +32.1%, +34.4%. The small differences are the ledger
storing `avg_entry_price_after` at four decimal places.

**What this does not cover.** The book is 727 LONG vs 15 SHORT, 494 CE, 230 PE,
16 EQ, 2 FUT, and every adverse-add position in it is a long option. Short
options, futures and equity are proven **synthetically** (24/24, symmetry matched
on four instrument pairs) and have **no real ledger case** to validate against.
That limitation has not moved and should not be quietly dropped.

## 5. Detector boundaries and the cross-strike gap

**Boundaries unchanged from the validation document and re-confirmed here.** All
four neighbours work position-to-position; the contract works inside a position;
`holding_loser` covers holding without adding. Nothing merged, nothing deleted,
all four keep their scope pending their own reviews.

### Cross-strike — and a correction to my own framing

My previous document said that moving 83500CE → 83000CE → 82700CE is
*"behaviourally the same decision as averaging down."*

**That was an overstatement and I withdraw it.** Strike progression on its own is
not evidence of anything. A trader moving to a cheaper strike may be managing
delta, rolling, or taking a different view. I had a count — 53 occurrences on 30
days — and turned it into a behavioural claim, which is the exact move this whole
review has been refusing everywhere else.

**Contract position, per instruction: cross-strike and cross-instrument sequences
stay OUT of `adding_to_adverse_position`.** The detector is strictly
position-level: *one symbol, one open position, adverse move, exposure added.*

What the 53 cases justify is a **research item, not a detector**: whether a
post-loss rotation episode exists — a loss on one strike, followed by a new
position on another with higher risk, followed by another loss and another
increase. That is a different hypothesis with a different unit, it needs its own
control and its own evidence, and it is recorded as such. **No rule, no
threshold, no detector is proposed for it.**

## 6. Contract changes required

The three additions from the validation document stand, with one changed and one
added:

| # | addition | status |
|---|---|---|
| 1 | **Scope is one symbol, one position.** A different strike is not an add — and strike progression is not asserted to be behavioural. Cross-strike/cross-instrument becomes a separate research item on post-loss rotation | **reworded** — the previous version implied cross-strike *was* the same behaviour |
| 2 | On abstention the exposure **amount is unusable**, and the abstention is **recorded as evidence** | unchanged |
| 3 | The trigger has **no dead band** — any adverse move reports, lowest severity; tick size recorded as the principled alternative | unchanged |
| 4 | **Event classification comes from `entry_type`**, not re-derived. `INCREASE` is the event; `DECREASE`/`CLOSE`/`FLIP` are not | **new** — found by inspecting the ledger |

Core definition unchanged for the fourth document running.

## Status

| question | answer |
|---|---|
| is the fill data available? | **Yes** — proven by running the replay; same task as live ingestion |
| minimum production change | one `EngineContext` field + one gated query. No model, no column, no migration |
| query and performance | existing index serves it exactly; ~0.1 queries per trade amortised; no N+1 possible |
| replay validation | contract walked over real ledger rows, both paths agree |
| boundaries | unchanged, complementary; cross-strike explicitly excluded and downgraded to research |
| contract changes | 4 additions, core definition untouched |

**Severity, thresholds, scores and the 1.5×/2× question remain untouched and
undecided, deliberately.** Nothing implemented.
