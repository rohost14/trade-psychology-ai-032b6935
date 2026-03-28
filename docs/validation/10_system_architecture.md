# System Architecture
*TradeMentor AI — Full Architecture Reference*

---

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser (React + Vite)                                         │
│  7 screens + ErrorBoundary × 2 + Sentry + WebSocket client      │
└───────────────┬──────────────────────────────┬─────────────────┘
                │ HTTPS/WSS                     │ HTTPS
                ▼                               ▼
┌───────────────────────────┐    ┌──────────────────────────────┐
│  FastAPI (uvicorn)         │    │  Zerodha Kite API            │
│  24 API routers            │    │  Orders, trades, positions,  │
│  WebSocket manager         │    │  margins, GTT, KiteTicker    │
│  Request ID middleware      │    └──────────────────────────────┘
│  Rate limiting middleware   │
│  Security headers           │
└──────┬────────────────┬────┘
       │                │
       ▼                ▼
┌────────────┐   ┌─────────────────────────────────────────────┐
│ PostgreSQL  │   │  Redis (Upstash, AOF persistence enabled)   │
│ (Supabase)  │   │  ├── Celery broker queue                    │
│             │   │  ├── Redis Streams (stream:events + per-acct)│
│ 23 models   │   │  ├── LTP cache (2s TTL)                     │
│ 9 indexes   │   │  ├── Rate limiter (sliding window)          │
│ pgbouncer   │   │  ├── Circuit breaker state                  │
│ pooler      │   │  ├── OAuth auth codes (30s TTL, atomic getdel)│
│             │   │  └── Various SETNX locks                    │
└────────────┘   └─────────────────────────────────────────────┘
                          │
                          ▼
              ┌──────────────────────┐
              │  Celery Workers      │
              │  (gevent pool, 50)   │
              │  ├── trade_tasks      │
              │  ├── alert_tasks      │
              │  ├── checkpoint_tasks │
              │  ├── position_monitor │
              │  ├── portfolio_radar  │
              │  ├── report_tasks     │
              │  └── reconciliation   │
              └──────────────────────┘
                          │
                          ▼
              ┌──────────────────────┐
              │  External Services   │
              │  Twilio (WhatsApp)   │
              │  OpenRouter (LLM)    │
              │  Sentry (errors)     │
              └──────────────────────┘
```

---

## Event-Driven Architecture (Phase 4)

**Zero polling in the system.** Every update is event-driven.

### How it works

```
1. Zerodha webhook → POST /api/webhooks/zerodha/postback
2. Webhook handler validates checksum → enqueues process_webhook_trade.delay()
3. Celery worker processes:
   - Classify trade (asset class, instrument, product)
   - Normalize (IST timestamp, lot size, exchange)
   - FIFO P&L match → create/update CompletedTrade
   - Run BehaviorEngine → create RiskAlert if pattern detected
   - publish_event(broker_account_id, "trade_update", {...})
   - Trigger position monitor + portfolio radar (per-fill, not beat)
4. publish_event() dual-writes to:
   - stream:events (global, MAXLEN 10000)
   - stream:{broker_account_id} (per-account, MAXLEN 500)
5. start_event_subscriber() (boot task) runs XREAD BLOCK 100ms loop:
   - Routes events to WebSocket manager
   - WebSocket manager broadcasts to connected browser
6. Browser WebSocketContext receives event:
   - Stores last_event_id in localStorage
   - Triggers React Query re-fetches for affected data
7. On reconnect: WebSocket ?since=last_event_id → XREAD replay
   - All missed events replayed
   - replay_complete event sent
   - Browser re-fetches all stale data
```

### Event Types

| Event | Emitted by | Consumed by |
|-------|-----------|------------|
| `trade_update` | trade_tasks.py | Dashboard, Analytics, My Patterns |
| `alert_update` | behavior detection, position monitor | Dashboard, My Patterns |
| `margin_update` | zerodha_service (after sync) | Dashboard margin cards |
| `price_update` | price_stream_service (KiteTicker) | OpenPositionsTable LTP column |
| `shield_update` | checkpoint_tasks (T+60) | BlowupShield timeline |
| `replay_complete` | websocket.py (on reconnect) | WebSocketContext (triggers full re-fetch) |

---

## Trade Processing Pipeline

```
Webhook (Zerodha) → order fill notification
  │
  ├── Checksum verify: SHA-256(order_id + timestamp + api_secret)
  │   FAIL → HTTP 400 (no Celery task enqueued)
  │
  ├── Idempotency check: Trade.processed_at IS NOT NULL?
  │   YES → HTTP 200 (already processed, skip)
  │
  └── process_webhook_trade.delay(order_id, account_id)
        │
        ├── Trade.processed_at = now() (atomic update + race verify)
        ├── Classify: trade_classifier.py
        │     asset_class: EQUITY | FUTURES | OPTIONS
        │     instrument_type: EQ | FUT | CE | PE
        │     product: MIS | NRML | MTF (skip CNC)
        │
        ├── Normalize: IST timestamp, exchange standardization
        │
        ├── FIFO P&L match:
        │     Redis SETNX lock f"fifo_lock:{account_id}" (60s TTL)
        │     position_ledger_service.process_fill()
        │     CompletedTrade upsert (UNIQUE on broker_account_id + exit_trade_ids)
        │
        ├── BehaviorEngine.detect_patterns(account_id, db)
        │     11 patterns, thresholds from UserProfile
        │     Creates RiskAlert for each detected pattern
        │
        ├── publish_event("trade_update") → Redis Streams
        │
        ├── check_position_overexposure.delay() (immediate)
        │
        ├── If BUY fill + no existing chain:
        │     Redis SETNX f"holding_loser_chain:{account_id}" (TTL=1900s)
        │     check_holding_loser_scheduled.apply_async(countdown=1800)
        │
        └── run_portfolio_radar_for_account.delay()
              (60s debounce via radar_debounce:{account_id})
