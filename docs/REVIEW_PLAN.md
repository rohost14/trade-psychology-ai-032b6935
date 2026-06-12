# Feature Logic Review Plan

End-to-end code review — one feature at a time, in priority order.
Goal: verify correctness of logic, data flow, edge cases. Not style.

---

## Order of Review

| # | Feature | Why this order |
|---|---|---|
| 1 | Zerodha OAuth + Trade Sync | Foundation — nothing works without it |
| 2 | Behavior Engine + Alert Pipeline | Core value prop |
| 3 | Dashboard | First thing users see |
| 4 | Analytics (8 tabs) | Most complex, most backend logic |
| 5 | AI Coach | LLM + SEBI guard + context building |
| 6 | Morning Intent + EOD Comparison | Push-based, async, easy to get wrong |
| 7 | Early Warning | Redis-based, dedup logic |
| 8 | Goals + Streak | Simple but data integrity matters |
| 9 | My Patterns + Risk Monitor | Aggregation logic |
| 10 | Blowup Shield | Cooldown + lock logic |
| 11 | Settings + Notifications | Push subscription, guardian phone |
| 12 | WebSocket real-time | Event bus, reconnect, replay |
| 13 | Reports | Low priority, WhatsApp pending |
| 14 | Admin Panel | Internal tooling, lowest risk |

---

## Per-Feature Review Scope

### 1. Zerodha OAuth + Trade Sync
**Frontend**: `BrokerContext.tsx`, `Settings.tsx` (Profile tab)
**Backend**: `api/zerodha.py`, `services/zerodha_service.py`, `tasks/trade_tasks.py`, `services/trade_sync_service.py`, `services/position_ledger_service.py`

Check:
- OAuth CSRF state nonce (Redis TTL, atomic GET+DELETE)
- Token storage (Fernet encryption on `api_secret_enc`)
- Webhook postback flow: order → fill → FIFO flush → CompletedTrade
- REST sync flow: `sync_trades_for_broker_account` — does it produce same result as webhook path?
- `classify_trade()` — correct asset_class/instrument_type for all exchange/product combos
- FIFO lock contention on rapid fills (race condition between two concurrent fills)
- Duplicate prevention: `uq_trades_broker_order` constraint actually enforced?

---

### 2. Behavior Engine + Alert Pipeline
**Frontend**: `AlertContext.tsx`, `pages/Alerts.tsx`
**Backend**: `services/behavior_engine.py`, `tasks/trade_tasks.py` (run_risk_detection_async + run_behavior_engine_full_session), `services/risk_detector.py`

Check:
- `session_trades` query: correct time window, excludes current trade (CROSS-1)
- `completed_trade_id` threading from FIFO flush → detection (INVOKE-1)
- Dedup logic: per-pattern windows applied correctly, historical replay uses exit_time (INVOKE-2)
- All 22+ patterns: do severity levels match documented intent?
- `cooldown_violation` → `severity="info"` → saved to DB, no notification
- Alert consolidation (5-min bucket + hard cap) — what's the cap, does it work?
- Full-session vs real-time detection — do they produce consistent results for same trade set?
- Frontend: `acknowledgeAlert` actually calls backend, optimistic update correct?

---

### 3. Dashboard
**Frontend**: `pages/Dashboard.tsx`, `components/dashboard/*`, `SessionHeroCard`, `SetupNudgeCard`, `VIX` inline
**Backend**: `api/positions.py`, `api/risk.py` (state endpoint), `services/vix_service.py`

Check:
- Hero stats (P&L, trades today, risk state) — data source correct, IST boundaries
- Positions table: live price update via WebSocket, P&L calculation
- Risk state (safe/caution/danger) — threshold logic in `risk_detector.py`
- VIX fetch: cache TTL, fallback if NSE API down
- SetupNudgeCard: when does it show/hide? condition correct?
- FAB (AI Coach): opens correct context, not visible to guest

---

### 4. Analytics (8 Tabs)
**Frontend**: `components/analytics/*`, each tab component
**Backend**: `api/analytics.py` (large file — review endpoint by endpoint)

Tabs to review individually:
- **Summary**: P&L chart, win rate, profit factor — data boundaries IST-correct?
- **Patterns**: pattern frequency, heatmap — uses RiskAlert data or CompletedTrade?
- **Trades**: table, filters — pagination? large dataset performance?
- **BTST**: entry/exit filter logic (already verified correct, confirm once more)
- **% Return**: calculation base (capital? margin?)
- **Edge Map**: signal-to-noise, is the underlying logic meaningful?
- **Expiry**: `GET /api/analytics/expiry-pattern` — uses `is_expiry_day()` or hardcoded Thursday?
- **Journal**: emotion tag → avg P&L correlation — data source, min sample size guard?

---

### 5. AI Coach
**Frontend**: `pages/Chat.tsx`, FAB in Dashboard
**Backend**: `api/coach.py`, `services/ai_service.py`, SEBI guard in `tasks/report_tasks.py`

Check:
- SEBI regex guard: fires before LLM, returns canned response — no API credit used?
- Context building: what trades/alerts/patterns get passed to LLM? capped correctly?
- SSE streaming: frontend handles partial chunks, reconnect on drop?
- Cache: `ai_cache["coach_insight"]` — TTL check, stale invalidation
- Guest mode: coach endpoint accessible without broker account?
- History trimmed to 6 messages — does it truncate correctly, maintain coherence?

