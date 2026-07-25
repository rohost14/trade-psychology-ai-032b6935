# P0 — Entry & Map (findings)

> Scope: `main.py`, `core/{config,database,celery_app,event_bus,redis_pool,rate_limit,rate_limiter,
> admin_state,request_context,error_feed,logging_config,metrics,market_hours}`, `api/deps.py`, plus
> `Procfile`/`Dockerfile` deploy topology. Files read in full. Money/engine constants (`exchange_constants`,
> `trading_defaults`, `trade_classifier`) deferred to P1/P2 where they're behaviour-critical.
>
> **Findings-only.** Severity: P0 crash/security/money/data-loss · P1 common-path or scale break · P2
> quality/maintainability · P3 nit. Each finding is code-verified (grep/exec), not doc-based.

---

## 🔴 P0 — must fix before production

### F1 · 9 of 16 scheduled Celery tasks never execute (queue routing vs Procfile) · category: correctness/config
- **Where:** `core/celery_app.py` `task_routes` + `beat_schedule` vs `backend/Procfile` `worker: celery … --queues=trades,alerts,reports`.
- **Problem (verified by exec):** tasks whose module has no `task_routes` entry land on Celery's **default `celery` queue**, which the only worker process **does not consume**. Orphaned beat tasks:
  1. `retention_tasks.dispatch_reports_tick` (every 60s) → **all time-based user report delivery is dead** (daily/scheduled reports never dispatched).
  2. `intent_tasks.send_morning_intent_push` → morning push dead.
  3. `intent_tasks.send_eod_comparison_push` → EOD comparison push dead.
  4. `intent_tasks.send_daily_score_push` → daily score/streak push dead.
  5. `intent_tasks.refresh_personalization_patterns` → danger_days/hours never refreshed (stale personalization).
  6. `maintenance_tasks.ensure_behavior_event_partitions` → **partition upkeep dead → `behavior_events` INSERTs will start failing once the pre-created partitions run out → the behaviour engine's writes break** (time-bomb).
  7. `maintenance_tasks.check_capital_reality` → nudge dead.
  8. `maintenance_tasks.recognize_tilt_recovery` → positive-reinforcement push dead.
  9. `market_data_tasks.refresh_market_data_token` (08:45) → **the dedicated market-data Zerodha token is never refreshed → the shared KiteTicker dies at daily token expiry → no live prices for anyone** until manual restart.
  10. `admin_watchdog_tasks.admin_health_watchdog` → infra watchdog dead (the "system can't tell you it's failing" hole reopens).
- **Why it matters:** a large fraction of the scheduled product surface (reports, all nudges/pushes, live-price token, DB partition upkeep, self-monitoring) silently does nothing in the declared deploy topology. No error — the tasks just queue on `celery` and pile up.
- **Fix (one of):** add the default queue to the worker (`--queues=celery,trades,alerts,reports`), **or** give every beat task an explicit `task_routes` entry to a consumed queue, **or** run a dedicated worker for the default queue. Then add a startup/CI assertion that every `beat_schedule` task routes to a consumed queue.
- **Caveat:** this is P0 **if** the Procfile is the real production start command (it is the declared one; Dockerfile defers worker/beat CMD to compose). **Confirm the actual prod worker `--queues` before fixing** — if ops already runs a default-queue worker, downgrade to P2 (fragile-by-default). Either way the config is a latent trap.

---

## 🟠 P1 — breaks a common path or at scale

### F2 · `setup_logging()` is never called → prod logging + admin error-feed both dead · category: correctness/ops
- **Where:** `core/logging_config.py:101` defines `setup_logging()`; **grep confirms zero callers** (only a stale reference comment at `main.py:308`). No `logging.basicConfig` anywhere either.
- **Consequences:**
  - **(a)** Production **JSON structured logging never activates** — root logger has no configured handler, so app logs fall to Python's `lastResort` (WARNING+ to stderr, unformatted). Intended INFO-level operational logs are effectively dropped; log-aggregation expectations (JSONFormatter) are unmet.
  - **(b) The admin "live error feed" feature is permanently empty** — `RedisErrorFeedHandler` is only attached inside `setup_logging()`, so `admin:error_feed` is never written. `read_error_feed()` on the admin System page always returns `[]`. A shipped observability feature that does nothing.
  - **(c)** `request_id` ContextVar is set by middleware but `RequestIdFilter` is never registered → request IDs don't appear in logs. The `main.py:308` comment ("works via RequestIdFilter registered in setup_logging") is false.
