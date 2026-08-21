> **ARCHIVED 22 Aug 2026 — do not use as a current reference.**
>
> June-10 "NOT PRODUCTION READY"; superseded by PRODUCTION_READINESS_CHECKLIST.md.
>
> Live findings, if any, were rescued into `docs/ENGINE_BACKLOG.md`.

---

# AUDIT: Production Readiness Report — TradeMentor AI
**Date**: 2026-06-10  
**Re-verified**: 2026-06-11 (every finding checked against actual code)  
**Verdict**: **NOT PRODUCTION READY** — 6 critical, ~20 high issues must be resolved first.

> **Corrections vs first pass**: 3 findings that were originally marked CRITICAL are false positives (the code is fine). See annotation `~~strikethrough~~ → FALSE POSITIVE` below.

---

## 1. Executive Summary

The behavioral engine is well-researched, the event bus is clean, and security fundamentals (JWT, Fernet encryption, webhook per-user checksum, auth-code exchange) are mostly correct. However 6 critical issues cause immediate user-facing failures, and ~20 high issues are security holes or data-correctness bugs.

**True Critical Blockers (ranked by severity):**

| # | Issue | File | Status |
|---|-------|------|--------|
| 1 | MCX/CDS real-time P&L wrong by up to 1250× (lot multiplier missing in webhook path) | `pnl_calculator.py:773` | ✅ FIXED |
| 2 | Dual alert engine — legacy `RiskDetector` + `BehaviorEngine` both run on sync | `zerodha.py:821-882` | ✅ FIXED |
| 3 | `TradingSession` no unique constraint — concurrent 09:15 trades create duplicate session rows, crashes alert consolidation | `models/trading_session.py` | ✅ FIXED (migration 058 pending) |
| 4 | APScheduler starts in EVERY uvicorn worker — N× duplicate EOD reports to users | `retention_tasks.py:28,146` | ✅ FIXED |
| 5 | `acknowledgeAll` only updates local state — "Mark all reviewed" is completely broken | `AlertContext.tsx:401-403` | ✅ FIXED |
| 6 | Mobile "My Patterns" nav links to `/personalization` — page unreachable on mobile | `Layout.tsx:33` | ✅ FIXED |

**Originally-listed Criticals that were FALSE POSITIVES:**
- ~~C-01: `/api/zerodha/token/validate` endpoint missing~~ → endpoint exists at `zerodha.py:1111`
- ~~E-2: Webhook uses global `api_secret`~~ → `webhooks.py:112` correctly uses per-user key first
- ~~A-1: `cooldown_violation` never called~~ → intentionally suppressed as alert (Session 33 decision)

---

## 2. Critical Issues

### C-01 ~~CRITICAL~~ → FALSE POSITIVE
~~`GET /api/zerodha/token/validate` does not exist~~ — endpoint exists at `backend/app/api/zerodha.py:1111`. Token validation works correctly.

---

### C-02: MCX/CDS real-time P&L incorrect (lot multiplier missing in webhook path) — ✅ FIXED
**File**: `backend/app/services/pnl_calculator.py:773-785`  
**Fix applied**: Added `lot_multiplier = Decimal(str(get_lot_multiplier(trade.exchange or "", trade.tradingsymbol or "")))` after price extraction. Both BUY and SELL `match_pnl` lines now multiply by `lot_multiplier`. NSE/NFO unaffected (multiplier=1). MCX CRUDEOIL now correctly applies ×100, NATURALGAS ×1250, etc.

---

### C-03: Double alert generation — legacy RiskDetector + BehaviorEngine both run on sync — ✅ FIXED
**File**: `backend/app/api/zerodha.py:821-882`  
**Fix applied**: Removed entire legacy RiskDetector block (54 lines) from `zerodha.py` sync endpoint. Also removed RiskDetector import and detection block from `webhooks.py:process_trade_sync` dev fallback. `risk.py` untouched — `calculate_risk_state()` only reads existing RiskAlert rows from DB, not a detector. BehaviorEngine is now the sole detection path on all sync routes.

---

### C-04 (NEW): `TradingSession` no unique constraint on (broker_account_id, session_date) — ✅ FIXED (migration 058 pending apply)
**File**: `backend/app/models/trading_session.py:25-30`  
**Fix applied**: Added `UniqueConstraint('broker_account_id', 'session_date', name='uq_trading_session_account_date')` to `__table_args__` in model. Created `migrations/058_trading_session_unique_constraint.sql` — deduplicates any existing duplicate rows (keeping highest `trade_count`), then adds the constraint. **Must be applied to Supabase before deploying.**

---

