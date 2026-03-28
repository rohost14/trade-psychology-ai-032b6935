# API Reference
*All endpoints, auth requirements, and expected responses*

---

## Authentication

All endpoints (except `/health`, `/`, `/api/zerodha/connect`, `/api/zerodha/callback`) require:
```
Authorization: Bearer {JWT}
```

JWT payload: `{sub: user_id, bid: broker_account_id, exp: unix_timestamp}`

Dependency: `get_verified_broker_account_id()` — decodes JWT, verifies broker_account_id matches DB, checks `token_revoked_at IS NULL`.

---

## Zerodha / Auth (`/api/zerodha/*`)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/zerodha/connect` | None | Generate Kite OAuth login URL |
| GET | `/api/zerodha/callback` | None | Exchange request_token → access_token, redirect with JWT |
| GET | `/api/zerodha/accounts` | JWT | List connected broker accounts |
| POST | `/api/zerodha/disconnect` | JWT | Revoke token, set status=disconnected |
| POST | `/api/zerodha/sync` | JWT | Trigger full trade sync from Kite |
| GET | `/api/zerodha/account/{id}/balance` | JWT | Get margin/balance snapshot |

---

## Trades (`/api/trades/*`)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/trades/sync` | JWT | Sync trades from Kite (triggers Celery pipeline) |
| GET | `/api/trades/` | JWT | List raw Trade records |
| GET | `/api/trades/stats` | JWT | Win rate, total P&L, trade count stats |
| GET | `/api/trades/completed` | JWT | CompletedTrade records (real FIFO P&L) |
| GET | `/api/trades/incomplete` | JWT | IncompletePosition records (sync gaps) |
| GET | `/api/trades/{trade_id}` | JWT | Single trade detail |

**Note**: Always use `/api/trades/completed` for P&L data, not `/api/trades/`. `Trade.pnl` is always 0.

---

## Positions (`/api/positions/*`)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/positions/` | JWT | Current open positions (from Kite, with LTP) |

---

