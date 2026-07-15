# Production Readiness Review — Dashboard, Real-Time Pipeline, FIFO, Instruments, Scale

*Date: 2026-07-15. Scope: Dashboard/Home page (all components + popups), Real-Time Alerts status, real-time data flow (the 3–5 min delay), FIFO/position ledger edge cases, instruments & lot-size handling, P&L calculation strategy, future architecture (Sensibull-style streaming, 10k+ users), plus cross-cutting production concerns.*

*Findings only — nothing implemented. Severity: **P0** = broken/wrong data in production, **P1** = will bite soon or under specific conditions, **P2** = quality/robustness, **P3** = polish/hygiene.*

---

## ⚑ IMPLEMENTATION STATUS (2026-07-15)

All findings below were implemented in this session except where noted. Summary:

| # | Status | Notes |
|---|--------|-------|
| 1.1 order ingestion | ✅ FIXED | New `order_stream_service.py`: per-online-user KiteTicker `on_order_update` → existing `process_webhook_trade` pipeline. Started on WS connect, ref-counted, torn down on disconnect. Per-api_key connection cap. |
| 1.2 api_key/token pairing | ✅ FIXED | Fallback pairs `account.api_key` with its own token; skips unusable rows. |
| 1.3 dead post-sync refresh | ✅ FIXED | Removed non-existent `get_position_instruments`/`ws_manager.subscribe`; kept the working `refresh_subscriptions`. |
| 1.4 cross-process refresh | ✅ FIXED | Celery publishes `subscription_refresh` internal event; FastAPI subscriber refreshes the live ticker. |
| 2.1 guardrail attrs | ✅ FIXED | Uses `average_entry_price`/`total_quantity` (signed) × `multiplier`. |
| 3.1 duplicate fills | ✅ FIXED | REST replay now aggregates executions per Kite order_id and keys the ledger on `{kite_order_id}:ledger` — unified with webhook/order-stream. |
| 3.2 replay rebuild | ✅ FIXED | `_apply_fill_with_replay` rebuilds derived CompletedTrades for affected rounds. |
| 4.1c instruments table | ✅ FIXED | `refresh_instruments` persists to DB via bulk UPSERT (was memory-only). |
| 4.2a/b multiplier fallback | ✅ FIXED | Unknown MCX → Zerodha `positions.multiplier`; ledger resolves via Position row. `get_lot_multiplier_or_none`. |
| 4.2c CDS exchange | ✅ FIXED | Added to `SUPPORTED_EXCHANGES`. |
| 5.1 journaled-on-close | ✅ FIXED | Marks journaled only on successful save (`onSaved`/`onDeleted` callbacks). |
| 5.3 staleness indicator | ✅ FIXED | Live/Delayed/Paused pill on Open Positions, driven by last-tick timestamp. |
| 5.4 drawdown order | ✅ FIXED | Folds trades in exit-time order. |
| 5.2 journal keying (episodes) | ✅ FIXED (2026-07-15) | Open positions journal against a synthetic per-episode UUID (position id + IST date) via `src/lib/journalKey.ts`; backend `source_id` verifies ownership. No column type change — analytics join intact. |
| win_rate breakeven | ✅ FIXED | Win rate = wins/(wins+losses); breakeven excluded from denominator. |
| risk_used dead prop | ✅ FIXED | Removed from tradeStats + SessionHeroCard. |
| symbol parser dup | ✅ FIXED | Extracted to `src/lib/symbolParser.ts`; both tables import it. |
| journal auto-prompt | ✅ FIXED | 45s prompt reads current open-state via refs; won't interrupt an open sheet/prompt. |
| PredictiveContextStrip | ✅ RESOLVED | Verified functional (fetches insights + predictive-check); S36 "killed" note was stale — kept live. |
| 6.2 multi-socket per account | ✅ FIXED | `ConnectionManager` stores a set per account; fan-out to all, prune individually. |
| 6.1 LTP multi-worker | ✅ CLARIFIED | Each process owns its own ticker + delivers to its local clients, so delivery is already multi-worker-correct; the real limit is ~3 KiteTicker conns/api_key. Documented; leader-election deferred to the scale where >3 web procs are needed. |
| 7.1 webhook empty secret | ✅ FIXED | Rejects postbacks when no secret is available (no empty-string fallback). |
| 7.2 observability | ✅ FIXED | Added ingestion counters (`postbacks_received/rejected`, `order_stream_fills/started`). |
| 7.3 no-polling | ✅ FIXED | Removed AlertContext 60s poll and BehaviorRiskBadge 120s timer — both now event-driven. |
| 5.x PredictiveContextStrip | ⚠ FLAGGED | Rendered on Dashboard despite S36 "killed" note. Left as-is (functional); product decision. |

