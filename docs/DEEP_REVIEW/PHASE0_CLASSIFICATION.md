# Phase 0 — Classification and Dependency Order

**29 Aug 2026. No production code changed.**

Every finding from the Trading Semantics audit and the Semantic Contract, in one
of four buckets. **Measured** means the in-process harness executed it;
**verified** means I read the code directly; nothing here is taken on a
subagent's word.

---

## FIX NOW — objectively wrong with existing data and code

| # | bug | evidence | affected |
|---|---|---|---|
| **F1** | **`exit_trade_ids` holds two identifier spaces.** Live ledger writes Kite order-id strings (`position_ledger_service.py:862` ← `trade_tasks.py:581`); batch FIFO writes `Trade.id` UUIDs (`pnl_calculator.py:570`). The one consumer casts `Trade.id` (`behavior_engine.py:551-553`). On the live path the lookup matches nothing, silently. | verified | `no_stoploss` (alerting, L2), `panic_exit`, **every live alert** (demoted `GOOD`→`PARTIAL`) |
| **F2** | **Absence rendered as a behavioural claim.** Empty `exit_order_types` → *"No stop-loss order detected"*. `num_entries=1` stub → *"opened in a single fill"*, a **negative finding** rather than an abstention. `abstained()` exists and is used 6 times across 23 detectors. | verified | `no_stoploss`, `panic_exit`, `adding_to_adverse_position` |
| **F3** | **Short option's capital at risk is a SPAN % of the premium *received*.** Measured: 9,000 premium → **1,080** "at risk", ratio 0.12. The class with unbounded downside gets the smallest number. `instrument_risk` classifies it correctly as `short_option`/`margin_posted` and passes the wrong amount through unchanged. | **measured** | `excess_exposure`, `constitution_violation`/`max_trade_risk`, `martingale_behaviour`, `revenge_trade`, `adding_to_adverse_position`, `baseline_service.own_position_risk` |
| **F4** | **`no_stoploss` has no direction guard** — references `direction` zero times. Denominator `entry_price × qty` is premium paid for a buyer, premium received for a writer. Measured: a short option whose premium tripled fires `no_stoploss`. | **measured** | `no_stoploss`, `opening_5min_trap` |
| **F5** | **Futures-hedge branch never reads the option leg's direction** (`strategy_detector.py:479-486`). Measured: FUT LONG + PE **SHORT** → `futures_hedge_bullish`; FUT SHORT + CE **SHORT** → `futures_hedge_bearish`. Risk-adding structures get the label and the suppression written for risk-reducing ones. | **measured** | the 5 detectors in `_STRATEGY_SUPPRESSED` |
| **F6** | **`MULTI_LEG_UNKNOWN` grants full hedge suppression.** Group built regardless of classification (`strategy_detector.py:90-98`); suppression tests presence, not type (`behavior_engine.py:748`). Contradicts `count_structures`, which refuses to collapse an unrecognised cluster. | verified | `revenge_trade`, `martingale_behaviour`, `rapid_reentry`, `no_stoploss`, `post_loss_recovery_bet` |
| **F7** | **Contract multiplier is applied to P&L but to no denominator.** `realized_pnl` uses it (`pnl_calculator.py:315`); every risk/size denominator omits it. `get_lot_multiplier_or_none` exists and is never called from a sizing path. | verified | MCX/CDS: `no_stoploss`, `excess_exposure`, `_notional` consumers |
| **F8** | **`is_comparable` contradicts its own docstring.** Documents False for *"an unclassifiable instrument"*; code is `kind not in (UNRELIABLE,)`. Measured: `unparseable_symbol` → `class=unknown`, **`is_comparable=True`**. | **measured** | `revenge_trade`, `martingale_behaviour`, `adding_to_adverse_position` |
| **F9** | **`parse_symbol` returns `EQ` for anything unparseable** (`instrument_parser.py:143-150`), so an unreadable derivative silently becomes equity with a delivery-value denominator. | verified | every `instrument_type` guard |
| **F10** | **FIFO position key omits `product`** (`pnl_calculator.py:198`) while the ledger and `positions` table include it. MIS and NRML holdings in one symbol net into rounds that never existed. Two fill-sequence readers drop it too. | verified | `pnl_calculator`, `adding_to_adverse_position`, position epoch |
| **F11** | **Monthly expiry hardcodes last-Thursday for every exchange** (`instrument_parser.py:176`), contradicting `exchange_constants.py`'s own documented BFO weekdays. | verified | `is_expiry_day` → `premium_loss_event`, `no_stoploss`, `fomo_entry` modifiers |
| **F12** | **`duration_minutes` has two definitions in one column** — wall clock (ledger) vs `market_minutes` (batch FIFO). An overnight hold is ~1,440 from one and ~375 from the other, and a recompute can overwrite. | verified | every hold-time gate |
| **F13** | **`opening_5min_trap` admits futures then cannot compute for them** — `loss_pct` is only computed for CE/PE, so the large-loss branch is unreachable for FUT. | verified | `opening_5min_trap` |
| **F14** | **Three detectors say "opened today" about a close-scoped count.** `session_facts` scopes on `exit_time` only (`:262-265`). The *scope* is a deliberate design; the **claim** is wrong. | verified | `daily_overtrading` message + registry copy, `constitution_violation`/`daily_trades` |

