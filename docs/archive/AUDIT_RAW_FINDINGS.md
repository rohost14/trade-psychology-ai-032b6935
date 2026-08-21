> **ARCHIVED 22 Aug 2026 — do not use as a current reference.**
>
> June raw scan, each item annotated CONFIRMED/FALSE POSITIVE; fix pass complete.
>
> Live findings, if any, were rescued into `docs/ENGINE_BACKLOG.md`.

---

# AUDIT RAW FINDINGS — TradeMentor AI
**Date**: 2026-06-10  
**Auditor**: Claude Sonnet 4.6 (exhaustive codebase scan)  
**Scope**: Full codebase — backend, frontend, config, tasks, models, schemas

---

---
> **Re-verification note (2026-06-11)**: Every finding below was checked against the actual source code. Each is annotated `[CONFIRMED]`, `[FALSE POSITIVE — reason]`, or `[INTENTIONAL]`.
---

## [SECURITY] — backend/app/api/zerodha.py

### Finding: OAuth state parameter is trivially guessable / not validated for CSRF
**Status**: [CONFIRMED]  
Severity: HIGH  
File: backend/app/api/zerodha.py:186-188  
Description: When `setup_token` is not provided, the OAuth `state` parameter is set to `user_id if user_id else "anonymous"`. The `user_id` is a caller-controlled query parameter — any value is accepted. The callback reads `state` to detect the setup flow but never validates that the state matches anything stored server-side.  
Impact: A CSRF attack could complete an OAuth flow with an attacker's `request_token` and link the victim's session to the attacker's Zerodha account. The protection gap is partially mitigated by the one-time-code exchange pattern, but the state itself is never bound to the initiating user session.  
Fix: Generate a cryptographically random state, store it in Redis with the initiating session, and validate on callback.

---

### Finding: `setup-credentials` endpoint stores user API secrets with no auth
**Status**: [CONFIRMED]  
Severity: HIGH  
File: backend/app/api/zerodha.py:121-148  
Description: `POST /api/zerodha/setup-credentials` accepts `api_key` and `api_secret` from anyone and stores them in Redis with no authentication required. Any caller can submit arbitrary credentials.  
Impact: An attacker can plant a `setup_token`, then trick a victim into navigating to `/api/zerodha/connect?setup_token=...` — the victim would connect using the attacker's Zerodha credentials, giving the attacker's account access to victim trade data.  
Fix: Require the user to be authenticated (at least have a prior JWT) before this endpoint, or at minimum rate-limit it aggressively and bind the setup_token to the initiating IP.

---

### Finding: OAuth callback leaks internal exception details to URL
**Status**: [CONFIRMED]  
Severity: MEDIUM  
File: backend/app/api/zerodha.py:378-380  
Description: On exception, `str(e)` is URL-encoded and put into the redirect URL: `{frontend_url}/settings?error={error_msg}`. Python exception strings can contain internal paths, DB error messages, stack-trace snippets.  
Impact: Information disclosure — exception messages visible in browser history, server logs, Zerodha postback logs.  
Fix: Map exception types to safe user-facing messages; never expose raw `str(e)` in redirects.

---

## [SECURITY] — backend/app/api/websocket.py

### Finding: WebSocket token revocation check is a single point of failure
**Status**: [CONFIRMED]  
Severity: MEDIUM  
File: backend/app/api/websocket.py:205-217  
Description: If the DB query for token revocation check throws an exception, the code catches it and closes the connection with "Authentication error". However, the logged message "WebSocket revocation check failed: {e} — closing connection" means an infrastructure blip (DB overload) will kick every live user off WebSocket simultaneously.  
Impact: Denial-of-service from a transient DB hiccup. Users lose real-time alerts mid-session.  
Fix: Retry once with a short delay before closing; allow connection on timeout (fail-open with shorter re-check interval is less bad than mass disconnect).

---

## [SECURITY] — backend/app/api/prometheus_metrics.py

### Finding: /metrics endpoint is publicly accessible, no auth
**Status**: [CONFIRMED]  
Severity: MEDIUM  
File: backend/app/api/prometheus_metrics.py:49  
Description: The `/metrics` Prometheus endpoint has no authentication. The docstring says "No auth required (internal only — protect at the reverse proxy / network layer)" — but there is no guarantee that reverse proxy protection is in place.  
Impact: Internal queue depths, WS connection counts, and error type distributions are disclosed. Low direct impact but useful for attackers doing reconnaissance.  
Fix: Add at minimum a shared-secret header check or IP allowlist; document the network-layer requirement explicitly in the deployment guide.

---

## [SECURITY] — backend/app/api/admin/auth.py

### Finding: Admin OTP is generated with `random.choices`, not `secrets`
**Status**: [CONFIRMED] — `random.choices(string.digits, k=6)` verified at auth.py:42  
Severity: MEDIUM  
File: backend/app/api/admin/auth.py:42  
Description: `_make_otp()` uses `random.choices(string.digits, k=6)`. Python's `random` module is a Mersenne Twister — it is not cryptographically secure. The internal state can be inferred if an attacker can observe enough OTP values (which is possible in a multi-admin scenario or via timing).  
Impact: An attacker who can observe previous OTPs can predict future ones.  
Fix: Replace `random.choices` with `secrets.choice` or `''.join(secrets.token_digits(6))`.

---

### Finding: Admin logout does not invalidate server-side state
**Status**: [CONFIRMED]  
Severity: LOW  
File: backend/app/api/admin/auth.py:207-210  
Description: Admin JWT is stateless — `/logout` just acknowledges, takes no server action. A stolen admin JWT remains valid until it expires (8 hours).  
Impact: If admin JWT is stolen (XSS, log exfiltration, etc.), it remains usable for up to 8 hours after the legitimate admin logs out.  
Fix: Maintain a Redis blocklist of logged-out admin JWTs with TTL = expiry time; check on every admin endpoint.

---

## [SECURITY] — backend/app/api/alerts.py

### Finding: alerts.py provides no test-alert rate limiting
**Status**: [CONFIRMED]  
Severity: MEDIUM  
File: backend/app/api/alerts.py:13-34  
Description: `POST /api/alerts/test` sends a WhatsApp message to any phone number provided by an authenticated user. There is no rate limiting on this endpoint.  
Impact: An authenticated user can spam arbitrary phone numbers (not just their own) with WhatsApp messages. The `phone_number` is not validated against the user's registered phone.  
Fix: Rate-limit this endpoint; validate that the supplied phone matches the user's guardian_phone or their own broker_email phone.

---

## [SECURITY] — backend/app/core/rate_limiter.py

### Finding: In-memory rate limiter is per-process and not shared across Celery workers
**Status**: [CONFIRMED]  
Severity: MEDIUM  
File: backend/app/core/rate_limiter.py:44  
Description: `RateLimiter._hits` is a plain Python dict. In a multi-process deployment (multiple uvicorn workers or gunicorn forks), each process has its own in-memory state. Rate limits effectively become N× more permissive where N = number of processes.  
Impact: Sync endpoint allows 10×N syncs per minute instead of 10; coach endpoint allows 10×N AI messages.  
Fix: Back rate limits with Redis (as already done in `rate_limit.py` — the Redis-backed version). Replace `rate_limiter.py` usages with `rate_limit.py` or migrate to Redis.

---

### Finding: rate_limiter.py is in-memory but rate_limit.py is Redis-backed — two competing systems
**Status**: [CONFIRMED]  
Severity: MEDIUM  
File: backend/app/core/rate_limiter.py, backend/app/core/rate_limit.py  
Description: Two entirely separate rate-limiting systems exist. Most endpoints use `rate_limiter.py` (in-memory). `rate_limit.py` (Redis-backed, per-account) exists but appears to be used by only a few endpoints. The in-memory one is NOT production-safe for multi-process deploys.  
Impact: Duplicate implementation leads to inconsistent enforcement; in-memory limits are easily bypassed at scale.  
Fix: Standardize on the Redis-backed `rate_limit.py` for all production endpoints.

---

## [SECURITY] — src/lib/api.ts

### Finding: JWT stored in localStorage — susceptible to XSS
**Status**: [CONFIRMED]  
Severity: MEDIUM  
File: src/lib/api.ts:49, src/contexts/BrokerContext.tsx:93  
Description: `AUTH_TOKEN_KEY` is stored and read from `localStorage`. Any XSS vulnerability in any component, third-party script, or browser extension can read and exfiltrate this token.  
Impact: Token theft via XSS — attacker gets full access to the victim's account until the 24-hour JWT expires.  
Fix: Store token in httpOnly cookie instead of localStorage. This is a major architectural change but is the industry-standard mitigation.  
Note: The current CSP (`'unsafe-inline'` for scripts) means browser-based XSS is still partially possible, compounding this issue.

---

## [SECURITY] — backend/app/main.py

### Finding: CSP includes 'unsafe-inline' for scripts
**Status**: [CONFIRMED]  
Severity: MEDIUM  
File: backend/app/main.py:246  
Description: `Content-Security-Policy` header includes `script-src 'self' 'unsafe-inline'`. This allows inline script execution which is the primary XSS vector — inline scripts injected by an attacker would be executed.  
Impact: Significantly weakens the XSS protection that CSP is supposed to provide. Allows any inline `<script>` to execute.  
Fix: Remove `'unsafe-inline'`; use nonces or hashes for any required inline scripts.

---

## [SECURITY] — backend/app/api/trades.py

