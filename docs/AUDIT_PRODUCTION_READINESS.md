# AUDIT: Production Readiness Report — TradeMentor AI
**Date**: 2026-06-10  
**Verdict**: **NOT PRODUCTION READY** — 3 critical blockers, 7 high issues must be resolved.  
**Full findings**: `docs/AUDIT_RAW_FINDINGS.md`

---

## 1. Executive Summary

TradeMentor AI is architecturally sound and has good bones — the behavioral engine is well-researched, the event bus is clean, security fundamentals (JWT, Fernet encryption, webhook checksum, auth-code exchange) are mostly correct. However, there are 3 critical issues that will cause immediate user-facing failures in production, and 7 high issues that are either security holes or data-correctness bugs.

**Top 5 Blockers (ranked by severity and likelihood):**

1. **`GET /api/zerodha/token/validate` does not exist** — token validation silently fails for every user, breaking the token-expired detection flow permanently.
2. **MCX/CDS real-time P&L is wrong by up to 100×** — the webhook FIFO path ignores lot multipliers.
3. **JWT in localStorage + `'unsafe-inline'` CSP** — XSS-exploitable token theft vector.
4. **In-memory rate limiter is per-process** — rate limits are ineffective in any multi-process deployment.
5. **Celery `worker_concurrency=100` with prefork** — will OOM-kill workers on any standard hosting plan.

---

## 2. Critical Issues (must fix before any real user traffic)

### C-01: Missing backend endpoint — `/api/zerodha/token/validate`
**File**: `src/contexts/BrokerContext.tsx:272` + `backend/app/api/zerodha.py`  
**Impact**: Token validation always fails silently. `tokenStatus` is always `'unknown'`. The `TokenExpiredBanner` never fires. Users with expired Zerodha tokens get confusing silent failures with no guidance to reconnect.  
**Fix**: Add a `/token/validate` endpoint to `zerodha.py` that attempts a lightweight Kite API call (e.g., `GET /user/profile`) and returns `{valid: bool, needs_login: bool}`.

---

### C-02: MCX/CDS real-time P&L incorrect (lot multiplier missing in webhook path)
**File**: `backend/app/services/pnl_calculator.py:773-785`  
**Impact**: For MCX Crude Oil futures (lot = 100 barrels), real-time P&L displayed on dashboard is 100× understated. Users can't trust live P&L for commodity trades. Behavioral patterns based on P&L thresholds (session_meltdown, revenge_trade) also fire incorrectly.  
**Fix**: Apply the same `lot_multiplier` lookup used in `_process_symbol_trades()` to `calculate_trade_pnl_realtime()`.

---

### C-03: Double alert generation — legacy RiskDetector + BehaviorEngine both run on sync
**File**: `backend/app/api/zerodha.py:820-885`  
**Impact**: Every `POST /api/zerodha/sync/all` runs two alert engines that partially overlap. Users see duplicate alerts for the same trade event. The legacy engine was supposed to be removed after Session 21 (per MEMORY.md). The two engines use different dedup windows and keys, so dedup does not prevent all duplicates.  
**Fix**: Remove the legacy `RiskDetector.detect_patterns()` call from `sync/all`. Keep only BehaviorEngine (the `run_behavior_engine_full_session` call). The legacy code can be preserved commented out for reference.

---

## 3. High Issues (should fix before launch)

### H-01: `is_expiry_day` bug in pnl_calculator.py feature computation
**File**: `backend/app/services/pnl_calculator.py:624`  
**Issue**: `is_expiry = exit_ist.weekday() == 3` — uses hardcoded Thursday, same bug fixed in behavior_engine.py in Session 27/28. Weekly options with non-Thursday expiry (SEBI has allowed Friday/Monday expiries) will have wrong `is_expiry_day` feature. Corrupts ML training data.  
**Fix**: Use `is_expiry_day(ct.tradingsymbol, exit_ist.date())` from `instrument_parser.py`.

---

### H-02: OAuth state parameter not CSRF-protected
**File**: `backend/app/api/zerodha.py:186-188`  
**Issue**: The `state` parameter in the OAuth flow is `user_id if user_id else "anonymous"` — not a random nonce bound to the initiating session. A CSRF attack can complete an OAuth flow linking a victim to an attacker's Zerodha account.  
**Fix**: Generate `state = secrets.token_urlsafe(16)` at connect time, store in Redis (30s TTL), validate on callback.

---

### H-03: `setup-credentials` endpoint accepts API secrets with no auth
**File**: `backend/app/api/zerodha.py:121-148`  
**Issue**: Anyone can POST api_key + api_secret without authentication. An attacker could plant credentials that, when clicked via a crafted URL, hijack the victim's OAuth flow.  
**Fix**: Require JWT auth on this endpoint, or at minimum heavy rate-limiting (1/IP/hour).

---

### H-04: In-memory rate limiter not shared across processes
**File**: `backend/app/core/rate_limiter.py`  
**Issue**: In multi-process deployment, each uvicorn worker has its own rate limiter state. Effective limit becomes N× the configured limit. The Redis-backed `rate_limit.py` already exists.  
**Fix**: Migrate all endpoint rate limiters to use `rate_limit.py` (Redis-backed).

