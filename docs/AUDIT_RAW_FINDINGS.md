# AUDIT RAW FINDINGS — TradeMentor AI
**Date**: 2026-06-10  
**Auditor**: Claude Sonnet 4.6 (exhaustive codebase scan)  
**Scope**: Full codebase — backend, frontend, config, tasks, models, schemas

---

## [SECURITY] — backend/app/api/zerodha.py

### Finding: OAuth state parameter is trivially guessable / not validated for CSRF
Severity: HIGH  
File: backend/app/api/zerodha.py:186-188  
Description: When `setup_token` is not provided, the OAuth `state` parameter is set to `user_id if user_id else "anonymous"`. The `user_id` is a caller-controlled query parameter — any value is accepted. The callback reads `state` to detect the setup flow but never validates that the state matches anything stored server-side.  
Impact: A CSRF attack could complete an OAuth flow with an attacker's `request_token` and link the victim's session to the attacker's Zerodha account. The protection gap is partially mitigated by the one-time-code exchange pattern, but the state itself is never bound to the initiating user session.  
Fix: Generate a cryptographically random state, store it in Redis with the initiating session, and validate on callback.

---

### Finding: `setup-credentials` endpoint stores user API secrets with no auth
Severity: HIGH  
File: backend/app/api/zerodha.py:121-148  
Description: `POST /api/zerodha/setup-credentials` accepts `api_key` and `api_secret` from anyone and stores them in Redis with no authentication required. Any caller can submit arbitrary credentials.  
Impact: An attacker can plant a `setup_token`, then trick a victim into navigating to `/api/zerodha/connect?setup_token=...` — the victim would connect using the attacker's Zerodha credentials, giving the attacker's account access to victim trade data.  
Fix: Require the user to be authenticated (at least have a prior JWT) before this endpoint, or at minimum rate-limit it aggressively and bind the setup_token to the initiating IP.

---

### Finding: OAuth callback leaks internal exception details to URL
Severity: MEDIUM  
File: backend/app/api/zerodha.py:378-380  
Description: On exception, `str(e)` is URL-encoded and put into the redirect URL: `{frontend_url}/settings?error={error_msg}`. Python exception strings can contain internal paths, DB error messages, stack-trace snippets.  
Impact: Information disclosure — exception messages visible in browser history, server logs, Zerodha postback logs.  
Fix: Map exception types to safe user-facing messages; never expose raw `str(e)` in redirects.

---

## [SECURITY] — backend/app/api/websocket.py

### Finding: WebSocket token revocation check is a single point of failure
Severity: MEDIUM  
File: backend/app/api/websocket.py:205-217  
Description: If the DB query for token revocation check throws an exception, the code catches it and closes the connection with "Authentication error". However, the logged message "WebSocket revocation check failed: {e} — closing connection" means an infrastructure blip (DB overload) will kick every live user off WebSocket simultaneously.  
Impact: Denial-of-service from a transient DB hiccup. Users lose real-time alerts mid-session.  
Fix: Retry once with a short delay before closing; allow connection on timeout (fail-open with shorter re-check interval is less bad than mass disconnect).

---

## [SECURITY] — backend/app/api/prometheus_metrics.py

### Finding: /metrics endpoint is publicly accessible, no auth
Severity: MEDIUM  
File: backend/app/api/prometheus_metrics.py:49  
Description: The `/metrics` Prometheus endpoint has no authentication. The docstring says "No auth required (internal only — protect at the reverse proxy / network layer)" — but there is no guarantee that reverse proxy protection is in place.  
Impact: Internal queue depths, WS connection counts, and error type distributions are disclosed. Low direct impact but useful for attackers doing reconnaissance.  
Fix: Add at minimum a shared-secret header check or IP allowlist; document the network-layer requirement explicitly in the deployment guide.

---

## [SECURITY] — backend/app/api/admin/auth.py

### Finding: Admin OTP is generated with `random.choices`, not `secrets`
Severity: MEDIUM  
File: backend/app/api/admin/auth.py:42  
Description: `_make_otp()` uses `random.choices(string.digits, k=6)`. Python's `random` module is a Mersenne Twister — it is not cryptographically secure. The internal state can be inferred if an attacker can observe enough OTP values (which is possible in a multi-admin scenario or via timing).  
Impact: An attacker who can observe previous OTPs can predict future ones.  
Fix: Replace `random.choices` with `secrets.choice` or `''.join(secrets.token_digits(6))`.

---