### Finding: `/api/trades/stats` fetches ALL trades without pagination
**Status**: [CONFIRMED]  
Severity: MEDIUM  
File: backend/app/api/trades.py:71-86  
Description: `GET /api/trades/stats` does `select(Trade).where(broker_account_id == ...)` with no LIMIT or date filter. A user with many months of trading history will load all rows into memory.  
Impact: Memory exhaustion for heavy users; potential OOM in production. Could be used as a low-effort DoS by a user with many trades.  
Fix: Add date range filter (default: last 90 days) and LIMIT to stats query.

---

## [BUSINESS LOGIC] — backend/app/services/pnl_calculator.py

### Finding: P&L repair on startup is silently non-idempotent for edge cases
**Status**: [CONFIRMED]  
Severity: MEDIUM  
File: backend/app/main.py:125-161  
Description: The startup `_repair_nse_pnl()` task recalculates P&L using `(exit - entry) * qty`. This formula ignores brokerage, STT, exchange charges, and SEBI fees. The comment says "FIFO engine is authoritative" but the repair overwrites with a simplified formula.  
Impact: Users who rely on accurate net P&L (after charges) will see artificially inflated P&L figures for any trades repaired by this function.  
Fix: Do not recalculate P&L using a simplified formula in the repair task. If reconciliation with Zerodha is needed, use the authoritative `realised` field from Zerodha's API.

---

### Finding: FIFO real-time path does NOT apply lot_multiplier for MCX/CDS
**Status**: [CONFIRMED] — `calculate_trade_pnl_realtime()` at pnl_calculator.py:773-785 has no multiplier lookup  
Severity: HIGH  
File: backend/app/services/pnl_calculator.py:773-785  
Description: `calculate_trade_pnl_realtime()` (webhook path) calculates P&L as `(price_diff * match_qty)` without any `lot_multiplier`. The batch FIFO path correctly applies `lot_multiplier` for MCX/CDS instruments. The real-time path is used when a trade arrives via webhook during live trading.  
Impact: MCX and CDS traders see wrong real-time P&L displayed on the dashboard. For CRUDEOIL futures (lot = 100 barrels), the real-time P&L is 100× understated.  
Fix: Apply the same `lot_multiplier` logic in `calculate_trade_pnl_realtime()` as in `_process_symbol_trades()`.

---

## [BUSINESS LOGIC] — backend/app/services/behavior_engine.py

### Finding: `_detect_overtrading_burst` — daily caution only fires when `session_pnl < 0`
**Status**: [CONFIRMED] — line 576: `if session_pnl < 0:`. Profitable overtrades never trigger caution despite high loss probability.  
Severity: MEDIUM (upgraded from LOW — affects all profitable high-frequency traders)  
File: backend/app/services/behavior_engine.py:574-586  
Description: When `session_pnl >= 0` but `losing_in_burst > 0`, the function fires a caution. This logic path is reached because it falls through from the `if session_pnl > 0 and all_burst_profitable: pass` branch. This means a session with net positive P&L but one losing trade in a burst fires an alert. While arguably informational, the severity is labeled "caution" which may be noisy for active scalpers.  
Impact: False positive caution alerts for legitimate profitable scalping sessions.

---

### Finding: `_detect_size_escalation` — comparison uses quantity not lots
**Status**: [CONFIRMED]  
Severity: MEDIUM  
File: backend/app/services/behavior_engine.py:613  
Description: `sizes = [t.total_quantity or 1 for t in prior]` compares raw quantities. For options trades, `total_quantity` is already in units (e.g., 50 for 1 Nifty lot). But when comparing across different expiry dates of the same underlying, lot sizes can change (Nifty lot changed from 75 to 25 in Nov 2024). An escalation from 25 (post-change) to 50 would trigger but represent the same notional risk.  
Impact: Potentially spurious escalation alerts around lot-size change events.  
Fix: Normalize by underlying lot size when comparing quantities.

---

### Finding: `_detect_end_of_session_mis_panic` — MIS auto-squareoff time hardcoded 15:20, wrong for all product types
**Status**: [CONFIRMED] — actual: F&O MIS = 15:25, equity MIS = 15:15; code uses 15:20 for both  
Severity: MEDIUM  
File: backend/app/services/behavior_engine.py  
Description: The comment in `trading_defaults.py` line 142 says "MIS trades entered after 15:00 IST face auto-square-off at ~15:20." But the pattern fires at `15:10`, missing the 15:00-15:10 window entirely. The docstring in the engine header (line 45) says "15:10" which matches, but the trading_defaults.py comment says "15:00".  
Impact: MIS trades entered between 15:00 and 15:10 that are the riskiest (20 minutes to forced exit) are not detected.  
Fix: Lower the window start to 15:00, matching the risk description in trading_defaults.py.

---

### Finding: `_detect_fomo_entry` — pre-close threshold uses `fomo_open_symbols` not `fomo_close_window_symbols`
**Status**: [CONFIRMED] — threshold reuse verified; no `fomo_close_symbols` key defined in trading_defaults.py  
Severity: LOW  
File: backend/app/services/behavior_engine.py:998-999  
Description: Line 998 assigns `threshold = fomo_open_symbols` for `is_close_window` — the same threshold as the opening window. There is no dedicated `fomo_close_symbols` threshold. The description in COLD_START_DEFAULTS says "last 30 min of session (pre-close panic)" but the threshold is shared.  
Impact: Minor — likely intentional reuse, but it means pre-close FOMO always has the same threshold as opening FOMO rather than being independently tunable.

---

## [BUSINESS LOGIC] — backend/app/services/risk_detector.py

### Finding: RiskDetector still runs on sync path AND BehaviorEngine runs on the same sync — double alert generation
**Status**: [CONFIRMED] — both called at zerodha.py:821-882  
Severity: HIGH  
File: backend/app/api/zerodha.py:820-885  
Description: `sync/all` calls BOTH `risk_detector.detect_patterns()` (legacy) AND `run_behavior_engine_full_session` (new BehaviorEngine). The dedup logic for legacy alerts uses a 24-hour window keyed on `(trigger_trade_id, pattern_type)`. BehaviorEngine has its own dedup. But the two engines detect overlapping patterns (both detect overtrading, consecutive losses, etc.) and save to the same `risk_alerts` table.  
Impact: Users see duplicate alerts in the Alerts page — one from legacy RiskDetector and one from BehaviorEngine — for the same behavioral event. Confuses users.  
Fix: Remove legacy RiskDetector from the sync path entirely; it was supposed to be deprecated in session 21.

---

## [DATABASE & DATA INTEGRITY]

### Finding: Missing index on risk_alerts(broker_account_id, detected_at)
**Status**: [FALSE POSITIVE — index already exists] — `Index('idx_risk_alerts_broker_detected', 'broker_account_id', 'detected_at')` is in `models/risk_alert.py:11-12`  
Severity: ~~HIGH~~ → N/A  
Description: `GET /api/risk/alerts` queries `risk_alerts` with `WHERE broker_account_id = X AND detected_at >= Y ORDER BY detected_at DESC`. Without a composite index on `(broker_account_id, detected_at)`, this is a sequential scan that grows linearly with alert count.  
Impact: Response time degrades as alert count grows. At 10,000 alerts (6-12 months of heavy use), this query could take seconds.  
Fix: Add `CREATE INDEX idx_risk_alerts_account_time ON risk_alerts(broker_account_id, detected_at DESC)`.

---

### Finding: Missing index on completed_trades(broker_account_id, exit_time)
**Status**: [FALSE POSITIVE — index already exists] — `Index('idx_completed_trades_broker_exit', 'broker_account_id', 'exit_time')` is in `models/completed_trade.py:20`  
Severity: ~~HIGH~~ → N/A  
Description: Analytics endpoint queries `CompletedTrade` with `WHERE broker_account_id = X AND exit_time >= Y`. Without a composite index this is a full table scan.  
Impact: Analytics page becomes slow as trade count grows.  
Fix: Add composite index on `(broker_account_id, exit_time)`.

---

### Finding: `_build_feature` uses hardcoded `is_expiry = exit_ist.weekday() == 3` — same bug as documented
**Status**: [CONFIRMED] — `exit_ist.weekday() == 3` at pnl_calculator.py:624 still hardcoded despite behavior_engine.py being fixed  
Severity: HIGH  
File: backend/app/services/pnl_calculator.py:624  
Description: `is_expiry_day = exit_ist.weekday() == 3 if exit_ist else False` — this is exactly the hardcoded Thursday bug documented in MEMORY.md session 27. The behavior_engine.py was fixed to use `parse_symbol().expiry_date`, but the feature computation in `pnl_calculator.py` still uses the hardcoded weekday check.  
Impact: `is_expiry_day` feature flag in ML features is wrong for weekly options with non-Thursday expiry (introduced SEBI mandate for weekly expirations on Fridays/Mondays for some indices). Will corrupt ML training data.  
Fix: Use `is_expiry_day(ct.tradingsymbol, exit_ist.date())` from `instrument_parser.py`.

---

### Finding: CompletedTrade.pnl_pct nullable — not populated for historic records
**Status**: [CONFIRMED]  
Severity: LOW  
File: backend/app/main.py:166-198  
Description: Startup backfill for `pnl_pct` runs on every deploy. For accounts with thousands of trades, this is an O(n) operation running on the critical startup path (main uvicorn process).  
Impact: Slow startup times for large accounts; repeated DB writes on every deploy even when no backfill is needed.  
Fix: Track a migration flag in DB so backfill only runs once; or run as a one-off migration rather than startup code.

---

## [API ENDPOINTS]

