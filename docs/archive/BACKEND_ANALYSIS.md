# TradeMentor AI - Backend Analysis & Development Plan

## Executive Summary

TradeMentor AI is a **behavioral trading intelligence platform** that helps traders identify and correct destructive patterns like revenge trading, overtrading, and poor risk control. The system:

1. **Ingests broker-level data** (trades, orders, positions) from Zerodha
2. **Reconstructs true trade rounds** (buy+sell as one decision)
3. **Converts activity into behavioral signals** (pattern detection)
4. **Uses AI to learn personal behavior patterns** and adapt over time

**Philosophy**: "Mirror, not blocker" - show traders facts about their behavior, not restrictions.

---

## Part 1: Frontend Analysis

### 1.1 Current State

The frontend is a **React 18 + TypeScript + Vite** application using:
- **shadcn/ui** (Radix + Tailwind) for components
- **React Query** for server state (not fully utilized)
- **react-router-dom** for routing
- **recharts** for visualizations
- **framer-motion** for animations

### 1.2 Pages & Data Requirements

| Page | Current Data Source | Backend API Needed |
|------|--------------------|--------------------|
| Dashboard | Mostly mock data + 2 API calls | Full API integration |
| Analytics | 100% mock data | New analytics API |
| Goals | localStorage only | Persist to backend |
| Chat | Simulated responses | Real AI coach API |
| Settings | UI only, no real OAuth | Zerodha OAuth flow |
| Money Saved | Mock data | Backend calculation |

### 1.3 API Calls Currently Made by Frontend

```typescript
// 1. Fetch positions (Dashboard.tsx:92)
GET /api/positions/?broker_account_id={uuid}
Response: { positions: Position[] }

// 2. Acknowledge alert (Dashboard.tsx:130)
POST /api/risk/alerts/{alertId}/acknowledge
Response: (none expected)
```

### 1.4 Data Structures Expected by Frontend

#### Position
```typescript
interface Position {
  id: string;
  tradingsymbol: string;        // "NIFTY26FEB22000CE"
  exchange: string;             // "NFO"
  instrument_type: string;      // "OPTION"
  total_quantity: number;
  average_entry_price: number;
  average_exit_price: number | null;
  realized_pnl: number;
  unrealized_pnl: number;
  current_value: number;
  status: 'open' | 'closed';
}
```

#### Trade
```typescript
interface Trade {
  id: string;
  tradingsymbol: string;
  exchange: string;
  trade_type: 'BUY' | 'SELL';
  quantity: number;
  price: number;
  pnl: number;
  traded_at: string;  // ISO 8601
  order_id?: string;
}
```

#### Alert
```typescript
interface Alert {
  id: string;
  pattern_name: string;
  severity: 'critical' | 'high' | 'medium' | 'positive';
  timestamp: string;
  message: string;
  acknowledged?: boolean;
  why_it_matters?: string;
}
```

#### RiskState
```typescript
interface RiskState {
  risk_state: 'safe' | 'caution' | 'danger';
  status_message: string;
  active_patterns: string[];
  unrealized_pnl: number;
  ai_recommendations: string[];
  last_synced: string;
}
```

#### MoneySaved
```typescript
interface MoneySaved {
  all_time: number;
  this_week: number;
  this_month: number;
  blowups_prevented: number;
}
```

#### Analytics Data (expected from backend)
```typescript
interface PerformanceData {
  totalPnl: number;
  winRate: number;
  totalTrades: number;
  avgWin: number;
  avgLoss: number;
  profitFactor: number;
  bestDay: { date: string; pnl: number };
  worstDay: { date: string; pnl: number };
}

interface BehavioralPattern {
  id: string;
  name: string;
  type: 'danger' | 'strength';
  count: number;
  impact: string;  // "₹8,400"
  description: string;
  trend: 'up' | 'down' | 'stable';
}

interface TimeAnalysis {
  hour: string;  // "9:15"
  pnl: number;
  trades: number;
  wins: number;
  losses: number;
}

interface AIInsight {
  id: string;
  title: string;
  description: string;
  action: string;
  priority: 'high' | 'medium' | 'low';
}
```

### 1.5 Client-Side Logic (to be moved to backend)

The frontend currently runs pattern detection locally in `src/lib/patternDetector.ts`:

