# Trading Semantics & Strategy Coverage Audit

**Status: 4 of 5 areas reported. Area E (MTF / exposure / data failure /
multi-account) still running.** Started 28 Aug 2026.

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
| iron condor | shape ✓, but **never forms a 4-leg group on the live path** |
| iron butterfly | **dead code** — the branch is unreachable; every real one returns `iron_condor` first |
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
| intraday directional, long options | **PASS** — the reference book |
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

## Conclusions

**Pending Area E.** Written once all five are in.