### Finding: Admin logout does not invalidate server-side state
Severity: LOW  
File: backend/app/api/admin/auth.py:207-210  
Description: Admin JWT is stateless — `/logout` just acknowledges, takes no server action. A stolen admin JWT remains valid until it expires (8 hours).  
Impact: If admin JWT is stolen (XSS, log exfiltration, etc.), it remains usable for up to 8 hours after the legitimate admin logs out.  
Fix: Maintain a Redis blocklist of logged-out admin JWTs with TTL = expiry time; check on every admin endpoint.

---

## [SECURITY] — backend/app/api/alerts.py

### Finding: alerts.py provides no test-alert rate limiting
Severity: MEDIUM  
File: backend/app/api/alerts.py:13-34  
Description: `POST /api/alerts/test` sends a WhatsApp message to any phone number provided by an authenticated user. There is no rate limiting on this endpoint.  
Impact: An authenticated user can spam arbitrary phone numbers (not just their own) with WhatsApp messages. The `phone_number` is not validated against the user's registered phone.  
Fix: Rate-limit this endpoint; validate that the supplied phone matches the user's guardian_phone or their own broker_email phone.

---

## [SECURITY] — backend/app/core/rate_limiter.py

### Finding: In-memory rate limiter is per-process and not shared across Celery workers
Severity: MEDIUM  
File: backend/app/core/rate_limiter.py:44  
Description: `RateLimiter._hits` is a plain Python dict. In a multi-process deployment (multiple uvicorn workers or gunicorn forks), each process has its own in-memory state. Rate limits effectively become N× more permissive where N = number of processes.  
Impact: Sync endpoint allows 10×N syncs per minute instead of 10; coach endpoint allows 10×N AI messages.  
Fix: Back rate limits with Redis (as already done in `rate_limit.py` — the Redis-backed version). Replace `rate_limiter.py` usages with `rate_limit.py` or migrate to Redis.

---

### Finding: rate_limiter.py is in-memory but rate_limit.py is Redis-backed — two competing systems
Severity: MEDIUM  
File: backend/app/core/rate_limiter.py, backend/app/core/rate_limit.py  
Description: Two entirely separate rate-limiting systems exist. Most endpoints use `rate_limiter.py` (in-memory). `rate_limit.py` (Redis-backed, per-account) exists but appears to be used by only a few endpoints. The in-memory one is NOT production-safe for multi-process deploys.  
Impact: Duplicate implementation leads to inconsistent enforcement; in-memory limits are easily bypassed at scale.  
Fix: Standardize on the Redis-backed `rate_limit.py` for all production endpoints.

---

## [SECURITY] — src/lib/api.ts

### Finding: JWT stored in localStorage — susceptible to XSS
Severity: MEDIUM  
File: src/lib/api.ts:49, src/contexts/BrokerContext.tsx:93  
Description: `AUTH_TOKEN_KEY` is stored and read from `localStorage`. Any XSS vulnerability in any component, third-party script, or browser extension can read and exfiltrate this token.  
Impact: Token theft via XSS — attacker gets full access to the victim's account until the 24-hour JWT expires.  
Fix: Store token in httpOnly cookie instead of localStorage. This is a major architectural change but is the industry-standard mitigation.  
Note: The current CSP (`'unsafe-inline'` for scripts) means browser-based XSS is still partially possible, compounding this issue.

---

## [SECURITY] — backend/app/main.py

### Finding: CSP includes 'unsafe-inline' for scripts
Severity: MEDIUM  
File: backend/app/main.py:246  
Description: `Content-Security-Policy` header includes `script-src 'self' 'unsafe-inline'`. This allows inline script execution which is the primary XSS vector — inline scripts injected by an attacker would be executed.  
Impact: Significantly weakens the XSS protection that CSP is supposed to provide. Allows any inline `<script>` to execute.  
Fix: Remove `'unsafe-inline'`; use nonces or hashes for any required inline scripts.

---

## [SECURITY] — backend/app/api/trades.py

### Finding: `/api/trades/stats` fetches ALL trades without pagination
Severity: MEDIUM  
File: backend/app/api/trades.py:71-86  
Description: `GET /api/trades/stats` does `select(Trade).where(broker_account_id == ...)` with no LIMIT or date filter. A user with many months of trading history will load all rows into memory.  
Impact: Memory exhaustion for heavy users; potential OOM in production. Could be used as a low-effort DoS by a user with many trades.  
Fix: Add date range filter (default: last 90 days) and LIMIT to stats query.

---

## [BUSINESS LOGIC] — backend/app/services/pnl_calculator.py