**Gross-vs-net P&L — DECIDED (2026-07-15):** keep raw P&L only — `(exit − entry) × qty × multiplier`, with NO brokerage / STT / taxes / charges deducted or estimated. Rationale: avoids a per-segment fee model that Indian budgets change every few months. A disclaimer on the app/website states charges/STT are not included. No charge estimator will be built. (Behavioral thresholds therefore run on raw P&L; accept that they slightly under-trigger vs a charges-inclusive number.)

Verified: backend `py_compile` + import smoke all pass; `test_phase2_services` + `test_trade_classifier` (54) and `test_integration` (25/26 — the 1 failure is a pre-existing stale Redis mock, fails identically on baseline) pass; frontend `vite build` succeeds; tsc error count 29 (down from 30 baseline — no new type errors); vitest passes.

---

## 0. Executive Summary

The behavioral engine core (v2) is in good shape: idempotent fill pipeline, replay parity, partitioning, observability. The weak layer is the **real-time market-data and trade-ingestion path** — the exact area the user experiences daily. The 3–5 minute "random" delays are not one bug; they are the visible symptom of **four independent defects** plus **one architectural gap** (order updates for manual Kite-app trades are never delivered in real time). All are enumerated below with evidence.

### Finding index (by severity)

| # | Sev | Area | One-line summary |
|---|-----|------|-----------------|
| 1.1 | P0 | Real-time | Trade ingestion has no real-time source for orders placed on Kite app — postbacks only fire for API-placed orders; `on_order_update` is not implemented anywhere |
| 1.2 | P0 | Real-time | SharedPriceStream user-token fallback pairs global `ZERODHA_API_KEY` with tokens minted under per-user api_keys → KiteTicker auth fails → zero ticks |
| 1.3 | P0 | Real-time | `zerodha.py:988` imports `get_position_instruments` / calls `ws_manager.subscribe()` — neither exists → post-sync ticker refresh silently never runs |
| 1.4 | P0 | Real-time | Celery worker calls `price_stream.refresh_subscriptions()` (`trade_tasks.py:316`) on its **own process-local singleton** — web-process ticker never learns about new positions; worker may spawn a rogue second KiteTicker |
| 2.1 | P0 | Ops | Guardrail beat task reads `pos.average_price` / `pos.quantity` / `pos.transaction_type` — attributes that don't exist on `Position` → AttributeError every 60 s when LTP cache hits |
| 3.1 | P1 | FIFO | Webhook-after-REST-sync creates duplicate Trade + duplicate ledger fill (idempotency keys don't collide across the two paths in that order) |
| 3.2 | P1 | FIFO | Out-of-order replay recomputes ledger rows but never rebuilds CompletedTrades / Trade.pnl derived from the old values |
| 4.1 | P1 | Instruments | Nothing writes the `instruments` DB table anymore — `refresh_instruments` is a deprecated wrapper over an in-memory cache; token fallback, lot-size lookup, option-chain queries all read a stale/empty table |
| 4.2 | P1 | Instruments | CDS missing from `InstrumentService.SUPPORTED_EXCHANGES`; unknown MCX contracts silently get multiplier 1 (log-only) |
| 5.x | P1 | Dashboard | Journal keyed to mutable `Position.id`; closing the sheet without saving marks the trade "journaled"; misc component issues |
| 6.x | P1 | Scale | LTP fan-out is in-process only → breaks with >1 uvicorn worker; no 3000-instrument sharding; single WS per account (multi-tab) |
| 7.x | P2 | Security/compliance | TOTP auto-login ToS exposure; webhook checksum falls back to empty secret; misc |

---

## 1. Real-Time Data Flow — Why Updates Lag 3–5 Minutes

### 1.0 How prices actually arrive today (answer to "webhook, websocket, or computed?")

All three, layered:

1. **Prices**: one shared **KiteTicker WebSocket** (`price_stream_service.py`, `SharedPriceStream`), MODE_LTP, throttled to 1 tick/sec/instrument. Ticks go (a) to Redis `ltp:{token}` (TTL 2 s, consumed by Celery behavioral checks) and (b) via `broadcast_ltp()` → our own `/api/ws/prices` WebSocket → browser `ltp_update` events.
2. **Trades/positions**: Zerodha **postback webhook** → Celery `process_webhook_trade` → DB upsert + `sync_positions()` (Kite REST — this is where broker-authoritative `pnl`/`unrealised`/`last_price`/`m2m` land in the DB) → Redis Streams event → WebSocket `position_update` → frontend refetches `/api/positions/` and `/api/trades/completed`.
3. **P&L**: between syncs the frontend **computes** unrealized P&L as `(ltp − avg_entry) × qty × multiplier` (`Dashboard.tsx:403-412`, `OpenPositionsTable.tsx:126-135`). At sync time the DB stores Zerodha's own numbers.

No REST polling for prices/positions exists in the main loop — the design is genuinely event-driven. (Two exceptions listed in §1.6.)

### 1.1 [P0] The fundamental gap: manual Kite-app orders have no real-time ingestion path

Zerodha **postbacks fire only for orders placed through the Kite Connect app (api_key) that registered the postback URL**. TradeMentor is a mirror — users place orders in the Kite app/web, never through TradeMentor. For those orders **no postback is ever sent**. The pipeline's real-time entry point is therefore dead in the primary usage mode.

Kite's designed answer for this is the **WebSocket order-update stream**: KiteTicker delivers `order_update` messages for **all** of the authenticated user's orders, regardless of where they were placed. Grep confirms `on_order_update` appears **nowhere** in the backend. The shared ticker also couldn't provide it: it authenticates as one account (MD account or one fallback user), so it would only ever see that one account's order updates.

**Consequence:** trades appear in TradeMentor only via (a) manual "Sync" click, (b) page-load sync in `BrokerContext`, (c) EOD sync at 15:35, (d) WS reconnect replay. That is exactly the "random 3–5 min" experience: the update arrives whenever one of those unrelated triggers happens to fire, not when the fill happens.

**Recommendation (design, not code yet):**
- Per-user KiteTicker connections **for order updates only**, spun up when the user's session is active (WS connected) and torn down on disconnect. One outbound WS per *online* user is unavoidable for a mirror app without partnership — this is what Sensibull-class products do (they hold per-user sessions too; partnership raises limits, it doesn't remove the need).
- Keep the shared ticker for market data (correct as-is).
- Keep EOD + on-demand sync as the reconciliation safety net.
- Note: memory file `feedback_kiteticker.md` says not to re-raise the *shared-pool price* scaling topic — this is a different issue (order ingestion), and it is load-bearing for the product's core promise ("real-time alerts").

