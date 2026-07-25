# P3 — Real-time & Scale (findings)

> Scope (read): `api/webhooks.py`, `tasks/trade_tasks.py` (`process_webhook_trade` + `run_risk_detection_async`
> + eod/retry), task structure across `tasks/*`, `services/price_stream_service.py` (surface),
> `event_bus.py` (P0), `Procfile`. Cross-checked B1–B7 from `SCALABILITY_REVIEW_10K.md`. **Findings-only.**

## Live path as-verified (sound design)
Postback → checksum-verified (per-user secret) → Celery `process_webhook_trade` → **atomic `processed_at` claim** (`UPDATE … WHERE processed_at IS NULL`, rowcount race-free) → **fifo_lock** (Redis SETNX) → `PositionLedgerService.apply_fill` → `build_completed_trade_on_close` → strategy detection → **behavior_lock** → `run_risk_detection_async` (BehaviorEngine → dedup w/ escalation + worsening re-arm → FK-ordered event persist → consolidation → staleness/mute push gates → guardian-vs-merged notify) → inline position checks + portfolio radar. Idempotency, locking, DLQ (Sentry), retry backoff, and the SLO metric (`alert_e2e_lag_ms`) are all present and well-done.

---

## 🔴 P1

### R1 · Procfile runs Celery `--pool=gevent` but tasks are `asyncio.run()` + asyncpg — an unsupported combo · scale/correctness
- **Where:** `backend/Procfile` → `worker: celery … --pool=gevent --concurrency=100`. Tasks use **`asyncio.run(_process())`** (38 sites across `tasks/*`) driving **async SQLAlchemy + asyncpg**. **No `gevent.monkey.patch_all()`** anywhere (grep clean). This also **contradicts** `celery_app.py`'s `worker_concurrency=4` (prefork) config.
- **Why it matters (three compounding problems):**
  1. **asyncpg under gevent is unsupported.** Celery's gevent pool monkey-patches the socket layer at worker boot; **asyncpg requires a real asyncio loop with real sockets** and explicitly does not support gevent. This is a known-broken pairing → intermittent hangs / connection faults under load.
  2. **Event-loop-per-task defeats the async pool.** `asyncio.run()` creates and tears down a **fresh loop per task**; asyncpg connections are loop-bound, so the `pool_size=5+max_overflow=10` engine pool cannot be reused across tasks — effectively no pooling, constant connect/teardown.
  3. **Concurrency 100 vs DB pool 15.** 100 greenlets contending for ≤15 connections → `pool_timeout=30s` waits → task stalls/failures at market-open burst (the exact 10k moment).
- **Status:** prod not deployed yet (owner-confirmed) → **verify at deploy**, but as written this is a **likely-broken 10k blocker**. **Fix:** run asyncio tasks under the **prefork** pool (or `--pool=threads`), size worker concurrency to the DB pool, and scale horizontally (B1). Reconcile Procfile with `celery_app.py`.

### R2 · Confirms E2 — the alert→trade unlink is triggered by `calculate_and_update_pnl` (analytics + import), not only EOD · correctness
`pnl_calculator.calculate_and_update_pnl` (deletes+recreates CompletedTrades in the window) is called from **`api/analytics.py:137`** (analytics recompute) and **`api/account_data.py:316`** (tradebook import) — plus EOD sync. Because batch uses the deterministic `_stable_ct_id`, the id churn is **bounded to the first batch recompute after live detection** (stable→stable is idempotent), but that first recompute still **NULLs** the live alert's `trigger_completed_trade_id` (FK `ON DELETE SET NULL`). Confirms **P2-E2 / P1-M6**; fix once by giving the live builder `_stable_ct_id`.

---

## 🟡 P2

### R3 · Postback endpoint: unauthenticated, unthrottled, DB query before checksum · security/scale
`api/webhooks.py` looks up the `BrokerAccount` (DB SELECT) **before** checksum verification and has **no rate limit**. A flood of forged postbacks (`tag=user_<uuid>`) forces one indexed DB query each before rejection → DoS amplification at scale. **Fix:** cheap pre-checks + per-IP throttle on the postback route; consider verifying the checksum from header before the DB hit where possible.

### R4 · B2 sequential all-account batch loops (confirmed) — and they intersect with P0-F1 · scale
Confirmed sequential per-account loops: `intent_tasks` re-learn (18:15, loops all accounts + per-account LLM in **one** task, one session), `reconciliation_tasks` (`for i, account in …`), `report_tasks` EOD. Weekly summary correctly fans out via `apply_async` (the pattern to copy). **Intersection:** `intent_tasks`/`maintenance_tasks`/`retention_tasks` are also on the **orphaned default queue (P0-F1)** → today they **don't run at all**; fixing the routing will immediately expose the B2 slowness. **Fix routing + fan-out together** (CR1).

### R5 · Blocking sync Redis inside the task's asyncio loop · scale
`process_webhook_trade` uses sync Redis (`_get_redis_client`, `_acquire_lock`, margin `_r.get/set`, chain SETNX) inside the `asyncio.run` loop — each blocks on Upstash RTT per fill. Lower severity than the web-server case (P0-F4) since each task owns its loop, but it compounds R1 and the market-open burst. Prefer async Redis or accept as worker-only.

---

## ⚪ P3
- **R6** `verify_zerodha_checksum` compares with `==` (`checksum == expected`), not `hmac.compare_digest` — timing side-channel on the postback HMAC. Low practical risk; use constant-time compare.
- **R7** Shared ticker **borrows any connected user's access_token** for the whole fleet's market-data feed (`price_stream_service`). Interacts with **P0-F1 #9**: with the `refresh_market_data_token` beat task orphaned and `ZERODHA_MD_*` unset, prod live prices depend on borrowing a user token that **expires 06:00 daily** → `noreconnect` → picks another user's token (churn). Also a Zerodha-ToS/commercial question (one user's token serving all — already in the roadmap) and **no instrument-count cap/shard** (B5) for the subscription union at 10k.

## ✅ Solid (credit)
Race-free `processed_at` idempotency + fifo/behavior Redis locks + DLQ→Sentry + capped retry backoff · per-pattern dedup with severity escalation + stateful worsening re-arm · FK-ordered event persistence · `alert_e2e_lag_ms` SLO metric · worker→FastAPI `subscription_refresh` internal event (correct cross-process ticker refresh) · inline position checks (killed the 3-task fan-out) · staleness + per-pattern-mute push gates · guardian-vs-merged notification (alert-fatigue aware).

## For P14 (QA / load)
- **Load-test the worker pool decision first (R1)** — prove prefork-vs-gevent under market-open burst before anything else; watch pool_timeout + asyncpg errors.
- Assert alert `trigger_completed_trade_id` survives an analytics recompute + import (R2).
- Forged-postback flood test (R3). Batch fan-out timing at 1k/10k after routing fix (R4). MD-token-expiry ticker recovery (R7). Instrument-union cap behaviour (B5).