## Risk & Alerts

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/risk/state` | JWT | Current risk state (safe/caution/danger) |
| GET | `/api/risk/alerts` | JWT | List RiskAlert records (`?hours=48&limit=20`) |
| POST | `/api/risk/alerts/{id}/acknowledge` | JWT | Acknowledge alert |
| POST | `/api/alerts/create` | JWT | Create manual alert |
| GET | `/api/alerts/` | JWT | List alerts (alias) |

---

## Danger Zone (`/api/danger-zone/*`)

| Method | Path | Auth | Rate Limit | Purpose |
|--------|------|------|-----------|---------|
| GET | `/api/danger-zone/status` | JWT | None | Danger level assessment |
| GET | `/api/danger-zone/summary` | JWT | None | Full summary with cooldown history |
| POST | `/api/danger-zone/trigger-intervention` | JWT | 4/15min | Trigger cooldown + notify |
| GET | `/api/danger-zone/escalation-status` | JWT | None | Escalation history for a trigger |
| POST | `/api/danger-zone/reset-escalation` | JWT | None | Reset escalation level |
| GET | `/api/danger-zone/notification-stats` | JWT | None | Notification count stats |

---

## Analytics (`/api/analytics/*`)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/analytics/overview` | JWT | Stats: trades, win rate, P&L, RRR (`?period=30`) |
| GET | `/api/analytics/behavior` | JWT | Pattern heatmap + top 5 costly patterns |
| GET | `/api/analytics/performance` | JWT | P&L curve, hold times, hours heatmap |
| GET | `/api/analytics/risk` | JWT | Margin, drawdown, concentration over time |
| GET | `/api/analytics/summary` | JWT | Combined summary (used by AI coach) |
| GET | `/api/analytics/ai-narrative` | JWT | AI-generated performance narrative |
| POST | `/api/analytics/export` | JWT | Export PDF/CSV of analytics |

---

## Coach (`/api/coach/*`)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/coach/session/today` | JWT | Load/create today's chat session |
| POST | `/api/coach/chat/stream` | JWT | Streaming AI response (SSE) |
| POST | `/api/coach/save-insight` | JWT | Save AI message to journal |
| GET | `/api/coach/insights` | JWT | List saved insights |

---

## Profile (`/api/profile/*`)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/profile/` | JWT | Load UserProfile |
| PUT | `/api/profile/` | JWT | Update UserProfile (trading limits, persona, etc.) |
| GET | `/api/profile/notification-status` | JWT | WhatsApp + push notification status |
| POST | `/api/profile/guardian/test` | JWT | Send test WhatsApp to guardian phone |

---

## Behavioral Analysis (`/api/behavioral/*`)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/behavioral/patterns` | JWT | BehaviorEngine pattern results |
| POST | `/api/behavioral/evaluate` | JWT | Run BehaviorEngine on demand |

---

## Portfolio Radar (`/api/portfolio-radar/*`)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/portfolio-radar/metrics` | JWT | Per-position risk metrics (DTE, theta, breakeven) |
| GET | `/api/portfolio-radar/concentration` | JWT | Portfolio concentration analysis |
| GET | `/api/portfolio-radar/gtt-discipline` | JWT | GTT order compliance % |
| POST | `/api/portfolio-radar/sync-gtts` | JWT | Pull latest GTTs from Kite |

---

## Blowup Shield (`/api/shield/*`)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/shield/summary` | JWT | Hero stats (capital_defended, shield_score) |
| GET | `/api/shield/timeline` | JWT | Intervention timeline with checkpoints |
| GET | `/api/shield/patterns` | JWT | Pattern breakdown (occurrences + total saved) |

---

## Journal (`/api/journal/*`)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/journal/` | JWT | Create journal entry |
| GET | `/api/journal/` | JWT | List journal entries |
| GET | `/api/journal/{id}` | JWT | Get single entry |
| PUT | `/api/journal/{id}` | JWT | Update entry |
| DELETE | `/api/journal/{id}` | JWT | Delete entry |

**Note**: trade_id ownership verified — 403 if trade doesn't belong to requesting account.

---

## Goals (`/api/goals/*`)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/goals/` | JWT | Create goal commitment |
| GET | `/api/goals/` | JWT | List goals |
| PUT | `/api/goals/{id}` | JWT | Update goal |
| DELETE | `/api/goals/{id}` | JWT | Delete goal |

---

## Cooldown (`/api/cooldown/*`)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/cooldown/active` | JWT | Get active cooldown (if any) |
| POST | `/api/cooldown/start` | JWT | Start a cooldown manually |
| POST | `/api/cooldown/cancel` | JWT | Cancel active cooldown |

---

## Notifications (`/api/notifications/*`)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/notifications/subscribe` | JWT | Register push subscription (VAPID) |
| POST | `/api/notifications/send` | JWT | Send test push notification |
| GET | `/api/notifications/status` | JWT | Check subscription status |

---

## Reports (`/api/reports/*`)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/reports/send-daily` | JWT | Trigger EOD report send |
| POST | `/api/reports/send-weekly` | JWT | Trigger weekly summary send |
| GET | `/api/reports/list` | JWT | List sent reports |

---

## WebSocket

| Protocol | Path | Auth |
|----------|------|------|
| WebSocket | `/api/ws` | First-message JWT handshake |

Query params: `?broker_account_id=UUID&since=event_id`

Messages after auth:
- Server → client: `{type: "trade_update"|"alert_update"|..., data: {...}, event_id: "X"}`
- Server → client: `{type: "replay_complete"}` (after reconnect replay)
- Client can send: heartbeat `{type: "ping"}` → server responds `{type: "pong"}`

---

## Infrastructure

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/health` | None | DB + Redis + circuit breaker status |
| GET | `/api/metrics` | None | Prometheus metrics |
| GET | `/` | None | Welcome message |