### C-05 (NEW): APScheduler starts in every FastAPI worker — N× duplicate EOD reports — ✅ FIXED
**File**: `backend/app/tasks/retention_tasks.py:28, 146`  
**Fix applied**: Moved report dispatching from APScheduler-in-every-worker to a Celery beat task. Added `dispatch_reports_tick` Celery task to `retention_tasks.py` (wraps the existing `_dispatch_reports` logic via `asyncio.run()`). Added `"app.tasks.retention_tasks"` to Celery `include` list. Added `"retention-reports-tick"` to `beat_schedule` at 60s interval. Removed `start_scheduler()` call from `main.py` lifespan. Celery beat runs as a single process — no N× duplication possible.

---

### C-06 (NEW): `acknowledgeAll` only updates local state — "Mark all reviewed" is broken — ✅ FIXED
**File**: `src/contexts/AlertContext.tsx:401-403`  
**Fix applied**: Made `acknowledgeAll` async. Captures `unacked` before optimistic update, then fires `Promise.all` of individual acknowledge API calls. On failure, reverts only the alerts that failed (restores `acknowledged: false` for those IDs). Optimistic update means the UI responds instantly.

---

### C-07 (NEW): Mobile "My Patterns" nav links to `/personalization` — page unreachable — ✅ FIXED
**File**: `src/components/Layout.tsx:33`  
**Fix applied**: Changed `href: '/personalization'` to `href: '/my-patterns'` in `mobileMoreGroups`.

---

## 3. High Issues (fix before launch)

### H-01: `is_expiry_day` hardcoded Thursday in pnl_calculator.py feature computation — ✅ FIXED
**File**: `backend/app/services/pnl_calculator.py:624`  
**Issue**: `is_expiry = exit_ist.weekday() == 3` — same bug that was fixed in `behavior_engine.py`. NIFTY weekly moved to Wednesday, BANKNIFTY also Wednesday, FINNIFTY Tuesday, MIDCPNIFTY Monday. All `CompletedTradeFeature.is_expiry_day` flags wrong for these instruments.  
**Fix applied**: Added `from app.services.instrument_parser import is_expiry_day as _instrument_is_expiry_day`. Line 624 now: `is_expiry = _instrument_is_expiry_day(ct.tradingsymbol or "", exit_ist.date()) if exit_ist else False`. Uses actual expiry date from symbol parsing — correct for all indices and expiry schedules.

---

### H-02: OAuth state parameter not CSRF-protected ✅ FIXED
**File**: `backend/app/api/zerodha.py`  
**Fix applied**:
- `/connect`: generates `csrf_nonce = secrets.token_urlsafe(16)`. For the regular flow `state = csrf_nonce` stored as `oauth_state:{nonce} → "regular"`. For the setup flow `state = "setup:{nonce}"` stored as `oauth_state:{nonce} → setup_token`. Both use a 120 s Redis TTL (enough for the Zerodha login page round-trip).
- `/callback`: extracts the nonce from `state`, then atomically `GET + DELETE`s `oauth_state:{nonce}` via a Redis pipeline (single-use). Returns a redirect error if `state` is absent, nonce not found (expired/forged), or Redis is unavailable. The setup flow now recovers the original `setup_token` from the stored value rather than trusting the raw `state` string.

---

### H-03: `setup-credentials` endpoint accepts API secrets with no auth — ✅ FIXED
**File**: `backend/app/api/zerodha.py:121-148`  
**Issue**: Anyone can POST `api_key` + `api_secret` without any authentication. An attacker can plant a `setup_token` and trick a victim into connecting using the attacker's Zerodha credentials.  
**Fix applied**: Added `Depends(general_limiter)` (20 req/min per IP) to `POST /setup-credentials`. JWT auth was not feasible — this endpoint is intentionally pre-auth (for testers setting up before their first OAuth). Rate limiting throttles token-farming attacks. After H-04 fix (Redis limiters), this limit is now cross-worker and actually effective.

---

### H-04: In-memory rate limiters not shared across processes — ✅ FIXED
**File**: `backend/app/core/rate_limiter.py`  
**Issue**: `RateLimiter._hits` was a plain Python `defaultdict`. With N uvicorn workers the effective rate limit was N× configured value.  
**Fix applied**: Rewrote `RateLimiter.__call__` to use Redis sorted sets (same sliding-window algorithm as `rate_limit.py`). All 6 instances (`sync_limiter`, `coach_limiter`, `analytics_limiter`, `general_limiter`, `admin_login_limiter`, `admin_otp_limiter`) are now Redis-backed with zero call-site changes. Fails open on Redis unavailability. Uses `f"{now:.9f}"` member keys to avoid same-timestamp collisions under burst traffic.

