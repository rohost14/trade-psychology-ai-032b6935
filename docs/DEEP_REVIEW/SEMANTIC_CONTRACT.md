# The Semantic Contract

**Phase 0 deliverable. 29 Aug 2026. No code changed.**

Ten core concepts, each defined as **what the code actually does today**, with
every place the code contradicts itself. Written before Phase 1 so that fixes
converge on one definition instead of repairing the same disagreement in twelve
detectors.

**How to read this.** Each concept has: the definition in force, the conflicts
found (with `file:line`), the definition we should converge on, and a
classification. **"No conflict found" appears where that is the honest answer** —
four of the ten are already consistent, and saying so is as useful as finding a
defect.

Evidence standard: every conflict below was verified directly against code.

---

## 1. What is a POSITION?

**In force:** a position is the running net quantity for a key, tracked as an
append-only ledger of fills.

**The key is `(broker_account_id, tradingsymbol, exchange, product)`** —
`position_ledger_service.py:72, 111`, and the same four columns form the
`UniqueConstraint` on the `positions` table (`models/position.py:11-14`).
`models/position_ledger.py:47` states the reason: *"the same symbol held in two
products at once is two independent positions and must not net together."*

### Conflict — one builder drops `product`

```
pnl_calculator.py:198     key = f"{trade.tradingsymbol}|{trade.exchange}"
```

Two of three agree; the FIFO calculator is the outlier. A trader holding NRML
overnight while scalping the same strike in MIS has those fills FIFO-matched
against each other into rounds that never existed.

Two consumers of the fill sequence drop it too — `behavior_engine.py:574-584`
and `position_monitor_tasks.py:1265-1273` filter on `broker_account_id +
tradingsymbol` only.

**Contract:** the position key is `(broker_account_id, tradingsymbol, exchange,
product)`. Everywhere. No path may net across products.
**Classification: FIX NOW** — objectively wrong, one definition already exists.

---

## 2. What is a TRADE?

**In force:** a `CompletedTrade` is **one complete round trip** — from flat, to a
position, back to flat. It is created only when the ledger records `CLOSE` or
`FLIP` (`trade_tasks.py:609-612`).

**19 of 23 detectors take `CompletedTrade` as their unit and fire on `trigger =
"exit"`** (verified). It is *the* unit of behavioural analysis.

### Consequence, not conflict — a partial exit is not a trade

Scaling out produces no `CompletedTrade` until the last tranche. A trader who
exits over three days is invisible for two of them, then the whole span is
attributed to one round.

This is a coherent definition, consistently applied. It is also the reason
"emit a CompletedTrade on partial exit" **is not a bug fix**: it changes the unit
of analysis for 83% of the engine.

**Contract:** a trade is a completed round trip, flat to flat. A partial exit is
a *fill*, not a trade. If we ever want partial exits analysed, that is a new
concept with its own name — not a redefinition of this one.
**Classification: DESIGN REQUIRED** (to change) / **PASS** (as it stands).

---

## 3. What is a FILL?

**In force:** one execution, stored as a `PositionLedger` row with
`fill_qty` **signed** — `+buy / −sell` (`models/position_ledger.py:56`) — and an
`entry_type` of `OPEN / INCREASE / DECREASE / CLOSE / FLIP` derived from the
running quantity, never from `transaction_type`
(`_compute_fill_effect`, `position_ledger_service.py:894-962`).

**No conflict found.** This is the strongest primitive in the system: pure,
correctly keyed, replay-safe on out-of-order arrival, idempotent on the Kite
order id across all three ingestion paths.

### But the ledger does not see every fill

`_FILL_STATUS = "COMPLETE"` (`order_stream_service.py:65`) drops a **partially
filled then cancelled** order in real time, on all three paths
(`order_stream_service.py:185-187`, `trade_tasks.py:493-494`,
`trade_sync_service.py:518`). The correctness of everything above depends on the
ledger having seen every fill, and this is the case where it has not.

**Contract:** a fill is any executed quantity, whatever the parent order's final
status. Terminal order status must not be the filter for whether a fill exists.
**Classification: FIX NOW.**

---

## 4. What is an EXIT?

**In force:** ambiguous. Three things are called "exit".

1. **A ledger fill that reduces or closes** — `DECREASE`, `CLOSE`, `FLIP`.
2. **The exit side of a round** — `exit_trade_ids`, `avg_exit_price`, `exit_time`.
3. **The order that caused it** — `exit_order_types`, used by `no_stoploss` and
   `panic_exit` to ask *"did a stop-loss fire?"*

### Conflict — `exit_trade_ids` holds two different identifier spaces

| builder | writes | space |
|---|---|---|
| ledger (**live path**) | `position_ledger_service.py:862` → `fill_order_id`, from `trade.order_id` (`trade_tasks.py:581`) | **Kite order-id strings** |
| batch FIFO | `pnl_calculator.py:570-571` → `str(f["trade_id"])` | **`Trade.id` UUIDs** |

