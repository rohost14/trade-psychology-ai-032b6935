# Trade Sync Pipeline — Screen Review

**Status**: REVIEWED (session 15, 2026-03-07)
**Reviewer**: Claude Code

---

## Scope

This review covers the full trade synchronisation pipeline:

- `POST /api/zerodha/sync/all` — manual sync endpoint
- `backend/app/services/trade_sync_service.py` — core sync logic
- `backend/app/tasks/trade_tasks.py` — Celery tasks (webhook + scheduled)
- `backend/app/tasks/report_tasks.py` — EOD/weekly report tasks
- `backend/app/api/zerodha.py` — sync endpoint + signal pipeline
- `backend/app/services/alert_service.py` — WhatsApp alert formatting

---

## Pipeline Summary

### Path A: Manual Sync (`POST /sync/all`)
1. Rate limited (1 req/user/window) + per-account concurrency lock
2. `sync_trades_for_broker_account()` — fetches `/trades` + positions + P&L FIFO
3. `sync_orders_to_db()` — fetches all orders (including cancelled/rejected)
4. Signal pipeline (after data pipeline):
   - RiskDetector → risk_alerts (dedup 24h)
   - BehavioralEvaluator → behavioral_events (dedup 60min by type)
   - DangerZone assessment → possible cooldown + WhatsApp
   - Behavioral baseline recompute (skipped if < 24h ago)

### Path B: Webhook (`POST /webhooks/zerodha/postback`)
1. Kite posts order update → `process_webhook_trade.delay()`
2. Saves/updates Trade row
3. Syncs positions immediately
4. For COMPLETE + SELL: real-time FIFO P&L calculation
5. `run_risk_detection_async()` → alerts + WhatsApp + AlertCheckpoint

---

## Bugs Found & Fixed

### TS-01 — Security: Debug Token Logging (FIXED)
**File**: `trade_sync_service.py:186-193`
**Severity**: HIGH (security)
**Description**: Debug logging block printed first 10 chars of Zerodha access token to logs on every sync call. Even partial tokens in logs are a security risk.
```python
# BEFORE (vulnerable):
logger.info(f"Access token (first 10 chars): {access_token[:10]}...")
logger.info(f"Token length: {len(access_token) if access_token else 0}")
```
**Fix**: Removed the 4 debug `logger.info()` lines. Kept the validity check (len < 20).

---

### TS-02 — Crash: `send_weekly_summary` calls non-existent method (FIXED)
**File**: `report_tasks.py:248`
**Severity**: HIGH (runtime crash — AttributeError)
**Description**: `alert_service.send_whatsapp_message(phone, report)` called on `AlertService`, which has no such method. Would crash every weekly summary.
**Fix**: Replaced with direct `whatsapp_service.send_message(phone, report)` call.

---

### TS-03 — Wrong P&L Source: Weekly Summary shows all-zeros (FIXED)
**File**: `report_tasks.py:207-224`
**Severity**: HIGH (wrong data)
**Description**: Weekly summary queried `Trade.pnl` (always 0) instead of `CompletedTrade.realized_pnl`. All totals were 0, win rate was 0%, best/worst were 0.
**Fix**: Changed to query `CompletedTrade` table filtered by `exit_time >= week_start`, using `realized_pnl` for all calculations.

---

### TS-04 — Dedup Gap: Account-level alerts always bypass deduplication (FIXED)
**Files**: `trade_tasks.py:204-217`, `zerodha.py:622-637`
**Severity**: MEDIUM (spam risk)
**Description**: Risk alerts without a `trigger_trade_id` (account-level patterns like consecutive_loss from scheduled scans) were never deduplicated because the existing_keys set only included alerts that had a trigger_trade_id. A `("None", "pattern_type")` key was never in `existing_keys` (since None-trigger alerts were excluded from that set), so the alert would be re-added on every sync.
**Fix**: Both code paths now use `("_account_", pattern_type)` as the dedup key for alerts without a trigger_trade_id. This prevents the same account-level pattern from firing more than once per 24h.

---

## Observations (No Fix Required)

### TS-05 — EOD/Morning Reports send to guardian only
`report_tasks.py` send_eod_report, send_morning_prep, send_weekly_summary all send to `user.guardian_phone` only. The User model has no own-phone field. This is by design — users who want reports set themselves as their own guardian, or the reports go to the person they trust.

### TS-06 — `run_risk_detection` Celery task has no deduplication
`trade_tasks.py:131-173` — the standalone `run_risk_detection` Celery task does no deduplication; it adds all alerts. However, this task is not wired to any current code path (webhook uses `run_risk_detection_async`, sync uses inline logic). Low risk.

### TS-07 — Instrument refresh on every sync
`trade_sync_service.py:209-228` — Instruments are refreshed if last update > 23h ago. This is a potentially slow operation (thousands of rows). It's non-fatal and logged, but adds latency to first sync of the day.

### TS-08 — asyncio.get_event_loop() pattern in Celery tasks
`trade_tasks.py`, `report_tasks.py` — all Celery tasks use `asyncio.get_event_loop().run_until_complete()`. In Python 3.10+, `get_event_loop()` emits a DeprecationWarning if there's no current running loop. In Celery workers (synchronous by default), this typically works because there IS no running loop. `asyncio.run()` is the modern equivalent but would require `asyncio.run()` to replace every call. Low risk for now.

---

## Test Coverage

No specific test file for the sync pipeline (integration testing requires live Kite API or mocks). The `test_dashboard_api.py` covers the endpoint authorization layer.

Recommend: Add `tests/test_trade_sync_service.py` mocking Kite API responses for isolated sync logic testing.

---

## Status

| ID | Issue | Severity | Fixed |
|----|-------|----------|-------|
| TS-01 | Token logging in debug output | HIGH | ✅ Yes |
| TS-02 | `send_weekly_summary` AttributeError crash | HIGH | ✅ Yes |
| TS-03 | Weekly summary uses Trade.pnl (always 0) | HIGH | ✅ Yes |
| TS-04 | Account-level alerts never deduplicated | MEDIUM | ✅ Yes |
| TS-05 | EOD/reports to guardian only | LOW | By design |
| TS-06 | `run_risk_detection` no dedup | LOW | Not wired |
| TS-07 | Instrument refresh latency | LOW | Acceptable |
| TS-08 | asyncio.get_event_loop deprecation | LOW | Deferred |
