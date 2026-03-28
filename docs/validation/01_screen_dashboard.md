# Screen 01: Dashboard
*Route: `/dashboard` | File: `src/pages/Dashboard.tsx`*

---

## Purpose
The hero screen. Trader lands here after login and sees everything they need: current risk state, open positions, recent trades, margins, active alerts, and a quick shield preview. All data is **event-driven via WebSocket** — zero polling.

---

## Layout (Desktop)

```
┌─────────────────────────────────────────────────────────────────┐
│  HEADER: TradeMentor logo | Nav links | Connection dot | Alerts │
├───────────────────────────────────────────────────────┬─────────┤
│  RiskGuardianCard (full width)                        │         │
│  [SAFE / CAUTION / DANGER] + AI message              │         │
│  Active patterns (badges) + recommendations           │         │
├───────────────────────────────────────────────────────┤         │
│  Row 2: MarginStatusCard | MarginInsightsCard         │         │
│         BlowupShieldCard  | ProgressTrackingCard      │         │
├───────────────────────────────────────────────────────┤         │
│  RecentAlertsCard (last 8 alerts, 48hr window)        │         │
├───────────────────────────────────────────────────────┤         │
│  OpenPositionsTable                                   │         │
│  [Symbol | Qty | Entry | LTP | Unr. P&L | Action]    │         │
├───────────────────────────────────────────────────────┤         │
│  ClosedTradesTable (last 50 completed trades)         │         │
│  [Symbol | Dir | Qty | Entry | Exit | P&L | Dur]      │         │
├───────────────────────────────────────────────────────┤         │
│  PredictiveWarningsCard                               │         │
│  "Next likely pattern: revenge_trading (78%)"         │         │
└───────────────────────────────────────────────────────┴─────────┘
```

---

## Components & Data Sources

### RiskGuardianCard (`src/components/dashboard/RiskGuardianCard.tsx`)
- **API**: `GET /api/risk/state` → `{level, message, patterns, session_pnl}`
- **Trigger**: `lastTradeEvent` or `lastAlertEvent` from WebSocketContext
- **State**: `safe` (green) / `caution` (amber) / `danger` (red)
- **Content**: Risk level badge, AI-generated message, active pattern badges, session P&L
- **Validation**: ✅ Level maps to `risk-safe` / `risk-caution` / `risk-danger` CSS variables

### MarginStatusCard (`src/components/dashboard/MarginStatusCard.tsx`)
- **API**: `GET /api/zerodha/account/{id}/balance` → `{available, utilized, net}`
- **Trigger**: `lastMarginEvent` from WebSocketContext (margin_update events from Redis Streams)
- **State**: Shows available margin, utilization %, manual refresh button
- **Validation**: ✅ One fetch on mount (Redis cache, 5-min TTL) + WebSocket updates only

### MarginInsightsCard (`src/components/dashboard/MarginInsightsCard.tsx`)
- **API**: Derived from margin history in DB
- **Content**: Utilization trend, recommendations ("You're using 82% of margin — consider reducing exposure")
- **Validation**: ✅ Informational only, no write operations

### BlowupShieldCard (`src/components/dashboard/BlowupShieldCard.tsx`)
- **API**: `GET /api/shield/summary` → `{capital_defended, shield_score, heeded_streak}`
- **Content**: Mini version of full BlowupShield stats with "View full report" link
- **Validation**: ✅ Read-only, links to `/blowup-shield`

### ProgressTrackingCard (`src/components/dashboard/ProgressTrackingCard.tsx`)
- **API**: `GET /api/goals/` + `GET /api/cooldown/active`
- **Content**: Cooldown status (active / inactive + duration remaining), current streak, daily adherence %
- **Validation**: ✅ Displays active cooldown countdown correctly