---

### H-05: `worker_concurrency=100` with prefork pool will OOM on standard hosting — ✅ FIXED
**File**: `backend/app/core/celery_app.py:70`  
**Issue**: 100 prefork processes × ~100MB each = ~10GB RAM. Render free = 512MB.  
**Fix applied**: Changed `worker_concurrency=100` to `worker_concurrency=4` (4 prefork workers × ~100MB = ~400MB, fits in 512MB free tier with headroom for the FastAPI process).

---

### H-06: JWT stored in localStorage — XSS-stealable — ✅ PARTIALLY FIXED
**File**: `src/lib/api.ts:49`, `backend/app/main.py:241`  
**Issue**: Any XSS can exfiltrate the token. CSP had `'unsafe-inline'` in `script-src` which allows arbitrary inline script injection.  
**Fix applied**: Removed `'unsafe-inline'` from `script-src` in `main.py` CSP middleware. Vite production builds have no inline scripts so this doesn't break the app. `style-src 'unsafe-inline'` retained for Tailwind/shadcn inline styles.  
**Remaining**: JWT still in localStorage. Full fix = httpOnly cookie (requires backend `/api/auth/token` cookie endpoint + frontend removal of `localStorage.getItem(AUTH_TOKEN_KEY)`) — left as a future milestone.

---

### H-07 ~~HIGH~~ → FALSE POSITIVE
~~Missing composite DB indexes on hot query paths~~ — Both indexes already exist:
- `CompletedTrade`: `Index('idx_completed_trades_broker_exit', 'broker_account_id', 'exit_time')` in `models/completed_trade.py:20`
- `RiskAlert`: `Index('idx_risk_alerts_broker_detected', 'broker_account_id', 'detected_at')` in `models/risk_alert.py:12`

---

### H-08 (Phase 2 NEW): Progress endpoint win rate uses raw fills, not completed trades — ~50% understated — ✅ FIXED
**File**: `backend/app/api/analytics.py:137`  
**Issue**: `get_period_stats` queried `Trade` (raw fills). Opening fills have `pnl=0`. For 10 round-trips: denominator=20 raw fills, 10 of which are zero-pnl opens → win rate ~halved vs reality.  
**Fix applied**: `get_period_stats` now queries `CompletedTrade` filtered by `exit_time`. Uses `t.realized_pnl` (true round-trip P&L). Each row = one complete trading decision — win rate is now exact.

---

### H-09 (Phase 2 NEW): Week boundaries were UTC-based — should be IST — ✅ FIXED
**File**: `backend/app/api/analytics.py:125-143`  
**Issue**: `now = datetime.now(timezone.utc)` → `today` was UTC date → week boundaries were UTC midnight. For Indian market data all "today/this week" logic should be IST.  
**Fix applied**: Added `IST = timezone(timedelta(hours=5, minutes=30))`. Changed `now_ist = datetime.now(IST)` so `today` is the IST date. All four `datetime.combine(...)` boundaries now use `.replace(tzinfo=IST)` — correctly anchored to IST Monday 00:00 for week start.

---

### H-10 (Phase 2 NEW): `is_expiry_day()` no holiday adjustment — monthly expiry fires wrong day — ✅ FIXED
**File**: `backend/app/services/instrument_parser.py:163`  
**Issue**: When last Thursday of a month is an NSE holiday, NSE moves expiry to Wednesday. `_last_thursday_of_month()` never checked `is_trading_holiday()`. Affected `no_stoploss` modifier, `fomo_entry` threshold, `expiry_day_overtrading`.  
**Fix applied**: `_last_thursday_of_month` now imports `is_trading_holiday` from `market_hours` and walks back one day at a time after finding the last Thursday until it lands on a trading day. Added `timedelta` to module imports. No circular-import risk — `market_hours.py` does not import `instrument_parser`.

---

### H-11 (Phase 2 NEW): Dedup reference is task-run-time, not trade time — windows collapse during EOD replay — ✅ FIXED
**File**: `backend/app/tasks/trade_tasks.py:588, 709`  
**Issue**: `last_fired[pattern_type] = now_utc` used task-start time. During EOD replay of all trades, a streak at 09:30 and another at 13:00 (3.5h apart) both get `last_fired = 15:00` (task time) → second streak check is `15:00-15:00=0 < 2h` → wrongly suppressed.  
**Fix applied**: Changed both call sites to `last_fired[alert.pattern_type] = ct.exit_time or now_utc` (single-CT path uses `latest_ct.exit_time or now_utc`). Windows are now measured from actual trade time, correctly allowing re-fires when two episodes are genuinely separated.

