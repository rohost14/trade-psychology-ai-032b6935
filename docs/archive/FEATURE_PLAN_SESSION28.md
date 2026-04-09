# Feature Plan — Session 28
**Date**: 2026-03-18
**Status**: AWAITING REVIEW — do not implement until approved

Two new features to implement:
1. **Position Guardrails** — custom alert rules on open positions (WhatsApp + push, no auto-execution)
2. **Portfolio AI Chat** — dedicated page to chat about full Zerodha portfolio (holdings, MF, margins)

---

## Feature 1: Position Guardrails

### What It Is
User-defined alert rules that fire when an open position hits a condition. When triggered, sends a WhatsApp message + push notification. **No order execution.** User acts manually.

### Design Decisions (already confirmed)
| Decision | Choice | Reason |
|----------|--------|--------|
| Execute exits automatically? | **No — alert only** | SEBI static IP requirement + no multi-user approval + liability risk |
| When do rules reset? | **Daily (next trading day)** | Fresh start each session |
| When can user configure? | **Before market opens** | Set guardrails ahead of time |
| Can rules be paused mid-day? | **Yes — pause/resume** | User needs flexibility |
| Trailing condition? | **Deferred** | Needs clarification — skip for now |
| Which positions are targeted? | **User selects** (all or specific symbols) | Flexible targeting |

### Guardrail Condition Types

| Condition | Meaning | Example |
|-----------|---------|---------|
| `loss_threshold` | Unrealized P&L falls below ₹X on a specific position | Alert if NIFTY PE loses > ₹5,000 |
| `loss_range_time` | Position has been in loss for > N minutes | Alert if losing for > 30 min |
| `total_pnl_drop` | Session total P&L (all positions combined) drops below ₹X | Alert if day total hits −₹10,000 |
| `profit_target` | Unrealized P&L on a position exceeds ₹X profit | Alert if BANKNIFTY CE up > ₹8,000 |

**Scope clarification:**
- `loss_threshold` / `profit_target` → per-position (user picks target symbol or "any open position")
- `total_pnl_drop` → across all open positions for that broker account

### Database Schema — `guardrail_rules` table

```sql
CREATE TABLE guardrail_rules (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id     UUID NOT NULL REFERENCES broker_accounts(id) ON DELETE CASCADE,
    name                  VARCHAR(100) NOT NULL,           -- User-defined label e.g. "Protect NIFTY trade"

    -- Which positions this rule watches
    -- NULL = watch ALL open positions, otherwise ["NIFTY24D19500PE", "BANKNIFTY..."]
    target_symbols        TEXT[],

    -- Condition (only ONE type active per rule)
    condition_type        VARCHAR(50) NOT NULL,
    -- loss_threshold | loss_range_time | total_pnl_drop | profit_target

    condition_value       NUMERIC(15, 2),
    -- Meaning depends on condition_type:
    --   loss_threshold  → negative ₹ amount e.g. -5000
    --   loss_range_time → minutes e.g. 30
    --   total_pnl_drop  → negative ₹ amount e.g. -10000
    --   profit_target   → positive ₹ amount e.g. 8000

    -- Delivery channels
    notify_whatsapp       BOOLEAN NOT NULL DEFAULT TRUE,
    notify_push           BOOLEAN NOT NULL DEFAULT TRUE,

    -- State
    status                VARCHAR(20) NOT NULL DEFAULT 'active',
    -- active | paused | triggered | expired

    triggered_at          TIMESTAMPTZ,                      -- NULL until first trigger
    trigger_count         INTEGER NOT NULL DEFAULT 0,       -- How many times it fired

    -- Auto-expiry: rule expires at end of trading day (15:30 IST)
    -- Set to next 15:30 IST when rule is created
    expires_at            TIMESTAMPTZ NOT NULL,

    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_guardrail_rules_account ON guardrail_rules(broker_account_id);
CREATE INDEX idx_guardrail_rules_active ON guardrail_rules(broker_account_id, status)
    WHERE status = 'active';
```

