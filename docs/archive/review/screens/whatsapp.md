# WhatsApp Alerts — Screen Review

**Status**: REVIEWED (session 15, 2026-03-07)
**Reviewer**: Claude Code

---

## Scope

- `backend/app/services/whatsapp_service.py` — Twilio send wrapper
- `backend/app/services/alert_service.py` — alert message formatting + guardian dual-send
- `backend/app/tasks/trade_tasks.py::send_danger_alert` — trigger point from risk detection
- `backend/app/tasks/report_tasks.py` — EOD/morning/weekly scheduled messages

---

## Architecture

1. **Risk Alert WhatsApp**: `run_risk_detection_async()` → `send_danger_alert.delay(broker_account_id, alert_id)` → `AlertService.send_risk_alert(alert, account, guardian_phone)` → `whatsapp_service.send_message()`
2. **EOD Report**: Celery Beat at 4 PM IST → `generate_eod_reports()` → `retention_service.send_eod_report()` → `whatsapp_service.send_message()`
3. **Morning Brief**: Celery Beat at 8:30 AM IST → `send_morning_prep()` → `retention_service.send_morning_brief()` → `whatsapp_service.send_message()`
4. **Weekly Summary**: On-demand → `send_weekly_summary(broker_account_id)` → `ai_service.generate_whatsapp_report()` → `whatsapp_service.send_message()`

---

## Bugs Fixed (in this session)

See `trade-sync.md` for TS-02 (AttributeError) and TS-03 (wrong P&L source in weekly summary) — both were in the WhatsApp path.

---

## Observations (No Fix Required)

### WA-01 — WhatsApp only sends to `guardian_phone`, not user's own phone
`User` model has `guardian_phone` and `guardian_name` but no `user_phone` field. All WhatsApp messages go to `guardian_phone`. The intended UX is: users who want WhatsApp themselves set up their own number as the guardian contact. This is by design.

### WA-02 — Emoji print() fixed in previous session
`whatsapp_service.py` safe-mode used `print(f"📱 ...")` which caused `UnicodeEncodeError` on Windows (cp1252 encoding). Fixed in session 15 by replacing with `logger.info()`.

### WA-03 — Twilio safe mode returns True (simulates success)
In safe mode (no Twilio credentials), `send_message()` returns True. This means callers get success=True even when no message was actually sent. Acceptable for development — logs a message instead.

### WA-04 — `asyncio.get_event_loop()` deprecated in Python 3.10+
`whatsapp_service.py:48` — `loop = asyncio.get_event_loop()` inside async method. The correct form is `asyncio.get_running_loop()` when inside an async context. However since this is inside `async def send_message()`, the running loop exists and `get_event_loop()` returns it correctly. Low risk, but `get_running_loop()` would be more explicit.

### WA-05 — `send_risk_alert_with_guardian()` not used in webhook path
`AlertService` has `send_risk_alert_with_guardian()` for dual-send (user + guardian), but `send_danger_alert` in `trade_tasks.py` only calls `send_risk_alert()` with the guardian phone. If a user wants WhatsApp alerts themselves AND their guardian, they'd need their own phone in the `guardian_phone` field. Feature gap if user wants separate messages.

---

## Status

| ID | Issue | Severity | Fixed |
|----|-------|----------|-------|
| WA-02 | Emoji UnicodeEncodeError | HIGH | ✅ Yes (prev session) |
| TS-02 | Weekly summary AttributeError | HIGH | ✅ Yes (this session) |
| TS-03 | Weekly summary wrong P&L | HIGH | ✅ Yes (this session) |
| WA-01 | Only guardian phone | N/A | By design |
| WA-03 | Safe mode returns True | LOW | By design |
| WA-04 | get_event_loop deprecation | LOW | Deferred |
| WA-05 | Guardian-only in webhook | LOW | Design gap |