**Patterns Detected:**
1. **Overtrading** - 5+ trades in 30 minutes
2. **Revenge Trading** - Re-entry within 5 min after loss > ₹500
3. **Loss Aversion** - Average loss > 1.5x average win
4. **Position Sizing** - Position > 5% of capital

This should be **moved to backend** for:
- Consistent analysis across sessions
- Historical tracking
- AI learning on patterns over time

---

## Part 2: Existing Backend Analysis

### 2.1 Tech Stack (Already Set Up)
- **FastAPI** with async endpoints
- **SQLAlchemy 2.0** with async PostgreSQL (asyncpg)
- **Supabase** as database
- **Pydantic v2** for schemas
- **httpx** for async HTTP calls
- **OpenRouter** for AI (Claude/GPT)
- **Twilio** for WhatsApp alerts

### 2.2 Working API Endpoints

| Endpoint | Status | Description |
|----------|--------|-------------|
| `GET /api/zerodha/connect` | ✅ Working | Generate OAuth URL |
| `GET /api/zerodha/callback` | ✅ Working | Handle OAuth callback |
| `GET /api/zerodha/status` | ✅ Working | Connection status |
| `POST /api/zerodha/disconnect` | ✅ Working | Revoke token |
| `POST /api/trades/sync` | ✅ Working | Sync trades from Zerodha |
| `GET /api/trades/` | ✅ Working | List trades |
| `GET /api/trades/stats` | ✅ Working | Trade statistics |
| `GET /api/positions/` | ✅ Working | List positions |
| `GET /api/positions/exposure` | ✅ Working | Exposure metrics |
| `GET /api/risk/state` | ✅ Working | Current risk state |
| `GET /api/risk/alerts` | ✅ Working | Risk alerts |
| `POST /api/risk/alerts/{id}/acknowledge` | ✅ Working | Acknowledge alert |
| `GET /api/behavioral/analysis` | ✅ Working | Behavioral analysis |
| `GET /api/behavioral/patterns` | ✅ Working | Detected patterns |
| `GET /api/behavioral/trade-tags` | ✅ Working | Trade tagging |
| `GET /api/coach/insight` | ✅ Working | AI coach message |
| `GET /api/analytics/risk-score` | ✅ Working | Weekly discipline score |
| `GET /api/analytics/money-saved` | ✅ Working | Loss prevention calc |
| `POST /api/webhooks/zerodha/postback` | ✅ Working | Real-time order sync |
| `POST /api/reports/whatsapp` | ✅ Working | Send report via WhatsApp |

### 2.3 Database Models (Existing)

```
broker_accounts
├── id (UUID, PK)
├── broker_name (default "zerodha")
├── access_token (encrypted)
├── api_key
├── status (connected/disconnected)
├── guardian_name, guardian_phone
└── connected_at, last_sync_at

trades
├── id (UUID, PK)
├── broker_account_id (FK)
├── order_id, tradingsymbol, exchange
├── transaction_type, quantity, price, average_price
├── status, pnl, asset_class, instrument_type
├── order_timestamp
└── raw_payload (JSON)

positions
├── id (UUID, PK)
├── broker_account_id (FK)
├── tradingsymbol, exchange, instrument_type
├── total_quantity, average_entry_price
├── realized_pnl, status
└── first_entry_time, last_exit_time

risk_alerts
├── id (UUID, PK)
├── broker_account_id (FK)
├── pattern_type (overtrading, revenge_sizing, consecutive_loss)
├── severity (danger, caution)
├── message, details (JSONB)
├── trigger_trade_id (FK)
├── detected_at, acknowledged_at
└── created_at
```

### 2.4 Services (Existing)

| Service | Status | Description |
|---------|--------|-------------|
| `ZerodhaService` | ✅ Complete | OAuth, trades, positions, orders API |
| `TradeSyncService` | ✅ Complete | Sync orchestration with risk detection |
| `RiskDetector` | ✅ Complete | 3 real-time patterns (consecutive loss, revenge sizing, overtrading burst) |
| `BehavioralAnalysisService` | ✅ Complete | 11 behavioral patterns with scoring |
| `AIService` | ✅ Complete | Trading persona, coach insights, reports |
| `AlertService` | ✅ Complete | WhatsApp alerts via Twilio |
| `AnalyticsService` | ✅ Complete | Risk score, money saved calculations |