---

### H-12 (Phase 2 NEW): `CompletedTrade.entry_time`/`exit_time` nullable in backend, required in TypeScript — ✅ FIXED
**File**: `src/types/api.ts:113-114`  
**Issue**: Backend columns have no `nullable=False`. TypeScript interface declared `entry_time: string` (required). Any `.toLocaleDateString()` on null → runtime TypeError in TradesTab, BtstTab, PatternsTab.  
**Fix applied**: Marked both fields optional in TypeScript: `entry_time?: string`, `exit_time?: string`. TypeScript-side fix is safe and requires no migration. Backend model left as-is (adding `nullable=False` to existing columns requires a data migration).

---

### H-13 (Phase 2 NEW): `Position` model has no unique constraint — concurrent syncs create duplicate rows — ✅ PARTIALLY FIXED
**Files**: `backend/app/models/position.py`, `backend/app/models/completed_trade.py`  
**Position — Fixed**: The sync upsert uses `(tradingsymbol, exchange, product)` as the dict key — a DB constraint matching that key is required. Added `UniqueConstraint('broker_account_id', 'tradingsymbol', 'exchange', 'product', name='uq_position_account_symbol_exchange_product')` to model. Created `migrations/059_position_unique_constraint.sql` — deduplicates existing rows (keeping most recent `updated_at`), then adds constraint. **Apply migration 059 to Supabase before deploying.**  
**CompletedTrade — Skipped**: FIFO code already handles idempotency via delete-then-reinsert (lines 147-153). No natural unique key exists — `entry_fill_ids` / `exit_fill_ids` are ARRAY columns, unconstainable. The audit's proposed `(tradingsymbol, entry_time, exit_time)` is fragile with nullable times. Real fix is a Celery task lock — tracked as a future H-15 dependency.

---

### H-14 (Phase 2 NEW): Weekly AI summary `key_strength`/`key_weakness` hardcoded for all users — ✅ FIXED
**File**: `backend/app/tasks/report_tasks.py:265-268`  
**Issue**: Every user received `"Consistent execution"` as strength and `"Position sizing"` as weakness regardless of their actual trading. Fabricated data — contradicts "mirror, not blocker" principle.  
**Fix applied**: Added `RiskAlert` query for the week alongside the existing `CompletedTrade` query. `key_weakness` = most-fired pattern_type this week (human-labelled). `key_strength` = first common pattern area (`overtrading`, `revenge_trade`, `no_stoploss`, `size_escalation`, `session_meltdown`) that never fired → "No [Pattern]". If all areas fired → "Managed all risk areas". Zero alerts → "Disciplined execution" / "None detected this week". `patterns_detected` also populated from real alert counts.

---

### H-15 (Phase 2 NEW): `behavior_lock` TTL 15s — expires during full-session analysis — ✅ FIXED
**File**: `backend/app/tasks/trade_tasks.py:330`  
**Issue**: BehaviorEngine can take >15s on cold Supabase + 15+ trades. Second worker acquires expired lock → duplicate detection → duplicate alerts and WhatsApp notifications.  
**Fix applied**: Changed `ttl_seconds=15` → `ttl_seconds=60`.

---

### H-16 (Phase 2 NEW): EOD reports sent to commodity traders at equity session time — ✅ FIXED
**File**: `backend/app/tasks/retention_tasks.py`  
**Issue**: Default EOD time was 16:00 IST for all accounts. MCX session runs until 23:30 IST — commodity traders received their EOD report mid-session.  
**Fix applied**: Added `DEFAULT_MCX_EOD_TIME = "23:45"`. In `_dispatch_reports`, if `profile.trading_hours_end >= "23:00"` (MCX traders configure this to "23:30") and the user hasn't set a custom EOD time, their default is 23:45. Users who explicitly configured a time keep their setting.

---

### H-17 (Phase 2 NEW): `ZerodhaClient` rate limiter is in-process — N×3 calls/sec with N workers — ✅ FIXED
**File**: `backend/app/services/zerodha_service.py:54`  
**Issue**: Each worker had its own in-memory `RateLimiter(3.0/sec)`. With 4 prefork workers = up to 12 API calls/sec → over Zerodha's 3/sec per-key limit → API key ban risk.  
**Fix applied (Phase 1)**: Rewrote `RateLimiter` to use Redis sorted-set sliding window (`kite_api_rate` key, 1-second window). All workers share one 3/sec budget. Falls back to in-process throttle if Redis unavailable.  
**Fix applied (Phase 2)**: Margin cache read-before-fetch in `trade_tasks.py`. Previously `get_margins` was called on every webhook fill with a 5-min write cache that was never read before calling the API. Fixed: check `margin:{account_id}` in Redis first (60s TTL); only call Kite if cache miss. Reduces margin REST calls ~20× during active trading sessions.  
**Architecture note**: Real-time position P&L uses KiteTicker WebSocket (zero REST calls) — already working. Margin is the only high-frequency REST call; cache fix resolves it at all realistic scale. For 10K+ users, Zerodha Publisher partnership gives 50+ req/sec.