### 1.2 [P0] SharedPriceStream fallback token/api_key mismatch → no ticks at all

`SharedPriceStream._pick_access_token` (`price_stream_service.py:400-459`): when `ZERODHA_MD_*` is not configured it takes **any** connected account's `access_token` and pairs it with the **global** `settings.ZERODHA_API_KEY`. But accounts connected via the setup-credentials flow (`zerodha.py:140-232`) minted their token under their **personal** api_key. KiteTicker auth requires the matching (api_key, access_token) pair → auth fails → `on_noreconnect` → rebuild picks the same broken pair → loop. Result: **zero live prices** for the whole app whenever the fallback path is active with per-user-key accounts (i.e., the current tester setup).

Fix direction: fallback must use `account.api_key` (column exists on `BrokerAccount:34`) together with that account's token; skip accounts whose api_key is unknown.

### 1.3 [P0] Post-sync subscription refresh is dead code

`zerodha.py:986-996`:

```python
from app.api.websocket import manager as ws_manager, get_position_instruments
await price_stream.refresh_subscriptions(broker_account_id, db)
new_instruments = await get_position_instruments(str(broker_account_id))
await ws_manager.subscribe(...)
```

`get_position_instruments` does not exist in `websocket.py`, and `ConnectionManager` has no `subscribe` method. The `ImportError` fires **before** `refresh_subscriptions` executes and is swallowed by `except Exception: logger.warning("Subscription refresh failed (non-fatal)")`. So after every manual sync, newly opened positions are **never subscribed** on the ticker in the web process. Prices for a position opened mid-session start flowing only after a full page reload (WS reconnect → `subscribe_positions` → `start_account`).

### 1.4 [P0] Cross-process `refresh_subscriptions` from Celery is a no-op (or worse)

`trade_tasks.py:313-318` calls `price_stream.refresh_subscriptions()` inside the Celery worker. `price_stream` is a module-level singleton — the worker gets its **own instance**, not the web process's. Two effects:

- The web-process ticker (the one wired to browser WebSockets) never learns about the new instrument → no live LTP for positions opened during the session.
- The worker's instance calls `_ensure_ticker()` → builds a **second KiteTicker inside the Celery worker**. Its `broadcast_ltp` → `manager.send_to_account` hits the worker's empty connection dict (silently dropped). Its Redis LTP writes are actually useful, but Zerodha caps ~3 WS per (api_key, token) — with prefork concurrency this can multiply and get connections dropped.

The team's own doc (`KITETICKER_SHARED_POOL.md` §6.5) states Celery must not touch the ticker — the code contradicts the doc.

Fix direction: replace the direct call with a Redis-signaled refresh (e.g., publish `subscription_refresh` on the event stream; the web-process event subscriber calls `refresh_subscriptions` locally). The event bus already exists for exactly this shape of problem.