The one consumer (`behavior_engine.py:551-553`) casts `Trade.id`. On the live
path the lookup matches nothing, silently.

A third variant: the overnight backfill writes `exit_trade_ids=[]`
(`trade_sync_service.py:1287`).

### Conflict — a FLIP is counted as pure exit quantity

`position_ledger_service.py:835-849` includes the FLIP's whole `fill_qty` in the
round's exit average, though part of it *opened the next position*. `pnl_pct` is
inflated; `realized_pnl` stays correct.

**Contract:** `exit_trade_ids` holds `Trade.id` UUIDs, one convention, both
builders. A FLIP contributes only its closing portion to the exit average.
**Classification: FIX NOW** (both).

---

## 5. What is LONG / SHORT?

**In force:** direction means **the sign of the position's exposure**, not the
instrument type. Nothing anywhere treats CE as bullish or PE as bearish — checked.

### Conflict — two representations across the two tables detectors read

| table | quantity | direction |
|---|---|---|
| `CompletedTrade` | **unsigned** (`models/completed_trade.py:34`) | explicit `direction` column, `LONG`/`SHORT` |
| `Position` | **signed** (Kite net qty) | **no direction column** — derived, `direction="LONG" if qty > 0 else "SHORT"` (`entry_detectors.py:147`) |
| `PositionLedger` | **signed** `fill_qty`, `+buy/−sell` | implicit in the sign |

All three are internally coherent. The hazard is a reader that assumes the wrong
one — and `abs(qty)` appears throughout the exposure paths, discarding the sign
deliberately in one place and accidentally in another.

**Contract:** direction is position exposure. Where a quantity is signed, the
sign is authoritative and must not be `abs()`-ed away without stating why.
Detectors read `CompletedTrade.direction`; live paths read the sign of
`Position.total_quantity`.
**Classification: PASS** (the definition is sound) with a **FIX NOW** on the
specific detectors that ignore it — `no_stoploss` references `direction` **zero
times**.

---

## 6. What is an UNDERLYING?

**In force:** the symbol prefix, parsed by `instrument_parser.parse_symbol`.
One definition, one implementation, **16 comparison sites** in the engine.

**No conflict found in the definition.**

### But the underlying is used where it is not sufficient

Sixteen detectors compare on `underlying` alone, with no expiry and often no
direction or strike test. So a futures roll, a calendar spread, and a genuine
re-entry after a loss are the same event to `revenge_trade`,
`same_symbol_obsession`, `post_loss_recovery_bet`, `options_premium_avg_down`
and `winning_streak_overconfidence`.

Related: `parse_symbol` returns `instrument_type="EQ"` for anything it cannot
parse (`instrument_parser.py:143-150`), so an unrecognised derivative silently
becomes equity.

**Contract:** the underlying identifies *what* is traded, never *which contract*.
Any detector reasoning about "the same thing again" must compare
`(underlying, expiry_key, strike, instrument_type, direction)` and state which
of those it deliberately ignores. Unparseable must be `UNKNOWN`, not `EQ`.
**Classification: FIX NOW** for the `EQ` fallback; **DESIGN REQUIRED** for what
"the same thing" means per detector.

---

## 7. What constitutes a MULTI-LEG STRUCTURE?

**In force:** two independent rules with **opposite conservatism**.

| | rule | window | on failure to classify |
|---|---|---|---|
| grouping (exit path) | `_find_siblings` + `classify_legs` | **15 min** by entry time (`ENTRY_WINDOW_MINUTES`) | still creates a group, typed `MULTI_LEG_UNKNOWN` |
| counting (session) | `cluster_legs` + `count_structures` | **30 s** (`STRUCTURE_GAP_SECONDS`) | refuses to collapse — counts legs separately |

`count_structures` states its principle: *"two directional trades on the same
underlying a minute apart are two decisions, not a mystery spread."* The grouping
path does the exact opposite — an unclassified pair becomes a group and silences
five detectors (`behavior_engine.py:748` tests presence, never type).

Also in force: a structure is asserted **without reading** the option leg's
direction (`strategy_detector.py:479-486`) or **any** quantity (`LegView` carries
only symbol and direction; `strikes` is a set).

**Contract:** a multi-leg structure is a *claim about intent* and requires
positive evidence — legs held simultaneously, compatible directions, compatible
quantities, one underlying and one expiry. **Absent that evidence the answer is
UNKNOWN, and UNKNOWN grants nothing.** One window, one rule, both paths.
**Classification: FIX NOW** for `MULTI_LEG_UNKNOWN` granting suppression and for
the ignored option direction; **DESIGN REQUIRED** for the unified rule
(quantity ratios and overlap are a new model).

---

## 8. What does "SAME POSITION" mean?

**In force:** two fills belong to the same position when they share the position
key **and** the running quantity has not passed through zero. Zero-crossing ends
a round (`CLOSE`) or ends one and starts another (`FLIP`). Re-entry after flat is
a **new** position, correctly.