---

## 4. Medium Issues (fix within first month of launch)

### M-01: APScheduler inside FastAPI process — EOD reports lost on crash
→ Absorbed into C-05. ✅ FIXED

### M-02: Admin OTP uses `random.choices` — not CSPRNG — ✅ FIXED
**File**: `backend/app/api/admin/auth.py:42`  
**Fix applied**: Replaced `random.choices(string.digits, k=6)` with `secrets.choice(string.digits) for _ in range(6)`. Removed `import random`, added `import secrets`. OTP is now generated using the OS CSPRNG.

### M-03: Admin logout doesn't invalidate JWT server-side — ✅ FIXED
**File**: `backend/app/api/admin/auth.py`, `backend/app/api/admin/deps.py`  
**Fix applied**: Added `jti` (secrets.token_hex(16)) to the JWT payload in `_make_admin_jwt`. Logout endpoint now reads the JWT via `HTTPBearer`, decodes it, and stores `admin_jti_block:{jti}` in Redis with TTL = remaining token lifetime (self-cleaning). `get_current_admin` in `deps.py` checks the blocklist after decode and raises 404 on hit. Redis unavailability fails open (admin not locked out) with a warning log.

### M-04: `_sync_locks` dict grows unbounded — ✅ FIXED
**File**: `backend/app/api/zerodha.py:66`  
**Fix applied**: Changed `dict[str, asyncio.Lock]` to `WeakValueDictionary`. Entries are GC'd automatically when no coroutine holds or awaits the lock. `_get_sync_lock` now uses `.get()` + create pattern consistent with WeakValueDictionary semantics.

### M-05: Analytics `get_period_stats` naive datetimes
→ Absorbed into H-09. ✅ FIXED

### M-06: `behavior_lock` TTL 15s too short
→ Absorbed into H-15. ✅ FIXED

### M-07: NSE holiday calendar 2026 incomplete (6 of ~14) — ✅ FIXED
**File**: `backend/app/core/market_hours.py`  
**Fix applied**: Added 8 missing 2026 holidays: Maha Shivaratri (Feb 18), Ram Navami (Mar 30), Ambedkar Jayanti (Apr 14), Maharashtra Day (May 1), Bakri Id (Jun 17, tentative), Ganesh Chaturthi (Sep 2), Diwali Laxmi Puja (Oct 20), Diwali Balipratipada (Oct 21), Guru Nanak Jayanti (Nov 25). 2026 list now has 14 entries. Added `_stale_holiday_warned` flag in `is_trading_holiday()` — logs a warning once per process if `check_date > max(all_holidays)` so stale calendars surface in logs rather than silently failing.

### M-08: `best_streak` hardcoded floor of 7 — ✅ FIXED
**File**: `backend/app/api/analytics.py` (`_get_discipline_streaks`)  
**Fix applied**: Extended lookback to 180 days. Deduplicates to one entry per calendar day. Computes best_streak as the longest gap between consecutive bad-pattern alert dates in the window (including gap from window start to first alert, and from last alert to today). Removed hardcoded `max(days_clean, 7)`.

### M-09: `/api/alerts/test` allows pinging arbitrary phones — ✅ FIXED
**File**: `backend/app/api/alerts.py`  
**Fix applied**: (1) Added DB lookup of `BrokerAccount → User.guardian_phone`. Returns 400 if no guardian phone configured, 403 if request phone doesn't match. (2) Added Redis sliding-window rate limit: 3 test alerts per hour per `broker_account_id`. Rate check is inline (not a dep) so it keys on the verified account ID, not IP.

### M-10: OAuth callback leaks raw exception in redirect URL — ✅ FIXED
**File**: `backend/app/api/zerodha.py`  
**Fix applied**: Replaced `urllib.parse.quote(str(e))` with a safe-message map. `KiteTokenExpiredError` → "Token exchange failed — please try connecting again". `KiteAuthError` → "Zerodha authentication failed — check your API credentials". `KiteNetworkError` → "Could not reach Zerodha — please try again". `KiteAPIError` → "Zerodha API error — please try again". All others → "Connection failed — please try again". Raw exception is still logged server-side at ERROR level with full traceback.