### Finding: P&L repair on startup is silently non-idempotent for edge cases
Severity: MEDIUM  
File: backend/app/main.py:125-161  
Description: The startup `_repair_nse_pnl()` task recalculates P&L using `(exit - entry) * qty`. This formula ignores brokerage, STT, exchange charges, and SEBI fees. The comment says "FIFO engine is authoritative" but the repair overwrites with a simplified formula.  
Impact: Users who rely on accurate net P&L (after charges) will see artificially inflated P&L figures for any trades repaired by this function.  
Fix: Do not recalculate P&L using a simplified formula in the repair task. If reconciliation with Zerodha is needed, use the authoritative `realised` field from Zerodha's API.

---

### Finding: FIFO real-time path does NOT apply lot_multiplier for MCX/CDS
Severity: HIGH  
File: backend/app/services/pnl_calculator.py:773-785  
Description: `calculate_trade_pnl_realtime()` (webhook path) calculates P&L as `(price_diff * match_qty)` without any `lot_multiplier`. The batch FIFO path correctly applies `lot_multiplier` for MCX/CDS instruments. The real-time path is used when a trade arrives via webhook during live trading.  
Impact: MCX and CDS traders see wrong real-time P&L displayed on the dashboard. For CRUDEOIL futures (lot = 100 barrels), the real-time P&L is 100× understated.  
Fix: Apply the same `lot_multiplier` logic in `calculate_trade_pnl_realtime()` as in `_process_symbol_trades()`.

---

## [BUSINESS LOGIC] — backend/app/services/behavior_engine.py

### Finding: `_detect_overtrading_burst` — profitable burst with ANY losing trade fires alert but only checks `session_pnl < 0`
Severity: LOW  
File: backend/app/services/behavior_engine.py:545-559  
Description: When `session_pnl >= 0` but `losing_in_burst > 0`, the function fires a caution. This logic path is reached because it falls through from the `if session_pnl > 0 and all_burst_profitable: pass` branch. This means a session with net positive P&L but one losing trade in a burst fires an alert. While arguably informational, the severity is labeled "caution" which may be noisy for active scalpers.  
Impact: False positive caution alerts for legitimate profitable scalping sessions.

---

### Finding: `_detect_size_escalation` — comparison uses quantity not lots
Severity: MEDIUM  
File: backend/app/services/behavior_engine.py:613  
Description: `sizes = [t.total_quantity or 1 for t in prior]` compares raw quantities. For options trades, `total_quantity` is already in units (e.g., 50 for 1 Nifty lot). But when comparing across different expiry dates of the same underlying, lot sizes can change (Nifty lot changed from 75 to 25 in Nov 2024). An escalation from 25 (post-change) to 50 would trigger but represent the same notional risk.  
Impact: Potentially spurious escalation alerts around lot-size change events.  
Fix: Normalize by underlying lot size when comparing quantities.

---

### Finding: `_detect_end_of_session_mis_panic` — window starts at 15:10 but MIS auto-square-off risk starts at 15:00
Severity: MEDIUM  
File: backend/app/services/behavior_engine.py  
Description: The comment in `trading_defaults.py` line 142 says "MIS trades entered after 15:00 IST face auto-square-off at ~15:20." But the pattern fires at `15:10`, missing the 15:00-15:10 window entirely. The docstring in the engine header (line 45) says "15:10" which matches, but the trading_defaults.py comment says "15:00".  
Impact: MIS trades entered between 15:00 and 15:10 that are the riskiest (20 minutes to forced exit) are not detected.  
Fix: Lower the window start to 15:00, matching the risk description in trading_defaults.py.

---

### Finding: `_detect_fomo_entry` — pre-close threshold uses `fomo_open_symbols` not `fomo_close_window_symbols`
Severity: LOW  
File: backend/app/services/behavior_engine.py:998-999  
Description: Line 998 assigns `threshold = fomo_open_symbols` for `is_close_window` — the same threshold as the opening window. There is no dedicated `fomo_close_symbols` threshold. The description in COLD_START_DEFAULTS says "last 30 min of session (pre-close panic)" but the threshold is shared.  
Impact: Minor — likely intentional reuse, but it means pre-close FOMO always has the same threshold as opening FOMO rather than being independently tunable.

---

## [BUSINESS LOGIC] — backend/app/services/risk_detector.py

### Finding: RiskDetector still runs on sync path AND BehaviorEngine runs on the same sync — double alert generation possible
Severity: HIGH  
File: backend/app/api/zerodha.py:820-885  
Description: `sync/all` calls BOTH `risk_detector.detect_patterns()` (legacy) AND `run_behavior_engine_full_session` (new BehaviorEngine). The dedup logic for legacy alerts uses a 24-hour window keyed on `(trigger_trade_id, pattern_type)`. BehaviorEngine has its own dedup. But the two engines detect overlapping patterns (both detect overtrading, consecutive losses, etc.) and save to the same `risk_alerts` table.  
Impact: Users see duplicate alerts in the Alerts page — one from legacy RiskDetector and one from BehaviorEngine — for the same behavioral event. Confuses users.  
Fix: Remove legacy RiskDetector from the sync path entirely; it was supposed to be deprecated in session 21.