- **Fix:** call `setup_logging()` in `main.py` lifespan startup (and at Celery worker init). Register the error-feed handler + filter on the **handlers**, not just the root logger (see F11).

### F3 · Per-account rate limiting silently degrades to per-IP; admin brute-force protection bypassable · category: security
- **Where:** `core/rate_limiter.py` `_default_key()` reads `request.state.broker_account_id`; **grep confirms nothing anywhere sets `request.state.broker_account_id`** (auth is via FastAPI dependency in `deps.py`, which never touches `request.state`).
- **Problem:** every limiter therefore falls through to `X-Forwarded-For` (first hop) or client IP. Two impacts:
  - **(a) Correctness:** authed limiters (`sync_limiter`, `coach_limiter`, `analytics_limiter`, `profile_put_limiter`, used across `analytics.py` ~30 endpoints, `coach`, `my_record`, `reports`, `account_data`, `zerodha`) group **all users behind a shared NAT/CGNAT IP into one bucket** → false 429s for unrelated users under one carrier/corporate IP.
  - **(b) Security (worse):** `admin_login_limiter` (5/15min) and `admin_otp_limiter` (5/5min) — the "strict brute-force protection" on `/api/admin/auth` — key on **unvalidated `X-Forwarded-For`**. An attacker sends a **different `X-Forwarded-For` per request** → each attempt is a distinct key → the limit never trips → **unlimited admin password + OTP/TOTP brute force**. Unlike the admin IP allowlist (gated by `ADMIN_TRUST_PROXY_HEADERS`), the limiter trusts XFF with no proxy-trust gate.
- **Fix:** for authed endpoints, key off the authenticated principal from the dependency (as `rate_limit.py` already does via `get_verified_broker_account_id`). For admin/unauthenticated, key off the real peer IP (`request.client.host`) and only honour `X-Forwarded-For` when `ADMIN_TRUST_PROXY_HEADERS` (or an equivalent trusted-proxy flag) is set — never raw.

### F4 · Blocking sync Redis calls inside the async event loop · category: scale
- **Where:** `core/rate_limiter.py` `__call__`, `core/rate_limit.py` `_check_rate_limit`, `core/error_feed.py` `emit` — all call `get_sync_redis()` + `pipe.execute()` (blocking socket I/O) from async contexts (FastAPI deps run on the event loop).
- **Problem:** every rate-limited request (30+ analytics endpoints, coach, profile, reports…) performs a **blocking** Redis round-trip on the event loop. Upstash RTT (often 30–100ms, TLS) × concurrent requests stalls the loop and caps throughput well before 10k. The error-feed handler compounds it during error storms (3 blocking Redis cmds per ERROR log, on the loop).
- **Fix:** use `get_async_redis()` + `await` in async deps; make the error-feed write non-blocking (fire-and-forget task or a sync-only path off the loop).

---

## 🟡 P2 — quality / maintainability / latent

### F5 · Duplicate rate-limit implementations · dead-code/quality
`core/rate_limit.py` (factory `rate_limit(max_calls,…)`, keys correctly off `get_verified_broker_account_id`) vs `core/rate_limiter.py` (class `RateLimiter`, buggy IP key per F3). Factory now used only by `danger_zone.py` (+ archived `portfolio_radar`). Consolidate on one correct, **async** implementation; retire the other. → ledger.

### F6 · Celery broker TLS cert verification disabled · security
`core/celery_app.py:configure_for_upstash()` sets `broker_use_ssl={"ssl_cert_reqs": ssl.CERT_NONE}`. The redis-py pools (`redis_pool.py`) verify certs by default; the broker connection does not, so broker traffic (task payloads incl. account IDs) is MITM-able. Upstash presents valid certs → use `CERT_REQUIRED`.

