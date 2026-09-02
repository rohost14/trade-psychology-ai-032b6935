# Trading Semantics & Strategy Coverage Audit

**Status: COMPLETE.** All five areas done, 28-29 Aug 2026.
Cross-checked against every requirement in the brief — see *Coverage of the brief*.

Brief: [`positional_validation.md`](positional_validation.md). **No code changes
in this audit.** Findings only.

---

## Why this exists

Patterns 6–11 each failed for the same underlying reason, which the brief states
directly:

> Before any detector is allowed to make a behavioural claim, establish that the
> underlying trading event is correctly classified at the position/strategy level.

This audit asks that prior question across the whole engine, for traders unlike
the one whose book it was built on.

## Classification scheme

**PASS** correctly represented and safely handled · **GAP** something important
missing · **FALSE-POSITIVE RISK** an existing detector could misclassify
legitimate behaviour · **UNSUPPORTED** current data cannot reliably determine it.

## Evidence standard used here

Subagent reports are **claims**. Every finding marked **VERIFIED** below was
re-checked by me directly against the code, with the file and line quoted.
Findings marked *reported* are recorded as claims to confirm when acted on.

## The engine under audit

23 detectors, 29 pattern types. Patterns 1–11 reviewed; 4, 6, 9, 10, 11 retired;
`revenge_trade` frozen; `overtrading_burst` **deferred and still live**.

**Bias in all prior evidence:** the reference book is one intraday long-options
buyer — **911 LONG vs 1 SHORT**, no MTF, 4 futures, 19 equity. Short options,
futures, equity, MTF, overnight and multi-leg structures are **untested rather
than deliberately handled.** The audit distinguishes *handled*, *guarded out* and
*silently wrong* throughout.

---

# THE HEADLINE FINDING

## `no_stoploss` tells disciplined traders they had no stop-loss — via two independent paths

`no_stoploss` is `alerting`, notification level **2**. Its PRIMARY CHECK
(`behavior_engine.py:2171-2173`) is:

```python
exit_types = {(ot or "").upper() for ot in (ctx.exit_order_types or [])}
if exit_types & _STOP_ORDER_TYPES:
    return None          # the mechanism worked as intended
```

`ctx.exit_order_types` is **always empty**, for two unrelated reasons:

**Path 1 — ID-space mismatch on the live path (VERIFIED).** Two builders write
two identifier spaces into `completed_trades.exit_trade_ids`:

| builder | writes | space |
|---|---|---|
| ledger (**the live path**) | `position_ledger_service.py:862` → `fill_order_id`, set from `trade.order_id` (`trade_tasks.py:581`) | **Kite order-id strings** |
| batch FIFO | `pnl_calculator.py:570-571` → `str(f["trade_id"])` | **`Trade.id` UUIDs** |

The single consumer assumes the second (`behavior_engine.py:551-553`):
`select(Trade.order_type).where(cast(Trade.id, String).in_(exit_trade_ids))`.
A Kite order id never equals a stringified UUID. The query does not error — it
matches nothing — and the surrounding `except` logs at `debug`.

**Path 2 — overnight backfill stubs the field (VERIFIED).**
`trade_sync_service.py:1287` writes `exit_trade_ids=[]` literally, plus
`num_entries=1` at `:1277`.

**Consequences, all verified:**

1. **A trader whose SL-M triggered is told *"No stop-loss order detected on this
   trade."*** This is a false positive against precisely the disciplined
   behaviour the product exists to reward. The spec even declares
   `consumes=("completed_trade", "exit_order_types", "thresholds")`.
2. `panic_exit` has the same short-circuit and the same failure.
3. **Every live alert is permanently confidence-demoted.**
   `behavior_engine.py:359-360`: `if data_quality == "GOOD" and not
   ctx.exit_order_types: data_quality = "PARTIAL"`. The `GOOD` branch is
   unreachable on the live path.
4. `num_entries=1` means `position_fills` is never loaded for an overnight
   position (`behavior_engine.py:571`), so `adding_to_adverse_position` reports a
   **negative** — "opened in a single fill" — rather than abstaining, however
   many times the position was averaged into.

**Why this is the headline:** it is unconditional rather than probabilistic, it
is silent, it inverts the product's own thesis, and two independent code paths
cause it.

---

# CROSS-CUTTING FINDINGS

## 0. CE→PE — the brief's flagged concern, answered directly

The brief raises this twice: *"CE→PE is NOT automatically direction instability.
It can be a genuine reversal, hedge, spread adjustment, or strategy
construction."*

**On the specific charge: PASS.** `direction_instability` was retired 28 Aug
2026 after measurement showed the opposite of its premise (flagged flips won
56.2% for +₹276 against 41.7% and −₹73 unflagged). **`grep` confirms zero
occurrences of `_detect_direction_instability` in the engine — no detector
anywhere now claims a CE→PE swap indicates directional instability.**

**But CE→PE is not invisible either, and two detectors still react to it:**

- **`options_premium_avg_down`** — VERIFIED. Its guards
  (`behavior_engine.py:2443-2464`) require only that both the prior and current
  trade are `instrument_type in ("CE","PE")`, `direction == "LONG"`, same
  underlying, prior loss ≥20% of premium. **A CE losing 20% followed by a PE buy
  satisfies every one.** It does not call this direction instability — it calls
  it averaging down, and its message says *"after N losing options positions"*.
  For a genuine reversal that framing is wrong in a different way than the
  retired detector was.