**Migration file**: `backend/migrations/051_guardrail_rules.sql`

### SQLAlchemy Model — `backend/app/models/guardrail_rule.py`

Fields mirror the table above. Relationship: `broker_account = relationship("BrokerAccount")`.
Add import + `__all__` entry to `backend/app/models/__init__.py`.

### Backend API — `backend/app/api/guardrails.py`

All endpoints require `broker_account_id` via `get_verified_broker_account_id` dep.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/guardrails/` | List all rules for today (includes expired/triggered) |
| `POST` | `/guardrails/` | Create a new guardrail rule |
| `PATCH` | `/guardrails/{id}/pause` | Toggle pause/resume on a rule |
| `DELETE` | `/guardrails/{id}` | Delete a rule |

**POST body schema** (Pydantic):
```python
class GuardrailCreate(BaseModel):
    name: str
    target_symbols: Optional[List[str]] = None  # None = all positions
    condition_type: Literal["loss_threshold", "loss_range_time", "total_pnl_drop", "profit_target"]
    condition_value: float
    notify_whatsapp: bool = True
    notify_push: bool = True
```

**Validation rules:**
- `loss_threshold` → condition_value must be < 0
- `profit_target` → condition_value must be > 0
- `loss_range_time` → condition_value must be > 0 (minutes)
- `total_pnl_drop` → condition_value must be < 0

**expires_at calculation at creation:**
```python
from zoneinfo import ZoneInfo
IST = ZoneInfo("Asia/Kolkata")
now_ist = datetime.now(IST)
# Expire at today's 15:30 IST (or tomorrow's if already past 15:30)
expiry_ist = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)
if now_ist >= expiry_ist:
    expiry_ist += timedelta(days=1)
expires_at = expiry_ist.astimezone(timezone.utc)
```

**Register router** in `backend/app/main.py`:
```python
from app.api import guardrails
app.include_router(guardrails.router, prefix="/api/guardrails", tags=["guardrails"])
```

### Celery Monitoring Task — `backend/app/tasks/guardrail_tasks.py`

**Beat schedule**: every 60 seconds, 09:15–15:25 IST, weekdays only.
**Queue**: `alerts` (same as alert_tasks).

**Task flow:**
```
check_guardrail_rules()
  → fetch all active guardrail_rules (not expired, not triggered)
  → group by broker_account_id
  → for each account:
      → fetch open positions from DB (Position.status == 'open')
      → fetch LTP from Redis cache (get_cached_ltp) — no Kite API calls
      → compute unrealized_pnl for each position = (ltp - avg_price) * qty
      → evaluate each rule:
          loss_threshold → min(position unrealized_pnl for target symbols) <= rule.condition_value
          loss_range_time → any position has been open AND in loss for > N minutes
          total_pnl_drop → sum(all open position unrealized_pnl) <= rule.condition_value
          profit_target → max(position unrealized_pnl for target symbols) >= rule.condition_value
      → if condition met:
          → update rule: status='triggered', triggered_at=now, trigger_count += 1
          → fire WhatsApp + push notification (existing services)
          → after trigger: set status='triggered' so it doesn't repeat
```

**Redis key for loss-range-time tracking:**
```
guardrail:loss_start:{rule_id}:{symbol} → timestamp when position entered loss
```
Set when position first goes negative. Clear when position goes positive.
Time delta from this key = how long the position has been in loss.

**Notification message format (WhatsApp):**
```
🚨 Guardrail Alert: "{rule_name}"
Symbol: {symbol or "Portfolio"}
Condition: {human description of what triggered}
Current P&L: ₹{value}
Time: {HH:MM IST}