---

## [DATABASE & DATA INTEGRITY]

### Finding: Missing index on risk_alerts(broker_account_id, detected_at)
Severity: HIGH  
File: backend/app/api/risk.py:55-65  
Description: `GET /api/risk/alerts` queries `risk_alerts` with `WHERE broker_account_id = X AND detected_at >= Y ORDER BY detected_at DESC`. Without a composite index on `(broker_account_id, detected_at)`, this is a sequential scan that grows linearly with alert count.  
Impact: Response time degrades as alert count grows. At 10,000 alerts (6-12 months of heavy use), this query could take seconds.  
Fix: Add `CREATE INDEX idx_risk_alerts_account_time ON risk_alerts(broker_account_id, detected_at DESC)`.

---

### Finding: Missing index on completed_trades(broker_account_id, exit_time)
Severity: HIGH  
File: backend/app/api/analytics.py:275-285  
Description: Analytics endpoint queries `CompletedTrade` with `WHERE broker_account_id = X AND exit_time >= Y`. Without a composite index this is a full table scan.  
Impact: Analytics page becomes slow as trade count grows.  
Fix: Add composite index on `(broker_account_id, exit_time)`.

---

### Finding: `_build_feature` uses hardcoded `is_expiry = exit_ist.weekday() == 3` — same bug as documented
Severity: HIGH  
File: backend/app/services/pnl_calculator.py:624  
Description: `is_expiry_day = exit_ist.weekday() == 3 if exit_ist else False` — this is exactly the hardcoded Thursday bug documented in MEMORY.md session 27. The behavior_engine.py was fixed to use `parse_symbol().expiry_date`, but the feature computation in `pnl_calculator.py` still uses the hardcoded weekday check.  
Impact: `is_expiry_day` feature flag in ML features is wrong for weekly options with non-Thursday expiry (introduced SEBI mandate for weekly expirations on Fridays/Mondays for some indices). Will corrupt ML training data.  
Fix: Use `is_expiry_day(ct.tradingsymbol, exit_ist.date())` from `instrument_parser.py`.

---

### Finding: CompletedTrade.pnl_pct nullable — not populated for historic records
Severity: LOW  
File: backend/app/main.py:166-198  
Description: Startup backfill for `pnl_pct` runs on every deploy. For accounts with thousands of trades, this is an O(n) operation running on the critical startup path (main uvicorn process).  
Impact: Slow startup times for large accounts; repeated DB writes on every deploy even when no backfill is needed.  
Fix: Track a migration flag in DB so backfill only runs once; or run as a one-off migration rather than startup code.

---

## [API ENDPOINTS]

### Finding: `GET /api/zerodha/token/validate` does not exist in backend
Severity: CRITICAL  
File: src/contexts/BrokerContext.tsx:272, backend/app/api/zerodha.py (entire file)  
Description: `BrokerContext.validateToken()` calls `GET /api/zerodha/token/validate`. This endpoint does NOT exist anywhere in the backend. The `zerodha.py` router has no `/token/validate` route.  
Impact: `validateToken()` will always return a 404, causing an unhandled error (axios will throw). The `catch` block sets `tokenStatus = 'unknown'` silently, so users see no error — but token validation never works. The Token Expired Banner and re-auth flows depend on this.  
Fix: Implement the endpoint in zerodha.py that checks if the stored access_token is still valid by making a lightweight Kite API call.

---

### Finding: `POST /api/zerodha/sync/all` has no rate limiter per account — only in-memory global
Severity: MEDIUM  
File: backend/app/api/zerodha.py:772-776  
Description: The `sync_limiter` is an in-memory global with 10 requests/60s. As discussed above, this is not shared across processes. Additionally, the tab-switch auto-sync in BrokerContext fires this on every tab focus (30s cooldown client-side). A user with multiple tabs open could easily hit the limit with legitimate usage.  
Impact: Users with multiple tabs get 429 errors during normal usage.

---

### Finding: `GET /api/analytics/progress` uses naive `datetime.combine` without timezone
Severity: MEDIUM  
File: backend/app/api/analytics.py:141-144  
Description: `datetime.combine(start_date, datetime.min.time())` creates a naive datetime without timezone. When compared against `Trade.order_timestamp` (which is timezone-aware UTC), SQLAlchemy/PostgreSQL may raise a warning or silently treat the naive datetime as UTC, which would be correct in this case — but it is fragile and non-explicit.  
Impact: If the DB server or SQLAlchemy changes behavior regarding tz-aware vs naive datetime comparisons, queries silently return wrong results.  
Fix: Use `datetime.combine(start_date, time.min, tzinfo=timezone.utc)` explicitly.