### 2.5 Known Issues in Backend

1. **P&L Calculation**: Most trades have `pnl: 0.0` - Zerodha doesn't provide P&L in orders API
2. **Position Sync Bug**: `trade_sync_service.py:188` references fields not in Position model
3. **Hardcoded Phone**: WhatsApp alerts use hardcoded phone number
4. **No User Auth**: Basic user schema exists but no auth endpoints
5. **Emotional Exit Pattern**: Stubbed (needs entry/exit linkage)

---

## Part 3: Gap Analysis

### 3.1 Frontend Expects But Backend Missing

| Feature | Frontend Expects | Backend Status |
|---------|-----------------|----------------|
| Real trades list | `GET /api/trades/` with closed trades | ✅ Exists but needs filtering |
| Today's closed trades | Trades with `pnl` for last 24h | ⚠️ P&L often 0 |
| Risk state for dashboard | Full `RiskState` object | ⚠️ Partial match |
| Money saved calculation | `MoneySaved` object | ✅ Exists |
| Performance analytics | `PerformanceData` | ❌ Need new endpoint |
| Hourly P&L breakdown | `TimeAnalysis[]` | ⚠️ Partial in behavioral |
| AI insights list | `AIInsight[]` | ❌ Need new endpoint |
| Settings OAuth flow | Real Zerodha connect/callback | ✅ Exists (not wired) |
| Goals persistence | Backend storage for goals | ❌ Need new tables/APIs |
| Chat AI responses | Real AI coach conversation | ⚠️ Single insight exists |

### 3.2 Critical Gaps to Address

#### Gap 1: P&L Calculation
**Problem**: Zerodha orders API doesn't include P&L
**Solution**: Calculate P&L by matching buy/sell pairs:
```python
# Match trades by tradingsymbol within same day
# P&L = (sell_price - buy_price) * quantity for long
# P&L = (sell_price - buy_price) * quantity * -1 for short
```

#### Gap 2: Trade Rounds Reconstruction
**Problem**: Raw orders don't show trade decisions
**Solution**: Create `trade_rounds` table:
```python
trade_rounds
├── id (UUID)
├── broker_account_id (FK)
├── tradingsymbol
├── entry_order_id (FK → trades)
├── exit_order_id (FK → trades)
├── entry_price, exit_price
├── quantity
├── direction (long/short)
├── pnl (calculated)
├── duration_minutes
├── entry_time, exit_time
├── behavioral_tags (ARRAY)
└── created_at
```

#### Gap 3: Goals Persistence
**Problem**: Goals only in localStorage
**Solution**: Create `trading_goals` table:
```python
trading_goals
├── id (UUID)
├── broker_account_id (FK)
├── max_risk_per_trade_percent
├── max_daily_loss
├── max_trades_per_day
├── require_stoploss
├── min_time_between_trades_minutes
├── max_position_size_percent
├── allowed_trading_start, allowed_trading_end
├── starting_capital, current_capital
└── created_at, updated_at

goal_commitment_log
├── id (UUID)
├── goals_id (FK)
├── type (goal_set, goal_modified, goal_broken, streak_milestone)
├── description
├── previous_value, new_value, reason
├── cost (for breaks)
└── timestamp
```

#### Gap 4: Chat Conversation API
**Problem**: Frontend uses simulated responses
**Solution**: Create conversation endpoint:
```python
POST /api/coach/chat
Request: { message: string, conversation_history: Message[] }
Response: { message: string, insights: string[] }
```

#### Gap 5: Comprehensive Analytics API
**Problem**: Frontend has all mock data
**Solution**: Create unified analytics endpoint:
```python
GET /api/analytics/dashboard?broker_account_id={id}&period=7d
Response: {
  performance: PerformanceData,
  behavioral_patterns: BehavioralPattern[],
  time_analysis: TimeAnalysis[],
  ai_insights: AIInsight[],
  profit_curve: { date: string, cumulative_pnl: number }[]
}
```

---

## Part 4: Recommended Backend Architecture

### 4.1 New API Endpoints Needed