---

### 6. Morning Intent + EOD Comparison
**Frontend**: `MorningIntentCard.tsx`, `EodComparisonCard.tsx` (Dashboard, time-gated)
**Backend**: `tasks/intent_tasks.py`, `api/session_intent.py`, migration 060

Check:
- Morning card: shows 7–10 AM IST only — timezone logic correct?
- EOD card: shows after 15:30 IST — correct boundary?
- `POST /api/session-intent` — stores intent, triggers acknowledge
- EOD comparison: fetches today's CompletedTrades, compares against morning intent — IST date boundary correct?
- Push at 8:30 AM: Celery beat schedule, IST offset correct in crontab?
- Danger-day context injection: fetches `get_personalized_insights()`, checks today's day name against `danger_days`

---

### 7. Early Warning
**Backend**: `tasks/intent_tasks.py` (or early warning module — find exact file)

Check:
- 70% P&L limit trigger: calculated against which limit? (daily max loss threshold)
- 80% trade count trigger: count source (session_trades query)
- Redis dedup: key format, TTL, prevents double-send within session
- Consecutive-loss check excluded (confirmed intentional, no re-raise needed)
- Push delivery: same FCM path as morning push?

---

### 8. Goals + Streak
**Frontend**: `components/goals/*`, Goals page
**Backend**: `api/analytics.py` (progress endpoint), `models/goal.py`

Check:
- Goal creation: which fields required, defaults?
- Streak calculation: based on alert-free days or profitable days?
- Progress endpoint: this-week vs last-week comparison — IST boundaries (already verified, confirm)
- `clean_days` metric — how computed, can it go negative?
- Goal `primary_segment` field — used in EOD report segmentation, must be accurate

---

### 9. My Patterns + Risk Monitor
**Frontend**: `pages/MyPatterns.tsx` (Risk Monitor + Weekly Score sections)
**Backend**: `api/behavioral.py` or `api/risk.py`

Check:
- Weekly score: derived from real RiskAlert data (confirmed fixed) — verify formula
- Pattern frequency: 7-day window, IST-correct?
- Risk Monitor: same data as Dashboard risk state or separate calculation?
- "Strength/weakness" labels: how assigned from pattern counts?

---

### 10. Blowup Shield
**Frontend**: `pages/BlowupShield.tsx` (or component)
**Backend**: `api/cooldown.py`, cooldown model, `_trigger_cooldown` in risk_detector

Check:
- Cooldown creation: triggered by which patterns/thresholds?
- `active_cooldowns` query in behavior engine context: fetches only non-expired?
- Cooldown acknowledge endpoint: marks cooldown as acknowledged, does NOT delete
- Frontend: shows remaining time, correct expiry display?
- If user keeps trading during cooldown: `cooldown_violation` now fires (severity=info) — does it feed back into risk score?

---

### 11. Settings + Notifications
**Frontend**: `pages/Settings.tsx` (Profile, Notifications, Insights tabs)
**Backend**: `api/zerodha.py` (account update), push subscription endpoints

Check:
- Guardian phone: saved to User model, used by WhatsApp + alert service
- Push subscription: `PushSubscription` model, VAPID signing correct
- Notification preferences: which alerts can be muted? preference stored where?
- Insights tab (`InsightsTab.tsx`): ML pattern insights — data source, stale cache handling?

---

### 12. WebSocket Real-time
**Frontend**: `WebSocketContext.tsx`, `useWebSocket` hook
**Backend**: `api/websocket.py`, `core/event_bus.py`

Check:
- Auth flow: first message must be auth token, `isConnected` set on `auth_ok` only
- Reconnect: exponential backoff, `last_id` NOT reset to `$` on reconnect (confirmed fixed)
- Replay: `?since=last_event_id` — backend XREAD from that ID, returns missed events
- Price updates: throttled? or every tick?
- `isReconnecting` flag: set on non-clean close, reset on auth_ok (confirmed correct)
- Guest mode: WebSocket endpoint accessible without account?

---

### 13. Reports
**Frontend**: `pages/Reports.tsx`
**Backend**: `tasks/report_tasks.py`, `services/retention_service.py`

Check:
- EOD report: equity traders only (commodity skipped — confirmed)
- Commodity EOD: separate task, separate schedule
- Weekly summary: pattern strength/weakness from real RiskAlert data (confirmed fixed)
- Report content: what data is included? accurate for the day?
- WhatsApp delivery: blocked on Meta approval — does failure degrade gracefully?

---

### 14. Admin Panel
**Frontend**: admin pages (9 sub-pages)
**Backend**: admin routers

Check:
- Auth: admin endpoints protected by separate auth, not user JWT
- User management: can admin see all accounts?
- Pattern override: can admin adjust thresholds per user?
- Broadcast: any endpoint that can send mass notifications — confirm rate limiting

---

## Review Session Format

Each session:
1. Read frontend → backend flow for the feature
2. Identify any logic gaps, wrong assumptions, or edge cases
3. Flag: BUG (wrong behavior) / RISK (could fail under load/edge input) / COSMETIC
4. Fix only confirmed bugs — no speculative changes
5. Update this doc with findings

---

## What We Are NOT Reviewing

- UI pixel-perfect styling
- Code formatting / naming conventions  
- Features explicitly deferred: morning dynamic personalization, WhatsApp day 2, Dhan integration, Capacitor, Reports page (low priority)