---

### Finding: `/api/analytics/progress` — `best_streak` is hardcoded fallback
Severity: LOW  
File: backend/app/api/analytics.py:252  
Description: `"best_streak": max(days_clean, 7)` — the best streak is always at least 7, hardcoded. This is not calculated from actual history.  
Impact: Users with fewer than 7 days of clean trading always see 7 as their best streak, which is wrong.  
Fix: Actually compute best streak from history.

---

## [FRONTEND-BACKEND CONTRACT]

### Finding: `Alert.severity` type mismatch — frontend expects `'critical'|'high'|'medium'|'positive'` but backend sends `'danger'|'caution'`
Severity: HIGH  
File: src/types/api.ts:128, backend/app/services/behavior_engine.py  
Description: The TypeScript `Alert` interface defines `severity: 'critical' | 'high' | 'medium' | 'positive'`. The backend BehaviorEngine only produces `'danger'` or `'caution'`. The frontend AlertContext maps these, but `src/types/api.ts` has the wrong enumeration. Any code that switches on `severity` using the interface type will have dead branches for 'danger'/'caution' and will not handle them.  
Impact: TypeScript types give false safety; runtime comparisons against 'danger' work because JS is duck-typed, but the type definition is misleading and will cause errors for new developers.  
Fix: Update `Alert.severity` to `'danger' | 'caution' | 'critical' | 'high' | 'medium' | 'positive'` to cover all possible values.

---

### Finding: `CompletedTrade.pnl_pct` field missing from TypeScript interface
Severity: MEDIUM  
File: src/types/api.ts:99-121  
Description: The backend `CompletedTrade` model has a `pnl_pct` field (added in a recent migration). The frontend `CompletedTrade` TypeScript interface does not include `pnl_pct`.  
Impact: Frontend cannot use `pnl_pct` without TypeScript errors; any component that reads it gets typed as `undefined`.  
Fix: Add `pnl_pct?: number | null` to the frontend interface.

---

### Finding: `RiskState` interface missing fields returned by backend
Severity: MEDIUM  
File: src/types/api.ts:1-6  
Description: The frontend `RiskState` interface has `status_message` but the backend `RiskStateResponse` schema has `recommendations: List[str]` and `active_patterns: List[str]`. The `status_message` field is not in the backend schema at all.  
Impact: Frontend reads `risk_state.status_message` which doesn't exist on the actual API response — will always be `undefined`.  
Fix: Align `RiskState` with `RiskStateResponse`: remove `status_message`, add `recommendations`.

---

## [FRONTEND CODE QUALITY]

### Finding: `console.error` and `console.log` calls left throughout frontend
Severity: LOW  
File: src/lib/api.ts:79, src/contexts/BrokerContext.tsx:101,143,203, multiple others  
Description: Multiple `console.error` and `console.log` calls remain in production code paths (not behind a DEBUG flag). These leak internal API error details, state transitions, and potentially partial token information to browser devtools.  
Impact: Information disclosure to technical users who open devtools; also pollutes production logs.  
Fix: Replace with a configurable logger that suppresses output in production (`VITE_ENV === 'production'`); or explicitly allow specific logging and remove ad-hoc console calls.

---

### Finding: BrokerContext.validateToken calls non-existent endpoint — returns 'unknown' forever
Severity: HIGH  
File: src/contexts/BrokerContext.tsx:272-291  
Description: (Same as API finding above.) `validateToken()` calls `/api/zerodha/token/validate` which 404s. The catch block sets `tokenStatus = 'unknown'`. The `useEffect` on line 293-297 calls this on every account load. So every user is always in `tokenStatus: 'unknown'` state.  
Impact: `TokenExpiredBanner` component and any logic gated on `tokenStatus === 'expired'` never fires. Expired Zerodha tokens are not detected, and users can be confused by silent failures.

---

### Finding: Missing error boundaries around lazy-loaded analytics tabs
Severity: MEDIUM  
File: src/pages/Analytics.tsx  
Description: Analytics tabs use `lazy()` + `<Suspense>`. If a lazy-loaded tab component throws an error after loading (e.g., data parsing error), there's no `ErrorBoundary` wrapping the Suspense — the error propagates up and could crash the whole page.  
Impact: One broken analytics tab takes down the entire Analytics page.  
Fix: Wrap each Suspense boundary with an `<ErrorBoundary>` that shows a "failed to load" message for just that tab.

---