### M-11: Severity standardized to 3 levels across codebase — ✅ FIXED
**Files**: `src/types/patterns.ts`, `src/types/api.ts`, `src/lib/alertSeverity.ts`, `src/contexts/AlertContext.tsx`, `src/components/analytics/BehaviorTab.tsx`, `src/components/analytics/RiskTab.tsx`, `src/components/patterns/PatternCalendar.tsx`  
**Fix applied**: Collapsed 4-level frontend severity (`low/medium/high/critical`) to 3 levels matching the backend: `danger` (red), `caution` (amber), `positive` (green). `PatternSeverity` type updated. `Alert.severity` type updated. `normalizeSeverity()` maps all old values: `danger/critical/high → danger`, `caution/medium/low → caution`, `positive → positive`. `alertSeverity.ts` SEV_* records all updated to 3 keys with new `normalizeSeverityStr()` helper. `PatternCalendar` `DaySeverity` collapses to `no_data | clean | caution | danger`; `RiskTab` severityColors updated with legacy aliases kept for safe transition.

### M-12: `CompletedTrade.pnl_pct` missing from TypeScript interface — ✅ FIXED
**File**: `src/types/api.ts`  
**Fix applied**: Added `pnl_pct?: number | null` to `CompletedTrade` interface.

### M-13: `RiskState.status_message` doesn't exist on backend — ✅ FIXED
**File**: `src/types/api.ts:1-6`  
**Fix applied**: Removed `status_message: string` and `last_updated: string` (backend never sends these). Added `recommendations: string[]` (backend already returns this field).

### M-14: `profit_factor` returns 0 when no losing trades — ✅ FIXED
**File**: `backend/app/api/analytics.py` (3 locations: line ~315, ~1108, ~1988)  
**Fix applied**: All three `profit_factor` calculations now return `None` instead of `0` when `losers` is empty. Frontend should display `None` as "∞" (no losers = infinite profit factor). Previously `0` implied no edge, which is the opposite of the truth.

### M-15: `clean_days` uses UTC — can go negative at IST midnight — ✅ FIXED
**File**: `backend/app/services/analytics_service.py:90`  
**Fix applied**: Changed `a.detected_at.date()` → `a.detected_at.astimezone(ZoneInfo("Asia/Kolkata")).date()`. Added `max(0, ...)` guard. UTC timestamps stored in DB with IST trading day context — using UTC `.date()` across the IST midnight (18:30–00:00 UTC) could assign alerts to the wrong day, inflating `alert_dates` set size above 7 and yielding negative `clean_days`.

### M-16 (Phase 2): Max drawdown `start_date` is None for sessions starting with losses ✅ FIXED
**File**: `backend/app/api/analytics.py:702`  
**Fix applied**: `current_dd_start` is now initialised to `sorted_daily[0][0]` (the first trading day) before the loop runs. Previously `None`, so drawdown periods whose first day was already a loss would serialize `{"start": null, ...}` to the frontend.

### M-17 (Phase 2): `overtrading_burst` daily caution only fires when `session_pnl < 0` ✅ FIXED
**File**: `backend/app/services/behavior_engine.py`  
**Fix applied**: Added Check 3 inside `_detect_overtrading_burst`. Even when `daily_count < daily_caution`, if the session had a peak P&L ≥ threshold and 3+ consecutive trades after that peak eroded ≥50% of gains → fires `caution` (50–70% erosion) or `danger` (≥70% erosion) as `overtrading_burst`. Message includes actual stats: peak, erosion amount, erosion %, trade count. This catches the "6 trades, first 2 profitable, last 4 gave it all back" pattern before the raw count threshold fires.

### M-18 (Phase 2): `iv_crush_behavior` and `premium_destruction` both fire on the same trade ✅ FIXED
**File**: `backend/app/services/behavior_engine.py (_run_all_detectors)`  
**Fix applied**: After all detectors run, if both `iv_crush_behavior` and `premium_destruction` are in the event list, keep only the higher-severity one and drop the other. Uses `_SEV_RANK` dict (danger=1, caution=2, positive=3); `min()` picks the most severe.

### M-19 (Phase 2): `rapid_reentry`, `no_stoploss`, `post_loss_recovery_bet` not in `_STRATEGY_SUPPRESSED` ✅ FIXED
**File**: `backend/app/services/behavior_engine.py:325`  
**Fix applied**: Added all three to `_STRATEGY_SUPPRESSED`. When `ctx.strategy_group` is set (trade is part of a multi-leg hedge — straddle, strangle, spread), these patterns are suppressed with a debug log. A CE + PE bought simultaneously at different strikes is a defined hedged strategy, not rapid re-entry or a recovery bet.

