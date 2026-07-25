# P1 — Money Math (findings)

> Scope (read in full): `services/pnl_calculator.py`, `services/position_ledger_service.py`,
> `services/mcx_contract_specs.py`, `core/exchange_constants.py`, the P&L reconcile + overnight-backfill in
> `services/trade_sync_service.py` (L930–1243), `models/completed_trade`, `models/trade`, `models/position_ledger`.
> **Findings-only.** Every ₹ path checked: FIFO/average-cost engines, multipliers, reconcile authority, idempotency.

## Architecture as-verified (ground truth — supersedes stale docstrings)
- **Two P&L engines:** (1) **live** `PositionLedgerService` = append-only ledger, **average-cost** method, per-fill, idempotent, handles partial/flip/out-of-order via replay; (2) **batch** `PnLCalculator` = **true FIFO** queue, runs on initial sync + EOD, idempotently deletes+recreates CompletedTrades in a `days_back` window. Over a full **flat-to-flat round the two agree on total P&L** (weighted-avg identity), so `CompletedTrade.realized_pnl` is consistent between them. ✅
- **Authority = our FIFO/ledger, RAW price-based** ((exit−entry)×qty×multiplier). The reconcile (`_reconcile_pnl_with_zerodha`) is now **log-only for MCX/CDS** (emits `data_quality_events` on >10% divergence) + an **avg-based repair pass for NSE/BSE/NFO/BFO**. It **never overwrites with Zerodha's `realised`** anymore. This honours the raw-P&L rule. ✅
- **Overnight/cross-day** positions FIFO can't match are backfilled from Zerodha carry-forward (`average_price` + `day_sell/buy_price` + `realised`). ✅
- **Multipliers** (`mcx_contract_specs`) are well-sourced (Z-Connect ₹/₹1-move); NSE/BSE/NFO/BFO=1 (Kite pre-expands units), MCX/CDS from tables with a Zerodha-`multiplier` fallback. ✅

---

## 🟠 P1 — correctness, common real-world paths

### M1 · Derived P&L does not segregate by product (MIS vs NRML vs MTF) · correctness
- **Where:** `position_ledger_service` keys positions by `(broker_account_id, tradingsymbol, exchange)`; `pnl_calculator._process_symbol_trades` groups by `f"{symbol}|{exchange}"`; `trade_sync._backfill_overnight_completed_trades` existence-check filters by `(symbol, exit_time)` only. **None include `product`.** By contrast the **Positions table IS keyed per-product** (`trade_sync` L758/797/910 `(symbol, exchange, product)`), and Zerodha holds MIS and NRML as **separate positions**.
- **Failure:** a trader **long NRML** and **short/scalping MIS** on the **same contract** (common in F&O) has both legs **netted into one position** by the ledger/FIFO → wrong entry/exit matching, wrong per-round P&L attribution, wrong direction/qty, and **missing or mis-built CompletedTrades**. The overnight backfill's product-blind existence check can **skip** a genuine NRML overnight close because an unrelated MIS CompletedTrade exists for that symbol today.
- **Fix:** include `product` in the ledger/round/backfill keys (map MTF→NRML-like if intended). Requires a ledger key/migration change — scope in the fix pass.