---

### H-05: `worker_concurrency=100` with prefork will OOM on standard hosting
**File**: `backend/app/core/celery_app.py:69`  
**Issue**: 100 prefork workers × ~100MB each = ~10GB RAM. Render free = 512MB. Will crash immediately.  
**Fix**: Set `worker_concurrency=4` in Procfile/startup command unless explicitly using gevent: `celery worker --pool=gevent -c 100`.

---

### H-06: JWT stored in localStorage — XSS-stealable
**File**: `src/lib/api.ts:49`  
**Issue**: Any XSS (even through a third-party script) can read and exfiltrate the JWT. CSP has `'unsafe-inline'` which doesn't prevent inline script injection.  
**Fix (phased)**: Short term — tighten CSP to remove `'unsafe-inline'` for scripts (use nonces). Medium term — migrate to httpOnly cookie for token storage.

---

### H-07: Missing composite DB indexes on hot query paths
**Files**: Multiple  
**Issue**: `risk_alerts(broker_account_id, detected_at)`, `completed_trades(broker_account_id, exit_time)` lack composite indexes. These are the two most-queried tables and both are queried with both columns.  
**Fix**: Migration adding:
```sql
CREATE INDEX IF NOT EXISTS idx_risk_alerts_account_time 
  ON risk_alerts(broker_account_id, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_completed_trades_account_exit 
  ON completed_trades(broker_account_id, exit_time DESC);
```

---

## 4. Medium Issues (fix within first month of launch)

### M-01: APScheduler inside FastAPI process — EOD reports lost on crash
**File**: `backend/app/tasks/retention_tasks.py`  
**Issue**: If FastAPI process dies at 16:00 IST exactly and takes >1 minute to restart, that minute's EOD report batch is silently dropped. Unlike Celery beat + redbeat, APScheduler has no persistence.  
**Fix**: Move EOD/morning briefs to Celery beat schedule (add to `celery_app.py:beat_schedule`).

---

### M-02: Admin OTP uses `random.choices` — not cryptographically secure
**File**: `backend/app/api/admin/auth.py:42`  
**Issue**: `random.choices(string.digits, k=6)` is Mersenne Twister, not CSPRNG.  
**Fix**: `import secrets; return ''.join(secrets.choice(string.digits) for _ in range(6))`.

---

### M-03: Admin logout doesn't invalidate JWT server-side
**File**: `backend/app/api/admin/auth.py:207-210`  
**Issue**: Stolen admin JWT valid for 8 hours after logout.  
**Fix**: Redis blocklist of logged-out admin JWTs with TTL = remaining expiry.

---

### M-04: `_sync_locks` dict grows unbounded (memory leak)
**File**: `backend/app/api/zerodha.py:66`  
**Fix**: `WeakValueDictionary` or periodic cleanup.

---

### M-05: Analytics `get_period_stats` uses naive datetimes
**File**: `backend/app/api/analytics.py:138`  
**Fix**: `datetime.combine(start_date, time.min).replace(tzinfo=timezone.utc)`.

---

### M-06: `behavior_lock` TTL 15s too short — race on slow DB
**File**: `backend/app/tasks/trade_tasks.py:330`  
**Fix**: Increase to 60s. Consider atomic Redis INCR for risk score updates.

---

### M-07: NSE holiday calendar 2026 incomplete (6 of ~12 holidays)
**File**: `backend/app/core/market_hours.py:42-48`  
**Fix**: Add complete 2026 calendar; add runtime warning when `today > max(NSE_HOLIDAYS)`.

---

### M-08: `/api/analytics/progress` best_streak hardcoded to max(days, 7)
**File**: `backend/app/api/analytics.py:252`  
**Fix**: Compute actual best streak from alert history.

---

### M-09: `/api/alerts/test` endpoint allows pinging arbitrary phone numbers
**File**: `backend/app/api/alerts.py`  
**Fix**: Validate phone matches user's registered guardian_phone; add per-user rate limit.

---

### M-10: OAuth callback leaks raw exception in redirect URL
**File**: `backend/app/api/zerodha.py:378-380`  
**Fix**: Map exception types to safe user-facing messages.

---

### M-11: `Alert.severity` TypeScript type mismatch with backend
**File**: `src/types/api.ts:128`  
**Fix**: Update type to include `'danger' | 'caution'`.

---

### M-12: `CompletedTrade.pnl_pct` missing from TypeScript interface
**File**: `src/types/api.ts`  
**Fix**: Add `pnl_pct?: number | null`.

---

### M-13: `RiskState.status_message` doesn't exist on backend response
**File**: `src/types/api.ts:1-6`  
**Fix**: Remove `status_message` field; add `recommendations: string[]`.

---

## 5. Low / Info Issues

### L-01: `console.error` / `console.log` in production frontend code
**Fix**: Use conditional logging (`if (import.meta.env.DEV) { ... }`).

