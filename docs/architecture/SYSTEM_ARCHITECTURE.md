# TradeMentor AI — Complete System Architecture

> **Document purpose**: End-to-end breakdown of every layer of the system, from the moment
> a user connects their Zerodha account through every feature screen and background process.
>
> **Last updated**: 2026-03-07 (session 15 — 8 bugs fixed, cross-cutting review complete)

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Infrastructure Layer](#2-infrastructure-layer)
3. [Database Schema](#3-database-schema)
4. [Authentication & Security](#4-authentication--security)
5. [The Trade Lifecycle — End-to-End](#5-the-trade-lifecycle--end-to-end)
6. [Backend Services Layer](#6-backend-services-layer)
7. [API Layer — All Endpoints](#7-api-layer--all-endpoints)
8. [Celery Task Queue](#8-celery-task-queue)
9. [Behavioral Pattern Detection](#9-behavioral-pattern-detection)
10. [Alert & Notification Pipeline](#10-alert--notification-pipeline)
11. [Danger Zone & Cooldown System](#11-danger-zone--cooldown-system)
12. [BlowupShield — Counterfactual P&L](#12-blowupshield--counterfactual-pl)
13. [AI Layer](#13-ai-layer)
14. [Frontend Architecture](#14-frontend-architecture)
15. [Screen-by-Screen Feature Map](#15-screen-by-screen-feature-map)
16. [Data Flow Diagrams](#16-data-flow-diagrams)
17. [Environment Configuration](#17-environment-configuration)

---

## 1. System Overview

TradeMentor AI is a trading psychology platform for Indian F&O traders. It connects to a trader's
Zerodha account, watches every trade in real time, detects harmful behavioral patterns (revenge
trading, overtrading, tilt spirals, etc.), and delivers interventions via in-app alerts, WhatsApp,
and browser push notifications.

**Philosophy**: "Mirror, not blocker" — show traders facts about their behavior. Never restrict,
always inform.

### Component Map

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                   EXTERNAL                                          │
│  ┌──────────────┐   ┌──────────────────┐   ┌─────────────┐   ┌──────────────────┐  │
│  │ Zerodha Kite │   │  Twilio WhatsApp  │   │  OpenRouter │   │  OpenAI / VAPID  │  │
│  │  (OAuth +    │   │  (guardian alerts │   │  (LLM API)  │   │  (embeddings +   │  │
│  │  Orders API) │   │   & EOD reports)  │   │             │   │  push notif.)    │  │
│  └──────┬───────┘   └────────┬─────────┘   └──────┬──────┘   └──────────────────┘  │
└─────────┼───────────────────┼────────────────────┼───────────────────────────────┘
          │                   │                    │
          ▼                   ▼                    ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                               BACKEND (FastAPI)                                      │
│                                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐    │
│  │  Zerodha    │  │  Webhook    │  │  Analytics  │  │  Coach / Behavioral /   │    │
│  │  Router     │  │  Router     │  │  Router     │  │  Risk / Shield Routers  │    │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘    │
│         │                │                │                      │                  │
│         └────────────────┴────────────────┴──────────────────────┘                  │
│                                     │                                               │
│                          ┌──────────▼──────────┐                                   │
│                          │   Service Layer      │                                   │
│                          │ TradeSyncService     │                                   │
│                          │ RiskDetector         │                                   │
│                          │ BehavioralEvaluator  │                                   │
│                          │ DangerZoneService    │                                   │
│                          │ ShieldService        │                                   │
│                          │ AIService (LLM)      │                                   │
│                          │ AlertService         │                                   │
│                          └──────────┬───────────┘                                   │
│                                     │                                               │
│  ┌──────────────────────────────────▼─────────────────────────────────────────┐    │
│  │                        Celery Task Queue                                    │    │
│  │  trades queue  │  alerts queue  │  reports queue  │  checkpoint queue       │    │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────────────┘
          │                                                      │
          ▼                                                      ▼
┌──────────────────────┐                              ┌─────────────────────────────┐
│    PostgreSQL         │                              │    React Frontend           │
│    (Supabase)         │                              │    (Vite + TypeScript)      │
│                       │                              │    Contexts, Pages,         │
│  17 tables            │                              │    Pattern Detector         │
│  34 migrations        │◄────────────────────────────►│    WebSocket listener      │
└──────────────────────┘                              └─────────────────────────────┘
          ▲
          │
┌─────────┴────────────┐
│    Redis (Upstash)    │
│    Celery broker      │
│    Result backend     │
│    Sync lock store    │
└──────────────────────┘
```

---

## 2. Infrastructure Layer

### Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Web framework | FastAPI (async Python) | HTTP API, WebSocket |
| ORM | SQLAlchemy (async) + asyncpg | Database access |
| Database | PostgreSQL via Supabase | All persistent data |
| Task queue | Celery 5 | Background jobs, scheduled tasks |
| Message broker | Redis (Upstash cloud) | Celery broker + result backend |
| Sync locking | Redis | Prevent concurrent syncs per account |
| JWT | python-jose (HMAC-SHA256) | Authentication tokens |
| Encryption | Fernet (cryptography) | Zerodha access token at rest |
| LLM | OpenRouter API | AI coach, persona analysis |
| Embeddings | OpenAI text-embedding | RAG / semantic journal search |
| WhatsApp | Twilio API | Guardian alerts, EOD reports |
| Push notifications | Web Push (VAPID) | Browser push notifications |
| Broker API | kiteconnect 5.0.1 | All Zerodha data + OAuth |
| Frontend | React 18 + Vite + SWC | UI |
| UI components | shadcn/ui (Radix + Tailwind) | Component library |
| Charts | recharts | Analytics visualizations |
| HTTP client | axios | Frontend API calls |

### Celery Queues

| Queue | Tasks | Workers |
|-------|-------|---------|
| `trades` | Trade sync, webhook processing, P&L calculation | 2–4 concurrent |
| `alerts` | Risk detection, alert checkpoint tasks | 2 concurrent |
| `reports` | EOD report generation, WhatsApp delivery | 1 concurrent |

### Celery Beat Schedule (IST)

| Task | Time (IST) | Description |
|------|-----------|-------------|
| `generate_eod_reports` | 16:00 (4:00 PM) | EOD summary to all users |
| `send_morning_prep` | 08:30 (8:30 AM) | Pre-market briefing |
| `generate_commodity_eod` | 23:45 (11:45 PM) | MCX close summary |

---

## 3. Database Schema

The database has **17 active tables** across **34 migrations**. Tables are grouped by function:

### 3.1 Identity Tables

#### `users` — Stable human identity

```
id              UUID (PK, default=uuid4)
email           TEXT UNIQUE NOT NULL       ← KYC-verified from Zerodha
display_name    TEXT
avatar_url      TEXT
guardian_name   TEXT                       ← Name of risk guardian
guardian_phone  TEXT                       ← WhatsApp number, +91XXXXXXXXXX
created_at      TIMESTAMPTZ
updated_at      TIMESTAMPTZ
```

**Key design decision**: Guardian contact lives on `users`, not `broker_accounts` —
the relationship is to the human, not the trading session.

#### `broker_accounts` — Zerodha connection (one user can have multiple)

```
id                  UUID (PK)
user_id             UUID FK→users CASCADE
broker_name         TEXT DEFAULT 'zerodha'
access_token        TEXT (Fernet-encrypted)
api_key             TEXT
status              TEXT  'connected' | 'disconnected'
broker_user_id      TEXT (e.g. "AB1234")
broker_email        TEXT
user_type           TEXT
exchanges           TEXT[]  (e.g. ["NSE","NFO","MCX"])
products            TEXT[]  (e.g. ["MIS","NRML","CNC"])
order_types         TEXT[]
sync_status         TEXT  'pending' | 'syncing' | 'complete' | 'error'
token_revoked_at    TIMESTAMPTZ   ← set on disconnect
connected_at        TIMESTAMPTZ
last_sync_at        TIMESTAMPTZ
meta                JSONB
```

### 3.2 Trade Architecture (3-Layer Model)

The trade data is stored in three tiers. This is intentional and critical:

```
Layer 1: trades         ← Raw order fills from Zerodha (immutable)
Layer 2: positions      ← Position snapshots (open/closed state)
Layer 3: completed_trades ← Full position lifecycle (real P&L lives here)
```

#### `trades` — Layer 1: Raw order fills

```
id                  UUID (PK)
broker_account_id   UUID FK CASCADE
order_id            TEXT UNIQUE(per account)  ← Zerodha order_id
tradingsymbol       TEXT
exchange            TEXT
transaction_type    TEXT  'BUY' | 'SELL'
order_type          TEXT  'MARKET' | 'LIMIT' | 'SL' | 'SL-M'
product             TEXT  'MIS' | 'NRML' | 'MTF'
quantity            INT
filled_quantity     INT
price               NUMERIC
average_price       NUMERIC
status              TEXT  'COMPLETE' | 'REJECTED' | 'CANCELLED'
asset_class         TEXT  'EQUITY' | 'FNO' | 'COMMODITY' | 'CURRENCY'
instrument_type     TEXT  'EQ' | 'FUT' | 'CE' | 'PE'
pnl                 NUMERIC DEFAULT 0.0     ← ALWAYS zero (P&L is in completed_trades)
order_timestamp     TIMESTAMPTZ
raw_payload         JSONB
```

**Critical**: `trades.pnl` is ALWAYS 0. All detectors that need P&L use `completed_trades.realized_pnl`.

#### `positions` — Layer 2: Position snapshots

```
id                      UUID (PK)
broker_account_id       UUID FK CASCADE
tradingsymbol           TEXT
exchange                TEXT
product                 TEXT
total_quantity          INT    ← peak size in units (not lots)
average_entry_price     NUMERIC
last_price              NUMERIC
unrealized_pnl          NUMERIC  ← mark-to-market from Kite
realized_pnl            NUMERIC
status                  TEXT  'open' | 'closed'
synced_at               TIMESTAMPTZ
first_entry_time        TIMESTAMPTZ
last_exit_time          TIMESTAMPTZ
holding_duration_minutes INT
```

#### `completed_trades` — Layer 3: Decision lifecycle (the unit of psychology analysis)

```
id                  UUID (PK)
broker_account_id   UUID FK CASCADE
tradingsymbol       TEXT
exchange            TEXT
instrument_type     TEXT  'EQ' | 'FUT' | 'CE' | 'PE'
product             TEXT
direction           TEXT  'LONG' | 'SHORT'
total_quantity      INT   ← peak quantity (units, not lots)
num_entries         INT   ← how many buy/sell fills opened this position
num_exits           INT   ← how many fills closed it
avg_entry_price     NUMERIC  ← FIFO-weighted entry
avg_exit_price      NUMERIC  ← FIFO-weighted exit
realized_pnl        NUMERIC  ← THE core behavioral metric — real money made/lost
entry_time          TIMESTAMPTZ
exit_time           TIMESTAMPTZ
duration_minutes    INT
closed_by_flip      BOOL   ← true if close also opened reverse position
entry_trade_ids     UUID[] ← audit trail
exit_trade_ids      UUID[]
status              TEXT DEFAULT 'closed'
```

### 3.3 Signal Tables

#### `risk_alert` — Pattern alerts (legacy pipeline)

```
id                  UUID (PK)
broker_account_id   UUID FK CASCADE
pattern_type        TEXT  'consecutive_loss' | 'revenge_sizing' |
                          'overtrading' | 'fomo' | 'tilt_loss_spiral'
severity            TEXT  'caution' | 'danger' | 'critical'
message             TEXT
details             JSONB  ← pattern-specific context
trigger_trade_id    UUID FK→trades (nullable)
related_trade_ids   UUID[]
detected_at         TIMESTAMPTZ (indexed)
acknowledged_at     TIMESTAMPTZ (nullable)
```

#### `behavioral_event` — Confidence-scored events (new pipeline)

```
id                      UUID (PK)
broker_account_id       UUID FK CASCADE
event_type              TEXT  'REVENGE_TRADING' | 'OVERTRADING' |
                              'TILT_SPIRAL' | 'FOMO_ENTRY' | 'LOSS_CHASING'
severity                TEXT  'LOW' | 'MEDIUM' | 'HIGH'
confidence              NUMERIC(4,2)  ← 0.00–1.00
trigger_position_key    TEXT  'SYMBOL:EXCHANGE:PRODUCT:DIRECTION'
trigger_trade_id        UUID
message                 TEXT
context                 JSONB
detected_at             TIMESTAMPTZ
```

#### `alert_checkpoint` — Counterfactual P&L snapshots (BlowupShield)

```
id                      UUID (PK)
alert_id                UUID FK→risk_alert CASCADE
broker_account_id       UUID FK CASCADE
positions_snapshot      JSONB  ← position state at alert time
total_unrealized_pnl    NUMERIC
prices_at_t5            JSONB   ← LTPs at T+5 min
pnl_at_t5               NUMERIC
checked_at_t5           TIMESTAMPTZ
prices_at_t30           JSONB   ← LTPs at T+30 min
pnl_at_t30              NUMERIC  ← counterfactual: what would've happened
checked_at_t30          TIMESTAMPTZ
prices_at_t60           JSONB
pnl_at_t60              NUMERIC
checked_at_t60          TIMESTAMPTZ
user_actual_pnl         NUMERIC  ← what user actually made/lost
money_saved             NUMERIC  ← user_actual_pnl - pnl_at_t30
calculation_status      TEXT  'pending' | 'calculating' | 'complete' |
                              'no_positions' | 'error'
created_at              TIMESTAMPTZ
```

### 3.4 Behavior & Settings Tables

#### `user_profile` — Personalization and thresholds

```
id                      UUID (PK)
broker_account_id       UUID FK UNIQUE CASCADE
onboarding_completed    BOOL
experience_level        TEXT  'beginner' | 'intermediate' | 'advanced'
trading_style           TEXT  (free form)
risk_tolerance          TEXT  'conservative' | 'moderate' | 'aggressive'
trading_capital         NUMERIC    ← user-declared capital (Tier 1 override)
daily_loss_limit        NUMERIC    ← max daily loss in ₹
daily_trade_limit       INT        ← max trades/day
max_position_size       NUMERIC    ← max single position in ₹
sl_percent_futures      NUMERIC    ← stop-loss % for futures
sl_percent_options      NUMERIC    ← stop-loss % for options
cooldown_after_loss     INT        ← minutes to wait after a loss
push_enabled            BOOL
whatsapp_enabled        BOOL
guardian_enabled        BOOL
guardian_alert_threshold TEXT      ← 'caution' | 'danger' | 'critical'
guardian_daily_summary  BOOL
eod_report_time         TEXT       ← HH:MM in IST
morning_brief_time      TEXT       ← HH:MM in IST
ai_persona              TEXT       ← 'coach' | 'mentor' | 'friend' | 'strict'
detected_patterns       JSONB      ← behavioral baselines from 90-day history
ai_cache                JSONB      ← cached AI responses (with timestamps)
```

#### `cooldown`

```
id                  UUID (PK)
broker_account_id   UUID FK CASCADE
reason              TEXT       ← pattern_type that triggered it
duration_minutes    INT
can_skip            BOOL
trigger_alert_id    UUID FK→risk_alert (nullable)
started_at          TIMESTAMPTZ
skipped_at          TIMESTAMPTZ (nullable)
resumed_at          TIMESTAMPTZ (nullable)
```

#### `journal_entry`

```
id                  UUID (PK)
broker_account_id   UUID FK CASCADE
trade_id            UUID FK→completed_trades (nullable)
trade_symbol        TEXT
trade_pnl           TEXT
emotion_tags        TEXT[]   ← e.g. ["fear", "FOMO", "disciplined"]
notes               TEXT
emotions            TEXT
lessons             TEXT
entry_type          TEXT DEFAULT 'trade'
created_at          TIMESTAMPTZ
updated_at          TIMESTAMPTZ
```

### 3.5 Market Data Tables

#### `orders` — Kite API order history

Full order record from Zerodha including quantity, price, status_message, variety,
validity, tag, parent_order_id (for bracket/cover orders).

#### `holdings` — CNC/delivery positions

Zerodha portfolio holdings: ISIN, quantity, authorised_quantity, t1_quantity,
collateral_quantity, average_price, pnl, day_change.

#### `instrument` — Master instrument list from Kite

instrument_token, exchange_token, tradingsymbol, exchange, instrument_type,
segment, lot_size, tick_size, expiry, strike.

#### `margin_snapshot` — Margin history

Per-segment (equity/commodity) snapshots: available_cash, available_margin,
utilised_span, utilised_exposure, mtm_realised, mtm_unrealised, payout.

#### `push_subscription` — Browser push subscriptions

VAPID endpoint, p256dh, auth keys per browser/device.

---

## 4. Authentication & Security

### 4.1 Zerodha OAuth2 Flow

```
User clicks "Connect Zerodha"
        │
        ▼
Frontend → GET /api/zerodha/connect
        │
        ▼
Backend returns { login_url: "https://kite.zerodha.com/connect/login?api_key=..." }
        │
        ▼
Frontend redirects user to login_url
        │
        ▼
User logs in on Zerodha, grants permission
        │
        ▼
Zerodha redirects → GET /api/zerodha/callback?request_token=XXX&status=success
        │
        ▼
Backend:
  1. kite.generate_session(request_token) → access_token
  2. kite.get_profile() → user_id, email, exchanges, products, ...
  3. Encrypt access_token with Fernet (ENCRYPTION_KEY)
  4. Upsert User (by email)
  5. Upsert BrokerAccount (by broker_user_id)
  6. Issue JWT:
        { sub: user.id, bid: broker_account.id, exp: now+24h }
        │
        ▼
Backend redirects to:
  {FRONTEND_URL}/settings?connected=true&token={jwt}&broker_account_id={uuid}
        │
        ▼
Frontend extracts token from URL, stores in localStorage
  Triggers initial sync: POST /api/zerodha/sync/all
```

### 4.2 JWT Structure

```json
Header:  { "alg": "HS256", "typ": "JWT" }
Payload: {
  "sub": "550e8400-e29b-41d4-a716-446655440000",   // user_id (stable)
  "bid": "7c9e6679-7425-40de-944b-e07fc1f90ae7",   // broker_account_id (session)
  "exp": 1772984003,                                // 24h from issue
  "iat": 1772897603
}
```

### 4.3 Auth Dependencies

Every protected endpoint uses one of:

```python
# Fast path (JWT decode only — no DB query):
broker_account_id = Depends(get_current_broker_account_id)
  → Decodes JWT, extracts 'bid' claim
  → Raises 401 if expired, missing, or invalid signature

# Strict path (JWT + DB lookup — 1 extra query):
broker_account_id = Depends(get_verified_broker_account_id)
  → Decodes JWT
  → SELECT FROM broker_accounts WHERE id = bid
  → Raises 401 if account not found
  → Raises 401 if token_revoked_at IS NOT NULL
```

**All 102 protected endpoints use `get_verified_broker_account_id`** (the strict version).
This ensures tokens are immediately invalid after disconnect — no 24-hour grace window.

### 4.4 Token Revocation

```
POST /api/zerodha/disconnect
  → broker_account.token_revoked_at = now()
  → access_token = None
  → status = "disconnected"

Next API call with old JWT:
  → get_verified_broker_account_id queries broker_account
  → token_revoked_at IS NOT NULL → 401
```

### 4.5 Zerodha Webhook Security

```
POST /api/webhooks/zerodha/postback
  Incoming: { order_id, order_timestamp, checksum, ...order_data }

  Verification:
    expected = SHA-256(order_id + order_timestamp + ZERODHA_API_SECRET)
    if computed != checksum:
        return 200  # return 200 to stop Zerodha retrying
    else:
        queue Celery task and return 200
```

### 4.6 Encryption

Zerodha access tokens are encrypted at rest using Fernet symmetric encryption:

```python
# On connect:
cipher = Fernet(settings.ENCRYPTION_KEY)
encrypted = cipher.encrypt(access_token.encode()).decode()
broker_account.access_token = encrypted

# On use:
decrypted = cipher.decrypt(encrypted.encode()).decode()
kite.set_access_token(decrypted)
```

---

## 5. The Trade Lifecycle — End-to-End

This is the core of the system. Two paths exist:

### Path A: Real-time via Zerodha Webhook

```
Trader places order on Zerodha app / Kite
        │
        ▼
Zerodha sends POST /api/webhooks/zerodha/postback
  (contains: order_id, tradingsymbol, transaction_type, quantity,
   average_price, status, tag="user_{broker_account_id}")
        │
        ▼
Webhook handler:
  1. Extracts broker_account_id from order.tag
  2. Verifies checksum (SHA-256)
  3. process_webhook_trade.apply_async(trade_data, broker_account_id)
        │
        ▼
Celery task: process_webhook_trade
  1. Classify trade (exchange → asset_class, symbol → instrument_type)
  2. Normalize fields (timestamps, product type)
  3. Upsert to trades table (by order_id)
  4. If status = COMPLETE:
       a. Sync positions from Kite (to get updated unrealized P&L)
       b. Calculate P&L if sell trade:
            FIFO match: find oldest open lot of same symbol
            realized_pnl = (exit_price - entry_price) × quantity
            Create/update CompletedTrade record
       c. Run signal pipeline (risk detection, behavioral evaluation)
```

### Path B: Manual Sync (Button click or scheduled)

```
Frontend: POST /api/zerodha/sync/all
    (or Celery: sync_trades_for_account.delay)
        │
        ▼
zerodha.py: run_full_sync()
        │
        ├── Step 1: DATA PIPELINE
        │     a. Refresh instruments cache (if > 24h old)
        │     b. GET /trades (Zerodha API) → upsert all to trades table
        │     c. GET /positions → upsert to positions table
        │     d. GET /orders → upsert to orders table
        │     e. PNL Calculator: FIFO-match all completed positions
        │          → Create CompletedTrade records
        │     f. db.commit() ← all data committed here
        │
        ├── Step 2: SIGNAL PIPELINE (after commit)
        │     a. RiskDetector.detect_patterns(broker_account_id, db, trigger_trade)
        │          → Returns List[RiskAlert] (candidates)
        │          → 24h dedup: load existing alerts from last 24h
        │               key = (trigger_trade_id, pattern_type)     ← trade-level
        │               key = ("_account_", pattern_type)          ← account-level (no trigger_trade_id)
        │               Skip if key already exists → no duplicate alert
        │          → Saves only NEW alerts to risk_alert table
        │          → For danger/critical: create_alert_checkpoint.apply_async (countdown=10s)
        │          → For danger: trigger_cooldown(broker_account_id)
        │
        │     b. BehavioralEvaluator.evaluate(broker_account_id, new_fills, db)
        │          → Returns List[BehavioralEvent] (confidence-filtered, deduped)
        │          → Saves to behavioral_event table
        │          → WebSocket broadcast to connected frontend clients
        │
        │     c. DangerZoneService.assess_danger_level(db, broker_account_id)
        │          → Checks daily loss limit, consecutive losses, overtrading
        │          → Updates cooldown if needed
        │          → WhatsApp notification if critical (rate-limited)
        │
        │     d. BehavioralBaselineService.compute_and_store()  ← once/24h
        │          → Analyzes 90 days of completed trades
        │          → Updates user_profile.detected_patterns with personalized thresholds
        │
        └── Step 3: Return sync summary
              { trades_synced, positions_synced, new_alerts, pnl_updated, ... }
```

### Sync Lock

Before any sync begins:

```python
lock_key = f"sync_lock:{broker_account_id}"
if redis.get(lock_key):
    raise HTTPException(429, "Sync already in progress")
redis.setex(lock_key, ttl=120, value="1")
# ... sync ...
redis.delete(lock_key)
```

This prevents concurrent syncs from the same account (e.g., webhook + button click simultaneously).

---

## 6. Backend Services Layer

### 6.1 ZerodhaService

Wraps the Kite Connect API. All external calls go through here.

```
Methods:
  get_trades(access_token)              → List of raw order dicts
  get_positions(access_token)           → {net: [...], day: [...]}
  get_holdings(access_token)            → List of holding dicts
  get_orders(access_token)              → List of order dicts
  get_margins(access_token)             → {equity: {...}, commodity: {...}}
  get_order_history(access_token, id)   → List of order modifications
  get_ltp(access_token, instruments)    → {"NSE:INFY": 1430.15, ...}
  get_profile(access_token)             → User profile dict
  _request(method, url, access_token, params=None)
    → Handles authentication header injection
    → Rate limiter acquisition (prevents Zerodha API hammering)
    → Returns parsed JSON response
```

### 6.2 TradeSyncService

Orchestrates fetching from Zerodha and writing to DB.

```
sync_trades_for_broker_account(broker_account_id, db)
  → Fetches trades, normalizes, upserts
  → Returns: {success, trades_synced, new_trade_ids, errors}

sync_positions(broker_account_id, db, access_token)
  → Upserts open positions from Kite /portfolio/positions
  → Marks old positions as closed

sync_orders_to_db(broker_account_id, db)
  → Full order history sync to orders table

upsert_trade(db, trade_data, broker_account_id)
  → INSERT ... ON CONFLICT (order_id, broker_account_id) DO UPDATE
  → Returns (Trade, is_new_bool)

transform_zerodha_order(raw)
  → Normalizes Kite API order dict to our schema
  → Maps product types (CNC/MIS/NRML)
  → Classifies asset_class, instrument_type
```

### 6.3 PNLCalculator

FIFO P&L calculation — creates CompletedTrade records.

```
calculate_and_update_pnl(broker_account_id, db, symbol=None, days_back=30)
  → For each symbol with trades:
      1. Load all BUY and SELL fills in chronological order
      2. FIFO match:
           Each SELL is matched against oldest unmatched BUYs
           realized_pnl = Σ (exit_price - entry_price) × matched_quantity
      3. When net position → 0, create CompletedTrade
      4. Upsert CompletedTrade (by symbol + exit_time window)
  → Returns: {processed, updated, total_pnl, completed_trades: [...]}
```

### 6.4 RiskDetector (Legacy signal pipeline)

Fires `RiskAlert` objects. Called on every sync.

```
detect_patterns(broker_account_id, db, trigger_trade, profile)
  Queries:
    recent_trades    ← trades WHERE order_timestamp >= now-24h AND status=COMPLETE
    recent_completed ← completed_trades WHERE exit_time >= now-24h

  Runs 5 detectors:
    _detect_consecutive_losses(recent_completed, trigger_trade, thresholds)
    _detect_revenge_sizing(recent_trades, recent_completed, trigger_trade, thresholds)
    _detect_overtrading(recent_trades, trigger_trade, thresholds)
    _detect_fomo_entry(recent_trades, trigger_trade, thresholds)
    _detect_tilt_spiral(recent_trades, recent_completed, trigger_trade, thresholds)

  For danger alerts: _trigger_cooldown(broker_account_id, alert, db)
  Returns: List[RiskAlert]
```

### 6.5 BehavioralEvaluator (New signal pipeline)

Fires `BehavioralEvent` objects with confidence scores.

```
evaluate(broker_account_id, new_fills, db, profile)
  Loads context:
    recent_trades     ← 24h trades
    recent_completed  ← 24h completed_trades
    open_positions    ← WHERE total_quantity != 0
    recent_events     ← 4h behavioral_events (for dedup)

  Runs 5 detectors per fill:
    _detect_revenge_trading(fill, recent_completed, events, broker_id, thresholds)
    _detect_overtrading(fill, recent_trades, events, broker_id, thresholds)
    _detect_tilt_spiral(fill, recent_completed, events, broker_id, thresholds)
    _detect_fomo_entry(fill, recent_trades, positions, broker_id, thresholds)
    _detect_loss_chasing(fill, recent_completed, events, broker_id, thresholds)

  Filters:
    confidence >= THRESHOLDS[severity]  (LOW:0.70, MEDIUM:0.75, HIGH:0.85)
    _is_duplicate(event, recent_events)  (same type+key within 60 min)

  Returns: List[BehavioralEvent]  (not yet persisted — caller saves)
```

### 6.6 BehavioralAnalysisService

27-pattern comprehensive analysis for the `/api/behavioral/analysis` endpoint.

```
analyze_behavior(broker_account_id, db, time_window_days)
  Loads:
    completed_trades (CompletedTradeAdapter wraps for .pnl compatibility)
    open_positions
    journal_entries

  Runs all 27 detectors:
    - Emotional patterns: EmotionalExit, NoCooldown, OversizedPosition
    - Timing patterns: Overtrading, FOMO, MorningRush
    - P&L patterns: RevengeTrade, TiltSpiral, LossChasing
    - ... (27 total)

  Returns:
    patterns_detected: [{name, detected, frequency, severity, pnl_impact, recommendation}]
    behavior_score: 0-100
    top_strength: "..."
    focus_area: "..."
```

### 6.7 DangerZoneService

Graduated danger level assessment.

```
assess_danger_level(db, broker_account_id) → DangerZoneStatus
  Thresholds from get_thresholds(profile)

  Level progression:
    safe       → No active alerts, no loss limit breach
    caution    → ≥1 unacknowledged caution alerts
    warning    → Daily loss ≥70% of limit, or pattern alerts
    danger     → Daily loss ≥85% of limit, or consecutive losses ≥danger_threshold
    critical   → Daily loss ≥100% of limit

  Returns:
    level: "safe" | "caution" | "warning" | "danger" | "critical"
    triggers: [...]         ← what triggered this level
    daily_loss_used_pct: float
    consecutive_losses: int
    cooldown_active: bool
    cooldown_remaining_minutes: int
    recommendations: [...]
```

### 6.8 ShieldService (BlowupShield)

Aggregates AlertCheckpoint data for the capital defense screen.

```
get_shield_summary(broker_account_id, db) → ShieldSummary
  Loads all risk_alerts for account
  For each alert: load matching AlertCheckpoint (by alert_id)

  capital_defended = Σ max(0, checkpoint.money_saved)
                       for checkpoints WHERE status='complete'

  blowups_prevented = count of danger alerts where user heeded
    (defined as: user_actual_pnl > pnl_at_t30)

  shield_score = (heeded_alerts / total_alerts) × 100

  checkpoint_coverage = {
    complete: count,
    calculating: count (pending/calculating),
    unavailable: count (no_positions, error, predates_system)
  }

  Returns NO bootstrap / estimated numbers.
  Every number is from real trade data.

get_intervention_timeline(broker_account_id, db) → List[ShieldTimelineItem]
  Per alert: {
    alert_id, pattern_type, severity, detected_at,
    calculation_status,
    money_saved (if complete),
    counterfactual_pnl_t30,
    user_actual_pnl
  }
```

### 6.9 AIService (OpenRouter)

```
Models used:
  Primary:   anthropic/claude-3.5-haiku
  Reasoning: openai/gpt-4o-mini
  Fallback:  google/gemini-flash-1.5-8b

generate_trading_persona(patterns, total_trades, emotional_tax, time_perf)
  → Classifies trader:
       Tilted Gambler | Recovery Chaser | Compulsive Scalper |
       Methodical Executor | Impulsive Momentum Trader | Disciplined Swing Trader
  → Returns: {persona, description, strengths, weaknesses, next_steps}

generate_coach_insight(risk_state, total_pnl, patterns_active, recent_trades, ...)
  → Short insight for Dashboard card (1-2 paragraphs)
  → Context-aware (uses current risk state + patterns)
  → Cached in user_profile.ai_cache (invalidated every 4h)

generate_chat_response(message, context, history, rag_context, persona)
  → Full conversational response
  → Persona modes:
       coach  → structured, clinical analysis
       mentor → warm, supportive guidance
       friend → casual, empathetic
       strict → direct, no-nonsense
  → 7 absolute rules enforced (no fabricated numbers, no specific trade advice, etc.)
  → RAG context injected from journal entries if relevant
```

### 6.10 AlertService & WhatsAppService

```
AlertService:
  send_risk_alert(alert, broker_account, phone_number)
    → Only sends for severity="danger" (caution is suppressed)
    → Formats message per pattern type (overtrading, revenge_sizing, etc.)
    → Calls whatsapp_service.send_message()
    → Returns bool

  send_risk_alert_with_guardian(alert, broker, user_phone, guardian_phone, guardian_name)
    → Sends TWO different messages:
         User message:    "STOP TRADING NOW" format (urgent, commanding)
         Guardian message: "check in with them" format (informational)

  _format_alert_message(alert, broker)  → str
  _format_guardian_alert(alert, broker, guardian_name)  → str

WhatsAppService:
  send_message(to_number, content)
    → If Twilio not configured: logs message (safe mode), returns True
    → If configured: run_in_executor(twilio.messages.create) async
    → Prefixes "whatsapp:" to from/to numbers
    → Returns bool (never raises)
```

---

## 7. API Layer — All Endpoints

### Base URL: `http://localhost:8000` (dev) or production domain

All endpoints returning JSON. All protected endpoints require `Authorization: Bearer {jwt}`.

### 7.1 Zerodha Router — `/api/zerodha`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/connect` | No | Get OAuth login URL |
| GET | `/callback` | No | Handle OAuth, issue JWT, redirect |
| GET | `/test` | No | Verify API key configured |
| GET | `/health` | No | Service health check |
| GET | `/status` | Yes | Broker connection status |
| POST | `/disconnect` | Yes | Revoke token, disconnect |
| GET | `/accounts` | Yes | List broker accounts for user |
| GET | `/margins` | Yes | Live margin (equity + commodity) |
| GET | `/holdings` | Yes | CNC/delivery holdings |
| GET | `/order-analytics` | Yes | Order behavioral metrics (days=30) |
| POST | `/instruments/refresh` | Yes | Refresh master instrument list |
| GET | `/instruments/search` | Yes | Search instruments (query, exchange) |
| GET | `/orders/history/{order_id}` | Yes | Order modification history |
| POST | `/sync/orders` | Yes | Sync orders table only |
| POST | `/sync/holdings` | Yes | Sync holdings only |
| POST | `/sync/all` | Yes | **Full sync pipeline** (rate-limited 10/min) |
| POST | `/stream/start` | Yes | Start real-time price streaming |
| POST | `/stream/stop` | Yes | Stop streaming |
| POST | `/margins/check-order` | Yes | Pre-trade margin estimate |
| GET | `/margins/insights` | Yes | Margin history analysis |
| GET | `/token/validate` | Yes | Token validity check |
| GET | `/token/status` | Yes | Token status all accounts |

### 7.2 Trades Router — `/api/trades`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | Yes | List raw trades (filters: symbol, status, days, limit, offset) |
| GET | `/{trade_id}` | Yes | Get specific trade |
| POST | `/` | Yes | Create trade manually |
| PUT | `/{trade_id}` | Yes | Update trade |
| DELETE | `/{trade_id}` | Yes | Delete trade |
| GET | `/completed` | Yes | List completed_trades |
| GET | `/stats` | Yes | Daily stats summary |
| GET | `/stats/daily` | Yes | Per-day breakdown |
| GET | `/stats/symbol/{symbol}` | Yes | Per-symbol stats |

### 7.3 Positions Router — `/api/positions`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | Yes | All positions (filters: status, days, limit) |
| GET | `/{position_id}` | Yes | Single position |
| GET | `/open` | Yes | Open positions only |
| GET | `/closed` | Yes | Closed positions only |

### 7.4 Analytics Router — `/api/analytics`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/risk-score` | Yes | Weekly risk/discipline score (0–100) |
| GET | `/dashboard-stats` | Yes | Full stats for dashboard |
| POST | `/recalculate-pnl` | Yes | FIFO P&L recalc (symbol, days_back) |
| GET | `/unrealized-pnl` | Yes | Unrealized P&L on open positions |
| GET | `/money-saved` | Yes | Estimated capital defended |
| GET | `/session-stats` | Yes | Current trading session stats |
| GET | `/time-analysis` | Yes | P&L by hour of day |
| GET | `/ai-summary` | Yes | AI-generated behavioral narrative |
| GET | `/patterns` | Yes | Pattern frequency + cost breakdown |
| GET | `/predictions` | Yes | Pattern prediction (will this trade trigger?) |

### 7.5 Risk Router — `/api/risk`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/state` | Yes | Current risk state (safe/caution/danger) |
| GET | `/alerts` | Yes | Risk alerts (filters: days, severity, limit) |
| GET | `/alerts/{alert_id}` | Yes | Single alert |
| POST | `/alerts/{alert_id}/acknowledge` | Yes | Mark alert acknowledged |

### 7.6 Behavioral Router — `/api/behavioral`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/analysis` | Yes | 27-pattern behavioral analysis |
| GET | `/patterns` | Yes | Detected patterns list |
| GET | `/baseline` | Yes | Personalized thresholds (force_recompute param) |
| GET | `/events` | Yes | BehavioralEvent log |

### 7.7 Coach Router — `/api/coach`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/insight` | Yes | AI coach card insight (dashboard) |
| POST | `/chat` | Yes | Chat message, returns AI response |

`POST /chat` payload:
```json
{
  "message": "Why do I keep revenge trading?",
  "history": [{"role": "user", "content": "..."}],
  "use_rag": true
}
```

### 7.8 Shield Router — `/api/shield`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/summary` | Yes | Hero metrics (capital_defended, shield_score) |
| GET | `/timeline` | Yes | Per-alert intervention timeline |
| GET | `/patterns` | Yes | Per-pattern breakdown |

### 7.9 Danger Zone Router — `/api/danger-zone`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/status` | Yes | Danger level + triggers + cooldown |

### 7.10 Cooldown Router — `/api/cooldown`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/status` | Yes | Active cooldown (remaining minutes) |
| POST | `/skip` | Yes | Skip current cooldown (if can_skip=true) |
| POST | `/resume` | Yes | Manually resume trading |

### 7.11 Journal Router — `/api/journal`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | Yes | List entries (limit, offset, entry_type) |
| POST | `/` | Yes | Create entry (linked to trade_id or standalone) |
| GET | `/{entry_id}` | Yes | Get entry |
| PUT | `/{entry_id}` | Yes | Update entry |
| DELETE | `/{entry_id}` | Yes | Delete entry |
| GET | `/trade/{trade_id}` | Yes | Get entry for specific trade |
| DELETE | `/trade/{trade_id}` | Yes | Delete entry for trade |
| GET | `/stats/emotions` | Yes | Emotion tag frequency + avg P&L |
| GET | `/search/semantic` | Yes | Semantic search (RAG) |

**Security**: `POST /journal/` validates trade_id ownership — trade must belong to the
requesting broker account. Returns 403 if not.

### 7.12 Settings Router — `/api/settings`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/profile` | Yes | User profile + thresholds |
| PUT | `/profile` | Yes | Update profile |
| GET | `/notifications` | Yes | Notification preferences |
| PUT | `/notifications` | Yes | Update notification preferences |
| POST | `/guardian/test` | Yes | Send test WhatsApp to guardian |

### 7.13 Notifications Router — `/api/notifications`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/subscribe` | Yes | Register VAPID push subscription |
| GET | `/subscriptions` | Yes | List push subscriptions |
| DELETE | `/subscriptions/{id}` | Yes | Unsubscribe |

### 7.14 Webhooks Router — `/api/webhooks`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/zerodha/postback` | No (checksum) | Zerodha real-time order updates |

### 7.15 WebSocket

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| WS | `/api/ws?token={jwt}` | JWT query param | Real-time behavioral events |

WebSocket message format:
```json
{
  "type": "behavioral_event",
  "event": {
    "event_type": "REVENGE_TRADING",
    "severity": "HIGH",
    "confidence": 0.92,
    "message": "..."
  }
}
```

---

## 8. Celery Task Queue

### 8.1 Task Registry

#### Trade Tasks (`app.tasks.trade_tasks`)

**`process_webhook_trade`**
```
Queue: trades
bind=True, max_retries=3, countdown=60s on retry
Args: trade_data (dict), broker_account_id (str)
Flow:
  1. Parse and normalize trade data from Zerodha postback
  2. Classify trade (asset_class, instrument_type)
  3. Upsert to trades table
  4. If status=COMPLETE:
       - Sync positions from Kite
       - Run P&L calculation
       - Run risk detection
       - Run behavioral evaluation
  5. WebSocket broadcast new events
```

**`sync_trades_for_account`**
```
Queue: trades
bind=True, max_retries=2
Rate limit: 10/minute per account
Args: broker_account_id (str)
Flow: Full trade + position + P&L sync
```

#### Alert Tasks (`app.tasks.alert_tasks`)

**`send_whatsapp_alert`**
```
Queue: alerts
bind=True, max_retries=3, countdown=30s on retry
Args: broker_account_id (str), message (str), phone_number (str)
Flow: Calls AlertService.send_risk_alert()
```

#### Checkpoint Tasks (`app.tasks.checkpoint_tasks`)

**`create_alert_checkpoint`**
```
Queue: alerts
countdown=10s (let DB commit settle)
Args: alert_id (str), broker_account_id (str)
Flow:
  1. Load RiskAlert → get trigger_trade_id
  2. Load Trade → get tradingsymbol, exchange
  3. Decrypt BrokerAccount access_token
  4. GET /portfolio/positions (Kite) → find open position for symbol
  5. GET /quote/ltp for that symbol
  6. Create AlertCheckpoint {positions_snapshot, ltp_at_alert}
  7. Schedule: check_alert_t5.apply_async(countdown=300)
```

**`check_alert_t5`** (T+5 min)
```
Fetch LTP, compute pnl_at_t5
Schedule check_alert_t30.apply_async(countdown=1500)
```

**`check_alert_t30`** (T+30 min — primary counterfactual)
```
1. Fetch LTP for snapshotted symbol
2. pnl_at_t30 = qty × (current_ltp - avg_entry_price) × direction
3. Query CompletedTrade WHERE tradingsymbol=trigger_symbol
       AND exit_time BETWEEN alert_time AND alert_time+30min
4. user_actual_pnl = sum(realized_pnl)
5. money_saved = user_actual_pnl - pnl_at_t30
6. checkpoint.calculation_status = 'complete'
7. Schedule check_alert_t60.apply_async(countdown=1800)
```

**`check_alert_t60`** (T+60 min — final)
```
Same as T+30 but wider trade window (60 min)
Overwrites money_saved with final value
```

**P&L formula**:
```
direction = +1 if position is LONG, -1 if SHORT
counterfactual_pnl = abs(qty) × (price_at_tN - avg_entry_price) × direction
money_saved = user_actual_pnl - counterfactual_pnl_at_t30
  (positive = alert helped user avoid worse loss)
  (negative = market recovered, user exited at wrong time)
```

#### Report Tasks (`app.tasks.report_tasks`)

**`generate_eod_reports`** (scheduled 16:00 IST)
```
1. Query: SELECT broker_accounts JOIN users WHERE status='connected'
2. For each account WHERE user.guardian_phone IS NOT NULL:
     a. Load today's CompletedTrades (realized_pnl)
     b. Load today's RiskAlerts
     c. Format EOD summary message
     d. send_whatsapp_alert.delay(guardian_phone, message)
     e. If guardian_daily_summary: send separate guardian digest
```

**`send_weekly_summary`** (scheduled Monday 09:00 IST)
```
1. Query all connected broker_accounts
2. For each account with guardian_phone:
     a. Load CompletedTrades WHERE exit_time >= last Monday 00:00 IST
        Data source: CompletedTrade.realized_pnl (NOT Trade.pnl which is always 0)
     b. Compute: total_pnl, win_rate, best_trade, worst_trade, trade_count
     c. Format weekly digest message
     d. whatsapp_service.send_message(guardian_phone, report)
        (via WhatsAppService.send_message, not AlertService)
```

**`send_morning_prep`** (scheduled 08:30 IST)
```
Sends pre-market brief to users with morning_brief_time configured
Content: yesterday's final P&L, patterns to watch, encouragement
```

---

## 9. Behavioral Pattern Detection

### 9.1 Three-Tier Threshold System

Every threshold is resolved in priority order:

```
Tier 1 (highest): User profile
  user_profile.cooldown_after_loss → revenge_window_min
  user_profile.daily_trade_limit   → burst_trades_per_15min
  user_profile.daily_loss_limit    → loss_limit_warning threshold

Tier 2: Cold-start universal defaults (COLD_START_DEFAULTS)
  burst_trades_per_15min   = 6
  revenge_window_min       = 10
  consecutive_loss_caution = 3
  consecutive_loss_danger  = 5
  daily_trade_limit        = 10

Tier 3 (floor): Never fire below these
  burst_trades_per_15min   ≥ 3   (never alert for < 3 trades)
  revenge_window_min       ≥ 1   (can't be 0)
  consecutive_loss_caution ≥ 2   (at least 2 losses)
```

### 9.2 RiskDetector Patterns (5 patterns → RiskAlert)

#### Pattern 1: Consecutive Loss Spiral
```
Source data: CompletedTrade.realized_pnl (real P&L)
Logic:       Count losses from most recent backward, stop at first win
Caution:     consecutive_losses ≥ consecutive_loss_caution (default 3)
Danger:      consecutive_losses ≥ consecutive_loss_danger (default 5)
Message:     "DANGER: 5 consecutive losing trades, total loss ₹12,500"
Details:     {consecutive_losses, total_loss, loss_streak_started}
```

#### Pattern 2: Revenge Sizing
```
Source data: CompletedTrade (loss detection) + Trade (sizing)
Logic:       position_size > 1.5x previous_size within revenge_window_min of a loss
Trigger:     Only when trigger_trade present (real-time only, not historical)
Severity:    Always "danger"
Message:     "DANGER: Position size increased 85% within 4.0 minutes after ₹2,000 loss"
Details:     {previous_quantity, current_quantity, size_increase_pct, time_gap_minutes}
```

#### Pattern 3: Overtrading Burst
```
Source data: Trade timestamps (count-based, no P&L)
Logic:       Count trades in 15-minute rolling window
Caution:     count ≥ burst_threshold (default 6)
Danger:      count ≥ int(burst_threshold × 1.4) (default 8)
Message:     "DANGER: 9 trades in 15 minutes - Overtrading detected"
Details:     {trade_count, window_minutes, burst_threshold}
```

#### Pattern 4: FOMO Entry
```
Source data: Trade timestamps + tradingsymbol + transaction_type
Logic A (market open):   ≥3 trades in IST 9:15–9:20 window (first 5 min)
Logic B (chasing):       ≥3 same-direction trades on same symbol in 5 min
IST timezone:            Explicitly uses ZoneInfo("Asia/Kolkata"), not UTC offset
Severity:    Always "caution"
Message:     "CAUTION: 3 trades in first 5 minutes - Possible FOMO"
```

#### Pattern 5: Tilt/Loss Spiral
```
Source data: CompletedTrade (P&L) + quantity for sizing
Logic:
  1. Sort last 6 completed trades by exit_time
  2. Check total_pnl < 0 (losing overall)
  3. Compute notional sizes = qty × avg_entry_price
  4. Check recent_sizes[-4:] are monotonically increasing
  5. All conditions met → danger alert
Message:     "DANGER: Loss spiral detected - Increasing size while losing ₹8,000"
Details:     {total_loss, consecutive_losses, size_trend: "escalating"}
```

### 9.3 BehavioralEvaluator Patterns (5 patterns → BehavioralEvent)

#### Confidence Scoring Formula (Revenge Trading example)
```python
time_factor = max(0, 1 - (gap_minutes / revenge_window))  # faster = higher
size_factor = min(1, max(0, (size_ratio - 1) / 2))         # bigger = higher
raw_confidence = 0.70 + (time_factor × 0.15) + (size_factor × 0.15)
confidence = min(0.99, raw_confidence)

severity:
  size_ratio ≥ 2.0 AND gap ≤ window/3 → "HIGH"  (requires confidence ≥ 0.85)
  size_ratio ≥ 1.5 OR gap ≤ window/3  → "MEDIUM" (requires confidence ≥ 0.75)
  otherwise                           → "LOW"   (requires confidence ≥ 0.70)
```

#### Deduplication
```
Each BehavioralEvent has a trigger_position_key = "SYMBOL:EXCHANGE:PRODUCT:DIRECTION"
If same (event_type, trigger_position_key) was emitted in last 60 minutes: BLOCKED
This prevents flooding the user with the same alert for every subsequent trade
```

### 9.4 BehavioralAnalysisService (27 patterns)

The comprehensive analysis uses `CompletedTradeAdapter` to wrap CompletedTrade objects
so they expose `.pnl` (mapped from `.realized_pnl`) — making them compatible with all
27 detectors which were originally written for Trade objects.

Pattern categories:
- **Emotional**: EmotionalExit, RevengeTrade, FearExit
- **Sizing**: OversizedPosition, PositionSizing
- **Timing**: Overtrading, FOMO, MorningRush, EndOfDayRush
- **Loss**: LossChasing, LossAversion, LossHolding
- **Winning**: EarlyExit, WinStreakOverconfidence
- **Session**: NoCooldown, SessionReset
- **Patterns**: TiltSpiral, ConsecutiveLoss, SIC (size increase after consecutive loss)

---

## 10. Alert & Notification Pipeline

### 10.1 Alert Flow

```
Risk pattern detected (RiskDetector or BehavioralEvaluator)
          │
          ▼
    RiskAlert saved to DB
          │
          ├─── 24h deduplication check BEFORE save:
          │    key = (trigger_trade_id, pattern_type)  ← trade-level alerts
          │    key = ("_account_", pattern_type)       ← account-level alerts (no trigger_trade_id)
          │    If key exists in recent 24h alerts → skip (no duplicate fired)
          │
          ├─── severity = "danger" or "critical"?
          │         │ Yes
          │         ▼
          │    DangerZoneService: load user, check guardian_phone
          │    if guardian_phone configured AND whatsapp_enabled:
          │         └── whatsapp_service.send_message(guardian_phone, _format_whatsapp_message())
          │               "⚠️ RISK GUARDIAN ALERT"
          │               "DQATEST is showing high-risk behavior."
          │               "🔴 Pattern: Overtrading"
          │               "You may want to check in with them."
          │
          │    NOTE: WhatsApp goes to guardian ONLY. User model has no phone field.
          │    (AlertService.send_risk_alert_with_guardian exists but is not called
          │     in the sync pipeline — reserved for future direct user notifications.)
          │
          ├─── Push notification (browser)
          │    PushNotificationService.send_to_account(broker_account_id, title, body)
          │    → Iterates active PushSubscription rows for this account
          │    → pywebpush VAPID delivery per subscription
          │    → On failure: _handle_failed_delivery() increments failed_count
          │         failed_count >= MAX_FAILURES → subscription.is_active = False (deactivated)
          │
          └─── WebSocket broadcast
               WebSocketManager.broadcast(broker_account_id, {type: "behavioral_event", ...})
```

### 10.2 Notification Rate Limiter

Prevents WhatsApp spam when a trader is in persistent danger:

```
Rate limit tiers (per user per tier):
  "danger":  max 1 per 30 min
  "caution": max 1 per 2 hours
  "info":    max 1 per 6 hours

Implementation: Redis keys with TTL
  key: f"notif_rate:{broker_account_id}:{tier}"
  TTL: tier-dependent
```

### 10.3 EOD Report Format (WhatsApp)

```
📊 *TradeMentor EOD Report*
Date: 07 Mar 2026

💰 *Today's P&L*: ₹+2,340 (3 trades)
  ✅ Wins: 2  ❌ Losses: 1
  Best: NIFTY25MARFUT +₹3,100
  Worst: BANKNIFTY25MARFUT -₹760

⚠️ *Patterns Detected*: 2
  • Revenge Sizing (1x) — costed ~₹760
  • Overtrading (1x) — 9 trades in 15 min

🎯 *Discipline Score*: 71/100

💡 *Tomorrow*: Watch for overtrading in the first 30 minutes.

Account: AB1234 | TradeMentor AI
```

---

## 11. Danger Zone & Cooldown System

### 11.1 Danger Level States

```
safe     → No alerts, loss limit fine
    ↓ (≥1 caution alert)
caution  → Minor behavioral patterns
    ↓ (daily loss ≥70% OR active pattern alerts)
warning  → Approaching loss limit or pattern trigger
    ↓ (daily loss ≥85% OR consecutive_loss ≥ danger_threshold)
danger   → High risk of capital damage
    ↓ (daily loss ≥100%)
critical → Hard stop condition
```

### 11.2 Cooldown Trigger Logic

```
danger alert detected
      │
      ▼
_trigger_cooldown(broker_account_id, alert, db)
      │
      ├── Load user_profile.cooldown_after_loss (default 15 min)
      │
      ▼
create_cooldown(
  broker_account_id=...,
  reason=alert.pattern_type,
  duration_minutes=profile.cooldown_after_loss,
  can_skip=True,
  trigger_alert_id=alert.id
)
```

### 11.3 Cooldown API

```
GET /api/cooldown/status
Response:
{
  "active": true,
  "reason": "consecutive_loss",
  "started_at": "2026-03-07T10:30:00Z",
  "duration_minutes": 15,
  "remaining_minutes": 8,
  "can_skip": true,
  "trigger_alert_id": "..."
}

POST /api/cooldown/skip  (if can_skip=True)
→ cooldown.skipped_at = now()
→ Frontend: trading resumes immediately

POST /api/cooldown/resume
→ Clears all active cooldowns for account
```

---

## 12. BlowupShield — Counterfactual P&L

This is the "capital defended" calculation — the system's flagship feature.

### 12.1 The Problem with Estimates

Old approach: bootstrap estimates (₹3,000–₹8,000 per alert) for users without data.
New approach (Session 14): real counterfactual prices from Kite API.

**Core question**: "If the user had ignored this alert and held their position — what would they
have lost compared to what they actually did?"

### 12.2 Checkpoint Creation Flow

```
Danger alert created
      │ (10 second delay)
      ▼
create_alert_checkpoint task:
  1. Load RiskAlert → find trigger_trade_id
  2. Load Trade → get tradingsymbol + exchange
  3. Decrypt BrokerAccount.access_token
  4. Kite /portfolio/positions → find that symbol
  5. Kite /quote/ltp → get current price
  6. Save AlertCheckpoint:
       positions_snapshot = {tradingsymbol, quantity, avg_entry_price, ltp_at_alert}
       calculation_status = 'pending'
  7. Schedule check_alert_t5 (5 min)
```

### 12.3 T+30 Calculation (Primary)

```
check_alert_t30 task:
  1. Load AlertCheckpoint + original RiskAlert
  2. Kite /quote/ltp → price 30 min after alert
  3. pnl_at_t30 = qty × (price_t30 - entry_price) × direction
      (This is what would have happened if user ignored alert)
  4. CompletedTrade WHERE tradingsymbol=trigger_symbol
       AND exit_time BETWEEN alert_time AND alert_time+30min
     user_actual_pnl = Σ realized_pnl
      (This is what the user actually did)
  5. money_saved = user_actual_pnl - pnl_at_t30
       (+) User heeded alert: exited better than holding
       (-) User exited at worst time (market recovered)
  6. Update checkpoint: calculation_status = 'complete'
```

### 12.4 ShieldSummary Response

```json
{
  "capital_defended": 47500.00,
  "shield_score": 78,
  "blowups_prevented": 3,
  "checkpoint_coverage": {
    "complete": 8,
    "calculating": 2,
    "unavailable": 1
  },
  "total_alerts": 11
}
```

**Key guarantees**:
- `capital_defended` is ONLY the sum of `max(0, money_saved)` from COMPLETE checkpoints
- Zero estimated numbers
- `money_saved` can be negative (honest — shown in timeline but not added to capital_defended)

---

## 13. AI Layer

### 13.1 AI Coach Chat

```
POST /api/coach/chat
  { message: "Why do I keep revenge trading?", history: [...], use_rag: true }

Backend flow:
  1. Load trading context:
       last 7 days of CompletedTrades (symbol, pnl, duration, exit_time)
       open positions (current exposure)
       recent RiskAlerts (what patterns triggered)
       user_profile (persona, experience, risk_tolerance)
  2. If use_rag=true:
       rag_service.search_similar(query, broker_account_id, "journal_entry")
       → Returns matching journal entries by semantic similarity
  3. Build system prompt (7 absolute rules):
       a. Never fabricate specific P&L numbers
       b. Never give specific entry/exit price advice
       c. Never predict market direction
       d. Always acknowledge uncertainty
       e. Never diagnose psychological conditions
       f. Always redirect to professional help for serious issues
       g. Never shame the trader — facts only
  4. Apply ai_persona:
       coach  → "You are a structured trading coach..."
       mentor → "You are a supportive mentor..."
       friend → "You are a fellow trader who understands..."
       strict → "You are a no-nonsense trading supervisor..."
  5. Call OpenRouter API with full context
  6. Return response

Cache: user_profile.ai_cache (insight-type responses, 4h TTL)
```

### 13.2 Trader Persona Classification

The system classifies traders into 6 behavioral archetypes:

| Persona | Key Characteristic |
|---------|-------------------|
| Tilted Gambler | Escalating losses, revenge trading, can't stop |
| Recovery Chaser | Obsessed with "making back" losses |
| Compulsive Scalper | Overtrading, too many small trades |
| Methodical Executor | Disciplined, follows plan (positive) |
| Impulsive Momentum Trader | FOMO-driven, chases moves |
| Disciplined Swing Trader | Patient, position-sized correctly (positive) |

Persona is re-evaluated every 7 days or on demand.

### 13.3 RAG (Semantic Journal Search)

```
Embedding pipeline:
  Journal entry created → embed_journal_entry_async(db, entry)
    → Concatenate: notes + emotions + lessons + symbol + pnl + tags
    → OpenAI text-embedding-3-small → 1536-dim vector
    → Store in vector_embeddings table (pgvector extension)

Search:
  rag_service.search_similar(db, query, broker_account_id, "journal_entry", limit=5)
    → Embed query
    → SELECT ... ORDER BY embedding <-> query_vector LIMIT 5
    → Returns [{content_id, similarity, content}]
```

---

## 14. Frontend Architecture

### 14.1 React Application Structure

```
src/
├── App.tsx              ← Route definitions
├── index.css            ← CSS variables (theme colors, risk colors)
├── contexts/
│   ├── AlertContext.tsx  ← Behavioral alerts state + client-side detection
│   └── BrokerContext.tsx ← Zerodha connection state + sync
├── pages/
│   ├── Dashboard.tsx        ← Main screen
│   ├── Analytics.tsx        ← 4-tab analytics
│   ├── BlowupShield.tsx     ← Capital defense
│   ├── MyPatterns.tsx       ← Goals + Danger Zone (merged)
│   ├── Chat.tsx             ← AI coach
│   ├── Settings.tsx         ← Profile + notifications + limits
│   ├── MoneySaved.tsx       ← Legacy screen
│   └── Personalization.tsx  ← AI persona settings
├── components/
│   ├── dashboard/
│   │   ├── OpenPositionsTable.tsx
│   │   ├── ClosedTradesTable.tsx
│   │   ├── RiskGuardianCard.tsx    ← Risk state + active patterns
│   │   ├── RecentAlertsCard.tsx
│   │   ├── TradeJournalSheet.tsx   ← Journal entry modal
│   │   ├── BlowupShieldCard.tsx
│   │   ├── HoldingsCard.tsx
│   │   ├── MarginInsightsCard.tsx
│   │   ├── MarginStatusCard.tsx
│   │   └── PredictiveWarningsCard.tsx
│   ├── analytics/
│   │   ├── OverviewTab.tsx
│   │   ├── PerformanceTab.tsx
│   │   ├── RiskTab.tsx
│   │   ├── BehaviorTab.tsx
│   │   ├── AINarrativeCard.tsx     ← AI-generated behavioral story
│   │   ├── OrderAnalyticsCard.tsx
│   │   └── ExportReportButton.tsx
│   └── settings/
│       ← Profile card, notification settings, guardian settings, risk limits
├── lib/
│   ├── api.ts              ← Axios instance + all API wrappers
│   ├── patternDetector.ts  ← Client-side pattern detection (15+ patterns)
│   ├── patternConfig.ts    ← buildPatternConfig(profile) 3-tier thresholds
│   ├── emotionalTaxCalculator.ts  ← $ cost of each pattern
│   ├── goalsApi.ts         ← Goal CRUD wrappers
│   └── pushNotifications.ts ← VAPID push subscription
├── hooks/
│   ├── useWebSocket.ts     ← WebSocket connection + event parsing
│   ├── useHoldings.ts
│   ├── useMargins.ts
│   ├── useOrderAnalytics.ts
│   └── usePriceStream.ts
└── types/
    ├── api.ts              ← All API response TypeScript interfaces
    └── patterns.ts         ← BehaviorPattern, PatternDetectorConfig, etc.
```

### 14.2 AlertContext (Client-side pattern detection)

```typescript
AlertContext provides:
  patterns:    BehaviorPattern[]   // from client-side detector (session only)
  alerts:      RiskAlert[]         // from backend risk_alerts table
  capital:     number              // resolved capital (profile → Kite → floor)
  traderProfile: UserProfile       // preferences + thresholds

Capital resolution order:
  1. profile.trading_capital (user-declared, most accurate)
  2. Kite equity margins.total (live, zero user effort)
  3. 100,000 (floor for cold start)

runAnalysis(trades):
  → detectAllPatterns(trades, capital, buildPatternConfig(profile))
  → Updates patterns state

Auto-poll:
  → /api/risk/alerts every 60s (while mounted)
  → Persists unacknowledged alerts in localStorage
```

### 14.3 BrokerContext (Connection state)

```typescript
BrokerContext provides:
  isConnected:  boolean
  account:      BrokerAccount | null
  tokenStatus:  "valid" | "expired" | "checking" | "unknown"
  syncStatus:   "idle" | "syncing" | "success" | "error"

connect()     → GET /api/zerodha/connect → redirect to Kite
disconnect()  → POST /api/zerodha/disconnect → clears localStorage token
syncTrades()  → POST /api/zerodha/sync/all → triggers full pipeline
validateToken() → GET /api/zerodha/token/validate

OAuth callback handling:
  URL params check on mount:
    ?token=...&broker_account_id=... (from Zerodha callback redirect)
  → Stores JWT in localStorage
  → Triggers initial sync automatically
```

### 14.4 Client-Side Pattern Detection

The frontend has its OWN pattern detector (`src/lib/patternDetector.ts`) that runs on the
browser. This provides INSTANT feedback before the backend completes its analysis.

```typescript
detectAllPatterns(trades: Trade[], capital: number, config: PatternConfig): BehaviorPattern[]

Patterns (15+):
  overtrading             → count trades in 15-min windows
  revenge_trading         → quick re-entry after loss, same symbol
  loss_aversion           → hold losers >30 min, cut winners <10 min
  position_sizing         → position > 20% of capital
  fomo                    → 3+ same-direction entries in 5 min
  no_stoploss             → position unrealized > -10% with no exit
  early_exit              → exits within 2 min of entry
  winning_streak          → overconfidence after 3 wins (sizing up)
  consecutive_losses      → 3+ losses in a row
  options_premium_risk    → premium > 5% of capital
  sic                     → size increase after consecutive loss
  breakeven_fixation      → exits exactly at entry price (fear-based)
  market_open_rush        → 3+ trades in first 5 min
  tilt_loss_spiral        → escalating sizes while losing

Each pattern returns:
  { name, detected, frequency, severity, pnl_impact, description,
    recommendation, affectedTrades }
```

### 14.5 useWebSocket Hook

```typescript
useWebSocket(broker_account_id: string):
  Connects to ws://localhost:8000/api/ws?token={jwt}

  Handles:
    "behavioral_event" → adds to alerts state, shows toast notification
    "trade_update"     → invalidates React Query cache (refetches data)
    "danger_zone"      → updates danger level indicator in navbar
    "price_update"     → updates unrealized P&L on open positions

  Reconnects: exponential backoff (1s, 2s, 4s, 8s, max 30s)
```

---

## 15. Screen-by-Screen Feature Map

### Screen 1: Dashboard (`/`)

```
Components:
  ┌─────────────────────────────────────────────────────────┐
  │  Risk Guardian Card                                     │
  │  • Current risk state (safe/caution/danger)             │
  │  • Active patterns list                                  │
  │  • AI coach micro-insight (from /api/coach/insight)     │
  └─────────────────────────────────────────────────────────┘
  ┌───────────────────────┐  ┌───────────────────────────┐
  │  Open Positions       │  │  Blowup Shield Card       │
  │  • Live unrealized PnL│  │  • Capital defended ₹     │
  │  • Symbol, qty, entry │  │  • Shield score           │
  └───────────────────────┘  └───────────────────────────┘
  ┌───────────────────────┐  ┌───────────────────────────┐
  │  Closed Trades        │  │  Recent Alerts Card       │
  │  • Realized P&L       │  │  • Last 5 pattern alerts  │
  │  • Journal icon/link  │  │  • Acknowledge button     │
  └───────────────────────┘  └───────────────────────────┘
  ┌─────────────────────────────────────────────────────────┐
  │  Margin Status Card                                     │
  │  • Equity + Commodity margin from Kite                  │
  │  • Available margin, utilised span/exposure             │
  └─────────────────────────────────────────────────────────┘
  ┌─────────────────────────────────────────────────────────┐
  │  Predictive Warnings Card                               │
  │  • "Your next trade may trigger overtrading"            │
  │  • Based on current session context                     │
  └─────────────────────────────────────────────────────────┘

Data sources:
  /api/positions/          → OpenPositionsTable
  /api/trades/completed    → ClosedTradesTable
  /api/risk/state          → RiskGuardianCard
  /api/risk/alerts         → RecentAlertsCard
  /api/coach/insight       → AI insight text
  /api/zerodha/margins     → MarginStatusCard
  /api/analytics/predictions → PredictiveWarningsCard
```

### Screen 2: Analytics (`/analytics`)

```
4 Tabs:

TAB 1: Overview
  • P&L chart (30-day line chart)
  • Win rate, total trades, best/worst day
  • Session stats (today)
  • Emotional tax calculator: "Your patterns cost ₹X this month"
  Data: /api/analytics/dashboard-stats

TAB 2: Performance
  • P&L by hour of day (bar chart — when is this trader profitable?)
  • P&L by symbol (which instruments work for them?)
  • Trade duration histogram (how long do they hold?)
  • Order analytics: LIMIT vs MARKET vs SL order performance
  Data: /api/analytics/time-analysis, /api/zerodha/order-analytics

TAB 3: Risk
  • Weekly risk score (0–100)
  • Pattern frequency chart (how often each pattern fires)
  • Pattern cost chart (which pattern costs the most?)
  • Alert history (acknowledged vs unacknowledged rate)
  Data: /api/analytics/risk-score, /api/analytics/patterns

TAB 4: Behavior (AI-enhanced)
  • AI narrative card (LLM-generated behavioral story)
  • Trader persona display
  • Top 3 pattern deep-dives with trade examples
  • Recommendations from behavioral analysis
  Data: /api/behavioral/analysis, /api/analytics/ai-summary
```

### Screen 3: Blowup Shield (`/blowup-shield`)

```
Hero Section:
  ┌─────────────────────────────────────────────────────┐
  │  ₹47,500 Capital Defended                          │
  │  78  Shield Score (% of heeded alerts)              │
  │  3 Blowups Prevented                                │
  └─────────────────────────────────────────────────────┘

Intervention Timeline (each alert):
  ┌─────────────────────────────────────────────────────┐
  │  Overtrading Alert — Mar 07, 10:32 AM              │
  │  [Verified ✓] Money Saved: ₹8,400                 │
  │  What would've happened: ₹-8,400 more loss        │
  │  What you actually did: ₹0 (you stopped)           │
  └─────────────────────────────────────────────────────┘
  ┌─────────────────────────────────────────────────────┐
  │  Revenge Sizing Alert — Mar 07, 14:15 PM           │
  │  [Calculating...] ⏳ 12 min remaining              │
  └─────────────────────────────────────────────────────┘
  ┌─────────────────────────────────────────────────────┐
  │  Consecutive Loss Alert — Mar 06, 11:00 AM         │
  │  [No position data] Position closed before check   │
  └─────────────────────────────────────────────────────┘

Badge states:
  [Verified ✓] green  → calculation_status = 'complete'
  [Calculating...] amber → status = 'pending' | 'calculating'
  [No position data] grey → status = 'no_positions'
  [Predates system] grey → alert before checkpoint system launch

Data: /api/shield/summary, /api/shield/timeline
```

### Screen 4: My Patterns (`/my-patterns`)

```
(Merged Goals + Danger Zone)

Section A: Status Banner
  • Current danger level (safe/caution/warning/danger/critical)
  • Cooldown timer if active (with Skip button)
  • Active triggers list ("consecutive_loss: 4 losses in a row")

Section B: Goal Commitments
  • GoalCommitmentsCard: daily_max_loss, daily_max_trades, primary_segment
  • Editable inline (no 24h cooldown — direct edit)

Section C: Emotional Tax
  • "Your patterns have cost ₹24,500 this month"
  • Per-pattern cost breakdown

Section D: Streak Tracker
  • Consecutive "clean days" (no danger alerts)
  • Current streak + best streak

Section E: Alert History
  • Last 30 days of alerts
  • Acknowledged vs unacknowledged
  • Breakdown by pattern type

Data: /api/danger-zone/status, /api/cooldown/status,
      /api/risk/alerts, (goals from local storage or backend)
```

### Screen 5: Chat (`/chat`)

```
• Chat input box + history display
• AI persona indicator (coach/mentor/friend/strict)
• Auto-populated context: "Based on your trading today..."
• Message suggestions based on recent alerts
• RAG toggle (include journal context)

Persona affects tone completely:
  Coach:  "Your overtrading pattern is costing you ₹X/session. Here's a structured approach..."
  Friend: "Hey, I noticed you were having a rough morning. Want to talk about it?"
  Strict: "9 trades in 15 minutes is unacceptable. This stops now."
  Mentor: "I've seen this pattern before. Let me help you understand what's happening..."

Data: POST /api/coach/chat
```

### Screen 6: Settings (`/settings`)

```
Tab 1: Profile
  • Experience level, trading style, risk tolerance
  • Known weaknesses (checkboxes)
  • AI persona selector

Tab 2: Risk Limits (6 fields)
  • Trading capital (₹)
  • Daily loss limit (₹)
  • Max position size (₹ or %)
  • SL % for futures
  • SL % for options
  • Cooldown after loss (minutes)

Tab 3: Notifications
  • WhatsApp toggle + phone number
  • Push notification toggle
  • Guardian phone + name
  • Guardian alert threshold (caution/danger/critical)
  • EOD report time (HH:MM IST)
  • Morning prep time (HH:MM IST)
  • "Send Test" button → POST /api/settings/guardian/test

Data: GET/PUT /api/settings/profile, /api/settings/notifications
```

---

## 16. Data Flow Diagrams

### Complete Trade-to-Alert Flow

```
╔═══════════════════════════════════════════════════════════════════╗
║  TRADER                                                          ║
║  Places SELL order on Zerodha for NIFTY FUT                     ║
╚═════════════════════════════╦═════════════════════════════════════╝
                               │ Zerodha executes order
                               ▼
╔═══════════════════════════════════════════════════════════════════╗
║  ZERODHA WEBHOOK                                                 ║
║  POST /api/webhooks/zerodha/postback                             ║
║  { order_id: "123", tradingsymbol: "NIFTY25MARFUT",             ║
║    transaction_type: "SELL", status: "COMPLETE",                 ║
║    average_price: 22500, quantity: 50, tag: "user_abc123" }     ║
╚═════════════════════════════╦═════════════════════════════════════╝
                               │ SHA-256 verified
                               ▼
╔═══════════════════════════════════════════════════════════════════╗
║  CELERY: process_webhook_trade                                   ║
║  trades queue                                                    ║
║                                                                  ║
║  1. Classify: NFO → FNO, ends in FUT → FUTURE                   ║
║  2. Upsert to trades table                                       ║
║  3. Status = COMPLETE → run P&L pipeline                        ║
║     FIFO match: BUY(22450, 50) + SELL(22500, 50)                ║
║     realized_pnl = (22500-22450) × 50 = +₹2,500                 ║
║     Create CompletedTrade {pnl=+2500, direction=LONG, ...}      ║
║  4. Sync positions: NIFTY25MARFUT qty → 0 (closed)              ║
╚═════════════════════════════╦═════════════════════════════════════╝
                               │ P&L saved, positions updated
                               ▼
╔═══════════════════════════════════════════════════════════════════╗
║  SIGNAL PIPELINE (same task)                                     ║
║                                                                  ║
║  RiskDetector.detect_patterns():                                 ║
║    consecutive_loss: [−500, −300, −200, +2500] → streak broken  ║
║    revenge_sizing: last loss was 30 min ago → outside window     ║
║    overtrading: 4 trades in 15 min < 6 threshold                 ║
║    → NO ALERTS this time                                         ║
║                                                                  ║
║  BehavioralEvaluator.evaluate(new_fill):                        ║
║    loss_chasing: SELL on NIFTY, last NIFTY trade was +2500 → WIN ║
║    → No events                                                   ║
╚═════════════════════════════╦═════════════════════════════════════╝
                               │
                               ▼
╔═══════════════════════════════════════════════════════════════════╗
║  WEBSOCKET BROADCAST                                             ║
║  No events to broadcast (no alerts)                              ║
╚═════════════════════════════╦═════════════════════════════════════╝
                               │ 1 second later, frontend polls
                               ▼
╔═══════════════════════════════════════════════════════════════════╗
║  FRONTEND                                                        ║
║  Dashboard refreshes:                                            ║
║    ClosedTradesTable shows NIFTY25MARFUT +₹2,500                ║
║    OpenPositionsTable removes NIFTY25MARFUT                      ║
║    Risk Guardian shows "safe" (no active alerts)                 ║
╚═══════════════════════════════════════════════════════════════════╝
```

### Alert → WhatsApp → Checkpoint Flow

```
Trader places revenge trade: 3x size, 4 minutes after ₹5,000 loss
                │
                ▼
  RiskDetector._detect_revenge_sizing():
    qty=30 vs prev_qty=10 → 3x > 1.5 threshold
    time_gap=4min < revenge_window=10min
    → RiskAlert(severity="danger", pattern="revenge_sizing")
    → Saved to risk_alert table
                │
                ├──── NOTIFICATION PIPELINE ────────────────────────►
                │                                                    │
                │     AlertService.send_risk_alert_with_guardian()   │
                │                                                    │
                │     User WhatsApp (+91XXXXX):                      │
                │     "🚨 TRADEMENTOR RISK ALERT 🚨                 │
                │      ⚠️ REVENGE TRADING DETECTED                  │
                │      Position size increased 200% after loss       │
                │      🛑 STOP IMMEDIATELY                          │
                │      You are in tilt mode."                        │
                │                                                    │
                │     Guardian WhatsApp (+91YYYYY):                  │
                │     "⚠️ RISK GUARDIAN ALERT                       │
                │      AB1234 is showing high-risk behavior.         │
                │      Pattern: Revenge Trading                      │
                │      Size increased 200% after loss                │
                │      You may want to check in with them."          │
                │                                                    ◄
                │
                ├──── CHECKPOINT PIPELINE (countdown=10s) ──────────►
                │                                                    │
                │     create_alert_checkpoint:                       │
                │       Kite positions: BANKNIFTY qty=30, entry=48000│
                │       Kite LTP: 47800 (losing ₹6,000 unrealized)  │
                │       Save AlertCheckpoint {ltp_at_alert: 47800}   │
                │         ↓ (5 min later)                            │
                │     check_alert_t5:                                │
                │       LTP = 47600 (would be -₹12,000)             │
                │         ↓ (25 more min)                            │
                │     check_alert_t30:                               │
                │       LTP = 47400 (pnl_at_t30 = -₹18,000)        │
                │       CompletedTrade(BANKNIFTY, exit_time in range)│
                │       user_actual_pnl = -₹6,800 (user stopped loss)│
                │       money_saved = -6800 - (-18000) = +₹11,200   │
                │       status = 'complete'                          │
                │                                                    ◄
                │
                └──── COOLDOWN TRIGGER ──────────────────────────────►
                      duration = user_profile.cooldown_after_loss = 15min
                      can_skip = True
                      Frontend shows: "Cooling down. 14 min remaining. [Skip]"
```

---

## 17. Environment Configuration

### Required Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@host/db

# Security
ENCRYPTION_KEY=<Fernet key>          # Generate: Fernet.generate_key()
SECRET_KEY=<random 32-byte hex>      # For JWT signing
ALGORITHM=HS256

# Zerodha
ZERODHA_API_KEY=your_api_key
ZERODHA_API_SECRET=your_api_secret
ZERODHA_REDIRECT_URI=https://your-domain.com/api/zerodha/callback

# Frontend
FRONTEND_URL=https://your-frontend-domain.com
```

### Optional Variables

```bash
# AI
OPENROUTER_API_KEY=sk-or-...         # For coach + persona features
OPENAI_API_KEY=sk-...                # For RAG embeddings

# Redis / Celery
REDIS_URL=rediss://...               # Upstash format (TLS)
CELERY_BROKER_URL=$REDIS_URL
CELERY_RESULT_BACKEND=$REDIS_URL

# WhatsApp
TWILIO_ACCOUNT_SID=ACxxx
TWILIO_AUTH_TOKEN=xxx
TWILIO_WHATSAPP_FROM=+14155238886    # Twilio sandbox or verified number

# Push Notifications
VAPID_PUBLIC_KEY=BAxxx
VAPID_PRIVATE_KEY=xxx

# Supabase (if using Supabase directly)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=xxx

# App
ENVIRONMENT=production              # dev | staging | production
CORS_ORIGINS=https://your-frontend.com
```

### Running Locally

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Celery worker (separate terminal)
celery -A app.core.celery_app worker -Q trades,alerts,reports -c 4 --loglevel=info

# Celery beat scheduler (separate terminal)
celery -A app.core.celery_app beat --loglevel=info

# Frontend
npm install
npm run dev  # starts on port 8080
```

---

## Appendix: Migration History

| Migration | Change |
|-----------|--------|
| 003 | Goals tables |
| 004 | Push subscriptions |
| 005 | Segment support |
| 006 | Journal entries |
| 007 | User profiles |
| 008 | Cooldowns |
| 009 | Kite API alignment |
| 010 | Orders, holdings, instruments |
| 011 | Margin snapshots |
| 012 | Vector embeddings (RAG) |
| 013 | broker_account_id on holdings |
| 014 | guardian_daily_summary |
| 016 | Fix missing columns |
| 017 | Cascade deletes |
| 018 | Data type fixes |
| 019 | Symbol standardization |
| 020 | **Trade architecture overhaul** (CompletedTrade, features) |
| 021 | Performance indexes |
| 022 | Cascade indexes + datetime |
| 023 | Segment column |
| 024 | Token revocation (token_revoked_at) |
| 025 | AI cache column |
| 027 | Report timing columns |
| 028 | Threshold fields (trading_capital, sl_percent, etc.) |
| 029 | Alert checkpoints (BlowupShield) |
| 030 | Journal trade FK fix |
| 031 | Timestamp indexes |
| 032 | Users table (stable identity, guardian_phone) |
| 033 | Schema fixes |
| 034 | Alert checkpoint column fixes |

---

---

## 18. Known Deferred Items

These are architecturally significant open items — reviewed and intentionally not fixed yet.

| ID | Area | Issue | Impact |
|----|------|-------|--------|
| WS-03 | WebSocket | No exponential backoff on reconnect — retries every 3s unconditionally | Creates rapid reconnect loop if token expired |
| WS-05 | WebSocket | No server-side heartbeat — half-open TCP connections undetected | Silent disconnects not cleaned up |
| PN-03 | Push Notifications | `webpush()` is a blocking/sync call inside async context | Thread blocking during push delivery |
| COLD-START | Product | No hook for new users (0 trades) — pattern detection silent first 2-3 weeks | Retention risk for new traders |

### Migrations Pending in Supabase

These migrations exist as SQL files but have not been run in production Supabase yet:

| Migration | What it adds |
|-----------|-------------|
| 022 | Cascade indexes + datetime fixes |
| 023 | Segment column |
| 024 | Token revocation |
| 025 | AI cache table |
| 028 | Threshold fields (trading_capital, max_position_size_pct, sl_percent, cooldown_after_loss_min, daily_trade_limit) |
| 029 | Alert checkpoints (BlowupShield counterfactual P&L) |

---

*Document generated from codebase analysis. All code paths, API shapes, and field names
reflect the current implementation as of 2026-03-07 (session 15 — cross-cutting review complete, 8 bugs fixed).*