### Finding: Guest mode interceptor uses `config.adapter` override — bypasses all interceptors after the first
Severity: LOW  
File: src/lib/guestMode.ts (implied), src/lib/api.ts:31-46  
Description: Setting `config.adapter` to return mock data directly bypasses the response interceptor. The response interceptor handles `503 → maintenance redirect` and `401 → token-expired event`. Guest mode responses skip these.  
Impact: In guest mode, if a mock returns a 503-like response, the maintenance redirect doesn't fire. Low impact since demo data is controlled, but the bypassing is architecturally risky.

---

## [INFRASTRUCTURE & CONFIG]

### Finding: APScheduler runs inside the FastAPI process — no failover if process dies
Severity: HIGH  
File: backend/app/tasks/retention_tasks.py  
Description: `AsyncIOScheduler` is started in the FastAPI `lifespan` handler (not Celery beat). If the FastAPI process dies and does not restart within the scheduled minute, EOD reports and morning briefs for that minute are silently skipped. Unlike Celery beat, APScheduler has no persistent state.  
Impact: Users miss scheduled EOD reports if the server crashes and restarts slowly (e.g., OOM kill, deploy restart > 1 min). No retry, no error.  
Fix: Move EOD/morning report scheduling into Celery beat (already configured with redbeat for persistence); remove APScheduler dependency.

---

### Finding: Celery `worker_concurrency=100` with default prefork pool — uses 100 OS processes
Severity: HIGH  
File: backend/app/core/celery_app.py:69  
Description: `worker_concurrency=100` with the default Celery prefork pool spawns 100 OS processes. Each process loads all Django/SQLAlchemy code (~100MB+). Total memory: ~10GB just for workers.  
Impact: On any free/cheap hosting (Render free = 512MB, $7/mo = 512MB), the workers will be OOM-killed immediately. The comment says "use --pool=gevent" but this is not enforced at startup.  
Fix: Either enforce `--pool=gevent` in the Procfile/Dockerfile command, or reduce `worker_concurrency` to 4-8 for prefork, or document clearly that this requires >10GB RAM.

---

### Finding: `ZERODHA_API_KEY` is optional but failures are silent
Severity: MEDIUM  
File: backend/app/core/config.py:18  
Description: `ZERODHA_API_KEY: Optional[str] = None`. If not set, the Zerodha integration silently fails — no startup error. The `/connect` endpoint would use `zerodha_client` which has `api_key=None`.  
Impact: Misconfigured production deployments (missing env vars) fail silently rather than fast.  
Fix: Add startup validation (similar to `ENCRYPTION_KEY` check) that warns loudly if `ZERODHA_API_KEY` is unset.

---

### Finding: NSE holiday calendar is hardcoded and incomplete after 2026
Severity: MEDIUM  
File: backend/app/core/market_hours.py:42-52  
Description: `NSE_HOLIDAYS_2026` only has 6 entries (several major Indian holidays are missing: Mahashivratri, Holi, Ram Navami, Maharashtra Day, Ganesh Chaturthi, Guru Nanak Jayanti, Diwali, etc.). The combined `NSE_HOLIDAYS` has no entries after December 2026.  
Impact: After December 2026, `is_trading_holiday()` returns False for all days, including NSE holidays. Market hours logic, `market_minutes()` duration calculation, and behavioral pattern detection will be wrong on holidays — alerts fire on non-trading days.  
Fix: Add complete 2026 holiday list (refer to NSE official calendar); add `NSE_HOLIDAYS_2027` for the following year; add a runtime warning if `today > max(NSE_HOLIDAYS)`.

---

### Finding: `ENCRYPTION_KEY` failure raises RuntimeError crashing entire server
Severity: INFO  
File: backend/app/main.py:67-76  
Description: Good design: validates the key at startup and raises RuntimeError. However, the error message says "all stored access tokens undecryptable" which is accurate but alarming. No recovery path is documented.  
Impact: If ENCRYPTION_KEY changes accidentally (e.g., env var reset on Render free tier), all users are locked out simultaneously and must reconnect.  
Fix: Consider supporting key rotation (store key version ID with encrypted values); document the recovery procedure.

---

## [EDGE CASES & RACE CONDITIONS]

### Finding: Concurrent Celery workers can both claim behavior_lock — 15s TTL is too short
Severity: MEDIUM  
File: backend/app/tasks/trade_tasks.py:322-330  
Description: `behavior_lock` TTL is 15 seconds. BehaviorEngine `analyze()` runs up to 5 DB queries. Under load, if a DB query takes >5s (connection pool exhaustion, Supabase cold start), the lock expires and a second worker claims it, running behavioral detection concurrently for the same account.  
Impact: Duplicate behavioral alerts; race condition in `TradingSessionService.update_risk_score()` which does a read-modify-write without atomic increment.  
Fix: Increase behavior_lock TTL to 60 seconds; use atomic INCR in Redis for risk_score updates.

