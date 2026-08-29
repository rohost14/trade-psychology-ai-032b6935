# Trading Semantics Audit — Consolidated Report

**29 Aug 2026. Complete. No pattern was reviewed, retired or retuned.
No FIX NOW item below is implemented. Awaiting approval.**

> **SUPERSEDED IN PART — 29 Aug 2026, later the same day.**
>
> Section 5 of this report lists *"true margin per position"* as effectively
> unobtainable, and the companion note concluded that SPAN could not be
> reproduced without exchange risk parameter files. **That conclusion was
> wrong.** NSE Clearing publishes the full methodology, every parameter and the
> pricing model; the historical inputs are public and archived. A working
> calculator now reproduces real broker margins — futures within 0.5%, a call
> spread within 0.3%, long options exactly 0, short options systematically
> +5-7% high.
>
> **The rest of this report stands.** The FIX NOW list, the dependency order and
> the Pattern 12 verdict are unaffected — Pattern 12 is about the *order book*,
> not margin. Nothing below has been edited; the correction is recorded at the
> end under "Superseded conclusions" and in detail in
> [`RISK_AND_MARGIN_VERIFICATION.md`](RISK_AND_MARGIN_VERIFICATION.md).


Sources: [`SEMANTIC_CONTRACT.md`](SEMANTIC_CONTRACT.md) ·
[`CANONICAL_TRADING_SEMANTICS.md`](CANONICAL_TRADING_SEMANTICS.md) ·
[`PHASE0_CLASSIFICATION.md`](PHASE0_CLASSIFICATION.md) ·
[`TRADING_SEMANTICS_AUDIT.md`](TRADING_SEMANTICS_AUDIT.md) ·
harness `backend/tests/semantics/`

**Evidence standard.** Every claim below was verified by me directly against
code, or measured by the harness. Subagent findings were treated as claims;
the ones I could not verify are marked *reported*.

---

# 1. Canonical trading semantics

## Instrument × direction — all eight, measured

| combination | class | denominator kind | worked example | comparable |
|---|---|---|---|---|
| Buy Call | `long_option` | `loss_ceiling` | ₹9,000 premium paid | ✓ |
| **Sell Call** | `short_option` | `margin_posted` | ₹225,000 SPAN of contract notional | ✓ |
| Buy Put | `long_option` | `loss_ceiling` | ₹9,000 | ✓ |
| **Sell Put** | `short_option` | `margin_posted` | ₹225,000 | ✓ |
| Buy Future | `futures` | `margin_posted` | ₹225,000 | ✓ |
| Sell Future | `futures` | `margin_posted` | ₹225,000 | ✓ |
| Buy Equity | `equity` | `notional` | ₹290,000 | ✓ |
| Sell Equity | `equity` | `notional` | ₹290,000 | ✓ |

## Direction is never inferred from CE/PE — refuted twice, independently

**The brief asks this twice. The answer is no, and it is now confirmed by two
separate audits plus execution.** A `grep` for `bullish|bearish` across the
backend returns only the `FUTURES_HEDGE_BULLISH/BEARISH` structure labels, which
are named after the **futures leg's** direction. `instrument_risk.classify` is
the only place option type meets direction and it branches on `side == "LONG"`,
never on the CE/PE letters. `LONG` on a CE and `LONG` on a PE are both
`long_option`: the engine holds *"I bought an option"*, not *"I am bullish"*.

The only detector that ever read CE→PE as a directional claim was
`direction_instability`, retired 28 Aug on measurement.

## The ten structural concepts

Four already sound — *trade* (a complete round trip), *LONG/SHORT* (exposure
sign), the *underlying* definition, *same position* (same key, no zero-crossing).
Four contested — *exit* (three meanings, three ID spaces), *multi-leg structure*
(two rules with opposite conservatism), *authoritative data* (three writers, one
deletes the others), *UNKNOWN* (full vocabulary, ~6 uses across 23 detectors).

---

# 2. Scenario coverage and results

`backend/tests/semantics/` — in-process, real detectors, no DB, no Redis, no
synthetic rows. Runs in under a second.

| layer | coverage |
|---|---|
| L1 primitives | 29 structures · 19 capital-at-risk cases · 19 symbol-parsing cases |
| L2 lifecycle | 11 fill sequences via the ledger's pure `_compute_fill_effect` |
| L3 detectors | 26 scenarios through the real detector methods |