### M2 · FLIP-opened rounds produce no CompletedTrade in the live path · correctness
> ✅ **FIXED 2026-07-26 (test-first)** — extracted pure `_build_round_ct_fields(round_entries, preceding_flip)`; `build_completed_trade_on_close` now passes the FLIP that opened the round so its opened quantity counts as the round's entry (at the flip fill price), and bounds the round slice at the close entry (also fixes a latent replay-rebuild over-slice). `tests/test_flip_round.py` (normal unchanged · flip-opened short builds · flip+add weighted avg · insufficient→None) RED→GREEN; 155 tests pass, no regressions.
- **Where:** `position_ledger_service.build_completed_trade_on_close`. A `FLIP` entry closes round A **and** opens round B. `round_start_idx` sets the next round to start **after** the FLIP, and `entry_fills` only collects `OPEN/INCREASE`. The FLIP that **opened** round B is classified as an exit fill, so when round B later closes: `entry_fills` is **empty → returns None → no CompletedTrade** (or, if a post-flip `INCREASE` exists, `total_entry_qty`/`avg_entry` **understate** by the flip-opened quantity).
- **Failure:** long→(sell flips to short)→(buy to cover). The **short round is invisible** to the real-time BehaviorEngine (which triggers off the freshly-built CompletedTrade) → **no live pattern detection / features** for flip trades. The batch FIFO *does* handle flip-excess as a new entry fill, so the round reappears at **EOD** — masking the gap and creating intraday/EOD inconsistency.
- **Fix:** treat the flip-opened quantity as round B's opening entry (synthesise an OPEN from the FLIP's excess, at `fill_price`). Add a flip fixture to `test_behavior_engine`/ledger tests.

### M3 · MCX/CDS **unrealized** P&L ignores the lot multiplier · correctness (money-facing)
> ✅ **FIXED 2026-07-26 (test-first)** — extracted pure `_unrealized_pnl_for_position(qty, entry, current, multiplier)`; `get_unrealized_pnl` now resolves the multiplier via `get_lot_multiplier_or_none` (fallback `Position.multiplier`, else 1) and applies it. New `tests/test_pnl_multiplier.py` (4 cases: NSE=1×, MCX long/short/loss ×100) — RED before, GREEN after; 140 logic tests pass, no regressions.
- **Where:** `pnl_calculator.get_unrealized_pnl` computes `(current−entry)*qty` with the comment "Kite qty already in units — no multiplier". True for NSE/NFO, **false for MCX/CDS**, where `Position.total_quantity` is in **lots** and `Position.multiplier` is populated but **not applied here**. Called by `api/analytics.py:162`.
- **Failure:** a CRUDEOIL (×100) open position shows unrealized P&L **≈1/100th** of reality; ZINC ×5000 etc. Commodity/currency traders see grossly understated open P&L wherever this feeds. (Realized path *does* apply the multiplier — so realized vs unrealized are inconsistent for the same instrument.)
- **Fix:** multiply by `get_lot_multiplier_or_none(exchange, symbol)` (fallback `Position.multiplier`) as the ledger's `_resolve_lot_mult` already does.

---

## 🟡 P2 — correctness-adjacent / latent / stale

### M4 · `pnl_calculator` docstring is stale and misleads correctness reasoning · doc-stale
Lines 51–55 state P&L is "overwritten post-sync by `_reconcile_pnl_with_zerodha()` which uses Zerodha's authoritative 'realised' field". **No longer true** — reconcile is log-only (MCX/CDS) + avg-repair (NSE). Anyone reasoning about "which number wins" is misled. Update to describe the current raw/FIFO authority. → ledger.

### M5 · Unknown MCX contract: batch silently uses multiplier 1 (wrong P&L) while ledger falls back · correctness
`pnl_calculator` calls `get_lot_multiplier` (returns **1** + a warning for an untabulated MCX prefix) → persists **wrong** `realized_pnl`. The **ledger** uses `get_lot_multiplier_or_none` → falls back to `Position.multiplier` (correct). Two engines, two behaviours for the same gap. Reconcile only **logs** the divergence (`data_quality_events`), never corrects it. Any MCX contract not in `MCX_MULTIPLIERS` (and note `_extract_prefix` assumes variant symbols like `NATGASMINI` match table keys exactly — verify against a live Zerodha instrument dump) yields a wrong-P&L CompletedTrade until the table is updated. **Fix:** make batch use the `_or_none`+Position.multiplier fallback too.