→ Check your positions now
```

**Register in celery_app.py** beat schedule:
```python
"check-guardrails": {
    "task": "app.tasks.guardrail_tasks.check_guardrail_rules",
    "schedule": 60.0,  # every 60 seconds
},
```
Add to `include` list and `task_routes` (queue: `alerts`).

### Frontend Page — `src/pages/Guardrails.tsx`

**Route**: `/guardrails` (add to App.tsx + Layout nav)

**Page layout:**
```
Header: "Position Guardrails" + "Add Rule" button
Info banner: "Rules expire at market close (15:30 IST) and reset tomorrow."

[Active Rules section]
  Card per rule showing:
    - Name
    - Condition (human-readable: "Alert if NIFTY PE loses > ₹5,000")
    - Targets: "All positions" or symbol list
    - Status badge: Active / Paused / Triggered
    - Triggered count + last trigger time (if any)
    - Pause / Delete actions

[Add Rule Dialog/Sheet]
  - Name field
  - Condition type selector (4 options with descriptions)
  - Value input (₹ amount or minutes)
  - Target: "All positions" or symbol multiselect
  - Notify via: WhatsApp / Push toggles
  - Save button
```

**API calls** (use existing `api.ts` pattern, axios):
- `GET /api/guardrails/` — load rules
- `POST /api/guardrails/` — create rule
- `PATCH /api/guardrails/{id}/pause` — toggle pause
- `DELETE /api/guardrails/{id}` — delete

**Add to nav**: in `src/components/Layout.tsx` sidebar and mobile More sheet.
Icon: `Shield` or `Bell` from lucide-react.

---

## Feature 2: Portfolio AI Chat

### What It Is
A dedicated chat page where users can ask natural language questions about their full Zerodha portfolio — equity holdings, mutual funds, margins, sector exposure. Powered by Claude (via OpenRouter). SEBI compliant — no buy/sell advice.

### Design Decisions
| Decision | Choice |
|----------|--------|
| Data delivery | **Redis cache + background sync** — zero API calls on page open |
| Live P&L | **KiteTicker WebSocket** — same stream already running for traders |
| MCP | **Not used** — MCP wraps the same KiteConnect API, adds latency, solves nothing |
| Who can use it? | All users (not gated) |
| Investment advice? | **No** — SEBI IA Reg 2013. Analysis only. |
| Order history | Not needed |
| Streaming | **Yes** — SSE, same as `coach.py` pattern |
| Chat history | Ephemeral (no DB table needed) |

### Why NOT "Fetch On Page Open"

1000 users open the page at market open → 3000 KiteConnect API calls in a burst. Even though Zerodha rate-limits per user (not globally), our backend would be making 3000 outbound HTTP connections simultaneously — connection pool exhaustion.

**The correct approach is identical to how trader features work:**
```
WRONG:  User opens page → 3 API calls → render
RIGHT:  Background task → fetch → Redis cache → page reads cache → 0 API calls
        KiteTicker → LTP streaming → live P&L without any API calls
```

### Data Architecture

| Data | Source | Update trigger | Redis TTL |
|------|--------|---------------|-----------|
| Equity holdings (qty, avg price) | KiteConnect `/portfolio/holdings` | Background task at 9:00 AM + postback webhook on CNC settle | 4 hours |
| MF holdings | KiteConnect `/portfolio/mf/holdings` | Background task at 9:00 AM | 24 hours |
| Margins | KiteConnect `/user/margins` | Already synced by existing margin tasks | 5 min (existing) |
| Holdings LTP / live P&L | **KiteTicker WebSocket** (already running) | Continuous — no API calls | n/a |
| Open F&O positions | **Our DB** (Position table) | Already event-driven | n/a |

**Holdings quantity/avg_price don't change intraday** — they only change when a CNC trade settles (T+2). A background sync at 9:00 AM + postback-webhook invalidation is more than sufficient.

**Live portfolio value** — subscribe holdings' `instrument_token` values to KiteTicker (same ticker already subscribed for F&O). Compute `(ltp - avg_price) × qty` in real-time from the same Redis LTP cache we already use. Push updates via Redis Streams → WebSocket → frontend. Zero API calls.

### Redis Keys

```
portfolio:holdings:{broker_account_id}    → JSON, TTL 4h
portfolio:mf_holdings:{broker_account_id} → JSON, TTL 24h
portfolio:synced_at:{broker_account_id}   → timestamp of last sync
```

### Portfolio Sync Strategy — Lazy Loading (NOT bulk 9 AM sync)

**Critical constraint:** KiteConnect REST API = 10 req/sec per API key, shared across ALL users.
Bulk syncing N users at 9 AM = N×2 calls queued → 429 errors at scale.

**Correct approach: sync on demand, cache aggressively.**

```
User opens Portfolio Chat:
  → check Redis: portfolio:holdings:{id} exists?
  → YES (cache hit):  serve immediately, 0 KiteConnect calls
  → NO  (cache miss): acquire Redis lock, fetch holdings + MF (2 calls),
                       store in Redis TTL 4h, release lock

