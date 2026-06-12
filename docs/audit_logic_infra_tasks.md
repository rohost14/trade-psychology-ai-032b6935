# Infrastructure and Background Tasks Logic Audit

> Audit date: 2026-06-10  
> Scope: Celery tasks, Zerodha integration, core infra, models, WebSocket, config

---

## 1. Celery Task Logic

### 1-A: `process_webhook_trade` — `asyncio.run()` inside Celery worker is problematic at scale
**File**: `backend/app/tasks/trade_tasks.py:410`  
**Status**: MINOR_ISSUE  
**Finding**: Every task function uses `asyncio.run(_inner())`. With `worker_concurrency=100` and `--pool=gevent` (as the config comment suggests), `asyncio.run()` creates a new event loop per call. With the default prefork pool, each forked subprocess has its own loop and this works. But the config comment `use --pool=gevent` combined with `asyncio.run()` is a bug — gevent monkey-patches the stdlib, and `asyncio.run()` does not interoperate cleanly with gevent greenlets. The `asyncioreactor` comment in celery_app.py acknowledges the complexity.  
**Evidence**: `worker_concurrency=100 # ... use --pool=gevent` at `celery_app.py:69`, every task calls `asyncio.run()`.  
**Impact**: If deployed with `--pool=gevent`, tasks silently hang or produce unexpected coroutine errors. With the default prefork pool, 100 workers × 1 subprocess each is very heavy (RAM, DB connections).  
**Fix**: Either use `--pool=threads` (asyncio-compatible, one event loop per thread), or use `--pool=prefork` with a reduced `worker_concurrency` (16–32). Document explicitly which pool flag is required for production.

---

### 1-B: `behavior_lock` TTL too short for full-session replay
**File**: `backend/app/tasks/trade_tasks.py:330`  
**Status**: BUG  
**Finding**: `behavior_lock` is acquired with `ttl_seconds=15`. The lock protects `run_risk_detection_async`, but that function calls `behavior_engine.analyze()` per `CompletedTrade`. With 15+ trades in a session, the BehaviorEngine iterates over them all. If it takes >15s (slow DB, cold connection pool), the TTL expires while the lock is still in use. A second worker then acquires the lock and runs detection concurrently, firing duplicate alerts.  
**Evidence**: `trade_tasks.py:330` — `_acquire_lock(redis_client, behavior_lock_key, ttl_seconds=15)`. `run_risk_detection_async` at line 504 calls `behavior_engine.analyze()` which does multiple DB queries.  
**Impact**: Duplicate alerts saved to DB (dedup window may catch most, but not all within the same DB transaction window), and duplicate WhatsApp/push notifications sent to the user.  
**Fix**: Increase TTL to 60s. The behavior engine should never take >60s even with 50 trades. Keep the existing lock-skip-on-failure logic.

---

### 1-C: `fifo_lock` retry loop uses `await asyncio.sleep()` inside a blocking `asyncio.run()` on a thread pool
**File**: `backend/app/tasks/trade_tasks.py:196–208`  
**Status**: MINOR_ISSUE  
**Finding**: The backoff loop at line 196 does `await _asyncio.sleep(backoff)` with backoffs of 1s, 2s, 4s, 8s (total 15s max wait). This is inside `_process()`, which runs in `asyncio.run()`. This is fine for prefork workers, but means a single webhook event can hold a worker thread/process for up to 15 seconds waiting. Under burst load (100 orders at 09:15 open), 100 workers × up to 15s wait = all workers blocked.  
**Evidence**: `trade_tasks.py:196–208`.  
**Impact**: Under peak load, the `trades` queue fills up and subsequent webhook events are delayed. Orders already executed by the user will take minutes to appear in the dashboard.  
**Fix**: Reduce maximum backoff (e.g., 3 attempts × 1s backoff = max 3s), or drop the in-process backoff entirely and use `self.retry(countdown=5)` instead to release the worker.

---

### 1-D: `process_webhook_trade` — `processed_at` claim race is correct but relies on the same `db` session across two commits
**File**: `backend/app/tasks/trade_tasks.py:165–181`  
**Status**: MINOR_ISSUE  
**Finding**: The atomic `UPDATE ... WHERE processed_at IS NULL` on line 172 is the correct TOCTOU-safe pattern. However, both the `upsert_trade` commit (line 101) and the claim UPDATE use the same long-lived `db` session. Between line 101's commit and line 172's claim, the session is open but idle. Under high concurrency, this long-lived session holds a DB connection from the pool for 15+ seconds (FIFO lock wait). With `pool_size=5, max_overflow=10` (15 total), 16+ concurrent webhooks will exhaust the connection pool and get `pool_timeout=30` errors.  
**Evidence**: Single `async with SessionLocal() as db:` opened at `trade_tasks.py:78`, used until line 345 (end of function). FIFO lock wait up to 15s in between.  
**Impact**: At 09:15 with many simultaneous fills, `pool_timeout` exceptions cause `process_webhook_trade` tasks to fail, triggering 3 retries (each also holding a connection for up to 45s in the worst case).  
**Fix**: Split into two separate `async with SessionLocal()` blocks: one for upsert+claim, one for FIFO+behavior.

---

### 1-E: `run_behavior_engine_full_session` — dedup window uses `now_utc` but last_fired updates use the same `now_utc` for ALL alerts
**File**: `backend/app/tasks/trade_tasks.py:669–710`  
**Status**: BUG  
**Finding**: The full-session replay loops over all `trades_today` in chronological order, running `behavior_engine.analyze()` for each. When a pattern fires, `last_fired[pattern_type] = now_utc` (line 709). `now_utc` is captured **once** before the loop. This means the second trade firing the same pattern within 2h is correctly deduped, BUT the in-loop dedup check uses the same fixed `now_utc` timestamp for all subsequent iterations — if the loop itself takes >2h (impossible in practice, but the design is fragile), or if `now_utc` is used to compare against the `last_fired` from the DB (which uses real timestamps), the logic is inconsistent.  
**More concrete issue**: The dedup state is built from DB at loop start, but new alerts added within the loop update `last_fired[pt] = now_utc` in-memory only. If the process crashes mid-loop and restarts, the DB will have some alerts from the partial run — but the loop restarts from the beginning. The dedup window prevents exact duplicates (same pattern within 24h), but the `consecutive_loss_streak` escalation logic (`if pattern in today_patterns: severity = danger`) fires for EVERY remaining trade in the loop because `today_patterns` is already populated. This means on a restart after crash, every subsequent `consecutive_loss_streak` detection in the loop will be `danger` severity regardless of the actual escalation intent.  
**Evidence**: `trade_tasks.py:695–711`.  
**Impact**: On task retry after crash, consecutive_loss_streak may be incorrectly escalated to `danger` on every re-run, triggering multiple guardian WhatsApp messages.  
**Fix**: After adding an alert to DB and `db.commit()`, re-query `last_fired` from DB to keep in-memory state consistent with persisted state, rather than updating it speculatively in-memory.

---

