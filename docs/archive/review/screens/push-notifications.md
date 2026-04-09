# Push Notifications — Screen Review

**Status**: REVIEWED (session 15, 2026-03-07)
**Reviewer**: Claude Code

---

## Scope

- `backend/app/services/push_notification_service.py` — send + subscription management
- `backend/app/api/notifications.py` — subscribe/unsubscribe/test/status endpoints
- `backend/app/models/push_subscription.py` — PushSubscription model
- `backend/app/services/notification_rate_limiter.py` — in-memory rate limiter
- `public/sw.js` — browser service worker
- `src/lib/pushNotifications.ts` — frontend subscription library

---

## Architecture

1. Frontend calls `pushNotifications.setup(brokerAccountId)` from Settings page
2. SW registers at `/sw.js`, permission granted, browser creates PushSubscription
3. Frontend POSTs to `/api/notifications/subscribe` → saved to `push_subscriptions` table
4. When risk alert fires: `send_danger_alert.delay()` → `push_service.send_risk_alert_notification(alert, db)`
5. pywebpush sends VAPID-authenticated POST to browser's push service endpoint
6. SW receives push event → calls `showNotification()`
7. User taps notification → SW posts `NOTIFICATION_CLICKED` to main tab or opens `/dashboard`

---

## Bugs Found & Fixed

### PN-01 — Type mismatch: `failed_count` String vs Integer (FIXED)
**File**: `push_notification_service.py:91,335,343`
**Severity**: MEDIUM (implicit coercion; type safety issue)
**Description**: Model has `failed_count = Column(Integer, default=0)` but service used string assignments: `existing.failed_count = "0"` and `subscription.failed_count = str(current_count)`. Also `int(subscription.failed_count or "0")` suggested the code expected strings.
**Fix**: Changed all assignments to `int` (0, 1) and updated `int(subscription.failed_count or 0)`.

---

### PN-05 — `_handle_failed_delivery` never called; expired subscriptions never deactivated (FIXED)
**File**: `push_notification_service.py:215-231`
**Severity**: HIGH (subscriptions accumulate; send attempts to dead endpoints on every alert)
**Description**: `_handle_failed_delivery()` was only called in the `except Exception as e:` block. However, `_send_to_subscription()` catches `WebPushException` internally and returns `False` — no exception propagates. Result: for every failed push (404/410 from expired subscription), the failure counter was never incremented, and subscriptions were never deactivated. Stale subscriptions would be retried on every future alert.
**Fix**: Moved `await self._handle_failed_delivery(subscription, db)` into the `else: failed_count += 1` branch so it fires whenever `_send_to_subscription()` returns False.

---

### PN-06 — Duplicate singleton instantiation (FIXED)
**File**: `notification_rate_limiter.py:272-276`
**Severity**: LOW (cosmetic bug; second instance overwrites first)
**Description**: `notification_rate_limiter = NotificationRateLimiter()` appeared twice at module end. Second call overwrote the first, resetting any rate-limit state that might have been captured between the two lines (in practice none, but it's a latent bug).
**Fix**: Removed duplicate instantiation.

---

## Observations (No Fix Required)

### PN-02 — Frontend always force-unsubscribes before re-subscribing
`pushNotifications.ts:subscribe()` always calls `existing.unsubscribe()` before creating a new subscription. This ensures fresh VAPID auth but means the old endpoint is orphaned in the DB (marked active). However, when the next push is sent to the old endpoint, `_handle_failed_delivery` will now (post-fix PN-05) correctly deactivate it after 3 failures. Acceptable behavior.

### PN-03 — `webpush()` is synchronous; blocks async event loop
`push_notification_service.py:309-314` — `pywebpush.webpush()` makes an HTTP request synchronously. With multiple subscriptions, this blocks the FastAPI event loop for the duration. For MVP scale (1–100 subscriptions) this is acceptable. At scale, wrap with `asyncio.to_thread(webpush, ...)`.

### PN-04 — Rate limiter only wired for DangerZone, not for risk alerts
The `notification_rate_limiter` is used in `danger_zone_service.py` but NOT in `push_notification_service.send_risk_alert_notification()` or `alert_service.send_risk_alert()`. WhatsApp and push alerts from the risk detector can fire on every webhook without rate limiting. This relies on the 24h alert dedup in risk detection. Sufficient for MVP.

### PN-07 — SW console.log statements in production
`public/sw.js` has multiple `console.log()` calls that will appear in every browser's DevTools. Minor — but should be removed before production launch.

---

## Status

| ID | Issue | Severity | Fixed |
|----|-------|----------|-------|
| PN-01 | `failed_count` String vs Integer type mismatch | MEDIUM | ✅ Yes |
| PN-05 | Failed subscriptions never deactivated | HIGH | ✅ Yes |
| PN-06 | Duplicate singleton instantiation | LOW | ✅ Yes |
| PN-02 | Force-unsubscribe before resubscribe | LOW | By design |
| PN-03 | Blocking HTTP call in async context | MEDIUM | Deferred |
| PN-04 | Rate limiter not wired for push/WA alerts | LOW | Acceptable |
| PN-07 | SW console.log in production | LOW | Pre-launch |
