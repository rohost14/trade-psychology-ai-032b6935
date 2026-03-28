# Data Flows
*All critical data paths — from input to UI display*

---

## 1. Trade Lifecycle (Intraday MIS/NRML/MTF)

```
09:15 IST: Trader places order on Kite app/web
     │
     ▼
Zerodha executes fill → sends webhook to /api/webhooks/zerodha/postback
     │
     ├── Checksum verify (SHA-256) — invalid → 400, no processing
     ├── Rate limit check (sliding window) — exceeded → 429
     │
     ▼
process_webhook_trade.delay(order_data, broker_account_id)
     │
     ├── IDEMPOTENCY: Trade.processed_at IS NOT NULL → skip (already done)
     │
     ├── Classify trade:
     │     RELIANCE → EQUITY/EQ
     │     NIFTY2516025200CE → OPTIONS/CE (CE/PE check only on NSE/BSE F&O)
     │     BANKNIFTY25APR50000FUT → FUTURES/FUT
     │     Product: MIS/NRML/MTF (CNC skipped — delivery positions excluded)
     │
     ├── Normalize:
     │     timestamp → IST (pytz Asia/Kolkata)
     │     quantity → units (NOT lot size — Kite already returns units)
     │     exchange → standardize (NSE/BSE/NFO/BFO/MCX)
     │
     ├── FIFO P&L match (Redis lock, 60s TTL):
     │     BUY fill → open new position or add to existing LONG
     │     SELL fill → close LONG from oldest entry price (FIFO)
     │       → creates CompletedTrade (entry_price, exit_price, realized_pnl)
     │     SELL before BUY → open SHORT position
     │     Partial fill → update quantity, defer CompletedTrade until fully closed
     │
     ├── BehaviorEngine.detect_patterns():
     │     Queries CompletedTrade (real P&L), TradingSession, UserProfile
     │     11 patterns checked: overtrading, revenge, loss_aversion, fomo, etc.
     │     Threshold: UserProfile > style defaults > universal floors
     │     → RiskAlert created in DB if pattern detected (24h dedup)
     │
     ├── publish_event(account_id, "trade_update", {...}) → Redis Streams
     │
     └── Side effects:
           check_position_overexposure.delay()
           check_holding_loser_scheduled.apply_async(countdown=1800) [BUY only]
           run_portfolio_radar_for_account.delay() [60s debounce]
```

**Where P&L lives:**
- `Trade.pnl` = ALWAYS 0.0 (raw Kite order, before FIFO matching)
- `CompletedTrade.realized_pnl` = REAL P&L (FIFO matched)
- `Position.pnl` = unrealized P&L (from Kite positions API, live)

---

## 2. Pattern Detection Flow

### Backend (BehaviorEngine — source of truth for persistent alerts)
```
BehaviorEngine.detect_patterns(broker_account_id, db)
  → Queries CompletedTrade (last N trades, configurable per pattern)
  → Applies UserProfile thresholds
  → Creates RiskAlert in DB
  → Dedup: 24h window + 5-min bucket per (trigger_trade_id, pattern_type)
```

### Frontend (AlertContext — ephemeral client-side patterns)
```
AlertContext.runAnalysis()
  → Gets CompletedTrade[] from /api/trades/completed
  → Maps to Trade[] via CompletedTradeAdapter (real .pnl from realized_pnl)
  → detectAllPatterns(trades, capital, config) in patternDetector.ts
  → BehaviorPattern[] stored in AlertContext.patterns state
  → Shown as toast notifications in real-time
  → NOT persisted (session-only, refresh-safe)
```

**Important**: Frontend patterns are ephemeral signal (immediate, per-session). Backend patterns are the persisted record (RiskAlert in DB, shown in alert history).

---

## 3. Counterfactual P&L Flow (BlowupShield)

```
BehaviorEngine detects danger/critical pattern
  → RiskAlert created (severity=danger or critical)
    → trade_tasks.py triggers: create_alert_checkpoint.delay(alert_id)

T+0: create_alert_checkpoint
  → Snapshot: open position (qty, avg_price, market_cap)
  → get_ltp(instruments) → current market price
  → AlertCheckpoint.market_price_at_alert = LTP
  → AlertCheckpoint.status = "calculating"
  → self-chain: fetch_t5_pnl.apply_async(countdown=300)

T+5 min: fetch_t5_pnl
  → get_ltp() again
  → AlertCheckpoint.user_actual_pnl_t5 = (ltp_t5 - entry_price) × qty
  → self-chain: fetch_t30_pnl.apply_async(countdown=1500)

T+30 min: fetch_t30_pnl
  → get_ltp() again
  → AlertCheckpoint.counterfactual_pnl_t30 = (ltp_t30 - entry_price) × qty
  → money_saved = user_actual_pnl_t5 - counterfactual_pnl_t30
    (POSITIVE = user was right to exit; NEGATIVE = user would have made more by holding)
  → AlertCheckpoint.status = "complete"
  → self-chain: complete_checkpoint.apply_async(countdown=1800)

T+60 min: complete_checkpoint
  → publish_event("shield_update") → browser re-fetches BlowupShield
```