```

---

## WebSocket Architecture

```
Browser → WebSocket /api/ws?broker_account_id=X&since=last_event_id
  │
  ├── First message: {token: "JWT"} (auth handshake — token never in URL)
  │     Verified via get_verified_broker_account_id()
  │     FAIL → connection closed
  │
  ├── Backend: register account_id → connection in WebSocketManager
  │
  ├── Replay: XREAD stream:{account_id} from since=last_event_id
  │     All missed events replayed sequentially
  │     replay_complete event sent
  │
  ├── Ongoing: start_event_subscriber() loop broadcasts new events
  │     asyncio.wait_for(send_json, timeout=2.0) — slow clients don't block
  │     asyncio.gather() for concurrent sends (not sequential)
  │
  └── Disconnect → WebSocketManager.disconnect(account_id)
        Browser: exponential backoff reconnect (1s → 2s → 4s → ... → 30s max)
        On reconnect: since=last_event_id (resume, no data loss)
```

---

## Live Price Streaming

Separate from Redis Streams (different channel):

```
KiteTicker (Zerodha WebSocket) per account
  → MODE_LTP (one quote per instrument per tick)
    → Redis LTP cache: SET ltp:{instrument} value EX 2
    → WebSocket broadcast: price_update to subscribers
      (throttled: max 1 broadcast/second/instrument)

Lifecycle:
  price_stream.restart_all(db)   — called on FastAPI startup
  price_stream.start_account(id) — called when WS client connects
  price_stream.stop_account(id)  — called when WS client disconnects
  price_stream.refresh_subscriptions(id) — called after trade fill
```

**Scaling note**: Per-user KiteTicker = 1 WebSocket to Zerodha per account. Zerodha throttles at ~10 simultaneous connections. Shared KiteTicker is a Phase C item.

---

## Authentication Flow

```
1. User clicks "Connect Zerodha"
2. GET /api/zerodha/connect → generates Kite login URL with api_key + redirect_uri
3. User logs in on Zerodha → redirected to /api/zerodha/callback?request_token=X
4. Callback: exchanges request_token for access_token (Kite API)
   - access_token encrypted with Fernet → stored in BrokerAccount.access_token
   - Auth code stored in Redis with 30s TTL (atomic getdel — no replay attacks)
   - JWT generated: {sub: user_id, bid: broker_account_id, exp: 24h}
   - JWT returned in redirect URL fragment (#token=X) — not in query string
5. Frontend extracts JWT from URL fragment → stored in localStorage
6. All API calls: Authorization: Bearer {JWT}
7. get_verified_broker_account_id(): decodes JWT, verifies bid matches account in DB,
   checks token_revoked_at IS NULL (revoked on disconnect or KiteTokenExpiredError)
```

---

## Circuit Breaker Pattern

Wraps all Kite API calls:

```
States: CLOSED (normal) → OPEN (50% failure rate) → HALF_OPEN (after 60s) → CLOSED
Persisted in Redis (survives Celery worker restarts)
Fails open on Redis error (never blocks users for infra issues)
```

---

## Database Design

- **Connection pool**: pool_size=5, max_overflow=10, pool_pre_ping=True
- **Async**: asyncpg + SQLAlchemy AsyncSession
- **Pooler**: PgBouncer (Supabase transaction pooler on port 6543)
- **Indexes**: 9 composite indexes covering all hot query paths (migrations 043, 044)
- **Key tables**: broker_accounts, trades, completed_trades, risk_alerts, user_profiles, coach_sessions, alert_checkpoints, position_ledger

---

## Celery Configuration

```python
broker_url      = REDIS_URL        # Upstash Redis
result_backend  = REDIS_URL
worker_pool     = "gevent"         # I/O-bound tasks
worker_concurrency = 50
worker_shutdown_timeout = 30       # Graceful shutdown
task_routes = {
    "app.tasks.trade_tasks.*":         "default",
    "app.tasks.alert_tasks.*":         "alerts",
    "app.tasks.checkpoint_tasks.*":    "alerts",
    "app.tasks.position_monitor.*":    "default",
    "app.tasks.portfolio_radar.*":     "default",
    "app.tasks.report_tasks.*":        "reports",
    "app.tasks.reconciliation_tasks.*": "reports",
}
beat_schedule = {
    "eod-report":        (17:30 IST, staggered),
    "morning-prep":      (08:00 IST),
    "commodity-eod":     (23:55 IST, MCX positions),
    "eod-reconcile":     (04:00 IST, staggered),
    # NOTE: position-monitor and portfolio-radar NOT here — per-fill only
}
```

---

## Observability Stack

| Tool | Coverage |
|------|---------|
| Sentry (backend) | All unhandled exceptions, filtered (no Ctrl+C, no CancelledError), 10% trace sampling |
| Sentry (frontend) | ErrorBoundary crashes + unhandled promise rejections, event ID shown to user |
| Prometheus | `/api/metrics` — WS connections, queue depth, error counts, circuit breaker state |
| Structured logging | JSON logs with request_id on every line (RequestIdFilter) |
| Request ID | X-Request-ID header on every HTTP request, propagated into Celery tasks via ContextVar |
| Health check | `GET /health` — DB + Redis + circuit breaker state. Returns 503 if infra down. |