### 1-F: `eod_sync_all_accounts` — fires `sync_trades_for_account.delay()` without rate-limit awareness
**File**: `backend/app/tasks/trade_tasks.py:897`  
**Status**: MINOR_ISSUE  
**Finding**: `eod_sync_all_accounts` loops through all connected accounts and calls `sync_trades_for_account.delay()` for each. This fires all sync tasks simultaneously at 15:35 IST. The task has a Celery `rate_limit="10/m"`, but that's a per-worker limit, not a global limit. With 100 workers × 10/min = 1000 syncs/min permitted, all syncs can execute simultaneously against Zerodha's API. Zerodha's global rate limit is 10 req/sec across all users sharing the same API key.  
**Evidence**: `celery_app.py:86–88` — rate limit is `10/m` per worker. `trade_tasks.py:897` — fires all accounts at once.  
**Impact**: If 100+ accounts sync at 15:35, the first ~60 succeed, and the remaining get `KiteRateLimitError`. These retry, compounding the burst.  
**Fix**: Add a stagger in the EOD sync loop (similar to the reconciliation task's `await asyncio.sleep(1)` per batch of 10). Or use a Celery countdown: `sync_trades_for_account.apply_async(args=[str(account.id)], countdown=i*0.1)`.

---

### 1-G: `generate_eod_reports` and `retention_tasks.start_scheduler()` will double-send at 16:00 IST
**File**: `backend/app/tasks/report_tasks.py:112`, `backend/app/tasks/retention_tasks.py:131`  
**Status**: BUG  
**Finding**: The Celery beat schedule does NOT include `generate_eod_reports` for equity users (the comment at `celery_app.py:111` says this correctly). But `generate_eod_reports` still exists as a `@celery_app.task`. If it is ever scheduled (manually or by a mistake in a future deploy), it will run in parallel with APScheduler's `dispatch_eod_reports`. For commodity users, however, `generate_commodity_eod` IS in the beat schedule at 23:45, and `_send_commodity_eod_for_account` does NOT filter by commodity segment — it sends to whoever is passed in (the query already filters, so this is fine). But there's a deeper issue: `_send_eod_for_account` skips commodity accounts at line 48–49, while `generate_eod_reports` (Celery) queries ALL connected accounts — if this task were ever executed, it would send to all accounts and the commodity filter is only inside `_send_eod_for_account`. APScheduler's `_dispatch_reports` also queries all accounts without a segment filter. This means a commodity trader can receive an equity EOD report at 16:00 AND a commodity EOD report at 23:45 — two reports with different data.  
**Evidence**: `report_tasks.py:47–49` skips if `goal.primary_segment == "COMMODITY"`, but `retention_tasks.py:60–68` does not filter by segment, sending to all accounts at their configured `eod_report_time`.  
**Impact**: Commodity traders receive equity-format EOD report at their configured time (16:00 by default), even though their session ends at 23:30. The equity EOD report will show incomplete session data.  
**Fix**: In `retention_tasks._dispatch_reports("eod")`, check the user's `goal.primary_segment` and skip commodity accounts (send them only at the commodity EOD time).

---

### 1-H: `send_weekly_summary` — hardcoded "Consistent execution" / "Position sizing" as strengths/weaknesses
**File**: `backend/app/tasks/report_tasks.py:265–268`  
**Status**: ~~MINOR_ISSUE~~ **RESOLVED**  
**Finding**: ~~`send_weekly_summary` passes hardcoded constants.~~  
**Resolution**: Fixed in session 34. `report_tasks.py` now fetches the week's `RiskAlert` records, derives `key_weakness` from the most frequent `pattern_type` via `Counter`, and `key_strength` from the first common pattern that did NOT fire. Verified 2026-06-12.

---

### 1-I: `generate_commodity_weekly_report` — imports `re` inside a tight loop
**File**: `backend/app/tasks/report_tasks.py:401`  
**Status**: MINOR_ISSUE  
**Finding**: `import re as _re` is inside the `for t in trades:` loop (line 401). Python caches module imports, so this doesn't cause actual re-loading, but it's unnecessary overhead in a tight loop and is a code smell. Python's import machinery is a dict lookup after the first import, but this pattern is confusing.  
**Evidence**: `report_tasks.py:401`.  
**Impact**: Negligible performance impact; primarily a code quality issue.  
**Fix**: Move `import re as _re` to the top of the `_generate()` coroutine.

---

### 1-J: APScheduler (`retention_tasks.py`) runs inside every FastAPI worker process
**File**: `backend/app/tasks/retention_tasks.py:28`, `127–147`  
**Status**: ~~BUG~~ **NOT APPLICABLE**  
**Finding**: `start_scheduler()` is defined but **never called** from `main.py` or anywhere in the lifespan. The `AsyncIOScheduler` object is instantiated as a module-level singleton but never started. All report scheduling is handled by Celery Beat (`dispatch_reports_tick` every 60s with `redbeat` for single-instance guarantee). APScheduler is dead code. Verified 2026-06-12 by grepping all call sites of `start_scheduler`.

---

### 1-K: `_dispatch_reports` uses `async for db in get_db()` — non-standard generator usage
**File**: `backend/app/tasks/retention_tasks.py:47`  
**Status**: MINOR_ISSUE  
**Finding**: `get_db()` is an `async generator` dependency for FastAPI's `Depends()`. Using `async for db in get_db()` in a non-request context technically works (yields exactly once then cleans up), but is an unconventional pattern. More critically, the same `db` session is shared across all accounts in the loop (lines 60–92). This means if one account's `send_eod_report` raises an exception that is caught at line 91–92, the session may be in an indeterminate state for subsequent accounts, because `get_db()` only rolls back on unhandled exceptions (line 48–49 in database.py).  
**Evidence**: `retention_tasks.py:47`, `database.py:45–52`.  
**Impact**: If an exception occurs mid-loop and the session is partially dirty, subsequent account DB operations in the same loop iteration may fail or commit unexpected state.  
**Fix**: Open a fresh `async with SessionLocal() as db:` per account, similar to the pattern used in `report_tasks.py`.

---

## 2. Zerodha Integration

### 2-A: Global `ZerodhaClient` rate limiter is process-shared but not worker-shared
**File**: `backend/app/services/zerodha_service.py:77`  
**Status**: BUG  
**Finding**: `_rate_limiter = RateLimiter(calls_per_second=3.0)` is a module-level singleton. The `RateLimiter` uses `asyncio.Lock()` and `self.last_call_time`. This is process-local. With 100 Celery prefork workers (100 processes), each process has its own `_rate_limiter` instance, allowing up to 100 × 3 = 300 API calls/second to Zerodha — 100× over the stated 3/sec limit. During the 09:15 open rush, this will trigger Zerodha's rate limiter (`KiteRateLimitError`).  
**Evidence**: `zerodha_service.py:77` — `_rate_limiter = RateLimiter(calls_per_second=3.0)`. No Redis-backed rate limiting.  
**Impact**: Mass `KiteRateLimitError` at peak, all sync tasks retry simultaneously, compounding the burst. Zerodha may temporarily block the API key.  
**Fix**: Replace in-process `RateLimiter` with Redis-based rate limiting (e.g., using a sliding-window ZADD pattern, shared across all worker processes). The existing `rate_limit.py` pattern (Redis ZADD) is correct; apply the same to `zerodha_service.py`.

---

### 2-B: `_sync_locks` — does not exist in `zerodha_service.py`; investigation shows this was removed
**File**: `backend/app/services/zerodha_service.py`  
**Status**: CORRECT  
**Finding**: The audit brief mentioned checking `_sync_locks` for unbounded growth. This dict does not appear in the current codebase — it has been replaced by Redis SETNX locks in `trade_tasks.py`. No memory leak risk from this pattern.  
**Evidence**: Grep of `zerodha_service.py` shows no `_sync_locks` dict.  
**Impact**: None — correct design.

---

### 2-C: `get_instruments()` bypasses the `_request()` circuit breaker and rate limiter
**File**: `backend/app/services/zerodha_service.py:452–468`  
**Status**: MINOR_ISSUE  
**Finding**: `get_instruments()` opens a direct `httpx.AsyncClient()` instead of using `self._request()`. It calls `self.rate_limiter.acquire()` manually, but the circuit breaker check (which requires `broker_account_id`) is not applied, and a new `httpx.AsyncClient` is created per call (no connection reuse from the singleton `_client`). The instruments CSV is ~10MB; creating a new client per call wastes TCP connection setup time and ignores circuit breaker state.  
**Evidence**: `zerodha_service.py:452–468`.  
**Impact**: If Kite's instruments endpoint is down (circuit should be open), calls to `get_instruments` still proceed and generate `httpx.TimeoutException` errors. Each call creates and destroys an HTTP connection.  
**Fix**: Refactor to use `self._client` (the persistent singleton client) and add circuit breaker support when `broker_account_id` is available.

---

### 2-D: `exchange_token()` creates a new `httpx.AsyncClient()` without connection reuse
**File**: `backend/app/services/zerodha_service.py:261`  
**Status**: MINOR_ISSUE  
**Finding**: OAuth token exchange uses `async with httpx.AsyncClient() as client:` — creates a new client per call. This is fine for a one-time OAuth flow, but it also manually calls `await self.rate_limiter.acquire()` (line 259) without going through `self._request()`, so circuit breaker tracking is skipped.  
**Evidence**: `zerodha_service.py:259–279`.  
**Impact**: Minor — token exchange is low-frequency. No circuit breaker tracking means OAuth failures don't contribute to circuit open threshold.  
**Fix**: Low priority. Consider routing through `self._request()` for consistency.

---

### 2-E: `validate_token()` — on network error, returns `True` (treats unknown = valid)
**File**: `backend/app/services/zerodha_service.py:548–560`  
**Status**: MINOR_ISSUE  
**Finding**: `validate_token()` catches general `Exception` at line 558 and returns `True` (assume valid). This is intentional ("don't assume token is invalid on network error"), but it means if Redis/DB is down and reconciliation cannot validate tokens, it proceeds with potentially invalid tokens. The consequence is an attempted API call with an invalid token that then raises `KiteTokenExpiredError`, which is handled downstream — so this is not a blocking issue, just a design note.  
**Evidence**: `zerodha_service.py:558–560`.  
**Impact**: Minimal — callers handle `KiteTokenExpiredError` correctly.

---

### 2-F: `validate_postback_checksum()` uses global `api_secret` — breaks per-user API keys
**File**: `backend/app/services/zerodha_service.py:562–575`  
**Status**: ~~BUG~~ **RESOLVED**  
**Finding**: ~~Webhook endpoint uses global zerodha_client.validate_postback_checksum() instead of per-user secret.~~  
**Resolution**: Fixed in session 34. `webhooks.py` line 110 uses `account.decrypt_api_secret() or settings.ZERODHA_API_SECRET` — per-user secret first, global fallback. Both `verify_zerodha_checksum` (body) and `verify_zerodha_checksum_header` (header) paths use the per-user key. Verified 2026-06-12.

---

## 3. Data Integrity

### 3-A: `Trade` model — `order_id` has an index but the unique constraint is on `(broker_account_id, order_id)`
**File**: `backend/app/models/trade.py:16, 76–78`  
**Status**: CORRECT  
**Finding**: `order_id` has a standalone index (line 16) AND a composite unique constraint `uq_trades_broker_order`. The standalone index is redundant because the composite unique constraint will create a btree index on `(broker_account_id, order_id)`, which can service `WHERE order_id = ?` queries only if the planner uses an index scan. For queries filtering by `order_id` only (without `broker_account_id`), the standalone index is actually useful. This is correct design for multi-tenant data.  
**Impact**: No issue.

---

### 3-B: `Trade` model — `asset_class`, `instrument_type`, `product_type` are NOT NULL but have no default
**File**: `backend/app/models/trade.py:53–55`  
**Status**: BUG  
**Finding**: `asset_class`, `instrument_type`, and `product_type` are mapped as `Mapped[str]` (implicitly NOT NULL) with no `default=` or `nullable=True`. They're populated from `classify_trade()` in the webhook path. However, in the REST sync path (`TradeSyncService.sync_trades_for_broker_account`), if classification fails or is not applied before upsert, PostgreSQL will raise `NOT NULL constraint violation` and the entire batch sync will fail.  
**Evidence**: `trade.py:53–55`. The fields have no `default` values.  
**Impact**: If `classify_trade()` raises or returns incomplete data in a bulk sync, that trade is not saved and no error is surfaced to the user (the sync looks successful but the trade is missing).  
**Fix**: Add `default=""` or `nullable=True` to these columns, or ensure `TradeSyncService.transform_zerodha_order()` always populates these fields with safe fallback values.

---

### 3-C: `CompletedTrade` — no unique constraint on `(broker_account_id, tradingsymbol, entry_time, exit_time)`
**File**: `backend/app/models/completed_trade.py:19–20`  
**Status**: MINOR_ISSUE  
**Finding**: `CompletedTrade` has no unique constraint. The only protection against duplicate records is the `PositionLedger.idempotency_key` (unique on the ledger itself). If `build_completed_trade_on_close()` is called twice for the same ledger entry (e.g., a bug in the ledger service, or a very specific race where the FIFO lock expires mid-build and another worker also calls `build_completed_trade_on_close`), a duplicate `CompletedTrade` will be created. The behavior engine will then analyze the same trade twice, potentially doubling pattern detection.  
**Evidence**: `completed_trade.py:19–20` — only `idx_completed_trades_broker_exit` index, no unique constraint.  
**Impact**: Duplicate completed trades cause duplicate behavioral alerts; the dedup window may catch most but the 5-minute bucket check (by `pattern_type`) will not catch duplicates within the same `behavior_engine.analyze()` call.  
**Fix**: Add a unique constraint on `(broker_account_id, tradingsymbol, entry_time)` or use the ledger entry ID as a unique reference field on `CompletedTrade`.

---

### 3-D: `Position` model — no unique constraint on `(broker_account_id, tradingsymbol, product)`
**File**: `backend/app/models/position.py:12`  
**Status**: ~~BUG~~ **RESOLVED**  
**Finding**: ~~No unique constraint on positions table.~~  
**Resolution**: `UniqueConstraint('broker_account_id', 'tradingsymbol', 'exchange', 'product', name='uq_position_account_symbol_exchange_product')` exists in `position.py`. Verified 2026-06-12.

---

### 3-E: `RiskAlert.related_trade_ids` uses `ARRAY(UUID(as_uuid=True))` — PostgreSQL type mismatch
**File**: `backend/app/models/risk_alert.py:25`  
**Status**: BUG  
**Finding**: `related_trade_ids = Column(ARRAY(UUID(as_uuid=True)))`. In PostgreSQL, the column type will be `uuid[]`. However, `Trade.order_id` is a `String` (not a UUID), and many parts of the codebase use `order_id` (string) as the trade identifier. If `related_trade_ids` is intended to store `Trade.id` (UUID primary keys), the type is correct. But if anywhere in the code a `trade.order_id` (string) is stored in this array, the insert will fail with a type error. In Session 33 notes, the root cause of silent empty alerts was `UUID4` vs `UUID` in the schema. This is a related concern — the array element type should be verified against what the behavior engine actually stores.  
**Evidence**: `risk_alert.py:25`. `Trade.order_id` at `trade.py:16` is `String`.  
**Impact**: If the behavior engine stores `order_id` strings in `related_trade_ids`, every behavior engine `db.add(alert)` will fail with a PostgreSQL type error, silently dropping all behavioral alerts.  
**Fix**: Audit the behavior engine to confirm what is stored in `related_trade_ids`. If order IDs (strings) are stored, change the column type to `ARRAY(String)`.

---

### 3-F: `TradingSession` — no unique constraint on `(broker_account_id, session_date)`
**File**: `backend/app/models/trading_session.py:25–31`  
**Status**: BUG  
**Finding**: `TradingSession` has a `CheckConstraint` on `session_state` but no unique constraint on `(broker_account_id, session_date)`. If two concurrent processes both call `TradingSessionService` to get-or-create a session for today, both may read `None` and both insert a new row. The `_apply_alert_consolidation` function queries by `(broker_account_id, session_date)` and uses `scalar_one_or_none()` — if there are two sessions for today, `scalar_one_or_none()` will raise `MultipleResultsFound`, crashing alert consolidation and losing all new alerts.  
**Evidence**: `trading_session.py:25–31`. `trade_tasks.py:762–769` — `scalar_one_or_none()`.  
**Impact**: On the first day a new account has concurrent trades (common at 09:15), alert consolidation crashes. All behavioral alerts are saved to DB but no notifications are sent.  
**Fix**: Add `UniqueConstraint('broker_account_id', 'session_date', name='uq_trading_sessions_account_date')`. Use PostgreSQL's `INSERT ... ON CONFLICT DO NOTHING` for session creation.

---

### 3-G: `UserProfile.ai_cache` update — lost update race condition
**File**: `backend/app/tasks/report_tasks.py:507–514`, `backend/app/tasks/report_tasks.py:576–581`  
**Status**: BUG  
**Finding**: Both `generate_coach_insight_task` and `generate_analytics_narrative_task` update `UserProfile.ai_cache` using a read-modify-write pattern:
```python
current_cache = dict(profile.ai_cache or {})
current_cache[key] = new_value
profile.ai_cache = current_cache
await db.commit()
```
If two AI tasks run concurrently for the same account (e.g., coach insight and a behavior tab narrative), both read the same `ai_cache`, one overwrites the other's key. The second commit silently drops the first task's result.  
**Evidence**: `report_tasks.py:507–514` and `576–581`.  
**Impact**: AI cache entries are silently lost, causing repeated LLM calls on every dashboard load.  
**Fix**: Use PostgreSQL's `jsonb_set` in a single atomic UPDATE: `UPDATE user_profiles SET ai_cache = jsonb_set(ai_cache, '{key}', value) WHERE id = ?`.

---

### 3-H: `PositionLedger` — `occurred_at` uses `trade.order_timestamp` with fallback to `datetime.now()`
**File**: `backend/app/tasks/trade_tasks.py:231`  
**Status**: MINOR_ISSUE  
**Finding**: `occurred_at=trade.order_timestamp or datetime.now(timezone.utc)`. If `order_timestamp` is `None` (possible for some order types), `occurred_at` defaults to the current time (the time the task ran), not the actual fill time. For behavioral pattern detection (which uses `occurred_at` for time-window calculations), this can cause patterns like `end_of_session_mis_panic` (15:00–15:30 window) to fire at incorrect times or not at all if the task runs after market close.  
**Evidence**: `trade_tasks.py:231`.  
**Impact**: Behavioral patterns with time-window constraints produce incorrect results for orders where `order_timestamp` is missing.  
**Fix**: Also check `trade.fill_timestamp` and `trade.exchange_timestamp` as fallbacks before defaulting to `datetime.now()`. Log a warning when `datetime.now()` is used.

---

## 4. Event Bus and WebSocket

### 4-A: `replay_events_for_account` creates a new async Redis connection per call (no pool)
**File**: `backend/app/core/event_bus.py:143`  
**Status**: MINOR_ISSUE  
**Finding**: `r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)` inside `replay_events_for_account` creates a new Redis connection on every WebSocket connect. With 100 simultaneous reconnects (e.g., after a deploy), this creates 100 Redis connections simultaneously without connection pooling. The global stream subscriber (`start_event_subscriber`) also creates a new connection on every reconnect (line 191).  
**Evidence**: `event_bus.py:143`, `event_bus.py:191`.  
**Impact**: Redis connection count spikes on mass reconnect, potentially exceeding Upstash's connection limit (Upstash free tier: 100 connections).  
**Fix**: Create a module-level async connection pool for the async Redis client, similar to `_sync_pool` for the sync client.

---

### 4-B: `start_event_subscriber` — after reconnect, `last_id` resets to `"$"`, missing events during outage
**File**: `backend/app/core/event_bus.py:226`  
**Status**: BUG  
**Finding**: When the subscriber reconnects after a Redis error, `last_id` is reset to `"$"` (line 226), meaning any events that arrived during the outage window are permanently missed — they exist in `stream:events` (global) but will never be dispatched to connected WebSocket clients. The per-account stream (`stream:{account_id}`) retains the events for client-side replay on reconnect, but server-side dispatch (which pushes to currently-connected clients) skips them.  
**Evidence**: `event_bus.py:226`.  
**Impact**: After a Redis restart or network blip, trades and alerts that occurred during the outage are not pushed to open browser tabs. Users must manually refresh to see them.  
**Fix**: Persist `last_id` in Redis itself (e.g., `SET subscriber:last_id {last_id}`) so after reconnect the subscriber reads `GET subscriber:last_id` and resumes from the correct position. Use `"0-0"` as the initial value on first start.

---

### 4-C: WebSocket `send_to_account` — on failure, calls `disconnect()` which removes the client
**File**: `backend/app/api/websocket.py:76–85`  
**Status**: MINOR_ISSUE  
**Finding**: If `websocket.send_json()` raises (e.g., client sends a malformed message, or connection drops at exactly the wrong moment), `send_to_account` catches the exception and calls `await self.disconnect(account_id)`. This removes the account from `active_connections`. If multiple concurrent tasks are sending to the same account, one failure removes the connection for all. The next `send_to_account` call finds `None` in `active_connections` and silently does nothing — but the WebSocket is still technically open on the client side (the client hasn't disconnected, it just received a send error).  
**Evidence**: `websocket.py:82–85`.  
**Impact**: A temporary send error (e.g., 2-second timeout) causes the server to drop the account from the manager, preventing all subsequent alerts and trade updates until the client reconnects.  
**Fix**: Only call `disconnect()` if the error is a `WebSocketDisconnect` or `starlette.websockets.WebSocketState.DISCONNECTED` state. For timeout errors, retry once before disconnecting.

---

### 4-D: `ConnectionManager` — `active_connections` is a plain `dict`, not protected against concurrent writes outside `_lock`
**File**: `backend/app/api/websocket.py:39–45`  
**Status**: MINOR_ISSUE  
**Finding**: `broadcast_price()` (line 87) reads `self.subscriptions` inside `async with self._lock:` but then iterates over `subscribers` (a copy) outside the lock before calling `send_to_account`. This is safe. However, `send_to_account` (line 76) reads `self.active_connections.get(account_id)` without acquiring the lock. If a concurrent disconnect happens between this read and `websocket.send_json()`, the WebSocket object may be in a disconnected state. This is handled by the exception catch, so the impact is minor.  
**Evidence**: `websocket.py:76–79`.  
**Impact**: Harmless in most cases; the `try/except` in `send_to_account` handles it.

---

### 4-E: Event order not guaranteed — `alert_update` event published before `trade_update` for the same trade
**File**: `backend/app/tasks/trade_tasks.py:610–619`  
**Status**: MINOR_ISSUE  
**Finding**: After behavior detection, the code publishes `alert_update` then `trade_update`. The frontend may receive `alert_update` and fetch alerts before the `trade_update` triggers a trade list refresh. However, alerts reference trades (via `trigger_trade_id`), and if the frontend fetches alert details before the trade list is refreshed, the trade may already be in DB (committed before behavior detection). The actual order issue is: `alert_update` arrives at browser → frontend refreshes alerts → alert detail shows `trigger_trade_id` that isn't in the local trade list yet → detail sheet shows "trade not found". When `trade_update` arrives a few ms later, the trade list refreshes and all is well. This is a cosmetic race, not data corruption.  
**Evidence**: `trade_tasks.py:610–619`.  
**Impact**: Brief moment where alert detail sheet may not show associated trade.

---

## 5. Market Hours Logic

### 5-A: `is_market_open()` — holiday check is called on every invocation via `_load_extra_holidays()`
**File**: `backend/app/core/market_hours.py:70–73`  
**Status**: MINOR_ISSUE  
**Finding**: `is_trading_holiday()` calls `_load_extra_holidays()` which calls `os.environ.get("NSE_EXTRA_HOLIDAYS", "")` and parses a date string on every call. `is_market_open()` calls `is_trading_holiday()`, so every behavioral engine call that uses `is_market_open()` reads an environment variable. Under 100 trades/sec, this is 100 env reads/sec. Env reads are fast but the string splitting and date parsing adds unnecessary overhead.  
**Evidence**: `market_hours.py:56–73`.  
**Impact**: Negligible performance impact in most deployments. Could matter at very high throughput.  
**Fix**: Cache `_load_extra_holidays()` result with a module-level variable and a TTL, or use `functools.lru_cache` with a small `maxsize`.

---

### 5-B: `market_minutes()` — does not skip MCX evening→morning gap (no overnight break in the commodity window)
**File**: `backend/app/core/market_hours.py:192–234`  
**Status**: BUG  
**Finding**: `MARKET_HOURS[COMMODITY]` is defined as `open=09:00, close=23:30`. `market_minutes()` uses these times directly. For a BTST trade entered at 22:00 on Monday and exited at 10:00 on Tuesday, `market_minutes()` would correctly compute:
- Monday 22:00→23:30 = 90 minutes
- Tuesday 09:00→10:00 = 60 minutes  
Total = 150 minutes

This is correct for MCX. However, MCX has two sessions with a gap: morning (09:00–17:00) and evening (17:00–23:30) — there is NO gap between them (it's a continuous session). The current implementation treats it as one continuous session, which is correct for P&L-duration calculations.

**But**: For the BTST detection pattern (`entry after 15:00, exit before 09:45 next trading day`), `market_minutes()` using MCX hours would count the overnight gap (23:30 to 09:00 = 9.5 hours) as zero, which is correct. This is fine.

**Actual bug**: The commodity market is open 9:00–23:30 on weekdays only. The holiday check at line 221 checks `is_trading_holiday(current_date)` using NSE/BSE holidays. MCX has its own holiday calendar (sometimes different from NSE). Using NSE holidays for MCX market_minutes calculation is incorrect — MCX may trade on NSE holidays and vice versa.  
**Evidence**: `market_hours.py:221` — `is_trading_holiday(current_date)` uses NSE holidays regardless of segment.  
**Impact**: BTST `duration_minutes` calculations for MCX commodities are wrong on NSE-only holidays (MCX would be open but `market_minutes()` would count it as closed). This affects the BTST analytics tab.  
**Fix**: Add an MCX holiday calendar. For the short term, only apply NSE holiday logic to `EQUITY` and `FNO` segments.

---

### 5-C: NSE 2026 holiday calendar is incomplete
**File**: `backend/app/core/market_hours.py:42–49`  
**Status**: MINOR_ISSUE  
**Finding**: `NSE_HOLIDAYS_2026` has only 6 dates. The actual NSE 2026 holiday list has ~14 trading holidays. Missing holidays include: Holi (exact date TBD), Id-Ul-Fitr (moon-sighting), Ram Navami, Mahavir Jayanti, Good Friday date (2026-04-03 is included but needs verification), Maharashtra Day (May 1), Bakri Id, Ganesh Chaturthi, Dussehra, Diwali, Guru Nanak Jayanti. The code uses `NSE_EXTRA_HOLIDAYS` env var as a workaround, which requires manual intervention.  
**Evidence**: `market_hours.py:42–49` — only 6 dates for 2026.  
**Impact**: On NSE holidays not in the list, `is_market_open()` returns `True`, behavior engine patterns like `opening_5min_trap` and `end_of_session_mis_panic` may fire incorrectly, and Celery beat tasks (guardrail check every 60s) run all day when the market is closed.  
**Fix**: Complete the 2026 holiday list from the official NSE circular. Add 2027 dates before December 2026.

---

### 5-D: `get_session_boundaries()` does not check if `for_date` is a holiday
**File**: `backend/app/core/market_hours.py:332–363`  
**Status**: MINOR_ISSUE  
**Finding**: `get_session_boundaries()` returns market open/close times for any given date without checking if that date is a holiday or weekend. Callers that use this to filter trades for "today's session" on a holiday would get a valid-looking time window that contains no trades — this is harmless. But if used to trigger an EOD sync or report on a holiday, it will still fire.  
**Evidence**: `market_hours.py:332–363`.  
**Impact**: Minor — EOD reports generated on holidays contain no trades but are still sent.

---

## 6. Config and Environment

### 6-A: `ENCRYPTION_KEY` and `SECRET_KEY` are required but fail at import time — no user-friendly startup error
**File**: `backend/app/core/config.py:59–60`  
**Status**: MINOR_ISSUE  
**Finding**: `ENCRYPTION_KEY: str` and `SECRET_KEY: str` are required (no default, not `Optional`). If missing, pydantic-settings raises a `ValidationError` at import time when `settings = Settings()` is called (line 89). The error message from pydantic is a detailed JSON-style traceback — acceptable in development, but in production (Docker entrypoint, Render deploy), the process crashes immediately with a non-obvious error. There is no startup check that logs a clear human-readable message like "ENCRYPTION_KEY is required...".  
**Evidence**: `config.py:59–60`, `config.py:89`.  
**Impact**: Deploy failures are harder to diagnose; no graceful "missing env var" message.  
**Fix**: Wrap `settings = Settings()` in a try/except that logs field-level validation errors clearly before re-raising.

---

### 6-B: `DATABASE_URL` — no validation that it's an async-compatible URL
**File**: `backend/app/core/config.py:10`, `backend/app/core/database.py:17`  
**Status**: MINOR_ISSUE  
**Finding**: `DATABASE_URL: str` accepts any string. `create_async_engine()` requires `postgresql+asyncpg://...`. If the `.env` has `postgresql://...` (sync URL), `create_async_engine` will raise `NoSuchModuleError: Can't load plugin: sqlalchemy.dialects:postgresql` at startup. Supabase's connection string typically uses `postgresql://`, not `postgresql+asyncpg://`.  
**Evidence**: `config.py:10`, `database.py:17`.  
**Impact**: App fails at startup with a confusing SQLAlchemy error, not a config validation error.  
**Fix**: Add a validator in `Settings` that checks `DATABASE_URL.startswith("postgresql+asyncpg://")` and raises a clear error or auto-converts the scheme.

---

### 6-C: `REDIS_URL` defaults to `redis://localhost:6379/0` — unsafe production default
**File**: `backend/app/core/config.py:39`  
**Status**: MINOR_ISSUE  
**Finding**: `REDIS_URL: str = "redis://localhost:6379/0"` — has a default value, so it won't fail validation if unset. In production (Render.com), if `REDIS_URL` is not set, the app connects to `localhost:6379` which doesn't exist on Render, and every Redis operation silently fails open (because `rate_limit.py` catches `Exception` and `event_bus.publish_event` is fail-silent). The app runs but with no rate limiting, no event streaming, and no alerts.  
**Evidence**: `config.py:39`.  
**Impact**: Silent degradation in production if `REDIS_URL` is forgotten in the environment.  
**Fix**: Make `REDIS_URL` required with no default, or add a startup check that verifies Redis connectivity.

---

### 6-D: `ADMIN_JWT_SECRET` defaults to `None` — admin panel is silently disabled
**File**: `backend/app/core/config.py:65`  
**Status**: MINOR_ISSUE  
**Finding**: `ADMIN_JWT_SECRET: Optional[str] = None`. If not set, the admin panel's JWT signing will fail at runtime (when someone tries to log in), not at startup. Depending on how the admin auth router handles this, it may raise a `TypeError` (passing `None` to `jwt.encode()`) or return a silent 500 error.  
**Evidence**: `config.py:65`.  
**Impact**: Admin panel is non-functional if `ADMIN_JWT_SECRET` is not set, with no startup warning.  
**Fix**: Log a `WARNING` at startup if `ADMIN_JWT_SECRET` is `None`.

---

### 6-E: Celery broker uses `settings.REDIS_URL` by default — Upstash TLS config applied globally but `CELERY_BROKER_URL` can bypass it
**File**: `backend/app/core/celery_app.py:32, 160–177`  
**Status**: MINOR_ISSUE  
**Finding**: `configure_for_upstash()` is called when `settings.REDIS_URL.startswith("rediss://")`. But if `CELERY_BROKER_URL` is set separately (without `rediss://`), `celery_app.conf.broker` will use that URL without TLS. Meanwhile `REDIS_URL` (still `rediss://`) is used by `event_bus.py` and `rate_limit.py`. This is fine if intentional (separate Redis instances). But if `CELERY_BROKER_URL` is accidentally set to the non-TLS form of Upstash, Celery connections will fail silently.  
**Evidence**: `celery_app.py:32, 165`.  
**Impact**: Misconfiguration risk if `CELERY_BROKER_URL` is set independently.

---

## 7. Rate Limiting — Two Conflicting Systems

### 7-A: `rate_limiter.py` (in-memory) vs `rate_limit.py` (Redis-backed) — dual systems
**File**: `backend/app/core/rate_limiter.py`, `backend/app/core/rate_limit.py`  
**Status**: MINOR_ISSUE  
**Finding**: Two rate limiting modules exist:
- `rate_limiter.py`: In-memory `defaultdict(list)` sliding window. Used by `sync_limiter`, `coach_limiter`, `analytics_limiter`, `admin_login_limiter`, `admin_otp_limiter`. Thread-safe via `asyncio.Lock`. **Does not work correctly with multiple uvicorn workers** — each process has its own counter.
- `rate_limit.py`: Redis ZADD-based, per-account. Used via `rate_limit(max_calls, window_seconds)` dependency. Works correctly across multiple workers.

The admin rate limiters (`admin_login_limiter`, `admin_otp_limiter`) use the in-memory system — if the app runs with 4 uvicorn workers (4×gunicorn), each worker has 5 independent login attempts, giving an effective limit of 20 attempts/15min instead of 5. Admin brute-force protection is 4× weaker than intended.  
**Evidence**: `rate_limiter.py:98–99`.  
**Impact**: Admin brute-force protection is bypassed with multiple workers. Attacker can try `5 × num_workers` passwords per 15-minute window.  
**Fix**: Migrate `admin_login_limiter` and `admin_otp_limiter` to the Redis-backed system in `rate_limit.py`.

---

## 8. Reconciliation Logic

### 8-A: `_reconcile_all_accounts` passes the same `db` session to `_reconcile_account` for all accounts
**File**: `backend/app/tasks/reconciliation_tasks.py:97–113`  
**Status**: BUG  
**Finding**: `_reconcile_all_accounts` opens one `async with SessionLocal() as db:` at line 75 and reuses the same `db` for every `await _reconcile_account(account, db)` call (line 99) across all accounts. If any account's reconciliation does a `db.rollback()` (inside `process_webhook_trade` retry logic), it rolls back the entire session for all subsequent accounts. Additionally, `_reconcile_account` does not do `db.commit()` itself, but if `TradeSyncService.upsert_trade()` (called indirectly via `process_webhook_trade`) commits mid-loop, the session state for subsequent DB reads within the loop may be stale.  
**Evidence**: `reconciliation_tasks.py:75–126`. Single `db` session shared across 1000+ accounts.  
**Impact**: Partial rollbacks for one account can cause missing reconciliation entries for subsequent accounts in the same run.  
**Fix**: Open a fresh session per account inside `_reconcile_account` (same pattern as `_expire_stale_positions` which correctly does `async with SessionLocal() as db:` per call).

---

### 8-B: `reconcile_trades` uses today's orders from Kite, but comment says "yesterday's trading day"
**File**: `backend/app/tasks/reconciliation_tasks.py:59–68, 170–181`  
**Status**: BUG  
**Finding**: The comment at line 59 says "Finds COMPLETE orders from the previous trading day". `_today_ist_start_utc()` at line 313 computes `yesterday_ist - timedelta(days=1)` as the cutoff for the DB query. However, `get_orders()` from Kite returns TODAY's orders only (Kite's `/orders` endpoint returns only the current day's orders, not historical). So the Kite side has today's orders, but the DB query filters from yesterday's start. This means:
- Kite has today's orders → correct
- DB query uses yesterday's start → will return both yesterday's AND today's orders from DB

The `existing_ids` set contains both yesterday and today's order IDs from DB. The `missing_ids = kite_order_ids - existing_ids` will only miss orders that are in Kite today but NOT in DB from yesterday or today. This means orders from yesterday that never got into DB will NOT be detected — Kite doesn't return them anymore.

The reconciliation is supposed to catch missed webhooks, but it only catches orders missed on the SAME DAY it runs (4 AM IST = late night, so effectively it covers yesterday's session). The `_today_ist_start_utc()` name is misleading — it returns yesterday's start, not today's.  
**Evidence**: `reconciliation_tasks.py:313–321` — function name says "today_ist_start" but returns yesterday.  
**Impact**: The reconciliation does work correctly (yesterday's session orders), but the naming is confusing and could lead to bugs if modified. The "previous day" intent is correct but the function name is wrong.  
**Fix**: Rename `_today_ist_start_utc` to `_yesterday_ist_start_utc()` for clarity.

---

### 8-C: `_is_contract_expired` — monthly proxy detection using `expiry_date.day == 1` is fragile
**File**: `backend/app/tasks/reconciliation_tasks.py:212–231`  
**Status**: MINOR_ISSUE  
**Finding**: Monthly F&O contracts are identified by `expiry_date.day == 1` (a proxy because `instrument_parser.py` uses day=1 for monthly contracts when the exact last-Thursday is not known). Weekly contracts that happen to expire on the 1st of a month will be misclassified as monthly and will only be expired "after the full expiry month has passed" (line 227) — an entire extra month delay. The specific risk is NIFTY weekly contracts expiring on e.g. April 1, which would not be cleaned up until May 1.  
**Evidence**: `reconciliation_tasks.py:212–231`.  
**Impact**: Stale open positions for weekly options expiring on the 1st of any month persist in the DB for up to a month, inflating open position counts and potentially triggering false position size alerts.  
**Fix**: In `instrument_parser.py`, resolve the actual last-Thursday for monthly contracts rather than using day=1 as a proxy. This makes the classification unambiguous.

---

## 9. WebSocket Connection Lifecycle

### 9-A: WebSocket `accept()` is called twice — once manually and once via `manager.connect()`
**File**: `backend/app/api/websocket.py:185, 222–224`  
**Status**: BUG  
**Finding**: Line 185 calls `await websocket.accept()` for the HTTP→WS upgrade. The code then authenticates and registers the connection. At line 222–224, instead of calling `manager.connect()` (which calls `await websocket.accept()` again at line 51), the code directly sets `manager.active_connections[account_id] = websocket`. The comment says "skip the accept() in connect()". However, the `manager.connect()` method has `await websocket.accept()` as its first line and is not called from the endpoint. This is fine — the endpoint correctly avoids double-accepting. But `manager.connect()` is still a public method that could be called elsewhere and would cause "WebSocket is already connected" error.  
**Evidence**: `websocket.py:185`, `websocket.py:48–54`, `websocket.py:222–224`.  
**Impact**: If `manager.connect()` is accidentally called from another code path, it attempts a second `accept()` which raises a runtime error.  
**Fix**: Remove `await websocket.accept()` from `manager.connect()` (it should only register, not accept). Update the docstring. The endpoint already handles the upgrade.

---

### 9-B: `since` param — empty string `""` is treated as `"0-0"` (full replay)
**File**: `backend/app/api/websocket.py:237`  
**Status**: MINOR_ISSUE  
**Finding**: `replay_since = since if since else "0-0"`. If the client passes `?since=` (empty string), this evaluates to `"0-0"`, triggering a full replay of up to 500 events. The condition `if since is not None:` at line 234 means an empty string triggers the replay block, then `replay_since = "0-0"`. This could be intentional, but it's easy for a client to accidentally pass `?since=` and get flooded with 500 replay events on first connect.  
**Evidence**: `websocket.py:234–237`.  
**Impact**: Minor — worst case is excess messages to the client on first connect if `since` is accidentally empty.  
**Fix**: Change to `replay_since = since if since and since.strip() else "0-0"`. Or reject empty `since` as equivalent to "no replay".

---

## 10. Model Index Gaps

### 10-A: `positions` table — no index on `(broker_account_id, tradingsymbol)`
**File**: `backend/app/models/position.py:12`  
**Status**: MINOR_ISSUE  
**Finding**: Only `broker_account_id` is indexed. Queries filtering by `(broker_account_id, tradingsymbol)` (used in `_expire_stale_positions` and position upsert logic) will do a seq scan on the broker account's positions.  
**Evidence**: `position.py:12`.  
**Impact**: With 50+ open positions per account and 100 users, position queries become slow (5000 row scans per lookup).  
**Fix**: Add `Index('idx_positions_account_symbol', 'broker_account_id', 'tradingsymbol')`.

---

### 10-B: `risk_alerts` — no index on `broker_account_id` alone
**File**: `backend/app/models/risk_alert.py:11–13`  
**Status**: MINOR_ISSUE  
**Finding**: The only index is `idx_risk_alerts_broker_detected` on `(broker_account_id, detected_at)`. Queries that filter by `broker_account_id` with `detected_at >= cutoff` (the most common pattern in the dedup check) will use this composite index correctly. However, the compound index starts with `broker_account_id`, so it works for account-only filters too. This is correct design.  
**Impact**: None.

---

### 10-C: `completed_trades` — no index on `(broker_account_id, tradingsymbol)`
**File**: `backend/app/models/completed_trade.py:19–20`  
**Status**: MINOR_ISSUE  
**Finding**: Index `idx_completed_trades_broker_exit` covers `(broker_account_id, exit_time)`. Queries by `(broker_account_id, tradingsymbol)` (used in analytics and BTST detection) require a seq scan over all account's trades, filtered by symbol.  
**Evidence**: `completed_trade.py:19–20`.  
**Impact**: Symbol-specific analytics queries become slow as trade history grows. For a user with 1000 completed trades, a query for NIFTY only must scan all 1000 rows.  
**Fix**: Add `Index('idx_completed_trades_account_symbol', 'broker_account_id', 'tradingsymbol')`.

---

### 10-D: `position_ledger` — no index on `(broker_account_id, tradingsymbol)`
**File**: `backend/app/models/position_ledger.py:38–42`  
**Status**: MINOR_ISSUE  
**Finding**: Only `broker_account_id` is indexed. FIFO matching requires querying all ledger entries for a specific `(broker_account_id, tradingsymbol)` in order — this requires a seq scan over the entire ledger for the account.  
**Evidence**: `position_ledger.py:38–42`.  
**Impact**: For accounts with many symbols, FIFO matching slows significantly as ledger grows.  
**Fix**: Add composite index on `(broker_account_id, tradingsymbol, occurred_at)`.

---

## 11. WhatsApp Service

### 11-A: `whatsapp_service.py` — Gupshup vars are configured but silently inactive
**File**: `backend/app/services/whatsapp_service.py:23–30`  
**Status**: MINOR_ISSUE  
**Finding**: If only Gupshup API key is set (not Twilio), `whatsapp_service.is_configured` returns `False` and all messages are logged but not sent. A `logger.warning()` is emitted at startup, but this is easy to miss. There is no runtime check or health endpoint that clearly reports "WhatsApp is not delivering messages".  
**Evidence**: `whatsapp_service.py:23–30`.  
**Impact**: Production deployments that have completed the Gupshup migration config but haven't updated the code will silently drop all user alerts.  
**Fix**: Add `whatsapp: { configured: bool, provider: str }` to the admin health endpoint response and check it in deployment runbooks.

---

### 11-B: `send_risk_alert_notification` in `alert_tasks.py` — does not retry on failure, has no retry decorator applied correctly
**File**: `backend/app/tasks/alert_tasks.py:93–155`  
**Status**: MINOR_ISSUE  
**Finding**: `send_risk_alert_notification` has `max_retries=3, default_retry_delay=30` in its decorator. However, the inner `_send()` function catches `Exception` at line 152 and returns `{"error": str(e)}` — it does NOT call `raise self.retry(exc=e)`. So the task always returns success (from Celery's perspective) even when delivery fails. The outer `asyncio.run(_send())` also doesn't raise. The task will never retry.  
**Evidence**: `alert_tasks.py:151–154`.  
**Impact**: Failed WhatsApp alert delivery for risk alerts is silently dropped after the first attempt, despite the `max_retries=3` decorator making developers think retries are active.  
**Fix**: In the except block, call `raise self.retry(exc=e)` instead of `return {"error": str(e)}`, matching the pattern used in `send_whatsapp_alert` (lines 73–88).

---

## 12. Timestamp and Timezone Consistency

### 12-A: Mixed timezone libraries — `pytz` and `ZoneInfo` used interchangeably
**File**: `reconciliation_tasks.py:44–45`, `trade_tasks.py:643`, `retention_tasks.py:26`  
**Status**: MINOR_ISSUE  
**Finding**: The codebase uses both `pytz.timezone("Asia/Kolkata")` and `ZoneInfo("Asia/Kolkata")` in different files, sometimes in the same file:
- `reconciliation_tasks.py:44`: `IST = pytz.timezone("Asia/Kolkata")`
- `reconciliation_tasks.py:45`: `_IST_TZ = ZoneInfo("Asia/Kolkata")`
- `market_hours.py:16`: `IST = pytz.timezone('Asia/Kolkata')`

The `pytz` library requires `tz.localize(dt)` for naive datetimes; `ZoneInfo` uses `dt.replace(tzinfo=tz)`. Mixing them can cause subtle timezone conversion bugs if a `pytz`-aware datetime is passed to a function that uses `ZoneInfo` and vice versa.  
**Evidence**: `reconciliation_tasks.py:44–45`.  
**Impact**: Potential off-by-one-hour bugs around DST transitions (IST does not observe DST, so the impact is zero in India). However, the inconsistency increases maintenance burden and is a potential bug source if the codebase ever handles non-IST timezones.  
**Fix**: Standardize on `ZoneInfo` (Python 3.9+ stdlib) and remove `pytz` dependency.

---

### 12-B: `UserProfile.updated_at` — `onupdate` uses a lambda, not `server_default`
**File**: `backend/app/models/user_profile.py:108`  
**Status**: MINOR_ISSUE  
**Finding**: `updated_at = Column(DateTime(timezone=True), ..., onupdate=lambda: datetime.now(timezone.utc))`. The `onupdate` lambda runs in Python application code, not in PostgreSQL. If a row is updated directly via SQL (migrations, admin scripts), `updated_at` will NOT be updated. The same issue exists for `created_at` defaults that use lambdas instead of `server_default=text("now()")`.  
**Evidence**: `user_profile.py:107–108`.  
**Impact**: Minor — `updated_at` may be stale after direct DB edits. Not a runtime bug.  
**Fix**: Use `server_default=text("now()")` and `server_onupdate=text("now()")` for consistency with models like `Trade` and `BrokerAccount`.

---

## Summary Table

| ID | Component | Issue | Status | Severity |
|----|-----------|-------|--------|----------|
| 1-A | Celery workers | `asyncio.run()` + `--pool=gevent` incompatibility | MINOR_ISSUE | Medium |
| 1-B | behavior_lock TTL | 15s too short → duplicate alerts | BUG | High |
| 1-C | fifo_lock retry | 15s blocking wait exhausts workers | MINOR_ISSUE | Medium |
| 1-D | DB session | Long-lived session exhausts connection pool | MINOR_ISSUE | Medium |
| 1-E | Full-session dedup | `consecutive_loss_streak` over-escalates on retry | BUG | High |
| 1-F | EOD sync | All accounts fire simultaneously → rate limit burst | MINOR_ISSUE | Medium |
| 1-G | Report scheduling | Commodity traders receive equity EOD report at 16:00 | BUG | Medium |
| 1-H | Weekly summary | Hardcoded strength/weakness in AI report | MINOR_ISSUE | Low |
| 1-I | Report tasks | `import re` inside loop | MINOR_ISSUE | Low |
| 1-J | APScheduler | Fires once per uvicorn worker → N× duplicate sends | BUG | Critical |
| 1-K | retention_tasks | Shared DB session across loop iterations | MINOR_ISSUE | Medium |
| 2-A | Zerodha rate limiter | Per-process limiter allows 100× API calls | BUG | High |
| 2-B | `_sync_locks` | Not present (resolved) | CORRECT | — |
| 2-C | `get_instruments()` | Bypasses circuit breaker, creates new HTTP client | MINOR_ISSUE | Low |
| 2-D | `exchange_token()` | Bypasses circuit breaker | MINOR_ISSUE | Low |
| 2-E | `validate_token()` | Returns True on network error | MINOR_ISSUE | Low |
| 2-F | Postback checksum | Uses global api_secret, breaks per-user keys | BUG | Critical |
| 3-A | Trade model | Standalone index OK alongside composite unique | CORRECT | — |
| 3-B | Trade model | `asset_class` etc. not nullable, no default | BUG | Medium |
| 3-C | CompletedTrade | No unique constraint → duplicates possible | MINOR_ISSUE | Medium |
| 3-D | Position model | No unique constraint → concurrent sync duplicates | BUG | High |
| 3-E | RiskAlert | `related_trade_ids` ARRAY(UUID) may mismatch string order_ids | BUG | Critical |
| 3-F | TradingSession | No unique constraint → duplicate session rows | BUG | High |
| 3-G | ai_cache update | Lost-update race condition | BUG | Medium |
| 3-H | occurred_at fallback | Uses `datetime.now()` when order_timestamp is None | MINOR_ISSUE | Medium |
| 4-A | event_bus replay | New connection per call → pool exhaustion | MINOR_ISSUE | Low |
| 4-B | event_bus subscriber | Resets to `"$"` after reconnect → misses events | BUG | Medium |
| 4-C | WebSocket send | Timeout disconnects the client for all future events | MINOR_ISSUE | Medium |
| 4-D | ConnectionManager | Read outside lock is safe (exception-handled) | MINOR_ISSUE | Low |
| 4-E | Event ordering | alert_update before trade list refreshed | MINOR_ISSUE | Low |
| 5-A | market_hours | `_load_extra_holidays()` called on every check | MINOR_ISSUE | Low |
| 5-B | market_minutes | NSE holidays applied to MCX segment | BUG | Medium |
| 5-C | NSE 2026 calendar | Incomplete holiday list | MINOR_ISSUE | Medium |
| 5-D | get_session_boundaries | No holiday check | MINOR_ISSUE | Low |
| 6-A | Config | Required fields fail at import with unclear error | MINOR_ISSUE | Low |
| 6-B | DATABASE_URL | No async URL validation | MINOR_ISSUE | Medium |
| 6-C | REDIS_URL | Unsafe default → silent degradation | MINOR_ISSUE | Medium |
| 6-D | ADMIN_JWT_SECRET | None → silent admin panel failure | MINOR_ISSUE | Low |
| 6-E | Celery TLS | `CELERY_BROKER_URL` can bypass TLS config | MINOR_ISSUE | Low |
| 7-A | Rate limiting | In-memory limiters bypass multi-worker brute-force | MINOR_ISSUE | High |
| 8-A | Reconciliation | Shared DB session across all accounts | BUG | High |
| 8-B | Reconciliation | `_today_ist_start_utc` misleadingly named | MINOR_ISSUE | Low |
| 8-C | Reconciliation | Monthly proxy detection (day==1) is fragile | MINOR_ISSUE | Medium |
| 9-A | WebSocket | `manager.connect()` calls `accept()` after endpoint already did | BUG | Low |
| 9-B | WebSocket replay | Empty `since=""` triggers full replay | MINOR_ISSUE | Low |
| 10-A | positions | No index on `(broker_account_id, tradingsymbol)` | MINOR_ISSUE | Medium |
| 10-B | risk_alerts | Compound index is sufficient | CORRECT | — |
| 10-C | completed_trades | No index on symbol | MINOR_ISSUE | Medium |
| 10-D | position_ledger | No index on symbol | MINOR_ISSUE | Medium |
| 11-A | WhatsApp | Gupshup vars silently inactive | MINOR_ISSUE | Low |
| 11-B | alert_tasks | `send_risk_alert_notification` never actually retries | BUG | High |
| 12-A | Timezones | Mixed pytz/ZoneInfo | MINOR_ISSUE | Low |
| 12-B | updated_at | Lambda-based vs server-side | MINOR_ISSUE | Low |

---

## Critical Bugs (fix before next deploy)

1. **1-J** — APScheduler fires in every uvicorn worker → N× duplicate WhatsApp sends to all users
2. **2-F** — Postback checksum uses global API secret → all per-user-key users get no real-time webhooks  
3. **3-E** — `RiskAlert.related_trade_ids` as `ARRAY(UUID)` may silently drop all behavioral alerts if order_ids (strings) are stored  
4. **3-F** — `TradingSession` no unique constraint → duplicate rows cause `MultipleResultsFound` crash in alert consolidation

## High-Priority Bugs (fix within 1 sprint)

5. **1-B** — `behavior_lock` TTL=15s too short → duplicate alerts
6. **1-E** — `consecutive_loss_streak` over-escalates to `danger` on task retry
7. **2-A** — Zerodha rate limiter is per-process → 100× burst at market open
8. **3-D** — Position table no unique constraint → duplicate positions on concurrent sync
9. **7-A** — Admin brute-force protection bypassed with multiple workers
10. **8-A** — Shared DB session in reconciliation → partial rollbacks affect all accounts
11. **11-B** — `send_risk_alert_notification` never retries despite `max_retries=3`