There is also a **position epoch** for live dedup
(`position_monitor_tasks.py:1091-1112`), taken from the latest `OPEN`/`FLIP`.

**No conflict found in the rule.** It follows from §1 and §3 and is applied
consistently by `_compute_fill_effect`.

### One hazard, inherited

Because the epoch query drops `product` (§1), the epoch can be taken from the
wrong product's OPEN.

**Contract:** same position = same key, no zero-crossing between. Re-entry is
new. Rollover is new (it is a different contract, §6) — whether it is a new
*behavioural* event is a separate question and must not be inferred from the
position model.
**Classification: PASS**, inheriting §1's fix.

---

## 9. What data is AUTHORITATIVE?

**In force:** contested. Three writers produce `CompletedTrade` rows.

| writer | when | notes |
|---|---|---|
| ledger (`_build_round_ct_fields`) | live, per fill | `stable_completed_trade_id`, wall-clock duration |
| batch FIFO (`pnl_calculator`) | recompute / bulk | **DELETEs and recreates** (`pnl_calculator.py:205`); `market_minutes` duration; different `exit_trade_ids` space |
| overnight backfill | sync | random `uuid4()`, stubbed ids, approximated `entry_time` |

So a recompute can **overwrite** ledger-built rows with different values in
`duration_minutes` and `exit_trade_ids`. `duration_minutes` genuinely differs:
an overnight hold is ~1,440 minutes from one and ~375 from the other.

Separately, real Kite margin data is fetched (`margin_service.py:129-136`) and
**consumed by no detector**, while every detector divides by the self-reported
`trading_capital`.

**Contract:** the **ledger is authoritative** for position state, fills and round
boundaries — it is the only builder that sees every fill in order and can
replay. Batch FIFO is a reconstruction for history, and must produce identical
semantics or be clearly marked as degraded. `duration_minutes` needs one
definition, declared. Broker-reported margin outranks self-reported capital where
it exists.
**Classification: FIX NOW** for the `duration_minutes` dual definition and the
`exit_trade_ids` space; **DESIGN REQUIRED** for margin-vs-declared-capital.

---

## 10. What does UNKNOWN mean?

**In force:** a full vocabulary exists and is barely used.

`Verdict.ABSTAINED`, `Insufficiency`, `DetectorResult.abstained`,
`abstained(detector, reason, detail)` — `core/evidence.py:56-115`,
`core/detector_result.py:76, 97`. The design is explicit that `Optional[DetectedEvent]`
conflates "did not happen" with "cannot see", *"which is how three detectors
stayed silent for 203 sessions with nobody able to say which it was."*

**Only 6 `abstained()` call sites exist across 23 detectors.**

### The two violations that matter

| missing information | what the engine concludes |
|---|---|
| exit order type unreadable | *"No stop-loss order detected on this trade"* — `no_stoploss`, alerting, level 2 |
| fill count unknown (`num_entries=1` stub) | *"opened in a single fill"* — a **negative finding**, not an abstention |

**Contract:** UNKNOWN is a first-class result. Missing, stale, stubbed or
unparseable input produces `abstained(...)` with an `Insufficiency` reason —
never a behavioural claim, and never a *negative* finding either. A default value
substituted for missing data is a lie unless it is declared as one.
**Classification: FIX NOW.**

---

# SUMMARY

| # | concept | state | classification |
|---|---|---|---|
| 1 | position | one key, one path drops `product` | **FIX NOW** |
| 2 | trade | coherent; partial exits are not trades | PASS / DESIGN to change |
| 3 | fill | strongest primitive; misses partial-fill-then-cancelled | **FIX NOW** |
| 4 | exit | **three meanings, two ID spaces** | **FIX NOW** |
| 5 | LONG/SHORT | sound definition, three representations | PASS + **FIX NOW** on `no_stoploss` |
| 6 | underlying | one definition, used where insufficient | **FIX NOW** (`EQ` fallback) / DESIGN |
| 7 | multi-leg structure | **two rules, opposite conservatism** | **FIX NOW** / DESIGN |
| 8 | same position | consistent | PASS |
| 9 | authoritative data | **three writers, one deletes the others** | **FIX NOW** / DESIGN |
| 10 | UNKNOWN | vocabulary exists, 6 uses in 23 detectors | **FIX NOW** |

**Four concepts are already sound** (2, 5-definition, 6-definition, 8). The
damage is concentrated in **4, 7, 9 and 10** — and all four are the same shape:
*two parts of the system hold different definitions of one thing, and neither
knows.*

## The one principle that would have prevented most of this

> A definition that exists in two places will diverge, and nothing will notice
> until a detector makes a claim about a trader.

Every conflict above is silent at runtime. `exit_trade_ids` matches nothing and
logs at `debug`. `MULTI_LEG_UNKNOWN` suppresses without a word. The FIFO key
nets across products without complaint. **Phase 2's shared semantic layer should
be judged on whether it makes these fail loudly, not on whether it is tidier.**