---

### Finding: `_sync_locks` dictionary grows unbounded (memory leak)
Severity: MEDIUM  
File: backend/app/api/zerodha.py:66-74  
Description: `_sync_locks: dict[str, asyncio.Lock] = {}` is a module-level dict. Every unique `account_id_str` that calls `sync/all` adds a Lock object that is never removed. For an application with many users, this grows indefinitely.  
Impact: Memory leak. For 10,000 users, stores 10,000 Lock objects — small but grows forever.  
Fix: Use a `WeakValueDictionary` or explicitly clean up locks after use; or use Redis-based locking for cross-process correctness.

---

### Finding: Webhook postback checksum verified AFTER account status check — logic order issue
Severity: LOW  
File: backend/app/api/webhooks.py:100-144  
Description: The code checks account existence and status (lines 100-144) before verifying the checksum (lines 110-128). This means an attacker who knows a valid `broker_account_id` and forges a webhook payload can confirm whether an account exists (gets "connected" vs "deleted/suspended" response without needing a valid checksum) until the checksum is checked. The current code checks checksum at line 110-128 but has `if not account` before it.  
Impact: Very minor information disclosure — confirms account existence to an attacker who can observe response differences. Low severity given other protections.

---

### Finding: No timezone normalization in analytics `get_period_stats` — naive datetimes
Severity: MEDIUM  
File: backend/app/api/analytics.py:138-145  
Description: `datetime.combine(start_date, datetime.min.time())` creates naive datetime. `Trade.order_timestamp` is stored in UTC. The comparison `Trade.order_timestamp >= naive_datetime` may work on PostgreSQL (implicitly treating naive as UTC) but is undefined behavior per Python's datetime spec.  
Impact: Under certain PostgreSQL timezone settings or future SQLAlchemy version changes, period boundaries could shift by IST offset (+5:30), causing trades to appear in the wrong week.  
Fix: Always use timezone-aware datetimes: `datetime.combine(start_date, time.min).replace(tzinfo=timezone.utc)`.

---

## [KNOWN GAPS FROM MEMORY.md]

### Finding: WhatsApp Gupshup Day 2 migration not done — Twilio code still used
Severity: MEDIUM  
File: backend/app/tasks/alert_tasks.py:66, backend/app/services/whatsapp_service.py  
Description: `send_whatsapp_alert` still references Twilio via `AlertService`. The MEMORY.md states "Day 2 code (whatsapp_service.py rewrite) still pending." The config has both Twilio and Gupshup fields.  
Impact: If Twilio credentials are removed in favor of Gupshup, WhatsApp alerts will silently fail.  
Fix: Complete the Gupshup migration as documented; remove Twilio dependency.

---

### Finding: NSE holiday calendar 2026 is incomplete — 6 entries vs expected ~12
Severity: MEDIUM  
File: backend/app/core/market_hours.py:42-48  
Description: `NSE_HOLIDAYS_2026` is missing: Mahashivratri (~Mar), Holi (~Mar), Ram Navami/Good Friday (~Apr), Maharashtra Day (May 1), Buddha Purnima (~May), Bakri Id (~Jun), Muharram (~Jul), Independence Day already included, Ganesh Chaturthi (~Aug), Dussehra (~Oct), Diwali (~Oct/Nov), Guru Nanak Jayanti (~Nov).  
Impact: `is_trading_holiday()` returns False for 6-8 actual NSE holidays in 2026. `market_minutes()` duration calculations will over-count trading time on holidays. Pattern detection (end-of-session-MIS, expiry-day) can fire on days the market is closed.  
Fix: Download the complete 2026 NSE holiday list from https://www.nseindia.com/resources/exchange-communication-holidays

---

## [SECURITY — ADMIN]

### Finding: Admin broadcast has no per-message rate limit or message content filtering
Severity: MEDIUM  
File: backend/app/api/admin/broadcast.py  
Description: Admin can broadcast up to 700 characters to all users with phone numbers. No rate limit on how frequently broadcasts can be sent. No content filtering. A compromised admin account (OTP stolen) could send spam/phishing to all users.  
Impact: Compromised admin = ability to send phishing messages to entire user base via WhatsApp.  
Fix: Add a maximum of N broadcasts per 24 hours per admin; add a mandatory confirmation step (dry_run must be true first and returned count shown before actual send).

---

## [FRONTEND SPECIFIC]