**Every scenario the brief lists is covered except four, and those are declared
rather than faked:** multi-account aggregation (does not exist to test), MTF
margin (no model exists — only its absence), partial-exit emission (produces no
CompletedTrade by design), and strategy-group creation (needs stored rows).

## What the harness measured that reading could not

| scenario | measured result |
|---|---|
| FUT LONG + PE **SHORT** | `futures_hedge_bullish` — a risk-**adding** structure labelled a hedge |
| FUT SHORT + CE **SHORT** | `futures_hedge_bearish` — same |
| 1×2 ratio spread | `bull_call_spread` — quantity never read |
| iron butterfly | `iron_condor` — its own branch is unreachable |
| diagonal | `calendar_spread` — strike never read |
| futures roll, weekly-opt/monthly-fut hedge, covered call | `multi_leg_unknown` |
| averaging down | **silences `premium_loss_event`** — 50%→caution becomes 37.5%→nothing |
| short option, capital declared | `excess_exposure` **silent at 0.1%** pre-F3; **danger at 22.5%** post-F3 |
| MTF equity vs cash equity | **identical detector output** |
| 14 real book symbols | **unparseable** — see F15 |

---

# 3. FIX NOW — complete list

Objectively wrong, unambiguous correction, no product decision required.

## Already implemented (Stage 1 + F3)

| # | fix | status |
|---|---|---|
| F8 | `is_comparable` now False for unclassifiable instruments | ✅ **but bypassed — see F17** |
| F9 | `parse_symbol` returns `None`, not `"EQ"`, for unreadable derivatives | ✅ **but undone — see F16** |
| F7 | contract multiplier reaches the denominator | ✅ **path-selective — see F17** |
| F11 | BSE index monthlies no longer inherit NSE's last-Thursday rule | ✅ complete |
| F3 | short option's capital at risk = SPAN of contract notional | ✅ **bypassed — see F17** |

## Outstanding

| # | bug | evidence | affected |
|---|---|---|---|
| **F1** | `exit_trade_ids` holds **three** identifier spaces — Kite order ids (live ledger), `Trade.id` UUIDs (batch FIFO), `[]` (overnight backfill). The one consumer casts `Trade.id`, so the live lookup matches nothing, silently. | verified | `no_stoploss`, `panic_exit`, **every live alert** demoted `GOOD`→`PARTIAL` |
| **F2** | Absence rendered as a behavioural claim. Empty `exit_order_types` → *"No stop-loss order detected"*. `num_entries=1` stub → *"opened in a single fill"*, a **negative finding** not an abstention. | verified | `no_stoploss` (alerting L2), `panic_exit`, `adding_to_adverse_position` |
| **F4** | `no_stoploss` references `direction` **zero times** for CE/PE. Denominator `entry_price × qty` is premium *paid* for a buyer, *received* for a writer. | verified | `no_stoploss` |
| **F5** | Futures-hedge branch reads the option's **type** and never its **direction**. | measured | the 5 suppressed detectors |
| **F6** | `MULTI_LEG_UNKNOWN` grants full hedge suppression — group built regardless of classification; gate tests presence, not type. Directly contradicts `count_structures`. | verified | `revenge_trade`, `martingale_behaviour`, `rapid_reentry`, `no_stoploss`, `post_loss_recovery_bet` |
| **F10** | FIFO position key omits `product` while the ledger and `positions` table include it. Two fill-sequence readers drop it too. | verified | `pnl_calculator`, `adding_to_adverse_position`, position epoch |
| **F12** | `duration_minutes` has two definitions in one column — wall clock vs `market_minutes`. A recompute overwrites. | verified | every hold-time gate |
| **F13** | `opening_5min_trap` admits FUT then computes `loss_pct` only for CE/PE, so its large-loss branch is unreachable for futures. | *reported* | `opening_5min_trap` |
| **F15** | **`_RE_MONTHLY_OPT` cannot read real NSE stock options** — `(\d{3,6})` rejects 2-digit strikes, no decimal allowed, `[A-Z&]+` rejects hyphens. **17 of 722 symbols, 38 of 2,175 fills (1.7%) of the real book.** Before F9 they were carried as **equity**. | **measured** | `premium_loss_event`, `options_premium_avg_down`, `excess_exposure`, `same_symbol_obsession`, strategy grouping |
| **F16** | **F9 is undone by `or "EQ"`** at `position_monitor_tasks.py:1344` and `entry_detectors.py:134` — `None` converted straight back to equity. | verified | `adding_to_adverse_position` live path, entry detectors |
| **F17** | **Detectors bypass the safety layer entirely.** `excess_exposure` and `constitution_violation`/`max_trade_risk` call `estimate_capital_at_risk` directly, never `risk_basis` — so `is_comparable`, `is_spread` and every UNRELIABLE marking are unreachable. Verified: `_detect_excess_exposure` has **zero** references to either. | verified | `excess_exposure`, `constitution_violation` |
| **F18** | **`cooldown_violation` never reads the trade** — **zero** references to `ctx.completed_trade`. It fires on cooldown *presence*. The engine runs on position **close**, so closing a position during a cooldown asserts *"Traded during active cooldown"*. | verified | `cooldown_violation` |
| **F19** | `overexposure`'s position query omits `product` then calls `scalar_one_or_none()`. The unique constraint includes `product`, so a symbol held in MIS **and** NRML **raises `MultipleResultsFound`**. | verified | `overexposure` — a crash, not a wrong number |
| **F20** | **`overexposure` consumes other detectors' output** — queries `BehaviorEvent` for `revenge_trade`/`martingale_behaviour`/`post_loss_recovery_bet` and promotes its own severity. The registry states the rule verbatim: *"A.10: no detector may consume another detector's output."* | verified | `overexposure` |
| **F21** | `death_spiral`'s `_ALIAS_NATURE` has 5 entries; the registry has 6. **`capital_mismatch` is missing**, so its events are silently dropped and can never contribute a domain. | verified | `death_spiral` |
| **F22** | `post_loss_recovery_bet`'s `_cross` branch is **dead code** — `prior` is already filtered to one underlying, so the set can never exceed size 1. | verified | `post_loss_recovery_bet` |
| **F23** | `winning_streak_overconfidence` fires **danger unconditionally on a zero baseline** — `avg_baseline is not None` passes for `0.0`, making the test `current_qty >= 0`. | verified | `winning_streak_overconfidence` |
| **F24** | `adding_to_adverse_position`'s exit path **never runs** — declared `trigger="entry"`, skipped by the exit loop, and **not in `ENTRY_DECIDABLE`**. Its only invocation is the live task, which loses `strategy_group`, `product` and the F9 abstention. The best-guarded code in the engine is unreachable. | verified | `adding_to_adverse_position` |
| **F14** | `daily_overtrading` copy says *"positions opened today"* about a close-scoped count. **Copy only** — the scope is D5. | verified | `daily_overtrading` |