### Finding: `GET /api/zerodha/token/validate` does not exist in backend
**Status**: [FALSE POSITIVE — endpoint exists] — `@router.get("/token/validate")` is at `backend/app/api/zerodha.py:1111`. Token validation works. Original audit missed it.  
Severity: ~~CRITICAL~~ → N/A  
Description: `BrokerContext.validateToken()` calls `GET /api/zerodha/token/validate`. This endpoint does NOT exist anywhere in the backend. The `zerodha.py` router has no `/token/validate` route.  
Impact: `validateToken()` will always return a 404, causing an unhandled error (axios will throw). The `catch` block sets `tokenStatus = 'unknown'` silently, so users see no error — but token validation never works. The Token Expired Banner and re-auth flows depend on this.  
Fix: Implement the endpoint in zerodha.py that checks if the stored access_token is still valid by making a lightweight Kite API call.

---

### Finding: `POST /api/zerodha/sync/all` has no rate limiter per account — only in-memory global
**Status**: [CONFIRMED]  
Severity: MEDIUM  
File: backend/app/api/zerodha.py:772-776  
Description: The `sync_limiter` is an in-memory global with 10 requests/60s. As discussed above, this is not shared across processes. Additionally, the tab-switch auto-sync in BrokerContext fires this on every tab focus (30s cooldown client-side). A user with multiple tabs open could easily hit the limit with legitimate usage.  
Impact: Users with multiple tabs get 429 errors during normal usage.

---

### Finding: `GET /api/analytics/progress` uses naive `datetime.combine` without timezone
**Status**: [CONFIRMED] — also causes week boundaries to be UTC midnight (05:30 IST), so Monday IST morning trades appear in previous week  
Severity: MEDIUM  
File: backend/app/api/analytics.py:140-141  
Description: `datetime.combine(start_date, datetime.min.time())` creates a naive datetime without timezone. When compared against `Trade.order_timestamp` (which is timezone-aware UTC), SQLAlchemy/PostgreSQL may raise a warning or silently treat the naive datetime as UTC, which would be correct in this case — but it is fragile and non-explicit.  
Impact: If the DB server or SQLAlchemy changes behavior regarding tz-aware vs naive datetime comparisons, queries silently return wrong results.  
Fix: Use `datetime.combine(start_date, time.min, tzinfo=timezone.utc)` explicitly.

---

### Finding: `/api/analytics/progress` — `best_streak` is hardcoded fallback
**Status**: [CONFIRMED] — `max(days_clean, 7)` at analytics.py:252  
Severity: LOW  
File: backend/app/api/analytics.py:252  
Description: `"best_streak": max(days_clean, 7)` — the best streak is always at least 7, hardcoded. This is not calculated from actual history.  
Impact: Users with fewer than 7 days of clean trading always see 7 as their best streak, which is wrong.  
Fix: Actually compute best streak from history.

---

## [FRONTEND-BACKEND CONTRACT]

### Finding: `Alert.severity` type mismatch — frontend expects `'critical'|'high'|'medium'|'positive'` but backend sends `'danger'|'caution'`
**Status**: [CONFIRMED] — TypeScript interface at api.ts:128 does not include `'danger'|'caution'`  
Severity: HIGH  
File: src/types/api.ts:128, backend/app/services/behavior_engine.py  
Description: The TypeScript `Alert` interface defines `severity: 'critical' | 'high' | 'medium' | 'positive'`. The backend BehaviorEngine only produces `'danger'` or `'caution'`. The frontend AlertContext maps these, but `src/types/api.ts` has the wrong enumeration. Any code that switches on `severity` using the interface type will have dead branches for 'danger'/'caution' and will not handle them.  
Impact: TypeScript types give false safety; runtime comparisons against 'danger' work because JS is duck-typed, but the type definition is misleading and will cause errors for new developers.  
Fix: Update `Alert.severity` to `'danger' | 'caution' | 'critical' | 'high' | 'medium' | 'positive'` to cover all possible values.

---

### Finding: `CompletedTrade.pnl_pct` field missing from TypeScript interface
**Status**: [CONFIRMED] — `pnl_pct` is in the DB model but not in `src/types/api.ts:99-121`  
Severity: MEDIUM  
File: src/types/api.ts:99-121  
Description: The backend `CompletedTrade` model has a `pnl_pct` field (added in a recent migration). The frontend `CompletedTrade` TypeScript interface does not include `pnl_pct`.  
Impact: Frontend cannot use `pnl_pct` without TypeScript errors; any component that reads it gets typed as `undefined`.  
Fix: Add `pnl_pct?: number | null` to the frontend interface.

---

### Finding: `RiskState` interface missing fields returned by backend
**Status**: [CONFIRMED] — backend `RiskStateResponse` has `recommendations: List[str]` (no `status_message`, no `last_updated`); TypeScript interface has `status_message` and `last_updated` but not `recommendations`  
Severity: MEDIUM  
File: src/types/api.ts:1-6  
Description: The frontend `RiskState` interface has `status_message` but the backend `RiskStateResponse` schema has `recommendations: List[str]` and `active_patterns: List[str]`. The `status_message` field is not in the backend schema at all.  
Impact: Frontend reads `risk_state.status_message` which doesn't exist on the actual API response — will always be `undefined`.  
Fix: Align `RiskState` with `RiskStateResponse`: remove `status_message`, add `recommendations`.

---

## [FRONTEND CODE QUALITY]

### Finding: `console.error` and `console.log` calls left throughout frontend
**Status**: [CONFIRMED]  
Severity: LOW  
File: src/lib/api.ts:79, src/contexts/BrokerContext.tsx:101,143,203, multiple others  
Description: Multiple `console.error` and `console.log` calls remain in production code paths (not behind a DEBUG flag). These leak internal API error details, state transitions, and potentially partial token information to browser devtools.  
Impact: Information disclosure to technical users who open devtools; also pollutes production logs.  
Fix: Replace with a configurable logger that suppresses output in production (`VITE_ENV === 'production'`); or explicitly allow specific logging and remove ad-hoc console calls.

---

### Finding: BrokerContext.validateToken calls non-existent endpoint — returns 'unknown' forever
**Status**: [FALSE POSITIVE — endpoint exists] — the backend endpoint `GET /api/zerodha/token/validate` is at `zerodha.py:1111`. This finding was based on the same incorrect premise as the C-01 finding above.  
Severity: ~~HIGH~~ → N/A  
Description: (Same as API finding above.) `validateToken()` calls `/api/zerodha/token/validate` which 404s. The catch block sets `tokenStatus = 'unknown'`. The `useEffect` on line 293-297 calls this on every account load. So every user is always in `tokenStatus: 'unknown'` state.  
Impact: `TokenExpiredBanner` component and any logic gated on `tokenStatus === 'expired'` never fires. Expired Zerodha tokens are not detected, and users can be confused by silent failures.

---

### Finding: Missing error boundaries around lazy-loaded analytics tabs
**Status**: [CONFIRMED]  
Severity: MEDIUM  
File: src/pages/Analytics.tsx  
Description: Analytics tabs use `lazy()` + `<Suspense>`. If a lazy-loaded tab component throws an error after loading (e.g., data parsing error), there's no `ErrorBoundary` wrapping the Suspense — the error propagates up and could crash the whole page.  
Impact: One broken analytics tab takes down the entire Analytics page.  
Fix: Wrap each Suspense boundary with an `<ErrorBoundary>` that shows a "failed to load" message for just that tab.

---

### Finding: Guest mode interceptor uses `config.adapter` override — bypasses all interceptors after the first
**Status**: [CONFIRMED]  
Severity: LOW  
File: src/lib/guestMode.ts (implied), src/lib/api.ts:31-46  
Description: Setting `config.adapter` to return mock data directly bypasses the response interceptor. The response interceptor handles `503 → maintenance redirect` and `401 → token-expired event`. Guest mode responses skip these.  
Impact: In guest mode, if a mock returns a 503-like response, the maintenance redirect doesn't fire. Low impact since demo data is controlled, but the bypassing is architecturally risky.

---

## [INFRASTRUCTURE & CONFIG]

### Finding: APScheduler runs inside the FastAPI process — starts in EVERY worker, causing N× duplicate reports
**Status**: [CONFIRMED] — `scheduler = AsyncIOScheduler()` module-level, `start_scheduler()` in lifespan with no worker guard; `scheduler.start()` at retention_tasks.py:146  
Severity: CRITICAL (upgraded — duplicate EOD reports to all users on any multi-worker deploy)  
File: backend/app/tasks/retention_tasks.py  
Description: `AsyncIOScheduler` is started in the FastAPI `lifespan` handler (not Celery beat). If the FastAPI process dies and does not restart within the scheduled minute, EOD reports and morning briefs for that minute are silently skipped. Unlike Celery beat, APScheduler has no persistent state.  
Impact: Users miss scheduled EOD reports if the server crashes and restarts slowly (e.g., OOM kill, deploy restart > 1 min). No retry, no error.  
Fix: Move EOD/morning report scheduling into Celery beat (already configured with redbeat for persistence); remove APScheduler dependency.

---

### Finding: Celery `worker_concurrency=100` with default prefork pool — uses 100 OS processes
**Status**: [CONFIRMED] — `worker_concurrency=100` at celery_app.py:69  
Severity: HIGH  
File: backend/app/core/celery_app.py:69  
Description: `worker_concurrency=100` with the default Celery prefork pool spawns 100 OS processes. Each process loads all Django/SQLAlchemy code (~100MB+). Total memory: ~10GB just for workers.  
Impact: On any free/cheap hosting (Render free = 512MB, $7/mo = 512MB), the workers will be OOM-killed immediately. The comment says "use --pool=gevent" but this is not enforced at startup.  
Fix: Either enforce `--pool=gevent` in the Procfile/Dockerfile command, or reduce `worker_concurrency` to 4-8 for prefork, or document clearly that this requires >10GB RAM.