### L-02: Missing `ErrorBoundary` around lazy-loaded Analytics tabs
**Fix**: Wrap `<Suspense>` with `<ErrorBoundary>` per tab.

### L-03: `useEffect` without cleanup — potential memory leak on unmount
**Files**: `src/pages/MyPatterns.tsx`, `src/pages/BlowupShield.tsx`  
**Fix**: AbortController pattern.

### L-04: `DashboardStats` TypeScript interface unused and wrong
**File**: `src/types/api.ts:8-13`  
**Fix**: Remove or align with actual backend response.

### L-05: `api_key` stored plaintext in DB (defense-in-depth)
**File**: `backend/app/models/broker_account.py:34`  
**Fix**: Encrypt with Fernet like `api_secret_enc`.

### L-06: Admin broadcast has no per-day send limit
**Fix**: Add Redis counter limiting N broadcasts per 24h per admin.

### L-07: Prometheus `/metrics` publicly accessible
**Fix**: Document reverse-proxy IP restriction; or add shared-secret header.

### L-08: `overtrading_burst` fires caution for profitable scalpers
**Fix**: Increase burst threshold or add a "net profitable session" suppression.

### L-09: Webhook checksum verified after account lookup — minor info disclosure
**Fix**: Verify checksum first, before database lookup. Or accept current order as acceptable.

### L-10: Startup P&L repair task uses simplified formula (ignores charges)
**Fix**: Don't recompute P&L in startup; rely on Zerodha's authoritative `realised` field only.

---

## 6. What's Working Well

The following areas are solid and production-grade:

- **Auth code exchange flow**: JWT never appears in URL/history — the one-time Redis code with 30s TTL is excellent security design.
- **Fernet encryption for access tokens**: Correct implementation, validated at startup.
- **WebSocket token revocation check**: Checks DB on every new WS connection — correct.
- **FIFO P&L batch calculator**: Comprehensive implementation with lot multiplier, direction flips, incomplete position detection, and stable UUID for journal FK survival.
- **BehaviorEngine**: 23 patterns, all thresholds externalized to `trading_defaults.py`, strategy suppression for hedge legs, dedup with cooldown windows — well-architected.
- **CORS wildcard protection**: Runtime assertion prevents `allow_origins=['*']` with `allow_credentials=True` in non-development environments.
- **Security headers**: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Content-Security-Policy`, `Cache-Control` for API paths — comprehensive.
- **Celery task idempotency**: The `processed_at` atomic UPDATE with rowcount check is a correct race-free pattern.
- **Redis lock hierarchy**: `fifo_lock` + `behavior_lock` with retry/backoff is sound.
- **Admin panel security**: 404 for non-admins (not 403), separate JWT secret, OTP requirement, per-IP + per-email lockout — solid design.
- **Database connection pooling**: `statement_cache_size=0` for PgBouncer compatibility, `pool_pre_ping=True` — correctly configured.
- **Event bus durability**: Redis Streams with per-account replay on WS reconnect — production-grade.
- **Error boundaries**: `ErrorBoundary` component exists and is used.
- **Guest mode**: Clean axios adapter intercept pattern, no backend dependency.
- **Maintenance mode**: 503 middleware with `Retry-After` header.
- **Market hours**: `market_minutes()` correctly strips weekends and holidays for duration calculation.

---

## 7. Recommended Launch Checklist

**Week 0 — Blockers (do not launch until done):**
- [ ] C-01: Implement `GET /api/zerodha/token/validate` endpoint
- [ ] C-02: Fix lot multiplier in `calculate_trade_pnl_realtime()`
- [ ] C-03: Remove legacy RiskDetector from sync/all path
- [ ] H-01: Fix `is_expiry_day` hardcoded Thursday in `pnl_calculator.py`
- [ ] H-05: Fix Celery worker concurrency — enforce `--pool=gevent` or reduce prefork count
- [ ] H-07: Add composite DB indexes (migration)

**Week 1 — Security hardening:**
- [ ] H-02: CSRF protection for OAuth state parameter
- [ ] H-03: Auth requirement on `setup-credentials` endpoint
- [ ] H-04: Migrate rate limiters to Redis-backed `rate_limit.py`
- [ ] M-02: Fix admin OTP to use `secrets.choice`
- [ ] M-03: Admin JWT blocklist on logout

**Week 2 — Data & Reliability:**
- [ ] M-07: Complete NSE 2026 holiday calendar
- [ ] M-01: Move EOD reports to Celery beat + redbeat
- [ ] M-04: Fix `_sync_locks` memory leak
- [ ] M-05, M-13: Fix naive datetime usage in analytics
- [ ] M-11, M-12, L-04: Fix TypeScript interface mismatches

**Month 1 — Polish:**
- [ ] L-01: Remove `console.log` from production frontend
- [ ] L-02: Add ErrorBoundary per analytics tab
- [ ] L-03: AbortController cleanup in useEffect
- [ ] M-09: Phone validation on test-alert endpoint
- [ ] M-08: Compute real best_streak
- [ ] M-10: Safe error messages in OAuth redirect
- [ ] H-06: Increase behavior_lock TTL to 60s