**24 FIX NOW; 5 implemented, 19 outstanding.** Three of the five implemented are
partially defeated downstream (F16, F17) — **my Stage-1 fixes were correct where
they landed and did not reach every caller.**

---

# 4. DESIGN REQUIRED — complete list

| # | item | the decision needed |
|---|---|---|
| D1 | hedge model with quantity + overlap | what ratio and what simultaneity constitute a hedge? F5 fixes a wrong *reading*; a real model is new |
| D2 | one structure rule | grouping (15 min, groups on failure) vs counting (30 s, refuses on failure). Which conservatism wins? |
| D3 | net / hedge-adjusted exposure | "net" needs a definition. **`portfolio_concentration`'s `abs()` makes a hedge *increase* concentration** — but choosing the net measure is a product decision |
| D4 | partial exits as an analysable unit | 19 of 23 detectors take `CompletedTrade` as the unit |
| D5 | session scope | "closed today" is right for streaks and P&L, wrong for counting decisions. Two facts, not one |
| D6 | rollover as a concept | needs a definition before it can be detected |
| D7 | MTF risk model | needs leverage semantics and, realistically, broker margin |
| D8 | margin vs declared capital | Kite margin is fetched and consumed by no detector |
| D9 | multi-account aggregation | account-scoped today, which is the safe failure |
| D10 | trading style / horizon | 26 of 27 windows fixed; changing them is retuning |
| **D11** | **short equity denominator** | full notional today; a short posts ~20% margin with unbounded loss. Same question as D7/D8 |
| **D12** | **`same_symbol_obsession` identity** | groups on `underlying` alone, so equity + future + CE + PE are one "attempt sequence". What counts as "the same thing again"? |
| **D13** | **`holding_loser` hold clock** | measured from `last_entry_time`, so **adding to a loser resets it and silences the alert**. The more dangerous case goes quiet — but the fix is a definition |

---

# 5. UNSUPPORTED — the data cannot establish it