**F14 is deliberately narrow.** Changing the scope is DESIGN (D5). Making the
copy stop claiming "opened" is a fix.

---

## DESIGN REQUIRED — needs a decision before any code

| # | item | the decision needed |
|---|---|---|
| **D1** | Hedge model with quantity and overlap | What ratio and what degree of simultaneity constitute a hedge? F5 fixes a wrong *reading*; a real hedge model is new. |
| **D2** | One structure rule | Grouping (15 min, groups on failure) vs counting (30 s, refuses on failure) must become one rule. Which conservatism wins? |
| **D3** | Net / hedge-adjusted exposure | "Net" needs a definition — delta, notional, per underlying? No netting exists anywhere today. |
| **D4** | Partial exits as an analysable unit | 19 of 23 detectors take `CompletedTrade` as their unit. Emitting one per partial exit redefines "a trade" engine-wide. |
| **D5** | Session scope | "Closed today" is right for streaks and P&L, wrong for counting decisions. Both are needed; that is two facts, not one. |
| **D6** | Rollover as a concept | Requires a definition (same underlying, adjacent expiry, close+open within X). Then whether a roll is a behavioural event at all. |
| **D7** | MTF risk model | Needs the leverage semantics and, realistically, broker margin. |
| **D8** | Margin vs declared capital | Kite margin is fetched (`margin_service.py:129-136`) and consumed by no detector. Which is authoritative? |
| **D9** | Multi-account aggregation | Account-scoped today, which is the safe failure. Aggregating would merge two trading styles into one profile. |
| **D10** | Trading style / horizon | 26 of 27 time windows are fixed. Adapting them is retuning thresholds — explicitly out of scope for a semantics fix. |

---

## UNSUPPORTED — the data cannot answer it; the engine must abstain

| item | why |
|---|---|
| Cross-underlying hedging (RELIANCE + NIFTY PE, stock + index put) | no correlation, beta, sector or index-constituent data exists anywhere |
| Sector / correlated exposure | no sector taxonomy |
| Order intent (placed → modified → cancelled → filled) | `orders` is populated only on manual sync and read by one REST endpoint |
| Target vs discretionary limit exit | `order_type` is unreadable on the live path (and is F1 downstream) |
| Portfolio hedging against equity holdings | holdings are not synced at all |
| Automated vs manual trading | Kite exposes no such field |

**Requirement for all of these:** abstain explicitly. The regression test is that
missing information cannot produce a behavioural finding — which is F2.

---

## FALSE POSITIVE — audit concern disproved by the implementation

