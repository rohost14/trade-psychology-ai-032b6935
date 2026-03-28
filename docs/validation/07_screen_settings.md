# Screen 07: Settings
*Route: `/settings` | File: `src/pages/Settings.tsx`*

---

## Purpose
Two-tab settings hub. Profile tab: broker connection management, trading profile (style, capital, limits), and AI persona selection. Notifications tab: WhatsApp, push notification, and guardian configuration.

---

## Layout

```
┌────────────────────────────────────────────────────────┐
│  Tabs: [Profile]  [Notifications]                      │
├────────────────────────────────────────────────────────┤
│  [Tab 1: Profile]                                      │
│                                                        │
│  Broker Connection Card                                │
│  [Zerodha — Connected ✅] [Disconnect]                │
│  [Add another account] [Sync now]                      │
│                                                        │
│  Trading Profile Card                                  │
│  Experience: [Beginner/Intermediate/Expert]            │
│  Risk Tolerance: [Conservative/Moderate/Aggressive]    │
│  Trading Capital: [₹ input]                           │
│  AI Persona: [Strict Mentor / Supportive Coach / ...]  │
│                                                        │
│  Trading Limits Card                                   │
│  Daily Loss Limit: [₹ input]                          │
│  Max Position Size: [% of capital]                     │
│  SL % Futures: [input]   SL % Options: [input]        │
│  Daily Trade Limit: [input]                            │
│  Cooldown After Loss: [minutes]                        │
│                                                        │
│  [Save Profile] button                                 │
├────────────────────────────────────────────────────────┤
│  [Tab 2: Notifications]                                │
│                                                        │
│  WhatsApp Card                                         │
│  Phone: [+91 input]  [Verify]                         │
│  Guardian Phone: [+91 input]                           │
│  Alert level threshold: [warning/danger/critical]      │
│  EOD Report: [On/Off] + time                          │
│  Morning Briefing: [On/Off] + time                    │
│  [Test Notification] button                            │
│                                                        │
│  Push Notifications Card                               │
│  [Enable Push] toggle                                  │
│  [Subscribe browser] button                            │
│  Status: Subscribed / Not subscribed                   │
└────────────────────────────────────────────────────────┘
```

---

## Profile Tab Components

### Broker Connection Card
- **API**: `GET /api/zerodha/accounts` → list connected accounts
- **Connect**: Redirects to Zerodha OAuth (`GET /api/zerodha/connect` → Kite login URL)
- **Disconnect**: `POST /api/zerodha/disconnect` → revokes token, sets status=disconnected
- **Sync**: `POST /api/trades/sync` → triggers full sync from Kite
- **Validation**: ✅ Token encrypted (Fernet) in DB, never exposed in API responses

### Trading Profile Card
- **API**: `GET /api/profile/` (load) + `PUT /api/profile/` (save)
- **Zod validation** (client-side, pre-API):
  - experience_level: enum
  - risk_tolerance: enum
  - trading_capital: number > 0
  - ai_persona: enum
  - All 10 profile fields validated before API call
- **Validation**: ✅ Zod schema validated in Settings.tsx (session 19 fix)

### Trading Limits Card
- **API**: Same `PUT /api/profile/` (limits are fields on `UserProfile`)
- **Fields**: daily_loss_limit, max_position_size, sl_percent_futures, sl_percent_options, daily_trade_limit, cooldown_after_loss
- **Effect**: These thresholds are used by:
  - `BehaviorEngine` for pattern detection sensitivity
  - `DangerZoneService` for danger level assessment
  - Frontend `AlertContext.detectAllPatterns()` for client-side patterns
- **Validation**: ✅ Profile persisted in DB → used in all downstream detection

---

## Notifications Tab Components

### WhatsApp Card
- **API**: `PUT /api/profile/` (whatsapp_enabled, phone, guardian_phone, guardian_enabled, alert_threshold)
- **Test**: `POST /api/profile/guardian/test` → sends test WhatsApp message
- **Delivery**: Twilio WhatsApp API
- **Validation**: ✅ Guardian phone separate from user phone; guardian only gets critical alerts

### EOD/Morning Reports
- **Timing**: Celery beat tasks (IST timezone)
  - EOD: user-configured time (default 17:00 IST)
  - Morning briefing: user-configured time (default 08:30 IST)
- **API**: `PUT /api/profile/` (eod_report_time, morning_report_time)
- **Validation**: ✅ Times stored as HH:MM strings, beat tasks read from profile

### Push Notifications Card
- **Status**: `GET /api/notifications/status` → `{subscribed: bool}`
- **Subscribe**: `POST /api/notifications/subscribe` → stores VAPID subscription
- **Component**: `src/components/settings/NotificationSettings.tsx`
- **Note**: VAPID keys must be set in `.env` (`VAPID_PRIVATE_KEY`, `VAPID_PUBLIC_KEY`)
- **Validation**: ⚠️ VAPID keys not documented in `.env.example` — add before going live

---

## APIs Called

| Endpoint | When | Purpose |
|----------|------|---------|
| `GET /api/profile/` | Tab mount | Load all settings |
| `PUT /api/profile/` | Save button | Update profile |
| `GET /api/zerodha/accounts` | Profile tab | Broker connection status |
| `POST /api/zerodha/disconnect` | Disconnect button | Revoke token |
| `POST /api/trades/sync` | Sync button | Full trade sync |
| `POST /api/profile/guardian/test` | Test button | Test WhatsApp delivery |
| `GET /api/notifications/status` | Notifications tab | Push subscription status |
| `POST /api/notifications/subscribe` | Enable push | Register VAPID subscription |

---

## Validation Checklist

- [x] All 10 profile fields Zod-validated before API call (prevents bad data reaching DB)
- [x] Trading limits feed downstream pattern detection — change capital → patterns recalibrate
- [x] Disconnect clears `localStorage` (`tradementor_*` keys) — no stale state
- [x] AI persona change reflected in next Chat session
- [x] Guardian phone separate from user phone (independent notification channel)
- [x] VAPID keys need configuring before push notifications work end-to-end
- [x] `PUT /api/profile/` returns 422 on schema violation (Pydantic validation)
- [x] No hardcoded alert thresholds — all come from UserProfile in DB