### M6 · Live CompletedTrade uses a random UUID; batch uses a deterministic one → id churn on rebuild · correctness/quality
> ✅ **FIXED 2026-07-26 (test-first)** — extracted shared `stable_completed_trade_id`; the live `build_completed_trade_on_close` now sets `id=` from it, and the batch `_stable_ct_id` delegates to the same function (can't drift). `tests/test_stable_ct_id.py` proves determinism + **ledger==batch agreement** (RED→GREEN); 151 tests pass. **Also resolves P2-E2 (link survives rebuild) and P5-Q1 (behaviour-cost stops under-counting).**
> **CORRECTION (P5-C1):** id-churn fires on **CompletedTrade rebuild** (import / manual recalc / late-fill replay), **not** "at EOD/nightly" (grep: eod/webhook never call `calculate_and_update_pnl`). Latent, not guaranteed nightly. **P2.** Consequence: nulls alert `trigger_completed_trade_id` (P2-E2) → under-counts `behaviour-cost` (P5-Q1).
`build_completed_trade_on_close` constructs `CompletedTrade` with **no `id`** (random UUIDv4). `pnl_calculator._build_completed_trade` uses `_stable_ct_id` (deterministic uuid5). At EOD the batch **deletes+recreates** the window, so an intraday round's CompletedTrade **id changes**. Any FK captured intraday against the live id (e.g. a journal entry linked while the position was fresh) is **orphaned** at EOD. Memory claims the stable id "survives re-syncs" — only true for the batch path. **Fix:** have the live builder also use `_stable_ct_id`.

### M7 · Dead code: `PnLCalculator.calculate_trade_pnl_realtime` · dead-code
Replaced by the ledger (per its own docstring + `trade_tasks.py:421` comment). **Zero live callers** (grep). ~90 LOC of unbounded per-fill replay (would have been O(n²)/day per symbol). → ledger (archive/remove).

### M8 · Batch FIFO `days_back` window vs unbounded live replay can disagree for long holds · correctness (bounded)
`pnl_calculator.calculate_and_update_pnl` only loads trades with `order_timestamp >= now-days_back` (default 30). A closing fill inside the window whose **opening leg predates it** has no opener in the FIFO queue → mis-round/incomplete. The live ledger replays **all** priors (unbounded). Real overnight holds are covered by the separate overnight-backfill path, so impact is limited to the pure-FIFO edge — but the two engines aren't equivalent for >`days_back` positional holds. **Fix:** seed the batch queue from prior net position (or widen for open symbols).

---

## ⚪ P3 — nits
- **M9** `pnl_calculator` does float arithmetic *before* wrapping in `Decimal(str(...))` (e.g. `Decimal(str((price-open)*qty))`), so float rounding precedes Decimal; the ledger uses `Decimal` throughout (`quantize` HALF_UP). Round totals match at ₹ display precision, but the two engines carry different precision. Prefer Decimal end-to-end in batch.
- **M10** Two `is_market_open` implementations: `exchange_constants.is_market_open` (ignores holidays, `zoneinfo`) vs `market_hours.is_market_open` (honours holidays, `pytz`). Divergent answers on holidays; two tz libs. Consolidate (ties to P0-F7). → ledger.
- **M11** `_stable_ct_id` collides if two distinct rounds share `(symbol, entry_time, exit_time, direction)` (same-second scalps) → PK clash on recreate. Very low probability; note.

## ✅ Solid
Ledger idempotency + out-of-order replay + Decimal precision are well done; multiplier table is carefully sourced with a Zerodha fallback; reconcile correctly enforces **raw** P&L (no charges, no Zerodha-net overwrite) and records missing-multiplier divergences as data-quality events; overnight cross-day backfill uses Zerodha carry-forward correctly; round-total P&L is provably engine-consistent.

## For P14 (QA) — money regression must include
Multi-round symbol · partial fills · **product-mixed MIS+NRML same symbol (M1)** · **flip long→short→cover (M2)** · MCX unrealized (M3) · untabulated MCX contract (M5) · >30-day NRML hold (M8) · out-of-order webhook replay · double-postback idempotency. Golden dataset with expected per-round ₹.