| claim | reality |
|---|---|
| *"Six `PERSONAL_BASELINE` specs are false declarations"* (my earlier audit) | **Wrong, and already corrected.** The registry documents `metric` as declaring personalisation *available*, with `personalise=False` deliberate. Two existing tests enforce it and correctly rejected my attempt to change them. |
| *"Opposite direction is treated as a hedge"* | **No such rule exists.** The defect is different and worse: the futures branch reads the option's *type* and ignores its *direction* (F5). |
| *"CE→PE is read as directional instability"* | **No longer true.** `direction_instability` was retired; `grep` confirms zero occurrences. Measured: a CE→PE reversal now fires `options_premium_avg_down` and `revenge_trade` — mislabelled, but not as instability. |
| *"CE is treated as bullish / PE as bearish"* | **Nothing does this.** Direction consistently means position exposure. |
| *"`pnl_pct` is broken by an over-closing FLIP"* | **Narrowed by measurement.** `_compute_fill_effect` handles it correctly — realizes only the closing portion (−1500 on the 50 still held, not the whole 200). The defect is in `_build_round_ct_fields`' aggregation, not the fill primitive. |
| *"Stale/missing market data can become behaviour"* | **False for the live path.** `ltp_cache` enforces staleness per price and the monitor abstains. The absence problem is F2, and it is about *stored* fields, not market data. |
| *"Duplicate or out-of-order fills corrupt state"* | **False.** Unified `idempotency_key` on the Kite order id; out-of-order triggers a full replay. |
| *"Pyramiding is misread as martingale"* | **False.** `adding_to_adverse_position` excludes size deliberately and excludes favourable adds, with the reasoning documented. |

---

## Dependency order for the FIX NOW items

Ordered so each step is independently verifiable and none invalidates an earlier
measurement.

### Stage 1 — semantic primitives (nothing depends on these being wrong)

**F8** `is_comparable` → **F9** `EQ` fallback → **F7** contract multiplier →
**F11** expiry weekday.

Pure functions, no detector reads change except through the values they return.
Each is a one-line-to-one-function change with a direct harness assertion.

### Stage 2 — the denominators (must follow Stage 1)

**F3** short-option capital at risk → **F4** `no_stoploss` direction guard →
**F13** `opening_5min_trap` futures guard.

F3 must precede F4: fixing the direction guard while the denominator is still
wrong would produce a *different* wrong number and make the harness diff
unreadable. F7 must already be in, or MCX values move twice.

### Stage 3 — identity and persistence (independent of 1–2)

**F10** product in the FIFO key → **F12** one `duration_minutes` definition →
**F1** `exit_trade_ids` one space.

F1 last in this stage because F12 touches the same builder, and doing them
together makes the round-construction diff attributable.

### Stage 4 — the claim layer (depends on F1)

**F2** abstain instead of asserting.

**Must follow F1.** With F1 fixed, `exit_order_types` is populated, so F2's
abstention path is only reached when data is *genuinely* missing — which is the
behaviour we want to test. Doing F2 first would make every live alert abstain and
hide F1.

### Stage 5 — suppression (independent, do last)

**F5** read the option's direction → **F6** require a known structure type.

Last because both change which alerts survive, so their harness diff should not
be entangled with denominator changes. F5 before F6: F5 corrects the
classification, F6 then decides what an unknown classification earns.

### Deliberately not in any stage

**F14** — the "opened today" copy fix is trivial but sits on top of D5. Do the
copy with D5's decision, not before it, or we will write the sentence twice.

---

## Summary

| bucket | count |
|---|---|
| **FIX NOW** | **14** |
| DESIGN REQUIRED | 10 |
| UNSUPPORTED | 6 |
| FALSE POSITIVE | 8 |

**Eight audit concerns did not survive verification**, including one of my own
central claims. That is the harness and the re-check doing their job, and it is
why the classification came after the baseline rather than before it.

**None of the 14 FIX NOW items can produce a wrong alert for the current
single-account intraday long-options trader** — except **F1 and F2**, which
affect every user on the live path today.