### F7 · NSE holiday calendar hardcoded through 2026 only · correctness (future)
`core/market_hours.py` `NSE_HOLIDAYS` = 2025 + 2026 sets. After 2026-12-31 it warns **once** then treats every 2027 holiday as a **trading day**. Session boundaries, EOD/beat scheduling gates, and behaviour time-windows all depend on this. Needs an annual update process or a holiday data source. `NSE_EXTRA_HOLIDAYS` env is an escape hatch, not a fix.

### F8 · CORS private-IP origin regex active in all environments · security
`core/config.py` `BACKEND_CORS_ORIGIN_REGEX = http://(192.168…|10.…)` is applied unconditionally (not gated by `ENVIRONMENT`). In production this allows private-range origins with `allow_credentials=True`. Low real risk (private ranges), but unintended — gate it to development.

### F9 · Killed "guardrails/portfolio" feature still burns Celery compute · dead-code
Routers archived (2026-07-25) but the **Celery tasks remain scheduled/live**: `guardrail_tasks.check_guardrail_rules` runs every 60s during market hours looping accounts; `portfolio_radar_tasks`/`portfolio_sync_tasks` still triggered. Orphaned compute + Redis/DB load for a feature with no frontend. Decide retire vs restore. → ledger. (Also interacts with F1: `guardrail_tasks`→`alerts` queue *is* consumed, so it actually runs; the intent/maintenance ones don't.)

### F10 · Non-verified auth dep skips revocation on all read endpoints · security (low)
`api/deps.py` `get_current_broker_account_id` decodes the JWT only — no DB check. A disconnected/revoked account's 24h JWT keeps **reading** data until expiry on every endpoint that uses the non-verified dep. Own-data only (bounded blast radius) but worth an explicit accept/deny decision; `get_verified_broker_account_id` exists for the sensitive paths.

### F14 · Startup "one-time" P&L repair + backfill run on every boot, load all rows in memory · scale/quality
`main.py` `_repair_nse_pnl` + `_backfill_pnl_pct` are `create_task`'d on **every** startup (not one-time despite the comment). `_repair_nse_pnl` `select(CompletedTrade)` over the last 7 days and `_backfill_pnl_pct` over all rows with null `pnl_pct`, materialising into Python and rewriting — at 10k users this is a large boot-time scan + long transaction on each deploy. Gate behind a migration/flag or a bounded batched job. (Correctness of the avg-based P&L overwrite itself is examined in P1.)

---

## ⚪ P3 — nits
- **F11** `logging_config.py:142` adds `RequestIdFilter` to the **root logger**, not its handlers. Python applies a logger's filters only to records that logger handles directly; records from child loggers propagating up are not filtered. Attach the filter to each **handler** so request_id injects everywhere. (Moot until F2 is fixed.)
- **F12** `redis_pool.py` comment cites dead "VIX fetches" (vix_service archived). Stale.
- **F13** Two metrics subsystems coexist: in-memory `logging_config.MetricsCollector` (used by `prometheus_metrics.py`, `zerodha.py`) and Redis `core/metrics.py` (engine SLOs). Different purposes, not a bug — but document which is authoritative; the in-memory one is per-process and lost on restart.

---

## ✅ What's solid here (credit)
- Config **fails fast** on missing `ENCRYPTION_KEY`/`SECRET_KEY`; startup **validates the Fernet key** before serving (prevents silent token-decrypt breakage).
- Security headers + CSP on every response; `no-store` on `/api/*`.
- Maintenance mode + admin runtime state are **Redis-backed and cross-worker** (not per-process).
- Impersonation read-only enforced by a **single middleware choke point** (method-based, independent of endpoint auth).
- `event_bus` is **fail-silent** (Redis down never crashes the Celery pipeline); dual-stream design (global push + per-account replay) is sound; idle XREAD gating protects the Upstash budget.
- `/health` checks DB + Redis + circuit breakers and returns 503 for LB.
- DB engine correctly configured for PgBouncer transaction mode (`statement_cache_size=0`, `pool_pre_ping`).

## Deferred out of P0 (tracked)
- `exchange_constants.py`, `trading_defaults.py`, `utils/trade_classifier.py` → **P1/P2** (money + engine).
- Full router-by-router auth-surface threat model → **P4**.
- Batch-task fan-out (B1/B2) correctness + the per-fill trigger enqueue paths → **P3**.
- Deploy/Dockerfile/requirements deep review → **P10**.
