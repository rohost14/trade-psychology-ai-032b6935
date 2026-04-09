# Session 015 — Cross-Cutting Feature Review

**Date**: 2026-03-07
**Focus**: Screen-by-screen review of all pending cross-cutting features (A–H)

---

## What Was Done

### Prep
- Updated TRACKER.md to reflect sessions 11-14 (sessions were logged in MEMORY.md but TRACKER was stuck at session 10)
- Verified 212/212 tests passing from previous session

### Reviews Completed (5 cross-cutting features)

| Feature | Result |
|---------|--------|
| A: Zerodha OAuth Flow | ✅ Reviewed — 1 bug fixed (OA-01) |
| B: Trade Sync Pipeline | ✅ Reviewed — 4 bugs fixed (TS-01..04) |
| C: Real-time Price Stream | ✅ Reviewed — 0 bugs, 7 observations noted |
| D: Push Notifications | ✅ Reviewed — 3 bugs fixed (PN-01,05,06) |
| E: WhatsApp Alerts | ✅ Reviewed — see TS-02/TS-03 for fixes |
| H: Onboarding | ✅ Reviewed — 0 bugs, design choices noted |

---

## Bugs Fixed This Session (8 total)

### TS-01 — Security: Debug token logging removed
**File**: `backend/app/services/trade_sync_service.py`
Removed 4 `logger.info()` lines that logged first 10 chars of Zerodha access token on every sync.

### TS-02 — Crash: send_weekly_summary AttributeError
**File**: `backend/app/tasks/report_tasks.py`
`alert_service.send_whatsapp_message(phone, report)` called `AlertService` method that doesn't exist.
Fixed: replaced with `whatsapp_service.send_message(phone, report)`.

### TS-03 — Wrong P&L: Weekly summary used Trade.pnl (always 0)
**File**: `backend/app/tasks/report_tasks.py`
`Trade.pnl` is always 0. Weekly summary showed 0 for all P&L, win rate, best/worst.
Fixed: changed to query `CompletedTrade` and use `realized_pnl`.

### TS-04 — Dedup gap: Account-level alerts bypass 24h deduplication
**Files**: `backend/app/tasks/trade_tasks.py`, `backend/app/api/zerodha.py`
Alerts without `trigger_trade_id` (e.g. consecutive_loss from scheduled scans) had key `("None", "pattern_type")` which was never in `existing_keys`. Fired on every sync.
Fixed: both code paths now use `("_account_", pattern_type)` as dedup key for trigger_trade_id-less alerts.

### PN-01 — Type mismatch: failed_count String vs Integer
**File**: `backend/app/services/push_notification_service.py`
`failed_count` is `Integer` in DB but service assigned strings `"0"`, `"1"` etc.
Fixed: changed all assignments to integers.

### PN-05 — Critical: Failed push subscriptions never deactivated
**File**: `backend/app/services/push_notification_service.py`
`_handle_failed_delivery()` was only called in `except Exception` block. But `WebPushException` is caught inside `_send_to_subscription()` and returns False (no exception propagates). Result: failed/expired subscriptions accumulated forever; every alert attempted to push to dead endpoints.
Fixed: moved `_handle_failed_delivery()` call to `else:` branch (when success=False).

### PN-06 — Duplicate singleton instantiation
**File**: `backend/app/services/notification_rate_limiter.py`
`notification_rate_limiter = NotificationRateLimiter()` appeared twice at module end. Removed duplicate.

### OA-01 — OAuth error not shown to user
**File**: `src/contexts/BrokerContext.tsx`
`?error=...` param from failed OAuth callback was logged to console and cleared — no user-facing message.
Fixed: added `toast.error()` call to display the error for 8 seconds.

---

## Files Changed This Session

### Backend (Python)
1. `backend/app/services/trade_sync_service.py` — removed debug token logging
2. `backend/app/tasks/report_tasks.py` — fix weekly summary crash + wrong P&L
3. `backend/app/tasks/trade_tasks.py` — fix alert dedup for None trigger_trade_id
4. `backend/app/api/zerodha.py` — fix alert dedup for None trigger_trade_id
5. `backend/app/services/push_notification_service.py` — type fix + deactivation fix
6. `backend/app/services/notification_rate_limiter.py` — remove duplicate singleton

### Frontend (TypeScript)
7. `src/contexts/BrokerContext.tsx` — show OAuth error toast

### Docs
8. `docs/review/TRACKER.md` — updated to session 15
9. `docs/review/screens/trade-sync.md` — new
10. `docs/review/screens/push-notifications.md` — new
11. `docs/review/screens/whatsapp.md` — new
12. `docs/review/screens/zerodha-oauth.md` — new
13. `docs/review/screens/price-stream.md` — new
14. `docs/review/screens/onboarding.md` — new
15. `docs/SYSTEM_ARCHITECTURE.md` — created (1000+ lines, from prev session)

---

## Test Results

212/212 tests passing after all fixes (no regressions).

---

## Next Session

All TRACKER items are now REVIEWED:
- Screens 1–10: COMPLETE/REVIEWED
- Cross-cutting A–H: all REVIEWED

Remaining open issues (non-blocking, deferred):
- WS-03: WebSocket reconnect backoff
- WS-05: Server-side WebSocket heartbeat
- PN-03: `webpush()` blocking call in async
- Migrations 022, 023, 024, 025, 028, 029 still need running in Supabase

Next major task options:
1. **Commit all changes** (150+ files uncommitted since "Initial commit")
2. **Production hardening** (deferred WS/push improvements)
3. **Feature: cold start hook** (MEMORY.md: "OPEN: Cold start problem")
4. **End-to-end testing** with real Zerodha account