**Edge cases:**
- Position already closed at T+5 → user_actual_pnl = 0 (not the full exit P&L)
- Market closed (after 15:30 IST) → LTP = last traded price (stale but acceptable)
- Kite API error → retry with exponential backoff, max 3 attempts

---

## 4. WebSocket Reconnect Flow

```
Browser disconnects (network drop, sleep, etc.)
  │
  ▼
WebSocketContext detects close → starts reconnect with exponential backoff
  Interval: 1s → 2s → 4s → 8s → 16s → 30s (max)
  │
  ▼
Reconnect: WebSocket /api/ws?broker_account_id=X&since={last_event_id}
  │           last_event_id loaded from localStorage
  ▼
First message: {token: "JWT"} (auth handshake)
  │
  ▼
Server: XREAD stream:{account_id} COUNT 100 from since=last_event_id
  │
  ├── Replays each missed event in order (trade_update, alert_update, etc.)
  │     Each event triggers the same handler as a live event
  │
  └── replay_complete event sent
        → Browser triggers full re-fetch of all dashboard data
        → UI guaranteed to be in sync with server state
```

---

## 5. Zerodha OAuth Flow

```
User → Settings → "Connect Zerodha"
  │
  ▼
GET /api/zerodha/connect
  → Generates Kite login URL: https://kite.zerodha.com/connect/login?api_key=X&v=3
  → Stores state token in Redis (30s TTL)
  → Returns URL to frontend
  │
  ▼
Frontend → redirect to Kite login URL
  │
  ▼
User authenticates on Zerodha → redirect to:
GET /api/zerodha/callback?request_token=Y&status=success
  │
  ├── Exchange request_token → access_token (Kite API)
  ├── Fetch user profile from Kite (broker_email, broker_user_id)
  ├── Encrypt access_token with Fernet → BrokerAccount.access_token
  ├── Upsert BrokerAccount (broker_email as stable user identifier)
  ├── Generate JWT: {sub: user_id, bid: broker_account_id, exp: 24h}
  │
  ▼
Redirect: /dashboard#token={JWT}
  │
  ▼
Frontend:
  → Extracts JWT from URL fragment (never in query string, never logged)
  → Stores in localStorage as tradementor_token
  → URL fragment cleared immediately
  → BrokerContext.isConnected = true
```

---

## 6. Margin Data Flow

```
User opens Dashboard
  │
  ▼
MarginStatusCard mounts
  → GET /api/zerodha/account/{id}/balance
    → margin_service.get_margin_snapshot(account_id)
      → Check Redis: ltp:margin:{account_id} (5-min TTL)
        HIT → return cached snapshot
        MISS → GET Kite /user/margins → store in Redis + MarginSnapshot table
  │
  ▼
On trade fill (webhook processed):
  → zerodha_service refreshes margin from Kite
  → publish_event("margin_update", new_snapshot)
  → WebSocketContext receives margin_update
  → MarginStatusCard re-fetches /balance
  → No setInterval polling
```

---

## 7. AI Coach Flow

```
User opens /chat
  │
  ▼
GET /api/coach/session/today
  → Queries CoachSession WHERE date = today (IST) AND account_id = X
  → If exists → return messages + snapshot
  → If not → create new session, build snapshot:
      {pnl_today, trades_today, wins, losses, consecutive_losses,
       active_alerts, risk_state, open_positions_count, profile}
  │
  ▼
User sends message
  │
  ▼
POST /api/coach/chat/stream
  → Build system prompt:
      [persona rules] + [7 absolute rules] + [snapshot context]
  → POST to OpenRouter (Claude Haiku via /chat/completions with stream=true)
  → SSE stream: response tokens → frontend
  → After stream completes: persist full exchange to CoachSession.messages
  │
  ▼
Frontend streams tokens into chat UI progressively
```