### Finding: BlowupShield page uses module-level cache object — stale across account switches
Severity: MEDIUM  
File: src/pages/BlowupShield.tsx:16-20  
Description: `shieldCache` is a module-level object. If a user logs out and logs back in as a different account (or uses multi-account), the cache may serve stale data from the previous account for up to 5 minutes.  
Impact: Data leakage between accounts if account switching occurs (unlikely but possible in shared browser).  
Fix: Include `accountId` in cache key validation (already present in `shieldCache.accountId`) — verify the comparison logic is correct.

---

### Finding: MyPatterns.tsx and BlowupShield.tsx have unhandled promise in useEffect
Severity: LOW  
File: src/pages/MyPatterns.tsx, src/pages/BlowupShield.tsx  
Description: Multiple `useEffect` hooks call async functions directly without proper cleanup. If the component unmounts while a fetch is in-flight, the `setState` calls will run on an unmounted component.  
Impact: React warning "Can't perform a state update on an unmounted component"; potential memory leaks.  
Fix: Use AbortController pattern to cancel in-flight requests on unmount.

---

## [SECURITY — DATA]

### Finding: User's Zerodha `access_token` is stored encrypted but `api_key` is stored plaintext
Severity: LOW  
File: backend/app/models/broker_account.py:34  
Description: `api_key: Mapped[str] = mapped_column(String, nullable=True)` — the API key is stored in plaintext. The `api_secret_enc` is encrypted with Fernet. API keys from KiteConnect developer console are not single-use secrets (they identify the app, not the user's session), so this is lower severity than storing the access_token in plaintext. However, the API key combined with the user's credentials enables brute-forcing the OAuth flow.  
Impact: DB dump leaks all API keys. Low severity since API key alone isn't sufficient for access.  
Fix: Consider encrypting `api_key` as well for defense in depth.

---

## [INFRASTRUCTURE]

### Finding: Two schedulers running simultaneously — APScheduler AND Celery beat
Severity: MEDIUM  
File: backend/app/tasks/retention_tasks.py, backend/app/core/celery_app.py  
Description: Commodity EOD is in Celery beat schedule (`celery_app.py:116`). Equity EOD is in APScheduler (`retention_tasks.py`). If both a Celery beat worker and the FastAPI process run simultaneously, commodity accounts might receive reports from both schedulers.  
Impact: Double-sends for commodity users on overlap (the equity APScheduler dispatches via `send_eod_report` which skips COMMODITY accounts, but the commodity Celery beat task sends to all accounts with phones). The filter in `_send_eod_for_account` (line 48-49) skips COMMODITY — so this is actually OK. But the architecture is confusing and error-prone.  
Fix: Document explicitly which scheduler handles which report type; consider consolidating.

---

## [API — MISSING ENDPOINT]

### Finding: Multiple frontend API calls to endpoints that may not exist
Severity: HIGH  
File: src/contexts/BrokerContext.tsx  
Description: Beyond `token/validate`, BrokerContext calls `POST /api/zerodha/sync/all` (verified exists), `GET /api/zerodha/accounts` (verified exists). No other missing endpoints found in this file. The token/validate issue is the primary blocker.

---

## [SECURITY — WEBHOOK]

### Finding: Webhook endpoint has no authentication — relies entirely on checksum
Severity: INFO  
File: backend/app/api/webhooks.py:72  
Description: `POST /api/webhooks/zerodha/postback` has no JWT auth (correct — Zerodha can't authenticate). Relies on the HMAC-SHA256 checksum. This is industry standard for webhooks. The checksum is correctly implemented. Flagged as INFO only.

---

## [CELERY TASKS — IDEMPOTENCY]

### Finding: `eod_sync_all_accounts` task — no evidence of idempotency for per-account processing
Severity: MEDIUM  
File: backend/app/tasks/trade_tasks.py (referenced in celery schedule)  
Description: The `eod-sync` beat task at 15:35 IST calls `eod_sync_all_accounts`. If Celery retries (network error, worker crash), the task re-runs and potentially creates duplicate CompletedTrade records if the delete-then-recreate FIFO pattern is not guarded against concurrent runs.  
Impact: Duplicate CompletedTrade records could cause double-counting in analytics and duplicate behavioral alerts.  
Fix: Verify `eod_sync_all_accounts` acquires the fifo_lock per account before running FIFO.

---

## [FRONTEND-BACKEND CONTRACT]

### Finding: `DashboardStats` interface unused — backend returns different shape
Severity: LOW  
File: src/types/api.ts:8-13  
Description: `DashboardStats` interface defines `{total_pnl, win_rate, total_trades, max_drawdown}`. The actual `GET /api/analytics/dashboard-stats` endpoint returns `{"risk_score": {...}}`. These do not match.  
Impact: Frontend code using `DashboardStats` type would have wrong field names and get `undefined` at runtime.

---