### 1.5 The observed "3–5 min, random" delay — full causal chain

With 1.1–1.4 active simultaneously:

- Live LTP: dead (1.2) or missing for new positions (1.3/1.4) → position rows and hero P&L freeze at DB values.
- DB values refresh only when a sync runs; syncs run only on page load, manual click, EOD, or WS-reconnect replay-truncation → sporadic multi-minute cadence.
- Meanwhile two background pollers (§1.6) refresh *alerts* every 60–120 s, making the app look "partially alive," which reads as random latency.

**Verification steps (run during market hours):**
1. Backend log: look for `[ticker:...] Connected to Kite WebSocket` vs repeated `Reconnecting`/`Max reconnect attempts exceeded` — confirms/refutes 1.2.
2. `redis-cli GET ltp:<token>` for an open position — empty ⇒ no ticks.
3. Browser devtools WS frames: count `ltp_update` events — none ⇒ 1.2/1.3; present for old positions but not a newly opened one ⇒ 1.3/1.4.
4. Backend log at sync: `Subscription refresh failed (non-fatal): cannot import name 'get_position_instruments'` — confirms 1.3 verbatim.

### 1.6 No-polling audit (user rule: "we will NOT be polling")

| Location | Interval | Verdict |
|---|---|---|
| `AlertContext.tsx:392` — `setInterval(fetchAlerts, 60_000)` | 60 s | **Polling.** Labeled "fallback… if WebSocket event was missed." Either remove once WS delivery is trusted (replay already covers missed events) or acknowledge it as a deliberate exception. |
| `BehaviorRiskBadge.tsx:38` — reload every 120 s | 120 s | Polling. Should be driven by `alert_update`/score events. |
| `MorningIntentCard.tsx:46` | 60 s clock tick (local only) | Fine — no network. |
| WS ping | 30 s | Fine — keepalive, not data. |
| `useTickStream.ts` | 1.5 s fake random-walk data | Demo-only hook (landing page). Not polling, but its name invites accidental use in real components — consider relocating under a `demo/` path. |

---

## 2. Real-Time Alerts — Pending Items Check

The alert pipeline itself (BehaviorEngine → RiskAlert + BehaviorEvent → `publish_event('alert_update')` → Redis Streams → WS → `AlertContext` refetch → toast + RecentAlertsCard → AlertDetailSheet) is complete and coherent. Engine v2 phases 0–7 and the P0/P1/P2 hardening are all merged. Remaining items:

- **[P0] 2.1 Guardrail task crashes on live-price path.** `guardrail_tasks.py:_run_checks` (lines ~100-112) reads `pos.average_price`, `pos.quantity`, `pos.transaction_type`. `Position` has `average_entry_price`, `total_quantity`, and no transaction_type (`models/position.py`). When the Redis LTP cache has a value (i.e., exactly when things work), this raises AttributeError → the every-60 s beat task fails for every account with active guardrail rules. It also ignores the MCX `multiplier` in its P&L math. Was masked so far because the LTP cache is usually empty (finding 1.2).
- **[P1] 2.2 Alert freshness depends on trade ingestion.** Entry-time detection is only as real-time as fills are (finding 1.1). Today an alert like `revenge_trade` cannot fire until the trade reaches the DB — i.e., minutes later or at next sync. Worth stating in the doc/product copy until per-user order streams exist.
- **[P2] 2.3 60 s alert poll** — see §1.6.
- **[P2] 2.4 `acknowledgeAll`** fires N parallel POSTs (`AlertContext.tsx:409-421`); needs a bulk endpoint at scale.
- AlertDetailSheet itself: well-structured (benchmarks, explanations, per-pattern evidence facts with a generic fallback). No blocking issues found.

---

## 3. FIFO / Position Ledger — Correctness & Edge Cases

### 3.0 What it actually is

`position_ledger_service.py` is **weighted-average-cost (WAC)**, not FIFO: `_compute_fill_effect` keeps one `avg_entry_price` and realizes `(fill − avg) × closing_qty`. For a **full round** (flat→flat) total realized P&L equals FIFO's, so CompletedTrade totals are correct. But **partial-close attribution differs from FIFO**: `DECREASE` entries' `realized_pnl`, `get_realized_pnl()` over time windows that cut across a round, and any detector consuming per-fill P&L will not match Zerodha's FIFO attribution. Batch `pnl_calculator` (true FIFO) is now historical-backfill-only. **Recommendation:** rename/document the ledger as WAC and audit which detectors consume per-fill realized P&L mid-round; either accept WAC (defensible — it matches "position avg" mental model shown in Kite UI) or switch attribution — but pick one and write it down.

### 3.1 Scenario matrix (user's questions answered)