Postback webhook fires (CNC order settled):
  → invalidate portfolio:holdings:{id}
  → queue sync_portfolio_for_account.delay() — rate-limited queue

Rate limit protection:
  → Redis lock per account: "portfolio:syncing:{id}" with 30s TTL
  → if lock held (another worker already fetching), wait and read from cache when done
  → Celery task uses exponential backoff on 429 response
```

### New Celery Task — `backend/app/tasks/portfolio_sync_tasks.py`

```
sync_portfolio_for_account(broker_account_id):  ← on-demand only, NOT beat scheduled
  → acquire Redis lock (skip if already syncing)
  → fetch holdings from KiteConnect (1 call)
  → fetch MF holdings from KiteConnect (1 call)
  → compute sector_exposure dict (in-memory, no API)
  → store all in Redis with TTL 4h
  → release lock
  → subscribe holdings instrument_tokens to KiteTicker (if not already)
```

**No beat schedule for portfolio sync.** Sync is triggered only by:
1. User opens Portfolio Chat and cache is cold (lazy load)
2. Postback webhook fires a CNC settlement (invalidate + re-sync)

At 1,000 users: ~200 use Portfolio Chat daily → 400 KiteConnect calls spread over hours → well within 10 req/sec limit.

**Postback webhook trigger** (in existing `webhooks.py`): When a CNC order executes → call `sync_portfolio_for_account.delay(broker_account_id)` to invalidate + refresh holdings cache. Already have the webhook; just add one `.delay()` call.

### Sector Exposure (in-memory computation, no external API)

Kite doesn't return sector labels. Derive from tradingsymbol:
- Hardcoded dict of top-200 NSE stocks → sector (covers ~95% of retail portfolios)
- For unknowns: bucket as "Other"
- Computed from holdings list in `sync_portfolio_for_account` and stored in Redis alongside holdings

### Backend — `backend/app/api/portfolio_chat.py`

**Chat behavior = MCP-like dynamic tool calling, but tools read Redis (zero Kite API calls)**

The LLM does NOT receive all data upfront. Instead it calls tools on demand — exactly like MCP — but every tool just reads from Redis/DB. Fresh data, no polling, no external calls.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/portfolio-chat/snapshot` | UI snapshot for the left panel (reads Redis) |
| `POST` | `/portfolio-chat/message` | SSE streaming chat with tool calling |

**Tools defined for the LLM (OpenRouter tool calling):**

```python
PORTFOLIO_TOOLS = [
    {
        "name": "get_holdings",
        "description": "Get the user's equity holdings (CNC/delivery positions) with current LTP and unrealized P&L",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_mf_holdings",
        "description": "Get the user's mutual fund holdings with NAV and current value",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_margins",
        "description": "Get available cash, used margin, and collateral for the account",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_open_positions",
        "description": "Get currently open F&O/MIS/NRML intraday positions with live unrealized P&L",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_sector_exposure",
        "description": "Get portfolio sector breakdown — which sectors hold the most value",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_holding_detail",
        "description": "Get details for a specific stock holding by symbol",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "NSE tradingsymbol e.g. INFY, TCS"}
            },
            "required": ["symbol"]
        }
    }
]
```