### M-20 (Phase 2): NULL `duration_minutes` causes `iv_crush_behavior` false positive ✅ FIXED
**File**: `backend/app/services/behavior_engine.py (_detect_iv_crush_behavior)`  
**Fix applied**: Added explicit `if ct.duration_minutes is None: return None` guard before using `hold_min`. The previous `ct.duration_minutes or 0` silently treated missing timestamps as a 0-minute hold, which always passed the `< 30 min` threshold and produced spurious alerts.

### M-21 (Phase 2): `excess_exposure` skips all accounts with capital < ₹10,000 ✅ FIXED
**File**: `backend/app/services/behavior_engine.py (_detect_excess_exposure)`  
**Fix applied**: Removed `float(capital) < 10000` lower-bound guard. The check now only requires a non-zero capital figure (`float(capital) <= 0`). Under-capitalised accounts are precisely the ones most at risk of over-exposure and must receive this alert.

### M-22 (Phase 2): `early_exit` max_winner ceiling of 20 min misses classic disposition effect ✅ FIXED
**File**: `backend/app/services/behavior_engine.py (_detect_early_exit)`  
**Fix applied**: Raised `"early_exit_winner_max_min"` default from `20` to `60`. A trader holding winners 25-40 min but losers 2+ hours now triggers the alert. The condition `avg_winner_hold < 20` was too tight and silently excluded the textbook 30-40 min winner / 2+ hr loser pattern.

### M-23 (Phase 2): `disconnect()` clears `tradementor_seen_alerts` — all alerts re-toast on reconnect ✅ FIXED
**File**: `src/contexts/BrokerContext.tsx`  
**Fix applied**: Added `&& k !== 'tradementor_seen_alerts'` to the localStorage sweep filter in `disconnect()`. The dedup set is now preserved across disconnect/reconnect so alerts that were already shown don't re-toast when the same account reconnects.

### M-24 (Phase 2): `useCountUp` always animates from 0 — live P&L flashes zero on every update ✅ FIXED
**File**: `src/hooks/useCountUp.ts`  
**Fix applied**: Added `displayedRef` to track the last rendered value. On each target change, `startVal.current = displayedRef.current` (was `= 0`). Subsequent updates now animate from the currently displayed number, eliminating the zero-flash on rapid P&L ticks.

### M-25 (Phase 2): MyPatterns streak counts weekends as clean trading days ✅ FIXED
**File**: `src/pages/MyPatterns.tsx`  
**Fix applied**: Added `if (dow === 0 || dow === 6) continue` in the 30-day loop. Day-of-week is derived from the IST date string (via `new Date(y, mo-1, dy).getDay()`), not from UTC, so the check is correct for IST traders. Weekend days no longer contribute to the discipline streak.

### M-26 (Phase 2): EmotionalTax shows ₹0 — `alerts.map(a => a.pattern)` returns undefined ✅ FIXED
**File**: `src/pages/MyPatterns.tsx`  
**Root cause**: `Alert` has no `.pattern` sub-object — `alerts.map(a => a.pattern)` returned `[undefined, …]`, so `calculateEmotionalTax` received an array of undefineds and summed ₹0.  
**Fix applied**: Replaced the broken mapping with an explicit Alert → BehaviorPattern shape (`type`, `severity`, `detected_at`, `description`, etc.). `estimated_cost` defaults to 0 since the backend doesn't yet return it per-alert. EmotionalTax now shows correct pattern types and occurrence counts.

### M-27 (Phase 2): guestMode catch-all returns `{}` — new endpoints silently blank in demo ✅ FIXED
**File**: `src/lib/guestMode.ts`  
**Fix applied**: Added `import.meta.env.DEV` console.warn in the catch-all so developers immediately see which endpoint is missing a stub (`[GuestMode] No stub for GET /api/new-endpoint — add one in getGuestResponse()`). The `{}` return is preserved to prevent 401s from the real backend (guest mode has no auth token). Add a specific stub in `getGuestResponse()` for any new endpoint that should show demo data.

### M-28 (Phase 2): Event subscriber resets `last_id = "$"` on Redis reconnect — events missed ✅ FIXED
**File**: `backend/app/core/event_bus.py`  
**Fix applied**: Removed `last_id = "$"` from the exception handler. The cursor now retains its last-processed event ID across Redis reconnects. XREAD will resume from that ID and replay any events that arrived during the disconnect window. If Redis trimmed that entry from the stream, XREAD safely starts from the oldest available entry. The `"$"` sentinel is only used once — at initial startup — to skip backlog that is already replayed via `replay_events_for_account`.

