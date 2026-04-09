# TradeMentor AI - Architecture Guide

## Data Ingestion Architecture

### Current State vs Target State

```
CURRENT (Polling-Based):
┌──────────────┐     Manual Sync      ┌──────────────┐
│   Frontend   │ ──────────────────▶  │   Backend    │
│  (User Click)│                      │  /api/sync   │
└──────────────┘                      └──────┬───────┘
                                             │
                                             ▼
                                      ┌──────────────┐
                                      │ Zerodha API  │
                                      │  (Polling)   │
                                      └──────────────┘

PROBLEM: Rate limits, stale data, doesn't scale


TARGET (Event-Driven like Sensibull/Tijori):
┌──────────────┐                      ┌──────────────┐
│   Zerodha    │ ═══ Postback ═════▶  │   Backend    │
│   (Events)   │    (Real-time)       │  /webhooks   │
└──────────────┘                      └──────┬───────┘
                                             │
                                      ┌──────┴───────┐
                                      │ Redis Queue  │
                                      └──────┬───────┘
                                             │
                              ┌──────────────┼──────────────┐
                              ▼              ▼              ▼
                        ┌─────────┐   ┌─────────┐   ┌─────────┐
                        │ Worker1 │   │ Worker2 │   │ Worker3 │
                        │ (Trades)│   │ (Risk)  │   │ (Alerts)│
                        └─────────┘   └─────────┘   └─────────┘
```

## Setting Up Zerodha Postback (Webhook)

### Step 1: Get a Public URL

For local development, use Cloudflare Tunnel:
```bash
# Install cloudflared
# Windows: winget install cloudflare.cloudflared

# Start tunnel
cloudflared tunnel --url http://localhost:8000

# Output: https://xxx-yyy-zzz.trycloudflare.com
```

### Step 2: Configure in Zerodha Developer Console

1. Go to: https://developers.kite.trade/apps
2. Select your app
3. Under "Postback URL", enter:
   ```
   https://xxx-yyy-zzz.trycloudflare.com/api/webhooks/zerodha/postback
   ```
4. Save

### Step 3: Test the Webhook

Place a test order in Zerodha Kite. Check backend logs:
```
INFO: Received postback from Zerodha
INFO: Postback processed: ORDER_ID - Status: COMPLETE
```

## Market Hours by Segment

| Segment | Exchange | Market Hours (IST) | Notes |
|---------|----------|-------------------|-------|
| EQUITY | NSE, BSE | 9:15 AM - 3:30 PM | Pre-open: 9:00-9:08 |
| F&O | NFO, BFO | 9:15 AM - 3:30 PM | Same as equity |
| COMMODITY | MCX | 9:00 AM - 11:30 PM | Morning + Evening session |
| COMMODITY | NCDEX | 10:00 AM - 5:00 PM | Agricultural commodities |
| CURRENCY | CDS | 9:00 AM - 5:00 PM | Currency derivatives |

### High-Risk Windows

| Segment | Window | Time | Risk |
|---------|--------|------|------|
| EQUITY/F&O | Market Open | 9:15-9:30 | High volatility |
| EQUITY/F&O | Market Close | 3:00-3:30 | Expiry rush |
| COMMODITY | Morning Open | 9:00-9:15 | Gap risk |
| COMMODITY | Evening Start | 5:00-5:30 | Session change |
| COMMODITY | Night Close | 11:00-11:30 | Thin liquidity |
| CURRENCY | Open | 9:00-9:15 | Global cues |
| CURRENCY | Close | 4:30-5:00 | Position squaring |

## Scaling for Multiple Users

### Current Limitations
- Single-threaded processing
- No rate limiting
- Synchronous risk detection

### Recommended Architecture

```python
# 1. Use Redis Queue for async processing
from redis import Redis
from rq import Queue

redis = Redis()
queue = Queue(connection=redis)

# In webhook handler:
@router.post("/zerodha/postback")
async def handle_postback(data: dict):
    # Quick validation
    if not verify_checksum(data):
        return {"error": "Invalid checksum"}

    # Queue for async processing (non-blocking)
    queue.enqueue(process_trade, data)

    return {"status": "queued"}  # Return immediately

# 2. Worker processes trades
def process_trade(data):
    # Save trade
    # Run risk detection
    # Send alerts if needed
```

### Rate Limiting

```python
# Add to main.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.get("/api/trades/sync")
@limiter.limit("10/minute")  # 10 syncs per minute per user
async def sync_trades():
    ...
```

## File Structure

```
backend/
├── app/
│   ├── core/
│   │   ├── config.py          # Environment settings
│   │   ├── database.py        # DB connection
│   │   └── market_hours.py    # NEW: Market hours config
│   ├── api/
│   │   ├── webhooks.py        # Zerodha postback handler
│   │   ├── trades.py          # Trade sync endpoint
│   │   └── ...
│   ├── services/
│   │   ├── trade_sync_service.py
│   │   ├── risk_detector.py
│   │   └── behavioral_analysis_service.py
│   └── models/
│       ├── trade.py
│       ├── position.py
│       └── goal.py
└── migrations/
    ├── 003_goals_tables.sql
    ├── 004_update_positions_table.sql
    └── 005_add_segment_support.sql
```

## Environment Variables

```env
# Required
DATABASE_URL=postgresql+asyncpg://...
ZERODHA_API_KEY=your_key
ZERODHA_API_SECRET=your_secret
ENCRYPTION_KEY=your_fernet_key

# For Webhooks (Production)
ZERODHA_POSTBACK_URL=https://your-domain.com/api/webhooks/zerodha/postback

# For Scaling
REDIS_URL=redis://localhost:6379/0
```

## Next Steps

1. **Run SQL Migrations**:
   ```sql
   -- In Supabase SQL Editor, run in order:
   -- 003_goals_tables.sql
   -- 004_update_positions_table.sql
   -- 005_add_segment_support.sql
   ```

2. **Configure Zerodha Postback**:
   - Use cloudflared for local testing
   - Set postback URL in Zerodha developer console

3. **Test the Flow**:
   - Connect Zerodha via OAuth
   - Place a test order
   - Verify webhook receives data
   - Check Dashboard updates

4. **For Production**:
   - Deploy to cloud (Railway, Render, etc.)
   - Use proper domain with HTTPS
   - Set up Redis for queue
   - Add rate limiting