**All tool implementations read from Redis — zero KiteConnect calls:**
```python
async def _execute_tool(name: str, args: dict, broker_account_id: UUID) -> dict:
    r = get_redis()
    if name == "get_holdings":
        data = r.get(f"portfolio:holdings:{broker_account_id}")
        holdings = json.loads(data) if data else []
        # Enrich with live LTP from KiteTicker Redis cache
        for h in holdings:
            ltp = get_cached_ltp(h["instrument_token"]) or h["last_price"]
            h["ltp"] = ltp
            h["unrealized_pnl"] = (ltp - h["average_price"]) * h["quantity"]
        return {"holdings": holdings}

    elif name == "get_mf_holdings":
        data = r.get(f"portfolio:mf_holdings:{broker_account_id}")
        return {"mf_holdings": json.loads(data) if data else []}

    elif name == "get_margins":
        data = r.get(f"portfolio:margins:{broker_account_id}")
        return json.loads(data) if data else {}

    elif name == "get_open_positions":
        # Read from DB — already event-driven, always fresh
        positions = await db.execute(select(Position).where(...status == 'open'...))
        return {"positions": [...]}

    elif name == "get_sector_exposure":
        data = r.get(f"portfolio:sector:{broker_account_id}")
        return json.loads(data) if data else {}

    elif name == "get_holding_detail":
        symbol = args["symbol"].upper()
        data = r.get(f"portfolio:holdings:{broker_account_id}")
        holdings = json.loads(data) if data else []
        match = next((h for h in holdings if h["tradingsymbol"] == symbol), None)
        return match or {"error": f"{symbol} not found in holdings"}
```

**Chat endpoint flow (SSE streaming with tool loop):**
```
POST /portfolio-chat/message
  → send to OpenRouter with PORTFOLIO_TOOLS defined
  → LLM decides which tools to call
  → for each tool_use block:
      → execute tool → read Redis → return result to LLM
  → LLM generates text response
  → stream text chunks as SSE to frontend
```

Uses OpenRouter's tool calling (same API shape as Anthropic tool use). Handles multi-tool calls per turn (LLM may call 2-3 tools in one response). Stream the final text response as SSE.

**System prompt:**
```
You are a portfolio analysis assistant for Indian retail investors using Zerodha.
You have access to tools to fetch the user's holdings, mutual funds, margins, and positions.
Call only the tools you need based on the question.

RULES:
- Analysis and observations only. Never buy/sell/hold recommendations for specific securities.
- Never predict price movements or suggest entry/exit points.
- If asked for investment advice: explain you provide analysis only,
  suggest consulting a SEBI-registered Investment Adviser (IA).
- Always note that past performance does not indicate future results.
- When you fetch data, present it in a clear, concise way with ₹ formatting.
```

**zerodha_service.py additions needed:**
- `get_mf_holdings(access_token)` → `GET /portfolio/mf/holdings`

**Register in main.py:**
```python
from app.api import portfolio_chat
app.include_router(portfolio_chat.router, prefix="/api/portfolio-chat", tags=["portfolio-chat"])
```

### Frontend Page — `src/pages/PortfolioChat.tsx`

**Route**: `/portfolio-chat`

**Page layout:**
```
Left panel (desktop) / Top section (mobile): Portfolio Snapshot
  - Margin card: Available cash / Used / Collateral
  - Holdings summary: Total invested / current value / P&L % (live via WebSocket)
  - Sector exposure: Horizontal bar chart (recharts, from snapshot)
  - Top 5 holdings by current value
  - "Last synced: X min ago" + manual refresh button

Right panel (desktop) / Bottom section (mobile): Chat interface
  - Message history (scrollable)
  - Starter prompts when empty (4 suggestions)
  - Input + Send
  - SEBI disclaimer (ComplianceDisclaimer footer variant)
```