---

### Finding: `ZERODHA_API_KEY` is optional but failures are silent
**Status**: [CONFIRMED]  
Severity: MEDIUM  
File: backend/app/core/config.py:18  
Description: `ZERODHA_API_KEY: Optional[str] = None`. If not set, the Zerodha integration silently fails — no startup error. The `/connect` endpoint would use `zerodha_client` which has `api_key=None`.  
Impact: Misconfigured production deployments (missing env vars) fail silently rather than fast.  
Fix: Add startup validation (similar to `ENCRYPTION_KEY` check) that warns loudly if `ZERODHA_API_KEY` is unset.

---

### Finding: NSE holiday calendar is hardcoded and incomplete after 2026
**Status**: [CONFIRMED] — 2026 list has only 6 entries; missing Diwali, Maharashtra Day, Mahashivratri, Ganesh Chaturthi, Guru Nanak, Eid, etc.  
Severity: MEDIUM  
File: backend/app/core/market_hours.py:42-52  
Description: `NSE_HOLIDAYS_2026` only has 6 entries (several major Indian holidays are missing: Mahashivratri, Holi, Ram Navami, Maharashtra Day, Ganesh Chaturthi, Guru Nanak Jayanti, Diwali, etc.). The combined `NSE_HOLIDAYS` has no entries after December 2026.  
Impact: After December 2026, `is_trading_holiday()` returns False for all days, including NSE holidays. Market hours logic, `market_minutes()` duration calculation, and behavioral pattern detection will be wrong on holidays — alerts fire on non-trading days.  
Fix: Add complete 2026 holiday list (refer to NSE official calendar); add `NSE_HOLIDAYS_2027` for the following year; add a runtime warning if `today > max(NSE_HOLIDAYS)`.

---

### Finding: `ENCRYPTION_KEY` failure raises RuntimeError crashing entire server
**Status**: [CONFIRMED — intentional design, but recovery path should be documented]  
Severity: INFO  
File: backend/app/main.py:67-76  
Description: Good design: validates the key at startup and raises RuntimeError. However, the error message says "all stored access tokens undecryptable" which is accurate but alarming. No recovery path is documented.  
Impact: If ENCRYPTION_KEY changes accidentally (e.g., env var reset on Render free tier), all users are locked out simultaneously and must reconnect.  
Fix: Consider supporting key rotation (store key version ID with encrypted values); document the recovery procedure.

---

## [EDGE CASES & RACE CONDITIONS]

### Finding: Concurrent Celery workers can both claim behavior_lock — 15s TTL is too short
**Status**: [CONFIRMED] — TTL=15s at trade_tasks.py:330  
Severity: MEDIUM  
File: backend/app/tasks/trade_tasks.py:322-330  
Description: `behavior_lock` TTL is 15 seconds. BehaviorEngine `analyze()` runs up to 5 DB queries. Under load, if a DB query takes >5s (connection pool exhaustion, Supabase cold start), the lock expires and a second worker claims it, running behavioral detection concurrently for the same account.  
Impact: Duplicate behavioral alerts; race condition in `TradingSessionService.update_risk_score()` which does a read-modify-write without atomic increment.  
Fix: Increase behavior_lock TTL to 60 seconds; use atomic INCR in Redis for risk_score updates.

---

### Finding: `_sync_locks` dictionary grows unbounded (memory leak)
**Status**: [CONFIRMED]  
Severity: MEDIUM  
File: backend/app/api/zerodha.py:66-74  
Description: `_sync_locks: dict[str, asyncio.Lock] = {}` is a module-level dict. Every unique `account_id_str` that calls `sync/all` adds a Lock object that is never removed. For an application with many users, this grows indefinitely.  
Impact: Memory leak. For 10,000 users, stores 10,000 Lock objects — small but grows forever.  
Fix: Use a `WeakValueDictionary` or explicitly clean up locks after use; or use Redis-based locking for cross-process correctness.

---

### Finding: Webhook postback checksum verified AFTER account status check — logic order issue
**Status**: [CONFIRMED — minor]  
Severity: LOW  
File: backend/app/api/webhooks.py:100-144  
Description: The code checks account existence and status (lines 100-144) before verifying the checksum (lines 110-128). This means an attacker who knows a valid `broker_account_id` and forges a webhook payload can confirm whether an account exists (gets "connected" vs "deleted/suspended" response without needing a valid checksum) until the checksum is checked. The current code checks checksum at line 110-128 but has `if not account` before it.  
Impact: Very minor information disclosure — confirms account existence to an attacker who can observe response differences. Low severity given other protections.

---

### Finding: No timezone normalization in analytics `get_period_stats` — naive datetimes
**Status**: [CONFIRMED — same as the finding above for progress endpoint]  
Severity: MEDIUM  
File: backend/app/api/analytics.py:138-145  
Description: `datetime.combine(start_date, datetime.min.time())` creates naive datetime. `Trade.order_timestamp` is stored in UTC. The comparison `Trade.order_timestamp >= naive_datetime` may work on PostgreSQL (implicitly treating naive as UTC) but is undefined behavior per Python's datetime spec.  
Impact: Under certain PostgreSQL timezone settings or future SQLAlchemy version changes, period boundaries could shift by IST offset (+5:30), causing trades to appear in the wrong week.  
Fix: Always use timezone-aware datetimes: `datetime.combine(start_date, time.min).replace(tzinfo=timezone.utc)`.

---

## [KNOWN GAPS FROM MEMORY.md]

### Finding: WhatsApp Gupshup Day 2 migration not done — Twilio code still used
**Status**: [CONFIRMED — known gap, tracked in MEMORY.md]  
Severity: MEDIUM  
File: backend/app/tasks/alert_tasks.py:66, backend/app/services/whatsapp_service.py  
Description: `send_whatsapp_alert` still references Twilio via `AlertService`. The MEMORY.md states "Day 2 code (whatsapp_service.py rewrite) still pending." The config has both Twilio and Gupshup fields.  
Impact: If Twilio credentials are removed in favor of Gupshup, WhatsApp alerts will silently fail.  
Fix: Complete the Gupshup migration as documented; remove Twilio dependency.

---

### Finding: NSE holiday calendar 2026 is incomplete — 6 entries vs expected ~12
**Status**: [CONFIRMED — duplicate of finding above]  
Severity: MEDIUM  
File: backend/app/core/market_hours.py:42-48  
Description: `NSE_HOLIDAYS_2026` is missing: Mahashivratri (~Mar), Holi (~Mar), Ram Navami/Good Friday (~Apr), Maharashtra Day (May 1), Buddha Purnima (~May), Bakri Id (~Jun), Muharram (~Jul), Independence Day already included, Ganesh Chaturthi (~Aug), Dussehra (~Oct), Diwali (~Oct/Nov), Guru Nanak Jayanti (~Nov).  
Impact: `is_trading_holiday()` returns False for 6-8 actual NSE holidays in 2026. `market_minutes()` duration calculations will over-count trading time on holidays. Pattern detection (end-of-session-MIS, expiry-day) can fire on days the market is closed.  
Fix: Download the complete 2026 NSE holiday list from https://www.nseindia.com/resources/exchange-communication-holidays

---

## [SECURITY — ADMIN]

### Finding: Admin broadcast has no per-message rate limit or message content filtering
**Status**: [CONFIRMED]  
Severity: MEDIUM  
File: backend/app/api/admin/broadcast.py  
Description: Admin can broadcast up to 700 characters to all users with phone numbers. No rate limit on how frequently broadcasts can be sent. No content filtering. A compromised admin account (OTP stolen) could send spam/phishing to all users.  
Impact: Compromised admin = ability to send phishing messages to entire user base via WhatsApp.  
Fix: Add a maximum of N broadcasts per 24 hours per admin; add a mandatory confirmation step (dry_run must be true first and returned count shown before actual send).

---

## [FRONTEND SPECIFIC]

### Finding: BlowupShield page uses module-level cache object — stale across account switches
**Status**: [CONFIRMED — low real-world impact since multi-account same browser is rare]  
Severity: MEDIUM  
File: src/pages/BlowupShield.tsx:16-20  
Description: `shieldCache` is a module-level object. If a user logs out and logs back in as a different account (or uses multi-account), the cache may serve stale data from the previous account for up to 5 minutes.  
Impact: Data leakage between accounts if account switching occurs (unlikely but possible in shared browser).  
Fix: Include `accountId` in cache key validation (already present in `shieldCache.accountId`) — verify the comparison logic is correct.

---

### Finding: MyPatterns.tsx and BlowupShield.tsx have unhandled promise in useEffect
**Status**: [CONFIRMED]  
Severity: LOW  
File: src/pages/MyPatterns.tsx, src/pages/BlowupShield.tsx  
Description: Multiple `useEffect` hooks call async functions directly without proper cleanup. If the component unmounts while a fetch is in-flight, the `setState` calls will run on an unmounted component.  
Impact: React warning "Can't perform a state update on an unmounted component"; potential memory leaks.  
Fix: Use AbortController pattern to cancel in-flight requests on unmount.

---

## [SECURITY — DATA]