```
# Analytics (new consolidated endpoint)
GET  /api/analytics/dashboard?broker_account_id&period

# Goals Management
GET  /api/goals/?broker_account_id
POST /api/goals/
PUT  /api/goals/{id}
GET  /api/goals/{id}/adherence
GET  /api/goals/{id}/commitment-log
GET  /api/goals/{id}/streak

# Chat/Conversation
POST /api/coach/chat
GET  /api/coach/history?broker_account_id&limit

# Trade Rounds
GET  /api/trade-rounds/?broker_account_id&status&from&to
GET  /api/trade-rounds/{id}

# Sync trigger for frontend
POST /api/sync/trigger?broker_account_id
```

### 4.2 New Database Tables

```sql
-- Trade rounds (buy+sell pairs)
CREATE TABLE trade_rounds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID REFERENCES broker_accounts(id),
    tradingsymbol VARCHAR(50) NOT NULL,
    exchange VARCHAR(10) NOT NULL,
    direction VARCHAR(10) NOT NULL, -- 'long' or 'short'
    entry_order_id UUID REFERENCES trades(id),
    exit_order_id UUID REFERENCES trades(id),
    entry_price DECIMAL(12,2),
    exit_price DECIMAL(12,2),
    quantity INTEGER,
    pnl DECIMAL(12,2),
    duration_minutes INTEGER,
    entry_time TIMESTAMP WITH TIME ZONE,
    exit_time TIMESTAMP WITH TIME ZONE,
    behavioral_tags TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Trading goals
CREATE TABLE trading_goals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID REFERENCES broker_accounts(id) UNIQUE,
    max_risk_per_trade_percent DECIMAL(5,2) DEFAULT 2.0,
    max_daily_loss DECIMAL(12,2) DEFAULT 5000,
    max_trades_per_day INTEGER DEFAULT 10,
    require_stoploss BOOLEAN DEFAULT true,
    min_time_between_trades_minutes INTEGER DEFAULT 5,
    max_position_size_percent DECIMAL(5,2) DEFAULT 5.0,
    allowed_trading_start TIME DEFAULT '09:15',
    allowed_trading_end TIME DEFAULT '15:30',
    starting_capital DECIMAL(12,2) DEFAULT 100000,
    current_capital DECIMAL(12,2) DEFAULT 100000,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Goal commitment log
CREATE TABLE goal_commitment_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    goals_id UUID REFERENCES trading_goals(id),
    log_type VARCHAR(20) NOT NULL, -- goal_set, goal_modified, goal_broken, streak_milestone
    description TEXT,
    previous_value TEXT,
    new_value TEXT,
    reason TEXT,
    pattern_type VARCHAR(50),
    cost DECIMAL(12,2),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Chat history
CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID REFERENCES broker_accounts(id),
    role VARCHAR(10) NOT NULL, -- 'user' or 'assistant'
    content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Daily summaries (for faster analytics)
CREATE TABLE daily_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id UUID REFERENCES broker_accounts(id),
    date DATE NOT NULL,
    total_trades INTEGER,
    winning_trades INTEGER,
    losing_trades INTEGER,
    total_pnl DECIMAL(12,2),
    max_drawdown DECIMAL(12,2),
    patterns_detected JSONB,
    goals_broken TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(broker_account_id, date)
);
```

### 4.3 New Services Needed

#### TradeRoundService
```python
class TradeRoundService:
    async def reconstruct_rounds(self, broker_account_id: UUID, date: date) -> List[TradeRound]:
        """Match buy/sell orders into trade rounds with P&L"""

    async def calculate_pnl(self, entry_order: Trade, exit_order: Trade) -> Decimal:
        """Calculate P&L from matched orders"""

    async def tag_round_behaviors(self, round: TradeRound, previous_rounds: List[TradeRound]) -> List[str]:
        """Tag trade round with behavioral patterns"""
```

#### GoalsService
```python
class GoalsService:
    async def get_or_create_goals(self, broker_account_id: UUID) -> TradingGoals:
        """Get goals or create defaults"""

    async def update_goals(self, goals_id: UUID, updates: GoalsUpdate, reason: str) -> TradingGoals:
        """Update goals and log the change"""

    async def check_adherence(self, broker_account_id: UUID, trades: List[Trade]) -> List[GoalAdherence]:
        """Check goal adherence for given trades"""

    async def calculate_streak(self, broker_account_id: UUID) -> StreakData:
        """Calculate current discipline streak"""
```