| item | why |
|---|---|
| **whether a trader had a resting stop-loss** | see §8 and the Pattern 12 verdict |
| cross-underlying hedging | no correlation, beta, sector or index-constituent data |
| sector / correlated exposure | no sector taxonomy |
| order intent (placed → modified → cancelled) | `orders` populated only on manual/EOD sync, read by one REST endpoint |
| target vs discretionary limit exit | `order_type` unreadable on the live path (F1) |
| portfolio hedging against holdings | holdings sync explicitly skipped |
| automated vs manual trading | Kite exposes no such field |
| whether two legs were held simultaneously | grouping matches entry time ±15 min, never overlap |
| BSE index monthly expiry date | no sourced rule; **abstains since F11** |

---

# 6. FALSE POSITIVE — disproved by code and scenarios

| claim | reality |
|---|---|
| **CE treated as bullish / PE as bearish** | **Refuted twice, independently, plus execution.** Nothing does this |
| "Opposite direction is treated as a hedge" | No such rule. The real defect is F5 — type read, direction ignored |
| "CE→PE is read as directional instability" | `direction_instability` retired; zero occurrences remain |
| "`pnl_pct` is broken by an over-closing FLIP" | **Narrowed by measurement.** `_compute_fill_effect` is correct — realizes only the closing portion. The defect is in round *aggregation* |
| "Stale/missing market data becomes behaviour" | False for the live path — staleness enforced per price, monitor abstains |
| "Duplicate or out-of-order fills corrupt state" | False — unified `idempotency_key`, full replay |
| "Pyramiding misread as martingale" | False — `adding_to_adverse_position` excludes size deliberately and excludes favourable adds |
| "Six `PERSONAL_BASELINE` specs are false declarations" | **Mine, and wrong.** The registry documents `metric` as declaring availability; `personalise=False` is deliberate |
| "`overtrading_burst` counts legs" | False — the only detector using `count_structures` on all paths |
| "`rapid_reentry` conflates rollover" | False — matches exact `tradingsymbol`. The only "same thing again" detector that gets rollover right |
| "`premium_loss_event` / `options_premium_avg_down` mishandle shorts" | False — both guard `direction != "LONG"` explicitly, on every leg |
| "Averaging corrupts size semantics" | Largely false — `avg × peak qty` is the premium deployed. The real defect is upstream `pnl_pct` |

---

# 7. Dependency order for FIX NOW

**Stage A — reach (nothing else works until the fixes reach their callers)**
`F16` (`or "EQ"`) → `F17` (route `excess_exposure` + `constitution_violation` through `risk_basis`)
*Rationale: F3/F7/F8/F9 are already correct; these two make them apply. Doing anything else first re-measures against a layer that is bypassed.*

**Stage B — parsing (feeds every identity comparison)**
`F15` regex.
*Must follow Stage A: F15 turns 17 symbols from UNKNOWN into real options, and they should land in a world where the safety layer is actually consulted.*

**Stage C — identity and persistence**
`F10` (product in FIFO key) → `F12` (one duration definition) → `F1` (one ID space).
*F1 last: F12 touches the same builder.*

**Stage D — the claim layer**
`F2` abstain instead of asserting.
***Must follow F1***, or every live alert abstains and hides F1.

**Stage E — direction and denominators**
`F4` (`no_stoploss` direction guard) → `F13` (futures branch).
*After Stage A, so the fix routes through the corrected layer.*