**Starter prompts:**
- "What's my biggest sector concentration risk?"
- "Which holdings have the worst day P&L today?"
- "How much margin am I using vs available?"
- "Summarise my portfolio in plain language"

**WebSocket integration for live P&L:**
- Subscribe to `portfolio_value_update` events via existing WebSocket connection
- Backend fires these events when KiteTicker updates LTP for held instruments
- Frontend updates holdings P&L in real-time without any API calls

**API calls (REST, one-time only):**
- `GET /api/portfolio-chat/snapshot` on page load (reads Redis — 0 Kite API calls)
- `POST /api/portfolio-chat/message` for chat (SSE streaming)

---

## File Changes Summary

### New Files
| File | Purpose |
|------|---------|
| `backend/migrations/051_guardrail_rules.sql` | DB migration |
| `backend/app/models/guardrail_rule.py` | SQLAlchemy model |
| `backend/app/api/guardrails.py` | REST API |
| `backend/app/tasks/guardrail_tasks.py` | Celery monitoring task (60s, evaluates rules) |
| `backend/app/tasks/portfolio_sync_tasks.py` | **NEW** — daily 9:00 AM sync + on-demand |
| `backend/app/api/portfolio_chat.py` | REST API + SSE endpoint (reads Redis cache) |
| `src/pages/Guardrails.tsx` | Frontend page |
| `src/pages/PortfolioChat.tsx` | Frontend page |

### Modified Files
| File | Change |
|------|--------|
| `backend/app/models/__init__.py` | Add GuardrailRule import + __all__ |
| `backend/app/main.py` | Register guardrails + portfolio_chat routers |
| `backend/app/core/celery_app.py` | Add guardrail_tasks + portfolio_sync_tasks to include, beat schedule, routes |
| `backend/app/services/zerodha_service.py` | Add `get_mf_holdings()` |
| `backend/app/api/webhooks.py` | Add `sync_portfolio_for_account.delay()` on CNC order execution |
| `src/App.tsx` | Add /guardrails + /portfolio-chat routes |
| `src/components/Layout.tsx` | Add nav items for both pages |

---

## Implementation Order

**Step 1 (Foundation):** DB migration + SQLAlchemy model for guardrail_rules
**Step 2 (Backend API):** guardrails.py REST endpoints
**Step 3 (Monitoring):** guardrail_tasks.py Celery task + celery_app.py registration
**Step 4 (Portfolio backend):** portfolio_chat.py + zerodha_service additions
**Step 5 (Frontend):** Guardrails.tsx page
**Step 6 (Frontend):** PortfolioChat.tsx page
**Step 7 (Wiring):** App.tsx routes + Layout.tsx nav + main.py registrations

---

## Open Questions (for user review)

**Q1 (Guardrails):** After a rule triggers, should it:
  (A) Stay as `triggered` and NEVER fire again that day, OR
  (B) Re-arm after N minutes and can fire again if condition persists?
  *Current plan: (A) — fire once, done. Change if needed.*

**Q2 (Guardrails):** For `loss_range_time` — does the clock reset if the position briefly goes positive, or is it cumulative time in loss?
  *Current plan: clock resets when position turns positive — continuous loss duration only.*

**Q3 (Portfolio Chat):** Should chat history persist across sessions (saved to DB) or be ephemeral (in-memory, cleared on page refresh)?
  *Current plan: ephemeral — simpler, no DB table needed.*

**Q4 (Portfolio Chat):** Should the snapshot auto-refresh while the page is open (e.g., every 60s) or only load once on page open?
  *Current plan: load once on open + manual refresh button.*

---

## What Is NOT in Scope

- Trailing stop / profit lock condition (deferred — needs design clarification)
- Auto-execution of exit orders (explicitly rejected — legal risk)
- Guardian phone number guardrails (separate WhatsApp feature)
- MF NAV real-time pricing (Kite returns NAV from last business day)
- Sector data for F&O positions (only equity holdings are sector-mapped)
- Chat history persistence to DB (deferred)