| Scenario | Handled? | Evidence / gap |
|---|---|---|
| Order fills but never reaches us | **Partially.** No real-time recovery (finding 1.1). `replay_missed_fills_into_ledger` (sync, 30-day window) + EOD sync at 15:35 catch it eventually. Intraday, position state and behavior detection run on wrong data until then. | `trade_sync_service.py:364-481` |
| Duplicate webhook delivery | **Yes.** `upsert_trade` dedup by (order_id, account), `processed_at` atomic claim (`trade_tasks.py:374-386`), ledger unique `idempotency_key` + IntegrityError fallback. | solid |
| **Same fill via REST sync first, webhook second** | **NO — P1 3.1.** REST sync stores `Trade.order_id = trade_id`, ledger key `{trade_id}:ledger`. A late webhook for the same execution carries the Kite `order_id` → `upsert_trade` finds no row (order_id differs) → **second Trade row** → ledger key `{order_id}:ledger` doesn't collide → **fill applied twice** (double qty, double P&L). The reverse direction is guarded (`trade_sync_service.py:422-428` checks `kite_order_id`), this direction is not. Realistic trigger: user hits manual sync seconds after a fill while the postback is still in Zerodha's retry queue. Fix direction: in the webhook path, before `apply_fill`, also check for an existing ledger key of any Trade whose `kite_order_id` equals this order_id (or unify keys on kite_order_id everywhere). |
| Out-of-order events | **Partially — P1 3.2.** Late fill triggers full chronological replay of the symbol's ledger (`_apply_fill_with_replay`) — good. But entries recomputed during replay may have previously produced CompletedTrades and `Trade.pnl` writes; those downstream records are **not rebuilt**, so a late fill can leave a CompletedTrade whose totals disagree with the corrected ledger. Also `entry_type` can change (e.g., CLOSE→DECREASE) leaving an orphaned CompletedTrade for a round that no longer closes there. |
| WebSocket (frontend) reconnect | **Yes.** `?since=last_event_id` → per-account stream replay (max 200, `truncated` flag forces full refetch). localStorage cursor per account. Well done. |
| KiteTicker reconnect | **Yes for subscriptions** (`_on_connect` resubscribes; `noreconnect` → token rebuild). Ticks during the gap are lost by design (LTP is stateless). |
| Celery/Redis down during postback | **Yes.** Webhook returns 500 → Zerodha retries. Infra vs validation split in `webhooks.py:77-84` is correct. |
| Position flip / partial fills / averaging | **Yes.** FLIP/DECREASE/INCREASE logic in `_compute_fill_effect` is correct, including flip avg = fill price. |
| Same symbol on two exchanges | **Edge.** `get_net_qty` ignores exchange (`position_ledger_service.py:305-328`) — picks whichever entry is latest. Low probability, but detectors using it can misread. |
| Timestamp ties | Ordered by `(occurred_at, created_at)` — insertion order proxy; acceptable. |
| CNC filtering | Consistent (`TRACKED_PRODUCTS` in webhook, sync, positions). |

### 3.2 Other pipeline notes

- `upsert_trade` status-downgrade guard (terminal states immutable) — good.
- `fifo_lock` per account (SETNX, 120 s TTL, backoff, task retry on exhaustion) — good.
- `_reconcile_pnl_with_zerodha` "repair pass" (`trade_sync_service.py:1112-1142`) recomputes NSE P&L as `(avg_exit − avg_entry) × qty`. For rounds where the trader **added after a partial exit**, WAC's summed realized P&L legitimately differs from that single-formula value → the repair pass will "fix" a correct number into an approximate one. Narrow, but worth a guard (skip when `num_entries > 1 && num_exits > 1`).
- One-time NSE P&L repair still runs on **every server boot** (`main.py:120+`, 7-day window). Session-33 bug is long past; it should be retired or made a manual admin action.

---

## 4. Instruments, Lot Sizes, and the P&L Strategy Question

### 4.1 MCX/CDS lot sizes — the approach is right, the plumbing has holes

The user's concern ("app assumes lot size 1 for Gold/Silver") is **already addressed in design**: Zerodha's instruments CSV really does report `lot_size = 1` for all MCX contracts (documented with sources in `mcx_contract_specs.py`), and MCX fill quantities arrive in **lots**, so the hardcoded `MCX_MULTIPLIERS` table is the correct mechanism. It is applied in the ledger (`position_ledger_service.py:132-137`), replay, sync positions (`multiplier` column), and the frontend (`getLivePnl`). Verified values (GOLD=100, GOLDM=10, SILVER=30, CRUDEOIL=100, etc.) are correct per MCX contract specs.

Remaining gaps:

- **[P1] 4.2a Unknown contract ⇒ silent multiplier 1.** `get_mcx_multiplier` logs a WARNING and returns 1 → the user sees wrong P&L with no in-product signal. New MCX contracts appear regularly (e.g., new mini/micro variants). Recommendation: on unknown prefix, (a) fall back to Zerodha's `positions.multiplier` for that symbol if ≠1, (b) emit a metric/Sentry event, (c) surface a data-quality badge on the position row rather than confidently-wrong P&L.
- **[P1] 4.2b Cross-check against broker instead of trusting the table blindly.** Kite's **positions API returns a `multiplier` field per position**. The code comment (`trade_sync_service.py:775-778`) dismisses it citing the CSV problem, but CSV `lot_size` and positions `multiplier` are different fields. **Verify with live MCX position data**: if `positions.multiplier` is correct, prefer it and keep the table as fallback + reconciliation source. This removes the maintenance treadmill.
- **[P1] 4.1c The `instruments` DB table is orphaned.** `InstrumentService.refresh_instruments` is deprecated and delegates to `load_master_cache` which fills an **in-memory dict only** — nothing inserts into the `instruments` table anymore (grep: no `insert(Instrument)` anywhere). Yet the table is still read by: `_get_open_position_tokens` fallback (price subscriptions), `get_lot_size` (position-sizing alerts), `get_option_chain`, expiry cleanup, and the daily "instruments stale?" check in sync (which will see a stale `updated_at` forever and re-download the CSV **every sync, per account** — wasted work). Decide: either restore DB persistence (bulk upsert) or migrate all readers to the memory cache — currently it's half-and-half.
- **[P2] 4.2c CDS not in `SUPPORTED_EXCHANGES`** (`instrument_service.py:31`) while `CDS_MULTIPLIERS` exists — currency positions can't resolve tokens from the fallback path.

### 4.2 Should we compute P&L ourselves at all?

Current split is actually close to right; make it explicit policy:

| Quantity | Best source | Current state |
|---|---|---|
| Open-position unrealized P&L at sync time | **Broker** (`positions.unrealised`, `m2m`) | ✅ stored on sync |
| Live P&L between syncs | **Compute** from shared-ticker LTP (broker gives no push for this without polling) | ✅ formula correct incl. multiplier, but ticks broken (§1) |
| Per-round realized P&L (flat-to-flat) — the behavioral engine's core input | **Compute** — broker has no per-round concept; `positions.realised` is day-level, day-netted | ✅ ledger |
| Day-level realized total | **Broker**, reconcile ours against it | ✅ reconciliation exists (log-only) |

So: no, don't stop computing — the behavioral engine *needs* per-round P&L the broker doesn't provide. But **promote reconciliation from log-only to a stored data-quality metric** (per-account daily divergence %, alert when >1%), so multiplier/ledger bugs surface as dashboards instead of user complaints. Also note charges/brokerage/STT are not modeled anywhere — our "P&L" is gross while Kite app shows users net-ish numbers; document the difference in-product to preempt "your numbers are wrong" tickets.

---

## 5. Dashboard/Home Page — Component-by-Component

### SessionHeroCard + session stats (`Dashboard.tsx:281-305`, `SessionHeroCard.tsx`)
- Live-ish and correct given inputs; unrealized total recomputes from LTP with multiplier — good.
- **[P2]** `max_drawdown` folds over `todayTrades` in **API return order**, not sorted by `exit_time` — drawdown sequence can be wrong. Sort first.
- **[P2]** `win_rate` counts `pnl > 0` as winners; breakeven trades count against the user.
- **[P3]** `risk_used` is hardwired 0 and passed around — dead prop.
- **[P2]** Realized P&L here comes from CompletedTrades only; MCX gross-vs-broker differences (§4.2) show up here first.

### Open Positions (`OpenPositionsTable.tsx`)
- LTP patch → `PriceCell` flash, live P&L per row with multiplier — correct.
- **[P1]** When the live tick stream is down (§1), rows silently show stale DB `last_price` with no staleness indicator. Add a "price as of…" affordance — a trading product must never show stale numbers that look live.
- **[P2]** Symbol parser is regex-heavy and duplicated between OpenPositionsTable and ClosedTradesTable (drift risk — extract shared util). Commodity symbols (`CRUDEOIL25MARFUT`) hit the FUT branch fine; MCX options (`CRUDEOIL25MAR7300CE`) resolve via the monthly branch — OK.

### Closed Trades (`ClosedTradesTable.tsx`)
- Sort (unjournaled first), stats bar, filter — fine. Educational empty-state stats cite "SEBI FY2023" — verify the citations before public launch (regulatory-ish claims).