### RecentAlertsCard (`src/components/dashboard/RecentAlertsCard.tsx`)
- **API**: `GET /api/risk/alerts?hours=48` → last 8 alerts
- **Trigger**: `lastAlertEvent` from WebSocketContext
- **Content**: Alert cards with severity badge (low/medium/high/critical), pattern name, timestamp, acknowledge button
- **Acknowledge**: `POST /api/risk/alerts/{id}/acknowledge`
- **Validation**: ✅ Real-time via WebSocket, no polling

### OpenPositionsTable (`src/components/dashboard/OpenPositionsTable.tsx`)
- **API**: `GET /api/positions/` → current open positions from Kite
- **Trigger**: `lastTradeEvent` from WebSocketContext
- **Content**: Symbol, exchange, qty, avg entry price, LTP (live), unrealized P&L, "Journal" action button
- **LTP source**: Live from KiteTicker → Redis cache → WebSocket price events
- **Journal action**: Opens `TradeJournalSheet` slide-out for the selected trade
- **Validation**: ✅ LTP updates via WebSocket price events, not polling

### ClosedTradesTable (`src/components/dashboard/ClosedTradesTable.tsx`)
- **API**: `GET /api/trades/completed?limit=50` → CompletedTrade records
- **Trigger**: `lastTradeEvent` from WebSocketContext
- **Content**: Symbol, direction badge (LONG/SHORT), qty, avg entry, avg exit, realized P&L (colour-coded), duration
- **P&L source**: `CompletedTrade.realized_pnl` (FIFO-matched, real)
- **Journal action**: Opens `TradeJournalSheet` slide-out
- **Validation**: ✅ Uses CompletedTrade.realized_pnl, NOT Trade.pnl (which is always 0)

### PredictiveWarningsCard (`src/components/dashboard/PredictiveWarningsCard.tsx`)
- **API**: `GET /api/behavioral/patterns?predictive=true`
- **Trigger**: `lastTradeEvent?.timestamp` or `lastAlertEvent?.timestamp` changes
- **Content**: "Next likely pattern: {name} ({confidence}%)", estimated cost
- **Validation**: ✅ Event-driven (5-min setInterval was removed this session)

### TradeJournalSheet (`src/components/dashboard/TradeJournalSheet.tsx`)
- **API**: `POST /api/journal/` (new), `PUT /api/journal/{id}` (update)
- **Content**: Slide-out with fields: setup_notes, psychology, outcome_notes
- **Validation**: ✅ Ownership checked server-side (403 if trade doesn't belong to account)

---

## WebSocket Events Consumed

| Event Type | Triggers |
|-----------|---------|
| `trade_update` | Re-fetch positions + closed trades |
| `alert_update` | Re-fetch alerts + risk state |
| `margin_update` | Re-fetch margin |
| `price_update` | Update LTP column in positions table |
| `replay_complete` | All above after reconnect |

---

## State Management

```
BrokerContext     → brokerAccountId, isConnected, isTokenExpired
WebSocketContext  → lastTradeEvent, lastAlertEvent, lastMarginEvent
AlertContext      → alerts, patterns (client-side behavioral)
Local component   → loading, error states per card
```

---

## Known Issues / Gaps

| Issue | Severity | Notes |
|-------|----------|-------|
| Holdings card shows delivery holdings (CNC) | ⚪ Cosmetic | Not in nav for F&O traders, but present in code |
| PredictiveWarnings fires on ANY trade event | ⚪ Low | Could debounce to avoid burst API calls |
| No skeleton loading states on initial mount | ⚪ Low | Cards flash empty before data loads |

---

## Validation Checklist

- [x] Broker not connected → shows "Connect Zerodha" prompt, not broken UI
- [x] No trades yet → empty state messages in tables (not crashes)
- [x] Token expired → TokenExpiredBanner shown above content
- [x] WebSocket disconnects → reconnects automatically, replays missed events
- [x] Alert acknowledged → removed from card without page reload
- [x] P&L values are FIFO-calculated, not raw order fills
- [x] All API calls include `broker_account_id` auth guard
- [x] ErrorBoundary wraps `<Outlet />` — single card crash won't blank the page