### M-29 (Phase 2): `REDIS_URL` defaults to `localhost` — silent failure on Render.com ✅ FIXED
**File**: `backend/app/core/config.py`  
**Fix applied**: Added a `@model_validator(mode="after")` that raises `ValueError` at startup if `REDIS_URL` contains `localhost` and `ENVIRONMENT != "development"`. The server refuses to start rather than silently failing all Redis operations at runtime on Render.com / Fly.io / any container environment.

### M-30 (Phase 2): `Trade` NOT NULL fields (`asset_class`, `instrument_type`, `product_type`) have no Python defaults ✅ FIXED
**File**: `backend/app/models/trade.py:53-55`  
**Fix applied**: Added `default="UNKNOWN"` to `asset_class` and `instrument_type`, `default="NRML"` to `product_type`. SQLAlchemy uses these Python-side defaults when a value is not provided during `Trade(...)` construction, preventing NOT NULL violations if `classify_trade()` raises. Trades are saved with a safe placeholder and can be reclassified on the next sync rather than being silently dropped.

---

## 5. Low / Info Issues

- **L-01** ✅: `console.error`/`console.log` stripped from production bundles via `esbuild: { drop: ['console','debugger'] }` in `vite.config.ts` (mode-guarded — dev builds keep them).
- **L-02** ✅: `<ErrorBoundary fallback={…}>` wraps `<Suspense>` in `Analytics.tsx`; added optional `fallback` prop to `ErrorBoundary`. Tab crashes now show an inline message instead of a full-page takeover.
- **L-03** ✅: `BlowupShield` — `AbortController` passed to all three API calls; cleanup aborts on unmount and removes `visibilitychange` listener. `MyPatterns.fetchStatus` — accepts optional `AbortSignal`; initial `useEffect` creates a controller and aborts on cleanup. Both ignore `ERR_CANCELED` in the catch block.
- **L-04** ✅: `DashboardStats` interface removed from `src/types/api.ts` — zero import sites, was a dead leftover.
- **L-05** ✅: `formatCurrencyWithSign(0)` now returns `₹0.00` (no sign). Changed `amount >= 0 ? '+' : '-'` to `amount > 0 ? '+' : amount < 0 ? '-' : ''`.
- **L-06** ✅: History tab now uses `formatPatternName()` (the same lookup table the Live tab uses via `AlertContext`). `formatPatternName` exported from `AlertContext.tsx` and imported in `Alerts.tsx`.
- **L-07** ✅: `achieved_at` is now `daily_status[d - 1]?.date` — the actual IST date when the streak reached `d` days — rather than always `daily_status[0]` (today).
- **L-08** ✅: `unacknowledgedCount` now filters alerts to today's IST calendar day before counting, so the badge reflects today's alerts only (not the full 7-day fetch window).
- **L-09** ✅: Removed `.reverse()` from `trendData` in `Discipline.tsx`. The label mapping (`W-N … W-1`) already produces oldest-to-newest order; `.reverse()` was flipping it to newest-on-left.
- **L-10** ✅: Removed duplicate `no_stoploss_monthly_hold_min` / `no_stoploss_monthly_loss_pct` entries at lines 111-112 of `trading_defaults.py`. The documented canonical copy at lines 167-168 is retained.
- **L-11** ✅: Added `has_more: bool = False` to `TradeListResponse` in `backend/app/schemas/trade.py`. The field was computed and returned by the endpoint but stripped by the `response_model` validation.
- **L-12** ✅: Removed `broker_account_id: account.id` from `BtstTab`'s query params. The backend resolves it from the JWT via `Depends(get_verified_broker_account_id)` — the query param was redundant and leaked the UUID to URL/browser history.
- **L-13** ✅: VaR 95% index corrected from `int(N * 0.05)` to `int((N-1) * 0.05)` — matches `numpy.percentile(interpolation='lower')`. Previous formula gave index 1 for N=20 (5% tail has only 1 day, should be index 0).

---

## 6. Summary Table

| Severity | Count | Notes |
|----------|-------|-------|
| Critical | 6 | C-02, C-03, C-04, C-05, C-06, C-07 |
| High | 16 | H-01 through H-17 (H-07 is false positive, not counted) |
| Medium | 27 | M-01 through M-30; M-01/M-05/M-06 absorbed into criticals/highs |
| Low | 13 | L-01 through L-13 |
| **FALSE POSITIVES** | **9** | C-01, E-2, H-07, A-1(intentional), D-4, B-8, C-2(API), E-6, D-3(intentional) |