**Stage F — suppression**
`F5` (read the option's direction) → `F6` (require a known structure type).
*Last: both change which alerts survive.*

**Stage G — independent, any time**
`F18` `cooldown_violation` · `F19` `overexposure` crash · `F20` A.10 breach ·
`F21` alias map · `F22` dead branch · `F23` zero baseline · `F24` wiring.
*None interacts with A–F. **F19 is a crash and should arguably go first.***

**Excluded:** `F14` — sits on D5, write the copy once with that decision.

---

# 8. Missing data and API capabilities

| capability | Kite provides? | we ingest? | any detector reads? |
|---|---|---|---|
| resting stop-loss orders | **yes** — `get_orders()` returns the full day book with `order_type`, `trigger_price`, `status`, `pending_quantity` | **only on manual/EOD sync**; the real-time path filters to `COMPLETE` | **no** |
| true margin per position | **yes** — `span`, `exposure`, `option_premium` | **yes** — `margin_service` fetches it | **no** |
| historical resting stops | **no** — the order book is same-day | n/a | n/a |
| equity holdings | yes | **no** — sync explicitly skipped | no |
| MTF leverage / financing | partial | product tag only | no |
| instrument correlation / sector | **no** | n/a | n/a |
| automated-vs-manual flag | **no** | n/a | n/a |

**The two that matter most are both "Kite provides it, we drop it":** resting
stop-loss orders and real margin.

---

# 9. Pattern 1–11 impact register — INFORMATIONAL ONLY

**This is not permission to change any pattern.** It records which closed
patterns *may* be affected if the FIX NOW items land.

| pattern | status | may be affected by | why |
|---|---|---|---|
| 1 `martingale_behaviour` | COMPLETE | F3 ✅, F6, F15, F17 | takes ratios across denominator *kinds* without reading `.kind`; `is_spread` passed for `cur` but not `prv` |
| 2 `adding_to_adverse_position` | COMPLETE | **F24**, F16, F10 | its exit path **never runs**; the live path loses all three guards |
| 3 `same_symbol_obsession` | COMPLETE | F15, D12 | groups on `underlying` alone; `or 1` on quantity can escalate caution→danger |
| 4 `consecutive_loss_streak` | RETIRED | — | gone |
| 5 `daily_overtrading` | COMPLETE | F5, F14 | `count_structures` inherits the hedge misclassification |
| 5 `overtrading_burst` | **DEFERRED, live** | F15 | digit-containing underlyings never cluster |
| 6 `profit_giveaway` | RETIRED | — | gone |
| 7 `fomo_entry` | COMPLETE | F15 | unparseable underlyings inflate the distinct-underlying count |
| 8 `premium_loss_event` | COMPLETE | F12, F15, and the `pnl_pct` aggregation defect | caps a known-bad `pnl_pct` at 100% and states it as fact |
| 9 `expiry_day_overtrading` | RETIRED | — | gone |
| 10 `size_escalation` | RETIRED | — | gone |
| 11 `direction_instability` | RETIRED | — | gone |
| 99 `revenge_trade` | **FROZEN** | F6, F15, F17 | silenced by `MULTI_LEG_UNKNOWN` inside its own window; emits at `a_level=0` when both magnitude frames abstain |

**Measured impact of the already-landed fixes on the reference book:** F9 moved
**38 fills (1.7%)** from a wrong equity classification to abstention. F7 and F11
touched **nothing** in this book (no MCX; BSE monthlies present but the affected
19 contracts are all weeklies by expiry key). **I previously recorded F9 as
having no impact. That was wrong, and measuring the register is what caught it.**

---

# 10. Exact recommended changes — NOT IMPLEMENTED

Sketches for approval. No code has been written.

**F16** — delete the fallback at two sites; let `None` propagate:
```python
# position_monitor_tasks.py:1344, entry_detectors.py:134
-    return parse_symbol(symbol or "").instrument_type or "EQ"
+    return parse_symbol(symbol or "").instrument_type      # None -> UNKNOWN (F9)
```

**F17** — route both callers through `risk_basis` and honour `is_comparable`:
```python
# behavior_engine.py ~1914 (excess_exposure) and ~3123 (max_trade_risk)
-    capital_at_risk = estimate_capital_at_risk(..., exchange=ct.exchange)
+    basis = risk_basis(ct.instrument_type, ct.tradingsymbol or "", ct.direction,
+                       float(ct.avg_entry_price or 0), int(ct.total_quantity or 0),
+                       is_spread=ctx.strategy_group is not None, exchange=ct.exchange)
+    if not basis.is_comparable:
+        return abstained(<name>, Insufficiency.<reason>, basis.label)
+    capital_at_risk = basis.amount
```

**F15** — widen the strike and underlying classes only:
```python
# instrument_parser.py:46
-    r"^([A-Z&]+)(\d{2})(JAN|…|DEC)(\d{3,6})(CE|PE)$"
+    r"^([A-Z&\-]+)(\d{2})(JAN|…|DEC)(\d+(?:\.\d+)?)(CE|PE)$"
```
*Verify against the 5 control symbols; the harness holds both sets.*

**F1** — one identifier space. Make the ledger builder write `Trade.id`:
```python
# position_ledger_service.py:862
-    "exit_trade_ids": [e.fill_order_id for e in exit_fills],
+    "exit_trade_ids": [str(e.fill_trade_id) for e in exit_fills],
```
*Requires the ledger to carry `fill_trade_id`; confirm before committing to this shape.*

**F18** — read the trade:
```python
# behavior_engine.py ~1848
+    if not ct.entry_time or ct.entry_time < cooldown.started_at:
+        return None    # the position was OPENED before the cooldown began
```

**F19** — include `product`, or use `.all()` and evaluate each row:
```python
# position_monitor_tasks.py:372-377
+    Position.product == product,      # the unique constraint includes it
```

**F21** — add the missing alias:
```python
# behavior_scores_service.py:34-41
+    "capital_mismatch": "<its registry nature>",
```

**F23** — treat a zero baseline as no baseline:
```python
# behavior_engine.py:2375
-    if avg_baseline is not None and current_qty >= avg_baseline * size_mul_danger:
+    if avg_baseline and current_qty >= avg_baseline * size_mul_danger:
```

**F20, F22, F24, F4, F13, F5, F6, F10, F12, F2** — each needs its own diff
written against the code at the time; sketching them now would go stale behind
the earlier stages.

---

# Pattern 12 verdict — recorded, NOT implemented

**UNSUPPORTED as currently claimed.**

Kite *does* provide reliable resting stop-loss data and our schema can hold it.
The pipeline loses it: `sync_orders_to_db` is correct but called only from two
manual endpoints, the real-time path filters to `COMPLETE`, and **no detector
reads the `orders` table**.

Even with F1 fixed, the exit fill's order type answers a different question:

| question | answerable |
|---|---|
| "was this exit executed by a stop order?" | **yes**, after F1 — a fact |
| "did the trader have a resting stop-loss?" | **no** — needs the order book |
| "did the trader ignore their stop-loss?" | **no** |

A trader with a resting SL who exits manually first shows `MKT` and is flagged as
having had none — the inverse of the truth.

**A position losing 50% is a measurable fact. "The trader ignored their
stop-loss" is a behavioural claim the data as wired does not support.**


---

# Superseded conclusions — added 29 Aug 2026

Recorded here rather than edited into the text above, so the reasoning that led
to the wrong answer stays visible.

| # | claim in this report / its companion note | status |
|---|---|---|
| 1 | "SPAN cannot be reproduced without exchange risk parameter files" | **WRONG.** The `.spn` file is a convenience so members "need not execute complex option pricing calculations". The method, parameters and model are published; the inputs are public and archived back years |
| 2 | "any internal calculator is an approximation wearing a precise name" | **WRONG** for futures (−0.2%/+0.5%), spreads (−0.3%) and long options (exact). **Partly right** for short options, which carry a measured, unexplained +5-7% |
| 3 | "true margin per position — Kite provides it, we drop it" (§8) | **HALF WRONG.** Kite provides margin only for a **prospective** order. No API returns the margin of a past position, so for history it was never ours to drop — it must be computed |
| 4 | "the 12% constant is accurate to ±12-50%, overstating" | **WRONG.** Measured across a live strike ladder it runs **−35% to +158%**, under-stating deep ITM where risk is largest |
| 5 | "the probe reproduced a real margin to +0.77%" | **WITHDRAWN.** It compared a 4-day weekly against the oracle's 32-day monthly. Different contracts; the agreement was coincidence |
| 6 | **F15** — the parser cannot read 17 real symbols | **STILL VALID, but reordered.** For *historical* NSE data it dissolves: the bhavcopy states `FinInstrmTp`, `TckrSymb`, `StrkPric`, `OptnTp`, so nothing is parsed. The regex fix remains necessary on the **live** path, where only a tradingsymbol arrives |
| 7 | **F11** — monthly expiry hardcoded to last Thursday | **CONFIRMED AND WORSE.** NIFTY's 2026 monthlies are **Tuesdays** (09-29, 10-27, 11-23). The fix is to read `XpryDt`, never to compute a weekday |

**Unaffected:** every other FIX NOW item, the dependency order, the DESIGN /
UNSUPPORTED / FALSE POSITIVE lists, the Pattern 1-11 impact register, and the
Pattern 12 verdict.

**Pattern 12 specifically.** Nothing here changes it. Its problem is that the
resting **order book** is not available to detectors — a different pipeline from
margin. It remains UNSUPPORTED and unimplemented.

New deliverables: [`RISK_AND_MARGIN_VERIFICATION.md`](RISK_AND_MARGIN_VERIFICATION.md) ·
[`MARGIN_VALIDATION_MATRIX.md`](MARGIN_VALIDATION_MATRIX.md) ·
[`INSTRUMENT_MASTER_SPEC.md`](INSTRUMENT_MASTER_SPEC.md) ·
[`RISK_LAYER_ARCHITECTURE.md`](RISK_LAYER_ARCHITECTURE.md) ·
[`DETECTOR_RISK_DEPENDENCY_MAP.md`](DETECTOR_RISK_DEPENDENCY_MAP.md)