#### AnalyticsDashboardService
```python
class AnalyticsDashboardService:
    async def get_dashboard(self, broker_account_id: UUID, period_days: int) -> DashboardAnalytics:
        """Get comprehensive analytics for dashboard"""
        # Includes: performance, patterns, time analysis, AI insights

    async def get_performance_summary(self, trade_rounds: List[TradeRound]) -> PerformanceData:
        """Calculate win rate, P&L, etc."""

    async def get_hourly_analysis(self, trade_rounds: List[TradeRound]) -> List[TimeAnalysis]:
        """Break down performance by hour"""

    async def generate_ai_insights(self, analysis: BehavioralAnalysis) -> List[AIInsight]:
        """Generate actionable AI insights from patterns"""
```

#### ChatService
```python
class ChatService:
    async def chat(
        self,
        broker_account_id: UUID,
        message: str,
        history: List[ChatMessage]
    ) -> ChatResponse:
        """Process chat message with trading context"""
        # 1. Fetch recent trades, patterns, goals
        # 2. Build context for AI
        # 3. Call OpenRouter with context + message
        # 4. Save to chat_messages table
        # 5. Return response
```

### 4.4 Real-time Sync Pipeline

```
Zerodha Postback Webhook
    │
    ▼
/api/webhooks/zerodha/postback
    │
    ├─► Upsert trade to `trades` table
    │
    ├─► Check if trade completes a round
    │   └─► If yes: Create trade_round, calculate P&L
    │
    ├─► Run RiskDetector.detect_patterns()
    │   └─► Save to risk_alerts
    │
    ├─► Check goal violations
    │   └─► Log to goal_commitment_log
    │
    ├─► Update daily_summaries
    │
    └─► If DANGER pattern:
        └─► AlertService.send_risk_alert()
```

---

## Part 5: Implementation Priority

### Phase 1: Core Data Pipeline (Week 1)
1. ✅ Fix P&L calculation by creating trade rounds
2. ✅ Create `trade_rounds` table and reconstruction logic
3. ✅ Update positions to have accurate unrealized P&L
4. ✅ Wire frontend Dashboard to use real trades data

### Phase 2: Goals & Streaks (Week 2)
1. Create goals tables and API
2. Implement goal adherence checking
3. Implement streak tracking
4. Wire frontend Goals page to backend

### Phase 3: Analytics Dashboard (Week 3)
1. Create comprehensive analytics endpoint
2. Implement hourly P&L breakdown
3. Generate AI insights from patterns
4. Wire frontend Analytics page to backend

### Phase 4: AI Chat (Week 4)
1. Create chat history table
2. Implement conversation API with context
3. Wire frontend Chat page to backend
4. Add conversation memory/context

### Phase 5: Polish & Reliability (Week 5)
1. Add user authentication
2. Implement daily summary caching
3. Add error handling and retries
4. Performance optimization

---

## Part 6: Environment Setup

### Required Environment Variables
```bash
# Database (Supabase)
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=xxx

# Zerodha
ZERODHA_API_KEY=xxx
ZERODHA_API_SECRET=xxx
ZERODHA_REDIRECT_URI=http://localhost:8000/api/zerodha/callback

# AI (OpenRouter)
OPENROUTER_API_KEY=xxx

# Alerts (Twilio)
TWILIO_ACCOUNT_SID=xxx
TWILIO_AUTH_TOKEN=xxx
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886

# Security
ENCRYPTION_KEY=xxx  # Fernet key for token encryption
SECRET_KEY=xxx
```

### Running Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Database Migrations
Since using Supabase, run SQL directly in Supabase SQL Editor or use Alembic for local dev.

---

## Conclusion

The backend has a **solid foundation** with Zerodha integration, risk detection, and behavioral analysis already working. The main gaps are:

1. **P&L accuracy** - Need trade round reconstruction
2. **Goals persistence** - Currently localStorage only
3. **Analytics API** - Frontend using mock data
4. **Chat API** - Need real conversation endpoint

The recommended approach is to:
1. First fix the data pipeline (trade rounds with P&L)
2. Then wire existing APIs to frontend
3. Finally add new features (goals, chat)

This will create a **personal discipline engine** that evolves with each trader, learning their patterns and adapting thresholds based on outcomes.