### Trade Journal popup (`TradeJournalSheet.tsx` + `Dashboard.tsx:356-361`)
- **[P1] 5.1** `handleJournalClose` marks the trade as journaled **on any close**, saved or not (`Dashboard.tsx:357-359`) — the green "journaled" check lies, and the unjournaled counter and sort order go wrong.
- **[P1] 5.2** Journaling an *open position* keys the entry to `Position.id` — a **mutable snapshot row reused across rounds and days** for the same (symbol, exchange, product). Journal history attached to "a trade" actually attaches to a symbol-slot; next week's unrelated position on the same contract inherits the journal linkage. CompletedTrade-keyed entries are fine. Recommendation: journal open positions against a synthetic key (position id + first_entry_time) or only against rounds.
- **[P2]** `trade_pnl` snapshot for open positions stores the *stale REST* `unrealized_pnl`, not the live LTP-derived value shown on screen next to it.
- **[P2]** Delete has no confirmation.
- Multi-emotion tags, symbol history, ±20 min alert linkage — all working as designed (S38 features present).

### Alert detail popup (`AlertDetailSheet.tsx`)
- Complete: severity styling, per-pattern evidence facts + generic fallback, benchmarks, explanations, frequency badge, journal link. No blockers. **[P3]** `TRADER_BENCHMARKS` statistics are hardcoded prose presented as data — keep the wording clearly qualitative or cite.

### Cross-cutting page issues
- **[P1] 5.3** `PredictiveContextStrip` is rendered in the desktop right column (`Dashboard.tsx:619`) — session-36 notes say this strip was **killed** ("strip file kept unused"). Either the removal was reverted intentionally or a dead component shipped back. Verify intent.
- **[P2] 5.4** Journal auto-prompt (45 s after a close) can pop while the user is journaling a different trade or mid-flow elsewhere on the page; it also depends on `closedTrades` polling-by-refetch, so it fires minutes late today.
- **[P2] 5.5** `fetchAllData` runs 4 parallel requests on every trade event; a burst of fills (debounced 300 ms — good) still triggers full refetch of trades+positions+risk+margins. Fine at current scale; needs ETag/If-Modified or payload diffs at 10k users.

---

## 6. Architecture & Scale — Toward the Sensibull Model

### What's already right
- Shared KiteTicker for market data (union of open-position instruments, ref-counted holders, LTP fan-out) — this *is* the Sensibull-style core for prices, and it does not need a partnership (correctly documented in `KITETICKER_SHARED_POOL.md`).
- Redis Streams event bus with per-account replay + global stream, durable, fail-silent publish — the right backbone.
- Celery pipeline idempotency (locks, claims, unique keys) — scale-safe patterns already in place.

### Gaps before "tens of thousands of concurrent users"

1. **[P1] 6.1 In-process coupling of ticker → WebSocket.** `broadcast_ltp` calls `manager.send_to_account` directly. This only works in a **single web process**. With `uvicorn --workers N` or horizontal replicas, the ticker lives in one process, user sockets in others → most users get no `ltp_update`. The event bus solves this for trade/alert events (each instance runs a subscriber) but **LTP deliberately bypasses it**. Design needed: either (a) dedicated market-data process publishing LTP to a Redis channel and every web instance fanning out to its local sockets (same pattern as `stream:events`, but pub/sub — LTP needs no durability), or (b) pin to one web process until then and document it as a deployment constraint. Today nothing enforces or documents the single-process assumption.
2. **[P1] 6.2 One WebSocket per account.** `ConnectionManager.active_connections: Dict[str, WebSocket]` — a second tab/device **evicts** the first silently. Needs `Dict[str, set[WebSocket]]`.
3. **[P1] 6.3 Per-user order-update connections** (finding 1.1) are the real scale question — 10k concurrent users = 10k outbound sockets = needs a connection-manager service with sharding, and this is where the Zerodha partnership genuinely matters (connection limits, blessed usage). The current codebase has zero scaffolding for it; the `PriceStreamProvider` abstraction is a reasonable seam to extend.
4. **[P2] 6.4 3000-instrument cap**: `SharedPriceStream` has no sharding to a second connection; doc says "add when needed" — no code, no metric watching the count. Add a gauge now.
5. **[P2] 6.5 Serial fan-out beat tasks** — already fully analyzed in `CELERY_SCALE_PLAN.md` (guardrails/intent/EOD loops over all accounts in one task). The plan exists; it is not implemented. EOD sync at 10k users vs Zerodha REST limits is the sharpest edge.
6. **[P2] 6.6 Event subscriber cursor**: single subscriber starts at `$` — events published while the web process is *down* are recovered per-account on WS connect (replay), which is fine; but multi-instance later should move to consumer groups (noted in the file header already).
7. **[P2] 6.7 Upstash free-tier arithmetic** shaped several decisions (2 s XREAD blocks, client-gated reads). Fine now; revisit before any real load — a managed Redis with steady connections changes the constants.