### Finding: User's Zerodha `access_token` is stored encrypted but `api_key` is stored plaintext
**Status**: [CONFIRMED — low severity, api_key alone insufficient for access]  
Severity: LOW  
File: backend/app/models/broker_account.py:34  
Description: `api_key: Mapped[str] = mapped_column(String, nullable=True)` — the API key is stored in plaintext. The `api_secret_enc` is encrypted with Fernet. API keys from KiteConnect developer console are not single-use secrets (they identify the app, not the user's session), so this is lower severity than storing the access_token in plaintext. However, the API key combined with the user's credentials enables brute-forcing the OAuth flow.  
Impact: DB dump leaks all API keys. Low severity since API key alone isn't sufficient for access.  
Fix: Consider encrypting `api_key` as well for defense in depth.

---

## [INFRASTRUCTURE]

### Finding: Two schedulers running simultaneously — APScheduler AND Celery beat
**Status**: [CONFIRMED — confusing architecture; overlap may cause double-sends for some account types]  
Severity: MEDIUM  
File: backend/app/tasks/retention_tasks.py, backend/app/core/celery_app.py  
Description: Commodity EOD is in Celery beat schedule (`celery_app.py:116`). Equity EOD is in APScheduler (`retention_tasks.py`). If both a Celery beat worker and the FastAPI process run simultaneously, commodity accounts might receive reports from both schedulers.  
Impact: Double-sends for commodity users on overlap (the equity APScheduler dispatches via `send_eod_report` which skips COMMODITY accounts, but the commodity Celery beat task sends to all accounts with phones). The filter in `_send_eod_for_account` (line 48-49) skips COMMODITY — so this is actually OK. But the architecture is confusing and error-prone.  
Fix: Document explicitly which scheduler handles which report type; consider consolidating.

---

## [API — MISSING ENDPOINT]

### Finding: Multiple frontend API calls to endpoints that may not exist
**Status**: [FALSE POSITIVE — verified all BrokerContext endpoints exist] — `token/validate` exists (zerodha.py:1111), `sync/all` exists, `accounts` exists. No missing endpoints found.  
Severity: ~~HIGH~~ → N/A  
Description: Beyond `token/validate`, BrokerContext calls `POST /api/zerodha/sync/all` (verified exists), `GET /api/zerodha/accounts` (verified exists). No other missing endpoints found in this file. The token/validate issue is the primary blocker.

---

## [SECURITY — WEBHOOK]

### Finding: Webhook endpoint has no authentication — relies entirely on checksum
**Status**: [CONFIRMED — intentional and correct; industry standard for webhooks]  
Severity: INFO  
File: backend/app/api/webhooks.py:72  
Description: `POST /api/webhooks/zerodha/postback` has no JWT auth (correct — Zerodha can't authenticate). Relies on the HMAC-SHA256 checksum. This is industry standard for webhooks. The checksum is correctly implemented. Flagged as INFO only.

---

## [CELERY TASKS — IDEMPOTENCY]

### Finding: `eod_sync_all_accounts` task — no evidence of idempotency for per-account processing
**Status**: [CONFIRMED — FIFO lock protects against concurrent runs but task retry without proper guard can duplicate]  
Severity: MEDIUM  
File: backend/app/tasks/trade_tasks.py (referenced in celery schedule)  
Description: The `eod-sync` beat task at 15:35 IST calls `eod_sync_all_accounts`. If Celery retries (network error, worker crash), the task re-runs and potentially creates duplicate CompletedTrade records if the delete-then-recreate FIFO pattern is not guarded against concurrent runs.  
Impact: Duplicate CompletedTrade records could cause double-counting in analytics and duplicate behavioral alerts.  
Fix: Verify `eod_sync_all_accounts` acquires the fifo_lock per account before running FIFO.

---

## [FRONTEND-BACKEND CONTRACT]

### Finding: `DashboardStats` interface unused — backend returns different shape
**Status**: [CONFIRMED] — backend returns `{risk_score: {...}}`, interface has `{total_pnl, win_rate, total_trades, max_drawdown}`; endpoint not consumed by Dashboard.tsx  
Severity: LOW  
File: src/types/api.ts:8-13  
Description: `DashboardStats` interface defines `{total_pnl, win_rate, total_trades, max_drawdown}`. The actual `GET /api/analytics/dashboard-stats` endpoint returns `{"risk_score": {...}}`. These do not match.  
Impact: Frontend code using `DashboardStats` type would have wrong field names and get `undefined` at runtime.

---

---

# PHASE 2 DEEP LOGIC AUDIT — Appended 2026-06-11
**Scope**: All 5 subsystems — Behavioral Engine, P&L/Analytics Math, API Contracts, Frontend Logic, Backend Infrastructure/Tasks  
**Method**: 5 parallel specialist audit agents, each reading every file in their domain

---

## SECTION A: BEHAVIORAL ENGINE LOGIC

### A-1: `_detect_cooldown_violation` not in `_run_all_detectors`
**Status**: [INTENTIONAL — not a bug] — Session 33 decision (documented in MEMORY.md): "cooldown_violation removed as alert (kept in engine for analytics)." Deliberately suppressed. The method and RISK_DELTAS entry exist for future analytics use only.  
**File**: `backend/app/services/behavior_engine.py:334–358`  
**Severity**: ~~CRITICAL~~ → N/A

---

### A-2: Expiry day holiday adjustment not implemented in `is_expiry_day()`
**Status**: [CONFIRMED] — the docstring at instrument_parser.py:192-196 even acknowledges this limitation  
**File**: `backend/app/services/instrument_parser.py:181–209`  
**Severity**: HIGH  
**Finding**: Monthly expiry uses `_last_thursday_of_month()` without checking `is_trading_holiday()`. When last Thursday is an NSE holiday, NSE moves expiry to Wednesday. Affects `no_stoploss` modifier, `fomo_entry` threshold, `expiry_day_overtrading` — all misfire on actual expiry day.

---

### A-3: NSE_HOLIDAYS_2026 has only 6 of ~14 holidays
**Status**: [CONFIRMED] — verified at market_hours.py:42-49  
**File**: `backend/app/core/market_hours.py:42–49`  
**Severity**: HIGH  
**Finding**: Missing Mahashivratri, Eid, Ambedkar Jayanti, Maharashtra Day, Ganesh Chaturthi, Diwali, Guru Nanak. `is_trading_holiday()` returns False on actual holidays.

---

### A-4: Full-session replay dedup uses `now_utc` not trade exit_time — retry causes duplicate danger escalation
**Status**: [CONFIRMED] — `now_utc = datetime.now(timezone.utc)` at trade_tasks.py:669; `last_fired[alert.pattern_type] = now_utc` at line 709. On task retry, today_patterns already contains the pattern → severity escalates to `danger` → duplicate guardian WhatsApp fires.  
**File**: `backend/app/tasks/trade_tasks.py:669, 709`  
**Severity**: HIGH  
**Finding**: On task retry after crash, `today_patterns` is pre-populated causing `consecutive_loss_streak` to escalate to `danger` on every re-run, triggering repeated guardian WhatsApp messages.

---

### A-5: Overtrading daily caution gated on `session_pnl < 0` — profitable overtrades never alerted
**Status**: [CONFIRMED] — `if session_pnl < 0:` at behavior_engine.py:576  
**File**: `backend/app/services/behavior_engine.py:576`  
**Severity**: MEDIUM  
**Finding**: Daily overtrading caution only fires when `session_pnl < 0`. A profitable trader with 8+ trades/day never sees a caution despite SEBI data showing >7 trades/day has 94% loss probability.

---

### A-6: `fomo_entry` pre-close window uses open-window threshold (copy-paste error)
**Status**: [CONFIRMED — likely copy-paste, no `fomo_close_symbols` key in trading_defaults.py]  
**File**: `backend/app/services/behavior_engine.py:999`  
**Severity**: MEDIUM  
**Finding**: Pre-close FOMO uses `fomo_open_symbols` (2 underlyings) threshold. No `fomo_close_symbols` defined in `trading_defaults.py`. Undocumented, potentially intentional but inconsistent.

---

### A-7: `end_of_session_mis_panic` hardcodes wrong auto-squareoff time (15:20)
**Status**: [CONFIRMED]  
**File**: `backend/app/services/behavior_engine.py:1626–1675`  
**Severity**: MEDIUM  
**Finding**: Actual: F&O MIS = 15:25, equity MIS = 15:15. Code uses 15:20 for both. Wrong urgency shown to users.

---

### A-8: `iv_crush_behavior` and `premium_destruction` both fire on same trade — double alert
**Status**: [CONFIRMED] — both detectors in `_run_all_detectors`, no mutual exclusion; iv_crush requires hold_min < 30, premium_destruction has no hold constraint  
**File**: `backend/app/services/behavior_engine.py:1359–1466`  
**Severity**: MEDIUM  
**Finding**: A LONG option losing 65% premium in 20 min triggers both. Inflates risk score by +35 for a single event.

---

### A-9: Duplicate `no_stoploss_monthly_*` keys in `trading_defaults.py`
**Status**: [CONFIRMED] — both at lines 111-112 and 167-168  
**File**: `backend/app/core/trading_defaults.py:111–112 and 167–168`  
**Severity**: LOW  
**Finding**: Both keys defined twice. Python uses last definition. Future edit to one copy silently ignored.

---

### A-10: `excess_exposure` skips accounts with capital < ₹10,000
**Status**: [CONFIRMED] — `if not capital or float(capital) < 10000: return None` at behavior_engine.py:848  
**File**: `backend/app/services/behavior_engine.py:845–887`  
**Severity**: MEDIUM  
**Finding**: `if not capital or float(capital) < 10000: return None` — most under-capitalised traders never get over-exposure alerts.

---

### A-11: `early_exit` max_winner_min ceiling of 20 min misses disposition effect
**Status**: [CONFIRMED] — `max_winner_min = ctx.thresholds.get("early_exit_winner_max_min", 20)` at behavior_engine.py:1151  
**File**: `backend/app/services/behavior_engine.py:1130–1171`  
**Severity**: MEDIUM  
**Finding**: Requires `avg_winner_hold < 20 min`. Trader holding winners 25–40 min but losers for hours (classic disposition effect) never gets flagged.

---

### A-12: `rapid_reentry`, `no_stoploss`, `post_loss_recovery_bet` not in `_STRATEGY_SUPPRESSED`
**Status**: [CONFIRMED] — `_STRATEGY_SUPPRESSED = {revenge_trade, martingale_behaviour, size_escalation, consecutive_loss_streak}` at behavior_engine.py:325-330; the three missing patterns confirmed absent  
**File**: `backend/app/services/behavior_engine.py:325–330`  
**Severity**: MEDIUM  
**Finding**: These three patterns generate false positives on legitimate hedge legs of multi-leg strategies.

---

### A-13: NULL `duration_minutes` causes `iv_crush_behavior` false positive
**Status**: [CONFIRMED for iv_crush — `hold_min = ct.duration_minutes or 0` at behavior_engine.py:1368; 0 < hold_threshold(30) passes the guard, spurious alert fires. no_stoploss direction differs: 0 < threshold is True → alert fires, which may also be wrong depending on intent]  
**File**: `backend/app/services/behavior_engine.py:1050, 1368`  
**Severity**: MEDIUM  
**Finding**: `ct.duration_minutes or 0` — zero duration causes iv_crush_behavior to fire spuriously for any option trade with NULL duration.

---

## SECTION B: P&L AND ANALYTICS MATH

### B-1: `calculate_trade_pnl_realtime()` missing lot multiplier for MCX/CDS
**Status**: [CONFIRMED] — same root cause as C-02 in Phase 1; confirmed no multiplier at pnl_calculator.py:773-785  
**File**: `backend/app/services/pnl_calculator.py:774–784`  
**Severity**: CRITICAL  
**Finding**: Real-time webhook P&L has no lot multiplier. CRUDEOIL (100 bbl/lot): live P&L shown 100x understated. NATURALGAS (multiplier 1250): 1250x error. Corrupts behavioral alerts that use Trade.pnl before nightly EOD reconciliation runs. (Same root cause as C-02 in original audit — confirmed with additional detail.)

---

### B-2: `is_expiry` hardcodes Thursday in `pnl_calculator.py` feature computation
**Status**: [CONFIRMED] — `is_expiry = exit_ist.weekday() == 3 if exit_ist else False` at pnl_calculator.py:624; same as H-01  
**File**: `backend/app/services/pnl_calculator.py:624`  
**Severity**: HIGH  
**Finding**: `is_expiry = exit_ist.weekday() == 3`. NIFTY weekly moved to Wednesday 2024; BANKNIFTY also Wednesday, FINNIFTY Tuesday, MIDCPNIFTY Monday. All `CompletedTradeFeature.is_expiry_day` entries wrong — corrupts conditional performance analytics. (H-01 in original audit — confirmed still unfixed.)

---

### B-3: Progress endpoint win rate uses `Trade.pnl` not `CompletedTrade` — win rate halved
**Status**: [CONFIRMED] — `select(Trade)` at analytics.py:137; opening fills with pnl=0 in denominator but not in winners list  
**File**: `backend/app/api/analytics.py:137–159`  
**Severity**: HIGH  
**Finding**: Opening fills have `pnl = 0`. For 10 round-trips: denominator = 20 raw fills vs 10 completed trades. Displayed win rate approximately halved vs Overview tab.

---

### B-4: UTC week boundaries in progress/analytics — week-over-week data off by 5.5 hours
**Status**: [CONFIRMED] — naive `datetime.combine(start_date, datetime.min.time())` at analytics.py:140-141  
**File**: `backend/app/api/analytics.py:126–141`  
**Severity**: HIGH  
**Finding**: `datetime.combine(start_date, datetime.min.time())` creates naive datetimes. Week starts at UTC midnight = 05:30 IST Monday. Monday morning IST trades appear in previous week.

---

### B-5: `best_streak` hardcoded floor of 7 — fabricated metric
**Status**: [CONFIRMED] — `max(days_clean, 7)` at analytics.py:252  
**File**: `backend/app/api/analytics.py:252`  
**Severity**: MEDIUM  
**Finding**: `max(days_clean, 7)` — new users always see "7-day best streak" that never happened. Violates mirror-not-blocker principle.

---

### B-6: Profit factor returns 0 when no losses — implies no edge
**Status**: [CONFIRMED] — `if losers else 0` at analytics.py:304 and 1097  
**File**: `backend/app/api/analytics.py:304 and 1097`  
**Severity**: MEDIUM  
**Finding**: `if losers else 0` — zero implies no edge, opposite of reality. Should return `None` displayed as infinity.

---

### B-7: VaR 95% index calculation wrong on small sample sizes
**Status**: [CONFIRMED] — `idx_5 = max(0, int(len * 0.05))` at analytics.py:682; for ≤19 days, idx_5=0 = worst day always  
**File**: `backend/app/api/analytics.py:681–683`  
**Severity**: MEDIUM  
**Finding**: `int(len * 0.05)` — for ≤19 days of data, VaR 95% always equals worst single day.

---

### B-8: Timing heatmap UTC→IST arithmetic wrong — 50% of fallback trades in wrong hour
**Status**: [FALSE POSITIVE — formula is correct] — manually verified: `(h*60 + m + 330) // 60 % 24` correctly adds 5h30m offset for all values of h and m. Example: UTC 09:30 → (540+30+330)//60=15 = IST 15:00 ✓. The primary path uses `feat.entry_hour_ist` (already IST); the fallback formula is correct. No off-by-one found.  
**File**: `backend/app/api/analytics.py:1594`  
**Severity**: ~~MEDIUM~~ → N/A

---

### B-9: `clean_days` in progress endpoint can go negative
**Status**: [CONFIRMED] — `clean_days = 7 - len(alert_dates)` at analytics_service.py:90; UTC/IST boundary can yield 8 distinct alert dates in a 7-day IST window  
**File**: `backend/app/services/analytics_service.py:90`  
**Severity**: LOW  
**Finding**: `7 - len(alert_dates)` — UTC/IST boundary can yield 8 distinct dates in a 7-day IST window. Fix: `max(0, 7 - len(alert_dates))`.

---

### B-10: `critical` severity alerts ignored in discipline score
**Status**: [CONFIRMED — low real-world impact] — analytics_service.py:85-86 only checks `danger` and `caution`. BehaviorEngine currently only produces those two severities, so no existing alert is dropped. Becomes a real bug if any pattern is ever assigned `critical`.  
**File**: `backend/app/services/analytics_service.py:85–86`  
**Severity**: MEDIUM

---

### B-11: Max drawdown `start_date` is None for traders starting with losses
**Status**: [CONFIRMED] — `current_dd_start = None` init at analytics.py:691; if first trade is a loss, cumulative never exceeds peak=0, `current_dd_start` is never set → `_days_between(None, end)` returns 0  
**File**: `backend/app/api/analytics.py:696–726`  
**Severity**: MEDIUM  
**Finding**: `current_dd_start = None` initialized before any peak. `_days_between(None, end)` returns 0 — falsely reports drawdown duration as 0 days.

---

### B-12: Shield service session end hardcoded 15:30 IST — MCX evening trades invisible
**Status**: [INTENTIONAL for NSE/F&O scope — debatable for MCX] — shield_service.py:37-39 documents "Market closes at 15:30 IST." MCX extends to 23:30 but behavioral alerts currently target NSE session. Upgrading to MEDIUM only if MCX support is in scope.  
**File**: `backend/app/services/shield_service.py:37–51`  
**Severity**: MEDIUM (if MCX is in scope)

---

### B-13: MCX unknown symbol silently returns multiplier=1
**Status**: [CONFIRMED]  
**File**: `backend/app/services/mcx_contract_specs.py:148–154`  
**Severity**: MEDIUM  
**Finding**: New MCX contract variants not in lookup table use 1x multiplier silently. Should flag `pnl_data_quality = "estimated"`.

---

## SECTION C: API CONTRACTS

### C-1: `/api/analytics/dashboard-stats` completely orphaned — wrong shape on both ends
**Status**: [CONFIRMED] — backend returns `{risk_score: {...}}` at analytics.py:52-53; `DashboardStats` TS interface expects `{total_pnl, win_rate, total_trades, max_drawdown}`; endpoint not consumed by Dashboard.tsx  
**File**: `backend/app/api/analytics.py:40–57`, `src/types/api.ts`, `src/lib/guestMode.ts`  
**Severity**: HIGH  
**Finding**: Backend returns `{ risk_score: {...} }`. `DashboardStats` TypeScript interface expects `{ total_pnl, win_rate, total_trades, max_drawdown }`. Guest mode mock uses yet another shape. Endpoint is dead — not consumed by Dashboard.tsx.

---

### C-2: `/api/analytics/unrealized-pnl` field name mismatch
**Status**: [FALSE POSITIVE — frontend does not consume this endpoint directly] — Dashboard.tsx derives `unrealized_pnl` from position objects (line 98), not from `/api/analytics/unrealized-pnl`. Guest mode stub uses a different shape but does not affect production.  
**File**: `backend/app/api/analytics.py:93-107`, `src/lib/guestMode.ts:101-103`  
**Severity**: ~~HIGH~~ → LOW (dead endpoint, not consumed)

---

### C-3: `CompletedTrade.entry_time` and `exit_time` nullable in backend but required in TypeScript
**Status**: [CONFIRMED] — `entry_time = Column(TIMESTAMP(timezone=True))` in model (no nullable=False); TypeScript has `entry_time: string` (required)  
**File**: `src/types/api.ts:113-114`, `backend/app/models/completed_trade.py:52-53`  
**Severity**: HIGH  
**Finding**: `entry_time: Optional[datetime]` backend vs required `string` TypeScript. Any `.toLocaleDateString()` on null → runtime TypeError in TradesTab, BtstTab, PatternsTab.

---

### C-4: `RiskState.status_message` and `last_updated` in TypeScript never sent by backend
**Status**: [CONFIRMED] — `RiskStateResponse` schema has `risk_state`, `active_patterns`, `recommendations` only; TypeScript `RiskState` has `status_message` and `last_updated` which are never sent  
**File**: `src/types/api.ts:1–6`  
**Severity**: MEDIUM  
**Finding**: These fields don't exist in `RiskStateResponse`. Dashboard derives them locally (safe today), but type contract is wrong.

---

### C-5: `has_more` stripped by `response_model` in `/api/trades/`
**Status**: [CONFIRMED — low impact, client uses offset < total as equivalent]  
**File**: `backend/app/api/trades.py`  
**Severity**: LOW  
**Finding**: FastAPI `response_model=TradeListResponse` strips `has_more`. Client workaround `offset < total` is functionally equivalent.

---

### C-6: `BtstTab` sends `broker_account_id` in query string — leaks to logs/history
**Status**: [CONFIRMED]  
**File**: `src/components/analytics/BtstTab.tsx:54`  
**Severity**: LOW  
**Finding**: Backend ignores param (uses JWT). Account ID unnecessarily in URL.

---

### C-7: `CompletedTrade.pnl_pct` returned by backend but missing from TypeScript interface
**Status**: [CONFIRMED]  
**File**: `src/types/api.ts:99–121`  
**Severity**: LOW  
**Finding**: Free field available on backend but not typed. Components recompute it redundantly.

---

## SECTION D: FRONTEND LOGIC

### D-1: `acknowledgeAll` never calls the backend — "Mark all reviewed" feature is broken
**Status**: [CONFIRMED] — lines 401-403: only `setAlerts(prev => prev.map(a => ({ ...a, acknowledged: true })))`, no API call  
**File**: `src/contexts/AlertContext.tsx:401–403`  
**Severity**: CRITICAL  
**Finding**: Only updates local state. On next page load or WebSocket event, all alerts revert to unreviewed. The feature is completely non-functional.

---

### D-2: Mobile nav "My Patterns" links to `/personalization` — wrong page, route unreachable
**Status**: [CONFIRMED] — `{ name: 'My Patterns', href: '/personalization', icon: Brain }` at Layout.tsx:33  
**File**: `src/components/Layout.tsx:33`  
**Severity**: CRITICAL  
**Finding**: `href: '/personalization'` should be `href: '/my-patterns'`. My Patterns (Risk Monitor) is unreachable from mobile navigation.

---

### D-3: PortfolioRadar and PortfolioChat have no routes in App.tsx — pages unreachable
**Status**: [INTENTIONAL — deliberately removed features, dead code cleanup needed] — commit `ee736b4` "Remove overkill features: Portfolio Radar/Chat..." intentionally removed the routes. Page files remain as dead code. Not a regression, but `CommandPalette.tsx:26` still links to `/portfolio-radar` which should be cleaned up.  
**File**: `src/App.tsx`, `src/pages/PortfolioRadar.tsx`, `src/pages/PortfolioChat.tsx`  
**Severity**: LOW (dead code cleanup)

---

### D-4: Dashboard IST midnight cutoff wrong — today's alerts may not show
**Status**: [FALSE POSITIVE — math is correct] — manually verified: `Date.now() + IST_OFFSET_MS` creates a number 5.5h ahead; `setUTCHours(0,0,0,0)` on that shifted Date correctly zeros IST midnight in UTC representation; `- IST_OFFSET_MS` converts back. Works correctly regardless of browser timezone.  
**File**: `src/pages/Dashboard.tsx:331–334`  
**Severity**: ~~HIGH~~ → N/A

---

### D-5: `isReconnecting` stuck `true` after auth failure — amber dot permanently shown
**Status**: [CONFIRMED — partially] — code 4001 path skips `setIsReconnecting(true)` for new closes, but if a prior reconnect cycle set it to true and then 4001 fires, it's never cleared to false. Amber dot can get stuck after token expiry during an active session.  
**File**: `src/contexts/WebSocketContext.tsx:258–269`  
**Severity**: HIGH  
**Finding**: Code 4001 path skips reconnect scheduling but never sets `isReconnecting(false)`. Amber "Reconnecting" banner shows indefinitely after token expiry.

---

### D-6: Discipline page weekly trend chart is time-reversed
**Status**: [CONFIRMED] — `.reverse()` at Discipline.tsx:111 puts W-1 (most recent) on the LEFT of the chart. Improving discipline score looks like decline visually.  
**File**: `src/pages/Discipline.tsx:108–111`  
**Severity**: HIGH  
**Finding**: `.reverse()` puts most-recent week on the left. A score improvement looks like a decline on the chart.

---

### D-7: Chat SSE bypasses guest mode interceptor — guest users get network errors
**Status**: [CONFIRMED] — `fetchWithAuth` at Chat.tsx:260 uses native `fetch`, not axios. Guest mode interceptor only hooks axios. Guest SSE requests hit real network → 401.  
**File**: `src/pages/Chat.tsx:260`  
**Severity**: HIGH  
**Finding**: Native `fetch` bypasses axios guest-mode interceptor. Guest chat requests hit the real network → 401.

---

### D-8: Journal sheet close marks trade as journaled without saving
**Status**: [CONFIRMED] — `handleJournalClose` at Dashboard.tsx:319-323 adds trade to `journaledIds` on any close event, including dismiss without save  
**File**: `src/pages/Dashboard.tsx:319–323`  
**Severity**: HIGH  
**Finding**: Any dismiss/close of journal sheet marks trade journaled in local state without API call.

---

### D-9: PnlSparkline zero-line outside SVG bounds for all-profit sessions
**Status**: [CONFIRMED] — `toY(0)` when all points > 0: `H - ((0 - min)/range)*H*0.85 - H*0.075` with min>0 gives value > H, exceeding SVG viewBox  
**File**: `src/components/dashboard/PnlSparkline.tsx:25–29`  
**Severity**: HIGH  
**Finding**: `toY(0)` exceeds SVG height when all values are positive. Area fill visually breaks. Fix: `Math.max(0, Math.min(H, toY(0)))`.

---

### D-10: Alerts Patterns tab claims "last 48 hours" but uses 7-day data
**Status**: [CONFIRMED] — UI text "last 48 hours" at Alerts.tsx:364; AlertContext fetches `hours: 168` (7 days) at AlertContext.tsx:290  
**File**: `src/pages/Alerts.tsx:364`, `src/contexts/AlertContext.tsx:290`  
**Severity**: HIGH  
**Finding**: AlertContext fetches `hours: 168` (7 days). Label says "48 hours". Factually incorrect.

---

### D-11: `useCountUp` always animates from 0 — P&L flashes zero on every update
**Status**: [CONFIRMED] — `startVal.current = 0` at useCountUp.ts:15 resets on every target change  
**File**: `src/hooks/useCountUp.ts:15`  
**Severity**: MEDIUM  
**Finding**: `startVal.current = 0` resets on every target change. Live P&L update: ₹5,000 → ₹0 → ₹5,050 instead of smooth ₹5,000 → ₹5,050.

---

### D-12: MyPatterns streak counts weekends as clean trading days
**Status**: [CONFIRMED] — 30-day loop at MyPatterns.tsx:230 doesn't skip Saturday/Sunday; weekend days with no alerts counted as "clean"  
**File**: `src/pages/MyPatterns.tsx:229–246`  
**Severity**: MEDIUM  
**Finding**: 30-day loop includes Saturday/Sunday as "clean" days. "7-day streak" may include 2 non-trading days.

---

### D-13: MyPatterns milestone `achieved_at` always today's date
**Status**: [CONFIRMED] — `achieved_at: daily_status[0]?.date ?? ''` at MyPatterns.tsx:257; `daily_status[0]` is always today  
**File**: `src/pages/MyPatterns.tsx:255–257`  
**Severity**: MEDIUM  
**Finding**: `daily_status[0]?.date` = today for all milestones. A 7-day milestone achieved 3 days ago shows as "achieved today."

---

### D-14: Unread alert badge counts all 7 days — inflated count
**Status**: [CONFIRMED] — `unacknowledgedCount = alerts.filter(a => !a.acknowledged).length` over the 7-day fetch window  
**File**: `src/contexts/AlertContext.tsx:409`  
**Severity**: MEDIUM  
**Finding**: Badge shows count of all unacknowledged alerts across 7-day window. Week-old alerts inflate daily badge.

---

### D-15: Open positions subscription uses `.length` not symbol set — wrong symbols subscribed
**Status**: [CONFIRMED] — dep array has `openPositions.length` at OpenPositionsTable.tsx:88; if a position is replaced by one with same count, subscribe not re-called  
**File**: `src/components/dashboard/OpenPositionsTable.tsx:84–88`  
**Severity**: MEDIUM  
**Finding**: Dep `openPositions.length` — if positions change with same count, subscription not updated. New position shows no live price.

---

### D-16: `formatCurrencyWithSign(0)` shows `+₹0.00`
**Status**: [CONFIRMED] — `const sign = amount >= 0 ? '+' : '-'` at formatters.ts; zero gets `+` prefix  
**File**: `src/lib/formatters.ts`  
**Severity**: LOW  
**Finding**: `amount >= 0 ? '+' : '-'` — zero gets a `+` prefix at session start.

---

### D-17: History tab alert names inconsistently formatted vs Live tab
**Status**: [CONFIRMED — cosmetic]  
**File**: `src/pages/Alerts.tsx:207`  
**Severity**: LOW  
**Finding**: `iv_crush_behavior` → "Iv Crush Behavior" in History vs "IV Crush" in Live.

---

### D-18: EmotionalTax week/month cost shows ₹0 — trades array is empty
**Status**: [CONFIRMED]  
**File**: `src/pages/MyPatterns.tsx:285`  
**Severity**: MEDIUM  
**Finding**: `calculateEmotionalTax(patterns, [])` — empty trades causes week/month buckets to all be zero.

---

### D-19: `guestMode.ts` catch-all returns `{}` — unmocked routes cause silent blank states
**Status**: [CONFIRMED]  
**File**: `src/lib/guestMode.ts:234–236`  
**Severity**: MEDIUM  
**Finding**: New endpoints without stubs return `{}` in guest mode. Should return `undefined` to fall through to real network.

---

### D-20: `disconnect()` clears `tradementor_seen_alerts` — all alerts re-toast on reconnect
**Status**: [CONFIRMED]  
**File**: `src/contexts/BrokerContext.tsx:253–256`  
**Severity**: MEDIUM  
**Finding**: Clears all `tradementor_*` localStorage keys including seen-alerts dedup. All historical alerts re-toast as "new" on next login.

---

## SECTION E: BACKEND INFRASTRUCTURE AND TASKS

### E-1: `TradingSession` no unique constraint — MultipleResultsFound crashes alert consolidation
**Status**: [CONFIRMED — CRITICAL]  
**File**: `backend/app/models/trading_session.py:25–31`, `backend/app/tasks/trade_tasks.py:762–769`  
**Severity**: CRITICAL  
**Finding**: Concurrent 09:15 trades can create two session rows for same `(broker_account_id, session_date)`. `scalar_one_or_none()` raises `MultipleResultsFound` — alert consolidation crashes, no notifications sent despite alerts being in DB.

---

### E-2: Webhook checksum uses global `api_secret` — all per-user-key webhooks silently fail
**Status**: [FALSE POSITIVE — webhooks.py:110–122 does per-account lookup]  
**File**: `backend/app/services/zerodha_service.py:562–575`  
**Severity**: CRITICAL  
**Finding**: Global `zerodha_client.validate_postback_checksum()` uses global `api_secret`. Users with per-user API keys (Session 28 feature) have checksum validated against wrong secret. All their real-time webhooks are silently dropped. Live dashboard non-functional for these users.  
**Verification**: `webhooks.py:112` does `api_secret = account.decrypt_api_secret() or settings.ZERODHA_API_SECRET or ""` and passes it to standalone `verify_zerodha_checksum()` — never calls `zerodha_client.validate_postback_checksum()`. Per-user secrets are used correctly.

---

### E-3: APScheduler runs in every FastAPI worker — N× duplicate reports
**Status**: [CONFIRMED — CRITICAL]  
**File**: `backend/app/tasks/retention_tasks.py:28, 127–147`  
**Severity**: CRITICAL  
**Finding**: Module-level singleton starts in every uvicorn worker. With 4 gunicorn workers: 4× EOD/morning reports per user. Burns Gupshup quota, risks WhatsApp template ban.

---

### E-4: `Position` model no unique constraint — duplicate position rows possible
**Status**: [CONFIRMED]  
**File**: `backend/app/models/position.py:12`  
**Severity**: HIGH  
**Finding**: Concurrent webhook + EOD sync can create duplicate rows. Dashboard shows doubled quantities; false oversizing alerts.

---

### E-5: `CompletedTrade` no unique constraint — duplicate behavioral analysis
**Status**: [CONFIRMED]  
**File**: `backend/app/models/completed_trade.py:19–20`  
**Severity**: HIGH  
**Finding**: FIFO lock expiry race can create duplicate completed trades. Behavior engine analyzes each, potentially doubling pattern detection.

---

### E-6: `RiskAlert.related_trade_ids` is `ARRAY(UUID)` — may store string order IDs causing silent alert drops
**Status**: [FALSE POSITIVE — field never populated by behavior engine]  
**File**: `backend/app/models/risk_alert.py:25`  
**Severity**: HIGH  
**Finding**: If behavior engine stores `order_id` (String) in this array, `db.add(alert)` fails with PostgreSQL type error. All behavioral alerts silently dropped.  
**Verification**: `behavior_engine.py` creates `RiskAlert` objects with no `related_trade_ids` value — the field stays `NULL`. The type mismatch scenario can't occur in practice.

---

### E-7: `ZerodhaClient` rate limiter process-local — 100x Zerodha rate limit violation
**Status**: [CONFIRMED]  
**File**: `backend/app/services/zerodha_service.py:77`  
**Severity**: HIGH  
**Finding**: In-process `RateLimiter(3.0/sec)` with 100 prefork workers = up to 300 calls/sec. Mass KiteRateLimitError at 09:15, potential API key block.

---

### E-8: EOD reports sent to commodity traders at equity session time (16:00 vs 23:30)
**Status**: [CONFIRMED]  
**File**: `backend/app/tasks/retention_tasks.py:60–68`  
**Severity**: HIGH  
**Finding**: `_dispatch_reports` sends to all accounts without checking `goal.primary_segment`. MCX traders get equity-format EOD at 16:00 with incomplete data.

---

### E-9: Weekly AI summary strength/weakness hardcoded for all users
**Status**: [CONFIRMED]  
**File**: `backend/app/tasks/report_tasks.py:265–268`  
**Severity**: HIGH  
**Finding**: `key_strength="Consistent execution"`, `key_weakness="Position sizing"` — constants, not computed. Every user gets identical fabricated feedback.

---

### E-10: `behavior_lock` TTL 15s too short — expires during full-session analysis
**Status**: [CONFIRMED]  
**File**: `backend/app/tasks/trade_tasks.py:330`  
**Severity**: HIGH  
**Finding**: Engine may take >15s with 15+ trades + slow DB. Second worker runs duplicate analysis → duplicate alerts, duplicate WhatsApp notifications.

---

### E-11: `_reconcile_all_accounts` shares one DB session across all accounts
**Status**: [PARTIALLY CONFIRMED — low severity in practice]  
**File**: `backend/app/tasks/reconciliation_tasks.py:75–126`  
**Severity**: HIGH  
**Finding**: Single session shared across all account reconciliations. A rollback for one account corrupts session state for all subsequent accounts.  
**Verification**: `_reconcile_account` uses the shared session only for reads; writes go through Celery tasks. Exceptions per-account are caught before they propagate. Risk is real but only materialises if the session enters an error state (e.g. DB connectivity), not on application-level errors. Severity is MEDIUM in practice, not HIGH.

---

### E-12: Admin rate limiters in-memory — brute-force protection N× weaker
**Status**: [CONFIRMED]  
**File**: `backend/app/core/rate_limiter.py:98–99`  
**Severity**: HIGH  
**Finding**: With 4 uvicorn workers: effective admin login limit = 4×5 = 20 attempts/15min instead of 5. All `RateLimiter` instances use `defaultdict(list)` in process memory — state is not shared across workers.

---

### E-13: `UserProfile.ai_cache` lost-update race — concurrent AI tasks overwrite each other
**Status**: [CONFIRMED]  
**File**: `backend/app/tasks/report_tasks.py:507–514, 576–581`  
**Severity**: MEDIUM  
**Finding**: Read-modify-write on JSON blob. Two concurrent AI tasks silently drop each other's results.

---

### E-14: Long-held DB session during FIFO lock wait exhausts connection pool
**Status**: [CONFIRMED]  
**File**: `backend/app/tasks/trade_tasks.py:78–345`  
**Severity**: MEDIUM  
**Finding**: Single session held open for up to 15s backoff wait. At 09:15 burst: pool_timeout errors, all retries also hold connections.

---

### E-15: Event subscriber resets `last_id = "$"` on reconnect — events missed during Redis outage
**Status**: [CONFIRMED]  
**File**: `backend/app/core/event_bus.py:226`  
**Severity**: MEDIUM  
**Finding**: Events during a Redis outage never dispatched after reconnect. Users must refresh manually.

---

### E-16: `market_hours.py` uses NSE holidays for MCX duration calculations
**Status**: [CONFIRMED]  
**File**: `backend/app/core/market_hours.py:221`  
**Severity**: MEDIUM  
**Finding**: MCX has its own holiday calendar. Using NSE holidays for MCX makes BTST duration_minutes wrong on NSE-only holidays.

---

### E-17: `REDIS_URL` defaults to localhost — silent production degradation if env var missing
**Status**: [CONFIRMED]  
**File**: `backend/app/core/config.py:39`  
**Severity**: MEDIUM  
**Finding**: Default `redis://localhost:6379/0` connects to nothing on Render.com. Rate limiting, events, alerts all fail silently.

---

### E-18: `Trade` model NOT NULL fields have no defaults — bulk sync silently drops trades
**Status**: [CONFIRMED]  
**File**: `backend/app/models/trade.py:53–55`  
**Severity**: MEDIUM  
**Finding**: `asset_class`, `instrument_type`, `product_type` have no `default=`. If `classify_trade()` fails, NOT NULL violation silently drops the trade with no user-visible error.

---