- **`same_symbol_obsession`** — counts both legs as "attempts" on the underlying,
  direction and option type unread.

So the answer is: **the specific misclassification the brief warned about has
been removed; a CE→PE reversal is now mislabelled as averaging down rather than
as instability.** Same event, different wrong name, lower severity
(`notification_level=1` vs the retired detector's, and no `danger` tier).


## 1. Averaging down is measured in the currency it deflates — VERIFIED

Buy 100 CE @100, add 100 @60, exit 200 @50 → `avg_entry=80`,
`realized_pnl=−6000`, `pnl_pct=−37.5`. Without the add: `−5000` and **−50.0**.

**Doubling down lost ₹1,000 more and reported a loss percentage 12.5 points
smaller**, and it crosses thresholds:

| detector | no add | with add |
|---|---|---|
| `premium_loss_event` | 50% → caution | 37.5% → **below the 40% line, silenced** |
| `no_stoploss` | 50% → **danger** | 37.5% → caution |

The arithmetic is right for a blended position. The defect is that **every
trade-relative severity band divides by blended cost, and blended cost is exactly
what averaging down manipulates.** The absolute rupee loss is monotonic in the
behaviour and is what none of them band on.

`adding_to_adverse_position` is built to see through this and is well-built and
direction-symmetric — but it is `trigger="entry"` and has **three silent no-run
paths**: Redis/Celery degraded (the inline fallback runs three other checks and
not this one), bulk sync, and CSV import. **Coverage of the engine's most-cited
failure mode depends on Redis being up.**

## 2. `multi_leg_unknown` grants full hedge suppression — VERIFIED

`strategy_detector.py:90-98` classifies, then builds the `StrategyGroup`
**unconditionally** — `MULTI_LEG_UNKNOWN` is stored like any other type. The
suppression check (`behavior_engine.py:748`) tests only presence:

```python
if ctx.strategy_group and event.event_type in self._STRATEGY_SUPPRESSED:
```

So **any two F&O trades on the same underlying, different symbols, entered within
15 minutes — whatever their shape — silence `revenge_trade`,
`martingale_behaviour`, `rapid_reentry`, `no_stoploss` and
`post_loss_recovery_bet` on the second one to close.**

The 15-minute sibling window overlaps `revenge_window_caution_min = 20`, so **the
canonical revenge shape sits inside the window that silences it.** CE loses at
10:05, trader buys another strike at 10:08 → grouped → `revenge_trade`
suppressed. If the re-entry is the same strike opposite type, it classifies as
`straddle_buy`.

This directly contradicts `count_structures`, which deliberately refuses to
collapse an unrecognised cluster (*"two directional trades on the same underlying
a minute apart are two decisions, not a mystery spread"*). **Two grouping paths
with opposite conservatism.**

## 3. "Hedge" is asserted without reading the hedging leg's direction — VERIFIED

`strategy_detector.py:479-486`:

```python
if other_type == "PE" and fut_trade.direction == "LONG":
    return StrategyType.FUTURES_HEDGE_BULLISH
```

The option's own direction is **never read**. So:

| legs | classified as |
|---|---|
| FUT LONG + PE **LONG** (real protective hedge) | `futures_hedge_bullish` ✓ |
| FUT LONG + PE **SHORT** (naked short put on a long future — *doubled* bullish risk) | **`futures_hedge_bullish`** ✗ |
| FUT SHORT + CE **SHORT** | **`futures_hedge_bearish`** ✗ |

A risk-**adding** structure gets the label and the suppression written for
risk-*reducing* ones. Quantity is never read anywhere either — `LegView` carries
only `(tradingsymbol, direction)` and `strikes` is a set — so a **1×2 ratio
spread classifies as `bull_call_spread`** and receives full suppression on a
structure with unbounded short-side risk.

## 4. Short options: the denominator inverts silently — VERIFIED

`estimate_capital_at_risk` (`trading_defaults.py:572-585`) computes a **short**
option's capital at risk as a SPAN percentage of the premium **received** — so
the one class with unbounded downside gets a figure ~2 orders of magnitude too
small. Consumers: `excess_exposure`, `constitution_violation`/`max_trade_risk`,
`martingale_behaviour`, `revenge_trade`, `adding_to_adverse_position`,
`baseline_service.own_position_risk`. **Every capital-relative safety rule is
effectively silent for option writers.**

Separately, `_detect_no_stoploss` references `direction` **zero times**
(verified by scanning the whole function). Its denominator `entry_price × qty` is
premium *paid* for a buyer and premium *received* for a writer, so its meaning
flips with direction; >100% readings are possible and unclamped.

**The genuine guards** — and they are genuine — are `premium_loss_event`,
`options_premium_avg_down` and the two live paths, all of which gate
`direction != "LONG"` explicitly.

## 5. `overexposure` fires on every futures and MTF position — VERIFIED

`position_monitor_tasks.py:396-411`: `position_value = current_price * abs(qty)`
— full contract notional — then `exposure_pct >= 30 → critical`, `>= 50 →
"ALL-IN BET"`. One NIFTY future is ~₹18.75L; against ₹5L declared capital that is
375%. **Unconditional, on the highest-severity live path in the product.**

## 6. "Today" means "closed today", and three detectors say "opened today" — VERIFIED

`core/session_facts.py:262-265` scopes on `exit_time` only, no entry bound. This
is deliberate and correct for streaks and P&L, and **silently wrong for anything
counting decisions**. `daily_overtrading`'s message and its registry copy both
say *"positions opened today"* about a close-scoped count. Any trader holding
anything overnight is told they made decisions they did not make.

It also yields **two different counts for one declared rule**: `daily_overtrading`
uses `count_structures`, `constitution_violation`/`daily_trades` does not, so one
iron condor is 1 to the first and 4 to the second.

## 7. Twenty-six of twenty-seven time windows are fixed

Exactly one — `revenge_window_caution_min` — adapts to the trader. Every other
personalised threshold is a **count**, never a **duration**. There is no notion
of trading style anywhere: the 30-minute burst window is identical for a scalper
taking 40 positions an hour and a swing trader taking 3 a month.

`HOLDING_LOSER_MIN_DURATION = 30 min` / `MIN_LOSS_PCT = 0.5%` are module
constants not even on the threshold ladder — 0.5% is intraday noise for a swing
position, re-armed every 30 min for 4 hours.

## 8. Rollover is structurally undetectable, and every detector that fires on it keys on `underlying`

Three independent barriers, any one sufficient: siblings are matched on
**entry_time ±15 min** (a roll's legs are entered days apart); the calendar-spread
branch **excludes FUT**; `cluster_legs` buckets on `(underlying, expiry_key)` so
a roll is 2 structures to every counting detector.

Meanwhile `revenge_trade`, `same_symbol_obsession`, `post_loss_recovery_bet`,
`options_premium_avg_down` and `winning_streak_overconfidence` all compare on
`underlying` with no expiry test — so **a futures roll reads as "back into the
same thing after a loss"**, at larger size if the far month is priced higher.

Also: `instrument_parser.py:176` hardcodes **last-Thursday** monthly expiry for
every exchange, contradicting `exchange_constants.py`'s own documented BFO expiry
weekdays. `is_expiry_day` is wrong for every SENSEX/BANKEX monthly.

---

# COVERAGE MATRIX

## Position lifecycle (A)

| scenario | status |
|---|---|
| open · partial fill · multiple fills · complete close · reopen · close-and-reopen | **PASS** |
| **new position vs another fill of the same position** | **PASS** — the strongest part of the subsystem |
| add to existing position | PASS (ledger) / **GAP** (CompletedTrade aggregate) |
| partial exit / reduce | **GAP** — no CompletedTrade until flat, so nothing is analysed |
| LONG↔SHORT reversal | PASS for state; **GAP** for `pnl_pct` on an over-closing FLIP with ≥2 exits |
| simultaneous orders netting to zero | **FALSE-POSITIVE RISK** — direction decided by *arrival order*; Kite stamps are second-resolution |
| cancelled, **partially filled** | **GAP** — the real fill never reaches the ledger; `current_qty` desyncs and every later fill is misclassified |
| pending / `TRIGGER PENDING` | **GAP** — discarded by design, consequences undocumented |
| stop-loss execution | **FALSE-POSITIVE RISK** — invisible; see headline |
| target execution | **UNSUPPORTED** — `order_type` unreadable |
| MIS + NRML same symbol | **GAP** — fill-sequence readers drop `exchange`/`product` from the key |
| Kite position conversion (MIS→NRML) | **GAP** — no order, no fill, no handler; the round never closes |

## Average price & P&L (A)

| scenario | status |
|---|---|
| weighted average entry · realized P&L · remaining quantity | **PASS** |
| `total_quantity` = "peak position size" | **GAP** — it is the sum of entry fills; the model comment is wrong |
| **adding to a loser shrinking the loss %** | **GAP** — see cross-cutting #1 |
| unrealized P&L / adverse excursion of an open round | **UNSUPPORTED** — never stored |
| `duration_minutes` | **GAP** — two incompatible definitions in one column (wall clock vs market minutes); can change after an admin recompute |

## Long/short, futures, capital (B)

| scenario | status |
|---|---|
| long call / long put | **PASS** — the only class ever measured |
| **short call / short put** | **FALSE-POSITIVE RISK** — `no_stoploss`, `opening_5min_trap`, `excess_exposure`, `constitution_violation`, `martingale_behaviour`, `overexposure` |
| long / short futures | **FALSE-POSITIVE RISK** — `overexposure`, `excess_exposure`, `no_stoploss`, `winning_streak_overconfidence`, `post_loss_recovery_bet` |
| long / short equity | **GAP** — full notional regardless of direction |
| premium logic on a writer | **PASS** where guarded (3 detectors), FALSE-POSITIVE elsewhere |
| option logic on futures | **GAP** — `opening_5min_trap` admits FUT but computes `loss_pct` only for CE/PE, so half the detector is unreachable |
| contract multiplier | **GAP** — `realized_pnl` applies it; **no denominator does**. On MCX this inflates a ratio by up to 5000× |
| `EQ` doubles as the unknown bucket | **GAP** — any unparseable symbol becomes equity with a delivery-value denominator |
| what "risk" means | **GAP** — **nine denominators across four meanings**; only `instrument_risk` labels which |
| real Kite margin data | **GAP** — `margin_service` reads span/exposure/premium; **no detector consumes it** |

## Hedges & strategy geometry (C)

| scenario | status |
|---|---|
| protective hedge, same expiry | **GAP + FALSE-POSITIVE RISK** — direction of the option leg never read |
| protective hedge, **weekly option + monthly future** (the normal Indian index case) | **GAP** — `expiry_key` mismatch means it is never grouped |
| equity + option (covered call, protective put, collar) | **UNSUPPORTED** — EQ excluded from grouping entirely |
| neutral structure (straddle/strangle) | **PASS** shape / **FALSE-POSITIVE RISK** on provenance — no test that legs were held simultaneously |
| vertical spread | **GAP (safety)** — quantity never read, so a **1×2 ratio spread classifies as a defined-risk debit spread** |
| iron condor | ~~shape ✓~~ — the shape was NOT validated: any four mixed-direction CE/PE legs matched, including the inverted structure. **FIXED 2026-09-02 (`5844381`).** Still **never forms a 4-leg group on the live path** |
| iron butterfly | ~~**dead code** — the branch is unreachable; every real one returns `iron_condor` first~~ **FIXED 2026-09-02 (`5844381`)** |
| calendar / diagonal | direction never checked; diagonal → `calendar_spread`; unrepresentable on the counting path |
| futures roll | **GAP** — `multi_leg_unknown`, no suppression |
| strategy suppression reliability | **GAP both ways** — over-suppresses (`multi_leg_unknown`, revenge shape) and under-suppresses (needs the sibling to have *closed*; 4-leg structures starve; entry path has no group at all) |
| cross-underlying hedge | **UNSUPPORTED** — and correctly so. No correlation, beta, sector or index-constituent data exists. Do not claim it |

## Expiry, time horizon, archetypes (D)

| scenario | status |
|---|---|
| same strike, different expiry | **FALSE-POSITIVE RISK** |
| futures rollover | **GAP** — see cross-cutting #8 |
| rolling a spread | **UNSUPPORTED** |
| expiry-day adjustment | **PASS (narrow)** — survives only as a modifier, keyed on the instrument's own expiry |
| BFO monthly expiry weekday | **GAP** — hardcoded last-Thursday; wrong for SENSEX/BANKEX |
| intraday vs overnight | **GAP** — see cross-cutting #6 |
| multi-day position | represented but **degraded** — see headline |
| time windows assuming intraday | **GAP** — 26 of 27 fixed |
| product in the position key | **GAP** — FIFO keys on `symbol\|exchange`; the ledger keys on `…|product`. **Two position models, two answers** |

### Archetype false-positive summary

| archetype | worst offenders |
|---|---|
| pure intraday directional | **PASS** — the reference book |
| **long-options trader** | **PASS** — the other reference archetype; every threshold was fitted to it |
| **scalper** | `overtrading_burst` (p75 line alerts on ~25% of sessions by construction), `no_stoploss` (the 5-min floor exists to exclude scalps, but a 6-minute scalp at 25% still fires). `rapid_reentry` and `panic_exit` would fire constantly but are `info`-only — **PASS by disposition, not by logic** |
| **high-frequency / manual rapid** | as scalper, compounded. `burst_per_30min_p75` adapts the *count*; the 30-minute *window* never does |
| **expiry trader** | **PASS** on the main risk — `expiry_day_overtrading` was retired 27 Aug for exactly this. Residual **GAP**: `is_expiry_day` hardcodes last-Thursday monthly expiry, so it is wrong for every SENSEX/BANKEX monthly |
| averaging / pyramiding | **PASS by design** — `adding_to_adverse_position` deliberately excludes size and correctly excludes pyramiding. The strongest part of the engine on this axis |
| short-options seller | `no_stoploss` (wrong denominator), `excess_exposure` (understated ~130×) |
| futures trader | `overexposure` **critical on every position**, `revenge_trade` on every roll |
| options spread trader | `adding_to_adverse_position` on spread adjustment, `constitution_violation` counting legs, `portfolio_concentration` reading a condor as 100% concentrated |
| hedger | first leg of every hedge alerts before the group exists; 8 detectors not in `_STRATEGY_SUPPRESSED` at all |
| swing / positional | `daily_overtrading` "positions opened today", `holding_loser` at 0.5%/30min, `no_stoploss` on every overnight close |
| MTF equity | `excess_exposure` and `max_trade_risk` breach on **every** MTF trade — leverage is the instrument's purpose |
| market-neutral | `portfolio_concentration` reads a delta-neutral book as 100% concentrated |
| algorithmic | every behavioural claim attributes human intent; nothing marks a trade automated |
| portfolio hedger | **UNSUPPORTED** — equity holdings are not synced at all |

---

## Scenarios the brief did not list

- **Kite position conversion (MIS→NRML)** — a missing *event class*, not a timing problem. The ledger round never closes.
- **Same-second fill ordering** — second-resolution timestamps + a strict `<` replay guard make direction a coin flip for simultaneous legs.
- **`duration_minutes` dual definition** — the same round's hold time changes depending on which builder last wrote it.
- **Overnight-backfill CompletedTrades** carry a random `uuid4()` and an approximated `entry_time`, feeding every hold-time gate.
- **A partial exit produces no CompletedTrade at all** — a trader scaling out over days is invisible until the last tranche.
- **NSE lot-size revisions** break the comment at `behavior_engine.py:3204` that "every strike and expiry of one underlying shares a lot size".
- **`monitor_open_positions` and `monitor_live_premium` are not in the Celery beat schedule** — `holding_loser` and the legacy premium beat do not currently run.
- **Dead code**: the `IRON_BUTTERFLY` branch is unreachable.

---

## Area E — MTF, exposure, data failure, multi-account · DONE DIRECTLY

The subagent for this area failed on a session limit before starting, so I
investigated it myself. Everything below is first-hand.

### E1 · MTF is not modelled at all — VERIFIED

Every occurrence of `MTF` in live code:

```
api/webhooks.py:258            product not in {"MIS","NRML","MTF"}   ingest filter
services/order_stream_service.py:68   _TRACKED_PRODUCTS             ingest filter
services/trade_sync_service.py:34     TRACKED_PRODUCTS              ingest filter
tasks/reconciliation_tasks.py:56      TRACKED_PRODUCTS              ingest filter
tasks/trade_tasks.py:424              product not in {…}            ingest filter
models/completed_trade.py:30          product column                storage
models/position_ledger.py:47          part of the position key      storage
```

**No detector and no risk function reads it.** `estimate_capital_at_risk`
(`trading_defaults.py:558-564`) takes `instrument_type, tradingsymbol,
direction, avg_entry_price, total_quantity` — **there is no `product`
parameter**, so it cannot distinguish MTF from cash even in principle.

| scenario | status |
|---|---|
| cash equity without MTF | **PASS** (notional denominator, correct for delivery) |
| MTF long / increased / reduced / overnight | **GAP** — indistinguishable from cash equity |
| MTF + protective option | **UNSUPPORTED** — equity is excluded from strategy grouping entirely |
| available margin vs deployed capital | **UNSUPPORTED** — no leverage model exists |
| forced liquidation / broker square-off | **UNSUPPORTED** — no event class represents it |

Consequence: an MTF position's **full market value** is charged against declared
capital as if it were cash, so `excess_exposure` and
`constitution_violation`/`max_trade_risk` breach on essentially every MTF trade —
when leverage is the instrument's entire purpose. The brief's instruction that
*"MTF must not be treated as an F&O position"* is satisfied only accidentally: it
is treated as **cash equity**, which is a different wrong answer.

### E2 · There is no netting anywhere — VERIFIED

`grep` for `net_exposure|net_delta|gross_exposure|directional_exposure` across
`backend/app/` returns **nothing** in live code. Every aggregation uses `abs()`:

```
position_monitor_tasks.py:211   position_value = current_price * abs(qty)
position_monitor_tasks.py:396   position_value = current_price * abs(qty)
position_monitor_tasks.py:1389  ltp * abs(pos.total_quantity)
```

A short leg **adds** to exposure instead of offsetting it, so a fully hedged or
delta-neutral book reads as maximally concentrated.

| exposure concept | status |
|---|---|
| gross exposure | **PASS** — this is what is computed |
| net directional exposure | **GAP** — not computed anywhere |
| underlying exposure | **PASS** — bucketed by underlying |
| hedge-adjusted exposure | **GAP** |
| sector exposure | **UNSUPPORTED** — no sector taxonomy exists |
| correlated exposure | **UNSUPPORTED** — no beta, correlation or index-constituent data |

**Does the data support building these?** Gross, underlying and net-directional
are computable from what is stored. Sector and correlated exposure are **not** —
and per the brief, should not be claimed. Hedge-adjusted exposure is computable
only within one underlying and one expiry, given the grouping limits in area C.

### E3 · Data failure — the live path abstains correctly, but two detectors turn absence into a claim

**The good half — VERIFIED PASS.** `ltp_cache.read` returns `None` when a price
is missing *or stale*, and staleness is genuinely enforced with a per-price
timestamp (`_decode`, `ltp_cache.py:44-53`: `if now_ms - int(ts_s) > STALE_MS:
return None`). The monitor then abstains rather than guessing
(`position_monitor_tasks.py:171-174`):

```python
if current_price is None or avg_entry <= 0:
    # No live price available — KiteTicker not connected or token missing
    return events
```

| failure | status |
|---|---|
| stale LTP / missing LTP / delayed tick | **PASS** — staleness enforced, monitor abstains |
| broker disconnect / websocket reconnect / Redis restart | **PASS** — no price → abstain |
| broker API outage | **PASS** for detection — sync simply does not run, so no trades arrive and nothing is inferred. The stale-close risk is that positions closed during the outage are backfilled later via the overnight path, which carries the stubbed fields above |
| duplicate fills | **PASS** — unified `idempotency_key` on the Kite order id |
| out-of-order events | **PASS** — triggers a full ledger replay |
| market closed / partial session | **PASS** — beat gated 09:15–15:25 IST (though hardcoded NSE hours; MCX evening is never monitored — **GAP**) |
| app restart | **PASS** — state is in Postgres, rebuilt on demand |
| position sync delay | **GAP** — a partially-filled-then-cancelled order desyncs `current_qty` (area A) |

**The bad half — the hard principle IS violated, twice.** The brief's rule is
*"never interpret missing data as trader behaviour"*. Both violations are already
the headline finding, and this is the frame that makes them one defect rather
than two:

1. **`no_stoploss`** — an empty `exit_order_types` means *"we could not read the
   exit order type"*. The detector treats it as *"there was no stop-loss"* and
   raises an alerting, level-2 behavioural claim.
2. **`adding_to_adverse_position`** — `num_entries=1` on an overnight backfill
   means *"the fill count is unknown"* (`trade_sync_service.py:1277` says so in a
   comment). The detector returns a **negative finding** — "opened in a single
   fill" — rather than abstaining.

Both are absence rendered as fact. The engine has a proper vocabulary for this —
`DetectorResult.abstained` with an `Insufficiency` reason — and neither uses it.

### E4 · Behaviour is account-level, not user-level — VERIFIED

Everything scopes on `broker_account_id`: the engine (17 references), the alert
and dedup path in `trade_tasks.py` (92), `session_facts` (4). `BrokerAccount`
carries a `user_id` FK with its own index (`models/broker_account.py:21-26`), so
**one user can hold several broker accounts today**.

| question | answer |
|---|---|
| scoping | **account-level** |
| trader closes in Account A, hedges in Account B | the two are never related — **no false relationship is invented** |
| but | the hedge is **invisible**, and each account is judged in isolation |

This is the *safe* failure direction — the engine will not fabricate a
cross-account sequence — but a multi-account trader's risk is systematically
understated per account and never aggregated. Classify as **GAP**, not
FALSE-POSITIVE RISK. Note that `user_id`-level aggregation would be a genuine
design decision, not a bug fix: a hedge held in a different account is still a
real hedge, but combining accounts would also merge two independent trading
styles into one behavioural profile.

---

# COVERAGE OF THE BRIEF

Every requirement in `positional_validation.md`, mapped to where it is answered.
Checked line by line, 29 Aug. **"Covered — no issue found" is a real result and
appears below where that is the honest answer.**

## Opening list

| brief item | where | result |
|---|---|---|
| long/short equity | matrix §B | **GAP** — full notional regardless of direction; `EQ` also doubles as the unparseable bucket |
| long/short futures | matrix §B, archetypes | **FALSE-POSITIVE RISK** |
| long/short calls and puts | matrix §B, cross-cutting #4 | long **PASS**, short **FALSE-POSITIVE RISK** |
| CE↔PE reversals | **cross-cutting #0** | **PASS** on the flagged charge; residual mislabelling |
| partial exits, flips, averaging, pyramiding | matrix §A, cross-cutting #1 | partial exit **GAP**, flip `pnl_pct` **GAP**, averaging **GAP**, pyramiding **PASS by design** |
| protective hedges (FUT+PUT, FUT short+CALL, stock+option) | cross-cutting #3, matrix §C | FUT+PUT **GAP**, stock+option **UNSUPPORTED** |
| straddles / strangles | matrix §C | shape **PASS**, provenance **FALSE-POSITIVE RISK** |
| spreads, calendars, ratio, multi-leg | matrix §C | ratio **GAP (safety)**, calendar/diagonal **GAP**, 4-leg **GAP** |
| simultaneous / overlapping legs | matrix §C | **FALSE-POSITIVE RISK** — no test that legs were held together |
| hedge entry / removal / adjustment | cross-cutting #2, §C | entry **GAP** (first leg alerts), adjustment **FALSE-POSITIVE RISK**, removal — closing one leg leaves the other ungrouped, same root cause |
| intraday vs overnight | cross-cutting #6, matrix §D | **GAP** |
| MTF and MTF + hedges | area E1 | **GAP** / **UNSUPPORTED** |

## The 16 numbered additions

| # | item | where | result |
|---|---|---|---|
| 1 | position lifecycle | matrix §A (17 scenarios) | core discrimination **PASS**; 6 GAPs, 2 FP RISKs |
| 2 | average price changes | cross-cutting #1, matrix §A | **GAP** — the deflation is real and crosses thresholds |
| 3 | hedge recognition A/B/C | cross-cutting #3, matrix §C | the three states are **not** separated |
| 4 | hedge adjustment | cross-cutting #2, archetypes | **FALSE-POSITIVE RISK**, multiple detectors |
| 5 | expiry / rollover | cross-cutting #8, matrix §D | **GAP** — structurally undetectable |
| 6 | options strategy geometry | matrix §C (14 structures) | answered as "which detectors misunderstand it", per the brief |
| 7 | short-option sellers | cross-cutting #4 | 3 genuine guards; the rest **FALSE-POSITIVE RISK** |
| 8 | futures are not options | matrix §B | **GAP** — `opening_5min_trap` admits FUT then cannot compute for it |
| 9 | MTF | area E1 | **GAP** — not modelled; no `product` parameter anywhere in risk |
| 10 | cross-underlying hedges | matrix §C | **UNSUPPORTED**, correctly — not claimed |
| 11 | portfolio-level exposure | area E2 | gross **PASS**, net/hedge-adjusted **GAP**, sector/correlated **UNSUPPORTED** |
| 12 | capital / margin semantics | matrix §B | **GAP** — nine denominators, four meanings |
| 13 | time horizon | cross-cutting #7, matrix §D | **GAP** — 26 of 27 windows fixed |
| 14 | order intent vs execution | matrix §A, area E3 | **GAP** — intent not ingested; `TRIGGER PENDING` confirmed discarded |
| 15 | data failure states | area E3 (13 states) | **mostly PASS** — this is the best-handled area; two violations, both the headline |
| 16 | multi-account / multi-broker | area E4 | **GAP** — account-scoped; safe failure direction |
| — | trader archetypes (15) | archetype table | all 15 present |

## The seven "be especially strict" rules

| rule | verdict |
|---|---|
| CE→PE is not automatically direction instability | **HONOURED** — the detector that made this claim is retired |
| Opposite positions are not automatically a hedge | **VIOLATED** — but not in the way expected. Nothing infers a hedge from opposition; the futures-hedge branch infers one from option *type* while ignoring the option's *direction* |
| Adding to a loser can be averaging / pyramiding / strategy / harmful | **HONOURED** by `adding_to_adverse_position`, which deliberately excludes size and correctly excludes pyramiding |
| Premium loss differs long vs short | **VIOLATED** in `no_stoploss` and `opening_5min_trap`; **HONOURED** in `premium_loss_event`, `options_premium_avg_down` and both live paths |
| Position-level P&L, avg entry, realized/unrealized, remaining qty correct after fills | **MOSTLY HONOURED** — avg entry, realized P&L and remaining qty are correct. Unrealized/adverse excursion is never stored; `pnl_pct` breaks on an over-closing FLIP |
| MTF not treated as cash equity or F&O | **VIOLATED** — treated as cash equity |
| Never infer behaviour from missing/ambiguous data | **VIOLATED twice** — both are the headline finding |

## Required deliverables

| deliverable | status |
|---|---|
| PASS / GAP / FALSE-POSITIVE RISK / UNSUPPORTED for every scenario | done — 7 matrix sections |
| exact detector / service / file / line for every GAP and FP RISK | done |
| scenarios the brief did not list | done — 8 found |
| overall coverage assessment | done |
| highest-priority architectural gaps | done — 5 |
| pattern reviews to revisit | done — 7, with urgency |
| safe now vs needs more data | done |
| fix anything before Pattern 12 | done — **yes, one thing** |

## Checked and found clean — no issue to report

Recorded so the absence is deliberate rather than an omission:

- **Duplicate fills, out-of-order events, app restart, Redis restart** — handled
  correctly (unified `idempotency_key`, full ledger replay, state in Postgres).
- **Stale and missing LTP** — staleness genuinely enforced per price; the monitor
  abstains rather than guessing.
- **Rejected orders, and cancelled orders with zero fill** — correctly ignored.
- **Pyramiding** — deliberately and correctly excluded from
  `adding_to_adverse_position`, with the reasoning written down.
- **Cross-underlying hedging** — not claimed anywhere, which is the right answer
  for the data available.
- **Short options in `premium_loss_event`, `options_premium_avg_down` and both
  live paths** — properly guarded, with comments explaining why.
- **Position key** in the ledger — `(broker_account_id, tradingsymbol, exchange,
  product)` is correct and includes product.
- **`end_of_session_mis_panic`** — exchange-branched deliberately, with a
  documented MCX fix; correctly inert for non-intraday products.

---

# CONCLUSIONS

## Overall coverage assessment

**The engine models one trader correctly and asserts behaviour about everyone
else.**

What it does genuinely well, and these are not small things:

- **New-position vs additional-fill discrimination** (`_compute_fill_effect`) is
  pure, correctly keyed, replay-safe, and derives state from running quantity
  rather than `transaction_type` — the trap it records having already fallen into
  once. Weighted average entry, realized P&L and remaining quantity are correct.
- **`adding_to_adverse_position`** deliberately excludes size, correctly excludes
  pyramiding, and reports a fact rather than a cause. It is the strongest
  behavioural detector in the engine on the axis this audit examined.
- **Three short-option guards are real** — `premium_loss_event`,
  `options_premium_avg_down` and the two live paths gate `direction != "LONG"`
  explicitly, with a comment explaining why.
- **The live path abstains on missing or stale data**, with staleness genuinely
  enforced.
- **Cross-underlying hedging is not claimed**, which is the correct answer.

The failures cluster into one shape: **a percentage or a count is computed
against a denominator or a scope that is only valid for an intraday long-options
buyer, and the result is stated as a fact about the trader.**

## Highest-priority architectural gaps

**1. Absence is rendered as fact.** `no_stoploss` reads an unreadable exit-order
type as "no stop-loss existed"; `adding_to_adverse_position` reads an unknown
fill count as "opened in a single fill". Both are unconditional, silent, and
invert the product's thesis by scolding disciplined behaviour. The engine already
has `DetectorResult.abstained` and neither uses it. **This is the one finding
that is a bug on the current book, for the current trader, today.**

**2. There is no single, labelled definition of "size" or "risk".** Nine
denominators across four meanings, with `estimate_capital_at_risk` inverting for
short options and omitting the contract multiplier entirely. `instrument_risk`
exists precisely to prevent this, labels its answers correctly, and is bypassed
by the detectors that most need it. Real Kite margin data is fetched and read by
nothing.

**3. Strategy grouping is unreliable in both directions at once.** It
over-suppresses (`multi_leg_unknown` earns full hedge suppression; the canonical
revenge shape falls inside the window that silences it) and under-suppresses (the
group needs the sibling to have *closed*, so the first leg of every hedge alerts;
4-leg structures starve; the entry path has no group at all). A "hedge" is
asserted without reading the hedging leg's direction or any quantity.

**4. Session scope is `exit_time`-only while three detectors say "opened
today".** Correct for streaks and P&L, wrong for counting decisions, and it
yields two different counts for one declared rule.

**5. Time is fixed and style is unmodelled.** 26 of 27 windows are constants;
the only adaptive threshold is a duration by accident. Nothing in the codebase
represents a trading horizon.

## Which pattern reviews should be revisited

| pattern | why | urgency |
|---|---|---|
| **12 `no_stoploss`** | It was next in the queue anyway. It is now the audit's headline defect and **must not be reviewed on the current book** — the false positive is invisible there because the reference trader is intraday with the live-path ID mismatch masking everything. | **blocking** |
| **1 `martingale_behaviour`** | Verified as taking ratios across denominator *kinds* (`LOSS_CEILING` vs `MARGIN_POSTED`) without reading `.kind`. Its Pattern 1 rewrite specifically fixed the unit-mixing problem and this survived it. | high |
| **2 `adding_to_adverse_position`** | The detector is sound; its *dispatch* has three silent no-run paths and its entry-time context carries no `strategy_group`. Reviewed as logic, not as wiring. | high |
| **5 `overtrading_burst`** (deferred, still live) | Counts legs of a structure as separate decisions; 30-minute window fixed for every style. Should not ship without this. | high |
| **99 `revenge_trade`** (frozen) | The freeze should be **re-examined, not lifted**: it is silenced by `multi_leg_unknown` grouping inside its own window, and its per-instrument-class thresholds do not exist in the codebase. The frozen decision was made without knowing either. | medium |
| **3 `same_symbol_obsession`** | Conflates expiries and directions into "attempts"; assumes one lot size per underlying, which an NSE lot-size revision breaks. | medium |
| **8 `premium_loss_event`** | Its own short-option guard is correct. But it reads `ct.pnl_pct`, which is deflated by averaging down and inflated by an over-closing FLIP. The Pattern 8 conclusion holds; the input does not. | medium |

## What can safely be handled now vs what needs more data

**Safe to fix now, no new data required:**

- the `exit_trade_ids` ID-space mismatch (one column, one convention)
- abstaining instead of asserting when `exit_order_types` or `num_entries` are unknown
- adding `product` to `estimate_capital_at_risk`, and the contract multiplier to every denominator
- reading the option leg's direction in the futures-hedge branch
- testing `strategy_type != MULTI_LEG_UNKNOWN` before granting suppression
- separating "closed today" from "opened today" in the three detectors that claim the latter
- passing the already-computed `_open_structures()` into the entry-time context

**Needs data we do not have:**

- correlation / sector / index-constituent relationships → cross-underlying hedging is **UNSUPPORTED** and should stay so
- true margin per position → available from Kite, fetched, but plumbing it into detectors is a real change
- order intent (placed / modified / cancelled) → the `orders` table exists but is populated only on manual sync
- trading style / horizon → not derivable from trades alone without a stated definition
- equity holdings → not synced at all

## Should anything be fixed before Pattern 12?

**Yes — one thing, and Pattern 12 is the reason.**

Pattern 12 *is* `no_stoploss`. Reviewing it against the reference book would
measure a detector whose primary safety check has never once executed, on the one
dataset where that is invisible. Every conclusion drawn would be about the
degraded behaviour, not the intended one — the same error that made Pattern 9's
`expiry_day_overtrading` look like a threshold problem when it was a units bug.

**Recommendation: fix the `exit_order_types` plumbing and the
absence-as-fact handling first, then review Pattern 12 against a detector whose
primary check can actually fire.** That is a narrow, well-understood change with
a clear before/after test, and it does not require any of the architectural work
above.

Everything else in this audit is **recorded, not urgent**. None of the other
findings can produce a wrong alert for the current single-account intraday
long-options user; they are latent, and they become live the moment a futures
trader, an option writer, a spread trader, an MTF user or an overnight holder
connects an account.

## One caveat on this audit's own evidence

Areas A–D were investigated by subagents; I verified every finding labelled
VERIFIED against the code myself and marked the rest as claims. Area E I did
directly. No scenario in this audit was tested against a real multi-product
tradebook, because we do not have one — the conclusions about futures, short
options, MTF and overnight behaviour are **read from code, not measured**. They
are strong claims about what the code will do, not observations of what it did.