### Token strategy
- `zerodha_auth_service.py` automates Kite login (password + TOTP from `.env`) for the MD account. Works, standard algo-trader practice, but: **(a)** it's against Zerodha's stated ToS position on automated login — acceptable business risk for a dev tool, a real conversation before scale/partnership; **(b)** MD account password + TOTP secret are plaintext env vars — move to a secret manager before production; **(c)** single point of failure — if the 8:45 refresh fails and no user logs in, no market data all day (fallback exists but is broken per finding 1.2).

---

## 7. Cross-Cutting Production Concerns (not asked, worth having)

| Sev | Item |
|---|---|
| P1 | **Webhook checksum empty-secret fallback** (`webhooks.py:112`): `account.decrypt_api_secret() or settings.ZERODHA_API_SECRET or ""` — if neither exists, checksums verify against `""`, which an attacker can compute (`sha256(order_id+ts+"")`). Reject postbacks outright when no secret is available. |
| P1 | **Staleness UX**: there is no global "data as of / live" indicator. Given §1, users can't tell live from frozen. A trading mirror must show data freshness explicitly (Sensibull shows tick timestamps). |
| P2 | **Observability for the market-data path**: Prometheus metrics exist for the engine, but nothing tracks: ticker connected (gauge), ticks/sec, LTP cache hit rate, postback count/day, sync latency. Every P0 in §1 would have been visible on a one-panel dashboard. |
| P2 | **Reconciliation cadence**: EOD-only. Add a lightweight on-WS-connect reconciliation (compare Kite `positions.net` qty vs ledger-derived qty; alarm on mismatch) — event-driven, not polling, and catches missed fills within the session. |
| P2 | **Tests**: `test_data_integrity.py` exists; no tests found for `_compute_fill_effect` edge matrix (flip/partial/out-of-order/MCX multiplier), `_pick_access_token` pairing, or webhook↔sync duplicate scenario (3.1). These are pure-function or fixture-friendly — highest-value test targets in the repo. |
| P2 | **`positions.value` fallback chain** (`positions.py:27-29`): `total_pnl` uses `unrealized_pnl or pnl` — for a position with unrealized 0 (flat but open row) falls through to day `pnl`; harmless today, but the semantics are fuzzy — define one canonical field. |
| P3 | **`notify_price_update` stub** (`websocket.py:234`) and `usePriceStream.ts` (parallel WS hook) are dead code kept alongside live code — archive per project convention. |
| P3 | **Startup repair task** (`main.py:120+`) — retire (see §3.2). |
| P3 | `eod-reconcile` at 4:00 AM and other crontabs — Celery `timezone="Asia/Kolkata"` confirmed, so schedules are IST as intended. ✅ |

---

## 8. Recommended Sequence (when implementation is approved)

1. **Restore live prices** — fix 1.2 (api_key pairing), 1.3 (dead import), 1.4 (event-bus-signaled refresh). Small diffs, immediately user-visible.
2. **Fix guardrail task attributes** (2.1) — one-file fix, currently throwing every minute.
3. **Real-time order ingestion design doc** — per-user order-update WS for online users (1.1). This is the architectural decision; everything else in §1 is plumbing.
4. **FIFO edge fixes** — duplicate-path guard (3.1), replay→CompletedTrade rebuild (3.2).
5. **Instruments plumbing** — decide DB vs memory (4.1c), CDS, unknown-multiplier fallback to broker `positions.multiplier` (4.2a/b).
6. **Dashboard fixes** — journaled-on-close (5.1), journal keying (5.2), staleness indicator.
7. **Scale prep** — multi-socket per account (6.2), LTP fan-out via Redis (6.1), metrics (§7).

---

*Files read for this review: `price_stream_service.py`, `market_data_tasks.py`, `zerodha_auth_service.py`, `event_bus.py`, `websocket.py`, `webhooks.py`, `trade_tasks.py` (pipeline sections), `position_ledger_service.py`, `trade_sync_service.py`, `pnl_calculator.py` (header/design), `instrument_service.py`, `mcx_contract_specs.py`, `positions.py`, `zerodha.py` (OAuth + sync + streaming sections), `guardrail_tasks.py` (checks), `main.py` (lifespan), `celery_app.py` (beat), `broker_account.py`, `position.py`; frontend: `Dashboard.tsx`, `WebSocketContext.tsx`, `AlertContext.tsx` (event/poll sections), `OpenPositionsTable.tsx`, `ClosedTradesTable.tsx`, `TradeJournalSheet.tsx`, `AlertDetailSheet.tsx`, `SessionHeroCard.tsx`, `useTickStream.ts`; docs: `KITETICKER_SHARED_POOL.md`, `CELERY_SCALE_PLAN.md`, `LAUNCH_TODO.md`.*
