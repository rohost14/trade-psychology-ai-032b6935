# TradeMentor AI - Complete Product Documentation

> **Version:** 1.3.0-beta
> **Last Updated:** February 6, 2026
> **Status:** Development (Core Features Complete)

---

## Table of Contents

1. [Product Overview](#product-overview)
2. [Architecture](#architecture)
3. [Features - Implemented](#features---implemented)
4. [Features - Pending](#features---pending)
5. [Technical Stack](#technical-stack)
6. [API Reference](#api-reference)
7. [Pattern Detection System](#pattern-detection-system)
8. [Blowup Shield (Capital Defense)](#blowup-shield-capital-defense)
9. [Database Schema](#database-schema)
10. [Deployment Guide](#deployment-guide)
11. [Roadmap](#roadmap)

---

## Product Overview

### What is TradeMentor AI?

TradeMentor AI is a **trading psychology companion** for Indian retail F&O traders. It monitors trading behavior in real-time, detects destructive patterns (revenge trading, overtrading, loss chasing), and provides proactive intervention through notifications and guardian alerts.

### The Problem We Solve

According to [SEBI's 2024 study](https://www.sebi.gov.in/media-and-notifications/press-releases/sep-2024/updated-sebi-study-reveals-93-of-individual-traders-incurred-losses-in-equity-fando-between-fy22-and-fy24-aggregate-losses-exceed-1-8-lakh-crores-over-three-years_86906.html):

| Statistic | Value |
|-----------|-------|
| Traders who lost money (FY22-24) | **93%** |
| Total losses over 3 years | **₹1.81 lakh crore** |
| Average loss per trader | **₹2 lakh** |
| Traders under 30 years | **40%+** |
| Loss-makers who continued trading | **75%** |

**Root Cause:** Not strategy, but **psychology**. Revenge trading, FOMO, overtrading, and loss-chasing destroy accounts.

### Our Unique Position

| Competitor | Focus | Gap |
|------------|-------|-----|
| Sensibull/Opstra | Strategy building | No psychology |
| Edgewonk/TraderSync | Post-trade journaling | No real-time intervention |
| Zerodha Nudge | Generic warnings | No personalization |
| Guardian Angel Tools | Desktop blocking | No Indian broker integration |

**TradeMentor AI is the ONLY product that:**
- Integrates with Zerodha
- Detects patterns automatically
- Sends proactive notifications
- Alerts a designated guardian
- Learns personalized failure modes

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                 │
│  React + TypeScript + Vite + TailwindCSS + shadcn/ui            │
│  ┌─────────┬──────────┬────────┬─────────┬──────────┐          │
│  │Dashboard│ Analytics│ Goals  │  Chat   │ Settings │          │
│  └─────────┴──────────┴────────┴─────────┴──────────┘          │
│                           │                                      │
│                    REST API / WebSocket                          │
└───────────────────────────┼─────────────────────────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────────────┐
│                         BACKEND                                  │
│  FastAPI + SQLAlchemy + Celery                                  │
│  ┌─────────────────────────────────────────────────┐            │
│  │                  API Layer                       │            │
│  │  /zerodha  /trades  /risk  /coach  /analytics   │            │
│  └─────────────────────────────────────────────────┘            │
│                           │                                      │
│  ┌─────────────────────────────────────────────────┐            │
│  │              Service Layer                       │            │
│  │  RiskDetector │ BehavioralAnalysis │ AIService  │            │
│  └─────────────────────────────────────────────────┘            │
│                           │                                      │
│  ┌─────────────────────────────────────────────────┐            │
│  │              Data Layer                          │            │
│  │  PostgreSQL (Supabase) │ Redis (Upstash)        │            │
│  └─────────────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────────────┐
│                    EXTERNAL SERVICES                             │
│  ┌──────────┬────────────┬────────────┬─────────────┐          │
│  │ Zerodha  │ OpenRouter │   Twilio   │   Upstash   │          │
│  │ KiteAPI  │    LLMs    │  WhatsApp  │    Redis    │          │
│  └──────────┴────────────┴────────────┴─────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Zerodha Postback Webhook
         │
         ▼
   /webhooks/zerodha/postback
         │
         ▼
   ┌─────────────────┐
   │ Verify Checksum │
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │ Queue to Celery │ ──► Redis Broker
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │ Process Trade   │
   │ - Classify      │
   │ - Transform     │
   │ - Save to DB    │
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐
   │ Risk Detection  │
   │ - Loss Spiral   │
   │ - Revenge Size  │
   │ - Overtrading   │
   └────────┬────────┘
            │
            ▼
   ┌─────────────────┐       ┌─────────────────┐
   │ Create Alert    │──────►│ Send WhatsApp   │
   │ (if DANGER)     │       │ to Guardian     │
   └─────────────────┘       └─────────────────┘
```

---

## Features - Implemented

### 1. Zerodha Integration ✅

**Status:** WORKING

| Feature | Endpoint | Description |
|---------|----------|-------------|
| OAuth Flow | `GET /api/zerodha/connect` | Generate login URL |
| Callback | `GET /api/zerodha/callback` | Handle OAuth redirect |
| Disconnect | `POST /api/zerodha/disconnect` | Revoke token |
| Status Check | `GET /api/zerodha/status` | Connection status |
| Trade Sync | `POST /api/trades/sync` | Pull orders/positions |

**Implementation:**
- Token encryption using Fernet
- Auto-sync after successful OAuth
- Support for multiple broker accounts

### 2. Real-Time Trade Processing ✅

**Status:** WORKING (requires Zerodha postback configuration)

| Feature | Description |
|---------|-------------|
| Webhook Receiver | `/api/webhooks/zerodha/postback` |
| Checksum Verification | SHA256 signature validation |
| Async Processing | Celery task queue |
| Sync Fallback | For development without Celery |

**Trade Classification:**
```python
Asset Classes: EQUITY, FNO, COMMODITY, CURRENCY
Instrument Types: SPOT, FUTURE, OPTION
Product Types: CNC, MIS, NRML
```

### 3. Risk Detection Engine ✅

**Status:** WORKING (limited by P&L calculation - see Pending)

#### Backend Patterns (Real-time)

| Pattern | Severity | Trigger |
|---------|----------|---------|
| Consecutive Loss | CAUTION | 3-4 losses in a row |
| Consecutive Loss | DANGER | 5+ losses in a row |
| Revenge Sizing | DANGER | >1.5x size within 15 min of loss |
| Overtrading | CAUTION | 5-6 trades in 15 min |
| Overtrading | DANGER | 7+ trades in 15 min |

#### Behavioral Analysis Patterns (30-day window)

| Pattern | Severity | Detection Logic |
|---------|----------|-----------------|
| **PRIMARY BIASES** | | |
| Revenge Trading | HIGH | Trade within 15 min after loss |
| No Cooldown | HIGH/CRITICAL | Trade within 5 min of loss |
| After-Profit Overconfidence | MEDIUM | Size increase after wins |
| Recency Bias | MEDIUM | Same direction/symbol after wins |
| Loss Normalization | HIGH | Many small losses, negative expectancy |
| Strategy Drift | MEDIUM | Behavior changes mid-session |
| Hope & Denial | HIGH | Avg loss >> avg win |
| **BEHAVIORAL PATTERNS** | | |
| Overtrading | HIGH | >10 trades/day or 5+/hour |
| Martingale | CRITICAL | Position doubled after loss |
| Inconsistent Sizing | MEDIUM | High variance in position sizes |
| Time-of-Day Risk | MEDIUM | Low win rate in specific hours |
| Emotional Exit | MEDIUM | Winners cut early, losers held long |
| Chop Zone Addiction | MEDIUM | Directionless trading, many direction changes |
| **COMPOUND STATES** | | |
| Tilt/Loss Spiral | CRITICAL | 4+ consecutive losses |
| False Recovery Chase | CRITICAL | Larger/faster trades during drawdown |
| Emotional Looping | CRITICAL | Repeating give-back-gains pattern |
| **POSITIVE** | | |
| Stop Loss Discipline | POSITIVE | Max loss < 2.5x avg loss |

### 4. AI Coach ✅

**Status:** WORKING

| Feature | Endpoint | Model |
|---------|----------|-------|
| Real-time Insight | `GET /api/coach/insight` | claude-3.5-haiku |
| Chat Conversation | `POST /api/coach/chat` | claude-3.5-haiku |
| Trading Persona | Generated in analysis | gpt-4o-mini |
| WhatsApp Reports | `POST /api/reports/whatsapp` | claude-3.5-haiku |

**AI Personas (6 classifications):**
1. The Tilted Gambler
2. The Recovery Chaser
3. The Compulsive Scalper
4. The Impulsive Scalper
5. The Death by Cuts Trader
6. The Developing Trader

### 5. Guardian Alert System ✅

**Status:** WORKING

| Feature | Description |
|---------|-------------|
| Guardian Setup | `POST /api/settings/guardian` |
| User Alerts | WhatsApp to trader |
| Guardian Alerts | WhatsApp to designated contact |
| Pattern-specific Messages | Custom per pattern type |

**Alert Triggers:**
- DANGER severity patterns only
- Sent via Twilio WhatsApp API

### 6. Goals & Streak Tracking ✅

**Status:** WORKING

| Feature | Endpoint | Description |
|---------|----------|-------------|
| Get Goals | `GET /api/goals/` | Full goals + log + streak |
| Update Goals | `PUT /api/goals/` | Modify risk limits |
| Log Broken | `POST /api/goals/log-broken` | Record goal violation |
| Streak Update | `POST /api/goals/streak/increment` | Daily check-in |

**Goal Parameters:**
```typescript
{
  max_risk_per_trade_percent: 2,      // Max 2% per trade
  max_daily_loss: 5000,               // Max ₹5000/day
  max_trades_per_day: 10,             // Max 10 trades
  require_stoploss: true,             // Mandatory SL
  min_time_between_trades_minutes: 5, // Cooldown
  max_position_size_percent: 5,       // Max 5% of capital
  allowed_trading_start: "09:15",
  allowed_trading_end: "15:30",
  primary_segment: "EQUITY"           // or FNO, COMMODITY, CURRENCY
}
```

**Streak Milestones:**
- 7-day streak
- 2-week streak
- Monthly streak
- 60-day streak

**Review Window:** 1st-3rd of each month (goals can only be modified then)

### 7. Analytics & Money Saved ✅

**Status:** WORKING (needs enhancement - see Pending)

| Feature | Endpoint | Description |
|---------|----------|-------------|
| Risk Score | `GET /api/analytics/risk-score` | 0-10 discipline score |
| Money Saved | `GET /api/analytics/money-saved` | Estimated losses prevented |
| Interventions | `GET /api/analytics/interventions` | Detailed intervention history |
| Dashboard Stats | `GET /api/analytics/dashboard-stats` | Combined metrics |

**Current Money Saved Formula:**
```python
# Conservative estimate:
trades_prevented_per_alert = 3
avg_loss_per_trade = 1000  # ₹1,000
loss_prevented = danger_alert_count × 3000
```

### 8. WebSocket Price Streaming ✅

**Status:** IMPLEMENTED (needs Kite Ticker integration)

| Feature | Description |
|---------|-------------|
| Connection | `ws://host/api/ws/prices?token=JWT` |
| Subscribe | `{"action": "subscribe", "instruments": [...]}` |
| Unsubscribe | `{"action": "unsubscribe", "instruments": [...]}` |
| Position Subscribe | `{"action": "subscribe_positions"}` |

### 9. Market Hours Support ✅

**Status:** WORKING

| Segment | Open | Close |
|---------|------|-------|
| EQUITY | 9:15 AM | 3:30 PM |
| FNO | 9:15 AM | 3:30 PM |
| COMMODITY | 9:00 AM | 11:30 PM |
| CURRENCY | 9:00 AM | 5:00 PM |

**High-Risk Windows Detected:**
- Market Open Volatility (9:15-9:30)
- Market Close Rush (3:00-3:30)
- Expiry Day patterns

### 10. Frontend Dashboard ✅

**Status:** WORKING

| Component | Description |
|-----------|-------------|
| Risk Guardian Card | Current risk state + sync button |
| Open Positions Table | Live positions with P&L |
| Closed Trades Table | Recent completed trades |
| Recent Alerts Card | Pattern alerts with acknowledge |
| Money Saved Card | Intervention summary |
| Trade Journal Sheet | Notes modal |

---

## Features - Pending

### Recently Implemented ✅

#### 1. P&L Calculation from Trade Pairs ✅

**Problem:** `pnl` field defaults to 0, breaking all loss-based pattern detection.

**Solution:** FIFO (First In, First Out) BUY/SELL matching implemented in `pnl_calculator.py`

**Location:** `backend/app/services/pnl_calculator.py`

**Integration Points:**
- `trade_sync_service.py` - Calculates P&L after sync
- `trade_tasks.py` - Real-time P&L on webhook SELL trades
- `POST /api/analytics/recalculate-pnl` - Manual trigger

**Status:** ✅ IMPLEMENTED

#### 2. Blowup Shield Rebrand ✅

**Old:** "Money Saved" (weak, passive)

**New:** "Blowup Shield" with:
- Capital Defended stats
- Near-misses counter
- Protection history with confidence levels
- Active shield animation on recent activity

**Files Changed:**
- `MoneySaved.tsx` → `BlowupShield.tsx`
- `MoneySavedCard.tsx` → `BlowupShieldCard.tsx`
- Route: `/money-saved` → `/blowup-shield`

**Status:** ✅ IMPLEMENTED

---

#### 3. Pre-Trade Intervention Check ✅

**Problem:** We detect patterns AFTER trades happen.

**Solution:** API endpoint called before placing trades.

**Files Created:**
- `backend/app/api/cooldown.py` - Pre-trade check endpoint

```python
POST /api/cooldown/pre-trade-check
{
  "broker_account_id": "uuid",
  "symbol": "NIFTY24FEB22000CE",
  "quantity": 100,
  "direction": "BUY"
}

Response:
{
  "action": "allow",  // allow | warn | cooldown
  "reasons": ["revenge_pattern_detected"],
  "recommendations": ["Consider waiting 15 minutes before trading"],
  "active_cooldown": { ... },
  "recent_alerts": [ ... ]
}
```

**Detection Logic:**
- Checks for active cooldowns (returns `cooldown` action)
- Analyzes recent DANGER/CAUTION alerts (returns `warn` if recent)
- Checks trade frequency (warns if 3+ trades in last 15 min)
- Checks consecutive losses (warns if 2+ recent losses)
- Checks user-defined daily limits (trade limit, loss limit)

**Status:** ✅ IMPLEMENTED

#### 4. User Profiles & Onboarding System ✅

**Implementation:** 5-step onboarding wizard with adaptive user experience

**Files Created:**
- `backend/app/models/user_profile.py` - User profile model
- `backend/app/api/profile.py` - Profile and onboarding API
- `backend/migrations/006_user_profiles.sql` - DB migration
- `src/components/onboarding/OnboardingWizard.tsx` - 5-step wizard UI
- `src/hooks/useOnboarding.ts` - Onboarding state management

**Onboarding Steps:**
1. **Basic Info** - Name, trading since year
2. **Trading Style Quiz** - Experience level, trading style, risk tolerance
3. **Preferences** - Preferred instruments, market segments
4. **Risk Management** - Daily limits, cooldown duration, known weaknesses
5. **AI & Notifications** - AI persona preference, notification settings

**User Profile Fields:**
- `experience_level`: beginner | intermediate | experienced | professional
- `trading_style`: scalper | intraday | swing | positional | mixed
- `risk_tolerance`: conservative | moderate | aggressive
- `preferred_instruments`: NIFTY, BANKNIFTY, stocks, etc.
- `preferred_segments`: equity, fno, commodity, currency
- `daily_loss_limit`: Maximum daily loss threshold
- `daily_trade_limit`: Maximum trades per day
- `cooldown_after_loss`: Cooldown minutes after losing trade
- `known_weaknesses`: Self-identified patterns (revenge trading, FOMO, etc.)
- `ai_persona`: coach | mentor | friend | strict

**API Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/profile/` | Get profile + check if onboarding needed |
| PUT | `/api/profile/` | Update profile |
| POST | `/api/profile/onboarding/step/{n}` | Save specific step |
| POST | `/api/profile/onboarding/skip` | Skip onboarding |
| POST | `/api/profile/detect-style` | Auto-detect from trade history |

**Status:** ✅ IMPLEMENTED

#### 5. Cooldown System ✅

**Implementation:** Automatic and manual cooling-off periods after risky behavior

**Files Created:**
- `backend/app/models/cooldown.py` - Cooldown model
- `backend/app/api/cooldown.py` - Cooldown management API
- `backend/migrations/007_cooldowns.sql` - DB migration

**Cooldown Triggers:**
- `revenge_pattern` - Auto-triggered on revenge trading detection
- `loss_limit` - Auto-triggered when daily loss limit exceeded
- `consecutive_loss` - Auto-triggered after 3+ consecutive losses
- `overtrading` - Auto-triggered when trade frequency is excessive
- `fomo` - Auto-triggered on FOMO pattern detection
- `tilt` - Auto-triggered on tilt/loss spiral detection
- `manual` - User-initiated cooldown

**Features:**
- Configurable duration (default from user profile)
- Optional skip with acknowledgment (trader accountability)
- History tracking for pattern analysis
- Integration with pre-trade check API

**API Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/cooldown/active` | Get currently active cooldown |
| GET | `/api/cooldown/history` | List past cooldowns |
| POST | `/api/cooldown/start` | Start manual cooldown |
| POST | `/api/cooldown/{id}/skip` | Skip cooldown (requires acknowledgment) |
| POST | `/api/cooldown/{id}/acknowledge` | Acknowledge cooldown |
| POST | `/api/cooldown/pre-trade-check` | Pre-trade intervention check |

**Status:** ✅ IMPLEMENTED

#### 6. FOMO Pattern Detection ✅

**Implementation:** Detects fear-of-missing-out trading patterns

**Location:** `backend/app/services/risk_detector.py`

**Detection Logic:**
```python
# Pattern 1: Market Open Rush
# Trading in first 5 minutes (9:15-9:20)
if trade in first 5 min of market open:
    if multiple trades in this window:
        severity = DANGER
    else:
        severity = CAUTION

# Pattern 2: Chasing Behavior
# Multiple same-direction trades within 10 minutes
if 3+ same-direction trades in 10 min on same symbol:
    severity = DANGER (chasing a move)
```

**Triggers:**
- Auto-triggers cooldown when DANGER severity detected
- Sends push notification + WhatsApp alert

**Status:** ✅ IMPLEMENTED

#### 7. Tilt/Loss Spiral Detection (Enhanced) ✅

**Implementation:** Detects escalating position sizes while losing

**Location:** `backend/app/services/risk_detector.py`

**Detection Logic:**
```python
# Look at last 5 closed trades
# Check for pattern: losing + increasing size
for recent_trades:
    if trade.pnl < 0 and trade.quantity > previous.quantity:
        tilt_score += 1

if tilt_score >= 2:
    severity = DANGER (increasing size while losing)
```

**Triggers:**
- Auto-triggers cooldown when detected
- Sends push notification + WhatsApp alert to user and guardian

**Status:** ✅ IMPLEMENTED

#### 8. AI Personalization Service ✅

**Implementation:** Learns individual trader patterns for personalized intervention

**Files Created:**
- `backend/app/services/ai_personalization_service.py` - Pattern learning engine
- `backend/app/api/personalization.py` - API endpoints

**Features:**

**1. Personal Time Pattern Learning**
- Analyzes win rate by hour of day
- Identifies YOUR specific danger hours (e.g., "10:00 is your worst hour")
- Identifies YOUR best hours
- Analyzes day-of-week performance (e.g., "Thursday is your worst day")

**2. Symbol-specific Weakness Detection**
- Tracks P&L by trading symbol
- Identifies problem symbols (low win rate)
- Identifies strong symbols (high win rate)
- Normalizes symbols (NIFTY24FEB22000CE → NIFTY)

**3. Predictive Alerts**
- Warns BEFORE entering your danger window
- Symbol warnings when attempting to trade problem symbols
- Integrated into pre-trade check API

**4. AI-based Intervention Timing**
- Learns your typical revenge trading window
- Analyzes cooldown outcomes (skip vs complete)
- Recommends optimal cooldown duration for YOU

**Example Insights:**
```json
{
  "insights": [
    {"type": "danger_time", "title": "Your Danger Hour", "value": "10:00", "detail": "28% win rate"},
    {"type": "problem_symbol", "title": "Avoid This", "value": "BANKNIFTY", "detail": "32% win rate"},
    {"type": "revenge_window", "title": "Your Revenge Window", "value": "8 min", "detail": "Set cooldown to 12+ min"}
  ]
}
```

**Status:** ✅ IMPLEMENTED

#### 9. Automated Daily Reports ✅

**Implementation:** Bring value TO the trader without requiring them to open the app.

**Files Created:**
- `backend/app/services/daily_reports_service.py` - Report generation
- `backend/app/services/pattern_prediction_service.py` - Real-time predictions

**A. Post-Market Report (4:00 PM)**
```json
{
  "summary": { "trades": 7, "win_rate": 43, "pnl": -2340 },
  "patterns_detected": [
    { "pattern": "revenge_trading", "severity": "danger", "time": "11:23" }
  ],
  "emotional_journey": {
    "timeline": [
      { "time": "09:30", "pnl": 500, "mood": "confident", "emoji": "😊" },
      { "time": "11:23", "pnl": -1200, "mood": "frustrated", "emoji": "😤" }
    ]
  },
  "key_lessons": [
    { "lesson": "You traded 3 times within 5 min of losses. A cooldown could have saved ~₹2,400", "type": "actionable" }
  ],
  "tomorrow_focus": {
    "primary": "No revenge trades tomorrow",
    "rule": "After any loss, set a 15-minute timer"
  }
}
```

**B. Morning Readiness Briefing (8:45 AM)**
```json
{
  "readiness_score": { "score": 65, "status": "caution", "message": "Trade carefully today" },
  "day_warning": { "day": "Thursday", "win_rate": 38, "message": "⚠️ Thursday is your WORST day" },
  "watch_outs": [
    { "type": "time", "icon": "⏰", "message": "Avoid trading at 10:00 (your 28% win rate hour)" },
    { "type": "symbol", "icon": "🚫", "message": "Consider avoiding BANKNIFTY (32% win rate)" }
  ],
  "checklist": [
    { "item": "I have reviewed my trading plan", "category": "preparation" },
    { "item": "I commit to NO revenge trades today", "category": "personal" }
  ],
  "commitment_prompt": "What is your ONE rule for today?"
}
```

**C. Pattern Prediction Engine (Real-time)**
```json
{
  "current_state": {
    "consecutive_losses": 2,
    "session_pnl": -3500,
    "trades_today": 6,
    "minutes_since_last_trade": 8
  },
  "predictions": {
    "revenge_trading": { "probability": 78, "severity": "high" },
    "tilt_loss_spiral": { "probability": 45, "severity": "critical" },
    "overtrading": { "probability": 52, "severity": "medium" }
  },
  "risk_assessment": {
    "overall_risk": "high",
    "risk_score": 78,
    "action": "take_break",
    "message": "⚠️ HIGH RISK. 78% chance of revenge trading. Take a 15-minute break."
  },
  "recommendations": [
    { "action": "Take a 15-minute break", "specific": "Set a timer. Your typical revenge window is 8 min." }
  ]
}
```

**Status:** ✅ IMPLEMENTED

### High Priority

#### 3. Trade Journal Backend ✅

**Implementation:** REST API with localStorage fallback

**Files Created:**
- `backend/app/models/journal_entry.py` - Database model with emotion tags
- `backend/app/api/journal.py` - Full CRUD API endpoints
- `backend/migrations/005_journal_entries.sql` - DB migration

**Frontend Updated:**
- `src/components/dashboard/TradeJournalSheet.tsx` - Now uses API with offline fallback

**Features:**
- Save notes, emotions, lessons per trade
- Quick emotion tag selection (Confident, Anxious, FOMO, etc.)
- Offline support with localStorage fallback
- Auto-sync indicator (cloud/offline status)
- Emotion analytics endpoint for correlation analysis

**API Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/journal/` | List all entries |
| GET | `/api/journal/trade/{id}` | Get entry for trade |
| POST | `/api/journal/` | Create/update entry |
| DELETE | `/api/journal/trade/{id}` | Delete by trade |
| GET | `/api/journal/stats/emotions` | Emotion-P&L correlation |

**Status:** ✅ IMPLEMENTED

#### 4. Desktop/Mobile Push Notifications ✅

**Implementation:** Web Push API with VAPID authentication

**Files Created:**
- `public/sw.js` - Service Worker for handling push events
- `src/lib/pushNotifications.ts` - Frontend subscription manager
- `src/components/settings/NotificationSettings.tsx` - Settings UI
- `backend/app/services/push_notification_service.py` - Backend push sender
- `backend/app/api/notifications.py` - API endpoints
- `backend/app/models/push_subscription.py` - Database model
- `backend/migrations/004_push_subscriptions.sql` - DB migration

**Features:**
- Permission request flow in Settings page
- Automatic notification on DANGER patterns
- Action buttons in notifications ("View Details", "Take a Break")
- Test notification button
- Multi-device support (subscribe on desktop + mobile)
- Auto-deactivation after 3 failed deliveries

**Integration:**
- `trade_tasks.py` - Sends push + WhatsApp when danger alert triggers
- Requires VAPID keys in `.env`: `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`

**Status:** ✅ IMPLEMENTED

### Medium Priority

#### 7. Entry/Exit Trade Linkage 🟡

**Problem:** Can't calculate hold duration or round-trip P&L.

**Solution:** Create `TradeLink` table matching BUY with SELL.

**Status:** NOT IMPLEMENTED

#### 8. Journal Entries ✅

**Status:** FULLY IMPLEMENTED (see section above for details)

**Features:**
- Full CRUD API (`/api/journal/`)
- Emotion tag tracking
- Offline support with localStorage fallback
- Emotion-P&L correlation analytics

#### 9. AI Personalization 🟡

**Goal:** Learn each trader's unique patterns.

**Examples:**
- "YOUR revenge window is 12 minutes"
- "YOU lose 40% more after 2 PM"
- "YOUR worst day is Thursday (expiry)"

**Status:** NOT IMPLEMENTED

### Lower Priority

#### 10. Accountability Partner Matching 🟢

**Future:** Match traders with accountability buddies.

**Status:** NOT PLANNED YET

#### 11. Community Stats 🟢

**Future:** Anonymous comparisons ("93% of traders with your pattern lost money").

**Status:** NOT PLANNED YET

---

## Technical Stack

### Backend

| Component | Technology | Version |
|-----------|------------|---------|
| Framework | FastAPI | 0.109+ |
| ORM | SQLAlchemy | 2.0+ |
| Database | PostgreSQL (Supabase) | 14+ |
| Cache/Queue | Redis (Upstash) | 7+ |
| Task Queue | Celery | 5.3+ |
| AI/LLM | OpenRouter API | - |
| WhatsApp | Twilio | 8.10+ |
| Broker | Zerodha KiteConnect | 5.0+ |

### Frontend

| Component | Technology | Version |
|-----------|------------|---------|
| Framework | React | 18+ |
| Language | TypeScript | 5+ |
| Build | Vite | 5+ |
| Styling | TailwindCSS | 3+ |
| Components | shadcn/ui | - |
| Animation | Framer Motion | 10+ |
| State | React Context | - |
| Charts | Recharts | 2+ |

### Infrastructure

| Component | Service |
|-----------|---------|
| Database | Supabase (PostgreSQL) |
| Redis | Upstash |
| Hosting | TBD (Vercel/Railway/Render) |
| Domain | TBD |

---

## API Reference

### Authentication

Currently using broker_account_id passed as query parameter. JWT auth exists but not enforced.

### Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| **Zerodha** | | |
| GET | `/api/zerodha/connect` | OAuth login URL |
| GET | `/api/zerodha/callback` | OAuth callback |
| GET | `/api/zerodha/status` | Connection status |
| POST | `/api/zerodha/disconnect` | Disconnect broker |
| GET | `/api/zerodha/accounts` | List accounts |
| **Trades** | | |
| POST | `/api/trades/sync` | Sync from broker |
| GET | `/api/trades/` | List trades |
| GET | `/api/trades/stats` | Trade statistics |
| GET | `/api/trades/{id}` | Single trade |
| **Positions** | | |
| GET | `/api/positions/` | Open positions |
| GET | `/api/positions/exposure` | Risk metrics |
| **Risk** | | |
| GET | `/api/risk/state` | Current risk state |
| GET | `/api/risk/alerts` | Alert history |
| POST | `/api/risk/alerts/{id}/acknowledge` | Acknowledge alert |
| **Analytics** | | |
| GET | `/api/analytics/risk-score` | Discipline score |
| GET | `/api/analytics/money-saved` | Capital defended stats |
| GET | `/api/analytics/interventions` | Intervention history |
| POST | `/api/analytics/recalculate-pnl` | Recalculate P&L (FIFO) |
| GET | `/api/analytics/unrealized-pnl` | Open position P&L |
| **Coach** | | |
| GET | `/api/coach/insight` | Real-time insight |
| POST | `/api/coach/chat` | Chat with AI |
| **Goals** | | |
| GET | `/api/goals/` | Full goals data |
| PUT | `/api/goals/` | Update goals |
| POST | `/api/goals/log-broken` | Log violation |
| POST | `/api/goals/streak/increment` | Update streak |
| **Behavioral** | | |
| GET | `/api/behavioral/analysis` | Full analysis |
| GET | `/api/behavioral/patterns` | Detected patterns |
| GET | `/api/behavioral/trade-tags` | Trade labels |
| **Webhooks** | | |
| POST | `/api/webhooks/zerodha/postback` | Trade webhook |
| **Settings** | | |
| POST | `/api/settings/guardian` | Update guardian |
| **Reports** | | |
| POST | `/api/reports/whatsapp` | Send report |
| **Journal** | | |
| GET | `/api/journal/` | List journal entries |
| GET | `/api/journal/trade/{id}` | Get entry for trade |
| POST | `/api/journal/` | Create/update entry |
| PUT | `/api/journal/{id}` | Update entry |
| DELETE | `/api/journal/{id}` | Delete entry |
| DELETE | `/api/journal/trade/{id}` | Delete by trade |
| GET | `/api/journal/stats/emotions` | Emotion analytics |
| **Notifications** | | |
| POST | `/api/notifications/subscribe` | Subscribe to push |
| POST | `/api/notifications/unsubscribe` | Unsubscribe |
| POST | `/api/notifications/test` | Send test notification |
| GET | `/api/notifications/status` | Subscription status |
| **Daily Reports** | | |
| GET | `/api/reports/post-market` | Post-market day report |
| GET | `/api/reports/morning-briefing` | Morning readiness briefing |
| GET | `/api/reports/predictions` | Real-time pattern predictions |
| POST | `/api/reports/predictions/simulate` | Simulate predictions |
| GET | `/api/reports/weekly-summary` | Weekly psychology summary |
| **Profile & Onboarding** | | |
| GET | `/api/profile/` | Get profile + onboarding status |
| PUT | `/api/profile/` | Update profile |
| POST | `/api/profile/onboarding/step/{n}` | Save onboarding step |
| POST | `/api/profile/onboarding/skip` | Skip onboarding |
| POST | `/api/profile/detect-style` | Auto-detect trading style |
| **Cooldowns** | | |
| GET | `/api/cooldown/active` | Get active cooldown |
| GET | `/api/cooldown/history` | List cooldown history |
| POST | `/api/cooldown/start` | Start manual cooldown |
| POST | `/api/cooldown/{id}/skip` | Skip cooldown |
| POST | `/api/cooldown/{id}/acknowledge` | Acknowledge cooldown |
| POST | `/api/cooldown/pre-trade-check` | Pre-trade intervention |
| **AI Personalization** | | |
| POST | `/api/personalization/learn` | Trigger pattern learning |
| GET | `/api/personalization/insights` | Get personalized insights |
| POST | `/api/personalization/predictive-check` | Check for predictive alerts |
| GET | `/api/personalization/time-analysis` | Hourly/daily performance |
| GET | `/api/personalization/symbol-analysis` | Symbol performance |
| GET | `/api/personalization/intervention-timing` | Optimal cooldown timing |
| **WebSocket** | | |
| WS | `/api/ws/prices` | Price streaming |

---

## Pattern Detection System

### Detection Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    PATTERN DETECTION LAYERS                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Layer 1: REAL-TIME (per trade)                                 │
│  ├── RiskDetector.py (backend)                                  │
│  │   ├── Consecutive Loss Spiral                                │
│  │   ├── Revenge Sizing                                         │
│  │   └── Overtrading Burst                                      │
│  │                                                              │
│  └── Triggers: On webhook postback                              │
│                                                                 │
│  Layer 2: BEHAVIORAL (30-day window)                            │
│  ├── BehavioralAnalysisService.py (backend)                     │
│  │   ├── 11 pattern detectors                                   │
│  │   ├── Time performance analysis                              │
│  │   └── AI persona generation                                  │
│  │                                                              │
│  └── Triggers: On /behavioral/analysis request                  │
│                                                                 │
│  Layer 3: CLIENT-SIDE (immediate feedback)                      │
│  ├── patternDetector.ts (frontend)                              │
│  │   ├── Overtrading                                            │
│  │   ├── Revenge Trading                                        │
│  │   ├── Loss Aversion                                          │
│  │   └── Position Sizing                                        │
│  │                                                              │
│  └── Triggers: On trade data load                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Pattern Definitions

#### Revenge Trading
```
TRIGGER: Trade placed within 15 minutes of a losing trade
SEVERITY: HIGH
DETECTION:
  - Previous trade P&L < 0
  - Time gap < 15 minutes
  - (Optional) Position size increased
```

#### Overtrading
```
TRIGGER: Excessive trade frequency
SEVERITY: HIGH (10+/day), CAUTION (8+/day)
DETECTION:
  - Count trades in rolling 1-hour window > 5
  - OR count trades today > 10
```

#### Martingale/Loss Chasing
```
TRIGGER: Position size doubled after loss
SEVERITY: CRITICAL
DETECTION:
  - Previous trade P&L < 0
  - Current position size > 1.8x previous
```

#### Loss Spiral/Tilt
```
TRIGGER: 4+ consecutive losing trades
SEVERITY: CRITICAL
DETECTION:
  - Count consecutive trades where P&L < 0
  - Alert at 3 (CAUTION), 5+ (DANGER)
```

#### FOMO Entry ✅
```
TRIGGER 1: Market Open Rush
SEVERITY: CAUTION (1 trade), DANGER (2+ trades)
DETECTION:
  - Trade placed in first 5 minutes (9:15-9:20)
  - Multiple trades amplify severity

TRIGGER 2: Chasing Behavior
SEVERITY: DANGER
DETECTION:
  - 3+ same-direction trades on same symbol
  - Within 10 minute window
  - Indicates chasing a move
```

#### Tilt/Loss Spiral ✅
```
TRIGGER: Increasing position size while losing
SEVERITY: DANGER
DETECTION:
  - Analyze last 5 closed trades
  - For each: Check if losing AND size > previous
  - If 2+ such trades: DANGER pattern
  - Auto-triggers cooldown
```

---

## Blowup Shield (Capital Defense)

> Rebranded from "Money Saved" to "Blowup Shield" - active protection narrative

### P&L Calculator (CRITICAL FIX)

The core issue was that `pnl` field from Zerodha webhooks is always 0/NULL. We implemented FIFO trade matching:

```python
# Location: backend/app/services/pnl_calculator.py

class PnLCalculator:
    """FIFO (First In, First Out) trade matching for P&L calculation"""

    async def calculate_and_update_pnl(
        self,
        broker_account_id: UUID,
        db: AsyncSession,
        symbol: Optional[str] = None,
        days_back: int = 30
    ):
        # 1. Fetch all COMPLETE trades
        # 2. Group by symbol
        # 3. For each symbol: Match SELL with oldest unmatched BUY
        # 4. P&L = (sell_price - buy_price) * quantity
        # 5. Update trade records in database

    async def calculate_trade_pnl_realtime(self, trade: Trade, db: AsyncSession):
        # Real-time calculation for new SELL trades from webhook
        # Called automatically when webhook receives COMPLETE SELL

    async def get_unrealized_pnl(self, broker_account_id: UUID, db: AsyncSession):
        # Calculate unrealized P&L for open positions
```

### Integration Points

1. **Trade Sync Service** (`trade_sync_service.py`):
   - After syncing trades, calls `pnl_calculator.calculate_and_update_pnl()`

2. **Webhook Processing** (`trade_tasks.py`):
   - For SELL trades, calls `pnl_calculator.calculate_trade_pnl_realtime()`

3. **API Endpoint** (`/api/analytics/recalculate-pnl`):
   - Manual trigger for P&L recalculation

### Capital Defended Calculation

```python
# Location: backend/app/services/analytics_service.py

def calculate_money_saved(broker_account_id, db):
    # 1. Get DANGER alerts that were acknowledged/acted upon
    # 2. For each alert:
    #    - estimated_loss = trader's avg loss for this pattern
    #    - actual_outcome = trades after alert (if any)
    #    - defended = estimated_loss - actual_outcome
    # 3. Confidence: "high" if exact history match, "medium" for pattern averages

async def get_intervention_history(broker_account_id, db, limit=50):
    # Returns detailed breakdown:
    # - pattern, symbol, intervention type
    # - estimated_loss (what you would have lost)
    # - actual_outcome (what happened after alert)
    # - saved (capital defended)
    # - confidence level
```

### Frontend Components

| Old | New |
|-----|-----|
| `MoneySaved.tsx` | `BlowupShield.tsx` |
| `MoneySavedCard.tsx` | `BlowupShieldCard.tsx` |
| `/money-saved` route | `/blowup-shield` route |

### Key Messaging Changes

| Before | After |
|--------|-------|
| "Money Saved" | "Blowup Shield" |
| "Prevented losses" | "Capital defended" |
| "This Week" | "Active This Week" / "Shield Status" |
| "See breakdown" | "View protection history" |
| Passive green | Active blue/amber with shield pulse |

---

## Database Schema

### Core Tables

```sql
-- Broker Accounts
CREATE TABLE broker_accounts (
    id UUID PRIMARY KEY,
    user_id UUID,
    broker_name VARCHAR DEFAULT 'zerodha',
    access_token VARCHAR,  -- Encrypted
    api_key VARCHAR,
    status VARCHAR,  -- connected, disconnected
    broker_user_id VARCHAR,
    broker_email VARCHAR,
    guardian_name VARCHAR,
    guardian_phone VARCHAR,
    connected_at TIMESTAMPTZ,
    last_sync_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Trades
CREATE TABLE trades (
    id UUID PRIMARY KEY,
    broker_account_id UUID REFERENCES broker_accounts(id),
    order_id VARCHAR,
    tradingsymbol VARCHAR,
    exchange VARCHAR,
    transaction_type VARCHAR,  -- BUY, SELL
    order_type VARCHAR,
    product VARCHAR,
    quantity INTEGER,
    filled_quantity INTEGER,
    average_price DECIMAL(10,2),
    pnl DECIMAL(10,2),  -- CRITICAL: Often NULL/0
    status VARCHAR,
    asset_class VARCHAR,
    instrument_type VARCHAR,
    order_timestamp TIMESTAMPTZ,
    raw_payload JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Positions
CREATE TABLE positions (
    id UUID PRIMARY KEY,
    broker_account_id UUID REFERENCES broker_accounts(id),
    tradingsymbol VARCHAR,
    exchange VARCHAR,
    total_quantity INTEGER,
    average_entry_price DECIMAL(12,2),
    last_price DECIMAL(12,2),
    pnl DECIMAL(12,2),
    unrealized_pnl DECIMAL(12,2),
    day_pnl DECIMAL(12,2),
    status VARCHAR,  -- open, closed
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Risk Alerts
CREATE TABLE risk_alerts (
    id UUID PRIMARY KEY,
    broker_account_id UUID REFERENCES broker_accounts(id),
    pattern_type VARCHAR,
    severity VARCHAR,  -- caution, danger
    message TEXT,
    details JSONB,
    trigger_trade_id UUID,
    related_trade_ids UUID[],
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    acknowledged_at TIMESTAMPTZ
);

-- Trading Goals
CREATE TABLE trading_goals (
    id UUID PRIMARY KEY,
    broker_account_id UUID REFERENCES broker_accounts(id),
    max_risk_per_trade_percent DECIMAL DEFAULT 2,
    max_daily_loss DECIMAL DEFAULT 5000,
    max_trades_per_day INTEGER DEFAULT 10,
    require_stoploss BOOLEAN DEFAULT true,
    min_time_between_trades_minutes INTEGER DEFAULT 5,
    max_position_size_percent DECIMAL DEFAULT 5,
    allowed_trading_start VARCHAR DEFAULT '09:15',
    allowed_trading_end VARCHAR DEFAULT '15:30',
    primary_segment VARCHAR DEFAULT 'EQUITY',
    starting_capital DECIMAL,
    current_capital DECIMAL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Streak Data
CREATE TABLE streak_data (
    id UUID PRIMARY KEY,
    broker_account_id UUID REFERENCES broker_accounts(id),
    current_streak_days INTEGER DEFAULT 0,
    longest_streak_days INTEGER DEFAULT 0,
    streak_start_date DATE,
    daily_status JSONB DEFAULT '[]',
    milestones_achieved JSONB DEFAULT '[]',
    last_updated TIMESTAMPTZ DEFAULT NOW()
);

-- Commitment Logs
CREATE TABLE commitment_logs (
    id UUID PRIMARY KEY,
    broker_account_id UUID REFERENCES broker_accounts(id),
    log_type VARCHAR,  -- goal_set, goal_modified, goal_broken, streak_milestone
    description TEXT,
    previous_values JSONB,
    new_values JSONB,
    reason TEXT,
    cost DECIMAL,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Push Subscriptions (Web Push)
CREATE TABLE push_subscriptions (
    id UUID PRIMARY KEY,
    broker_account_id UUID REFERENCES broker_accounts(id),
    endpoint TEXT NOT NULL UNIQUE,
    p256dh_key VARCHAR(255) NOT NULL,
    auth_key VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    failure_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ
);

-- Journal Entries
CREATE TABLE journal_entries (
    id UUID PRIMARY KEY,
    broker_account_id UUID REFERENCES broker_accounts(id),
    trade_id UUID REFERENCES trades(id),  -- Optional link
    notes TEXT,
    emotions TEXT,  -- Pre-trade feeling
    lessons TEXT,
    emotion_tags JSONB DEFAULT '[]',  -- Quick tags
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

-- User Profiles (Onboarding & Personalization)
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY,
    broker_account_id UUID REFERENCES broker_accounts(id) UNIQUE,
    onboarding_completed BOOLEAN DEFAULT false,
    onboarding_step INTEGER DEFAULT 0,
    display_name VARCHAR(100),
    trading_since INTEGER,  -- Year started
    experience_level VARCHAR(20) DEFAULT 'beginner',
    trading_style VARCHAR(20) DEFAULT 'intraday',
    risk_tolerance VARCHAR(20) DEFAULT 'moderate',
    preferred_instruments JSONB DEFAULT '[]',
    preferred_segments JSONB DEFAULT '[]',
    trading_hours_start VARCHAR(5) DEFAULT '09:15',
    trading_hours_end VARCHAR(5) DEFAULT '15:30',
    daily_loss_limit FLOAT,
    daily_trade_limit INTEGER,
    max_position_size FLOAT,
    cooldown_after_loss INTEGER DEFAULT 15,
    known_weaknesses JSONB DEFAULT '[]',
    push_enabled BOOLEAN DEFAULT true,
    alert_sensitivity VARCHAR(20) DEFAULT 'medium',
    ai_persona VARCHAR(50) DEFAULT 'coach',
    detected_patterns JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

-- Cooldowns (Trading Breaks)
CREATE TABLE cooldowns (
    id UUID PRIMARY KEY,
    broker_account_id UUID REFERENCES broker_accounts(id),
    reason VARCHAR(50) NOT NULL,  -- revenge_pattern, loss_limit, etc.
    duration_minutes INTEGER NOT NULL DEFAULT 15,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    can_skip BOOLEAN DEFAULT true,
    skipped BOOLEAN DEFAULT false,
    skipped_at TIMESTAMPTZ,
    acknowledged BOOLEAN DEFAULT false,
    acknowledged_at TIMESTAMPTZ,
    trigger_alert_id UUID,
    message VARCHAR(500),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Deployment Guide

### Prerequisites

1. **Supabase Account** - PostgreSQL database
2. **Upstash Account** - Redis for Celery
3. **Zerodha Developer Account** - KiteConnect API
4. **Twilio Account** - WhatsApp Business API
5. **OpenRouter Account** - LLM API access

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db

# Zerodha
ZERODHA_API_KEY=your_api_key
ZERODHA_API_SECRET=your_api_secret
ZERODHA_REDIRECT_URI=https://yourdomain.com/api/zerodha/callback

# AI
OPENROUTER_API_KEY=your_openrouter_key

# Twilio
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886

# Redis
REDIS_URL=rediss://default:pass@host:6379

# Security
ENCRYPTION_KEY=your_fernet_key
SECRET_KEY=your_jwt_secret

# Push Notifications (Web Push VAPID)
VAPID_PUBLIC_KEY=your_vapid_public_key
VAPID_PRIVATE_KEY=your_vapid_private_key
VAPID_CLAIMS_EMAIL=mailto:admin@yourdomain.com
```

### Generate VAPID Keys

```bash
# Install pywebpush if not already installed
pip install pywebpush

# Generate VAPID keys
python -c "from py_vapid import Vapid; v = Vapid(); v.generate_keys(); print('Public:', v.public_key); print('Private:', v.private_key)"
```

### Database Migrations

Run these migrations in Supabase SQL Editor in order:

```bash
# Required migrations (run in order)
backend/migrations/001_initial.sql        # Core tables
backend/migrations/002_goals.sql          # Goals & streaks
backend/migrations/003_journal.sql        # Legacy journal
backend/migrations/004_push_subscriptions.sql  # Push notifications
backend/migrations/005_journal_entries.sql     # Journal entries
backend/migrations/006_user_profiles.sql       # User profiles & onboarding
backend/migrations/007_cooldowns.sql           # Cooldown system
```

### Running Locally

```bash
# Backend
cd backend
pip install -r requirements.txt
pip install pywebpush  # Required for push notifications
uvicorn app.main:app --reload --port 8000

# Celery Worker
cd backend
python scripts/run_celery.py worker

# Celery Beat (scheduled tasks)
cd backend
python scripts/run_celery.py beat

# Frontend
npm install
npm run dev
```

### Zerodha Postback Configuration

In Zerodha Developer Console:
```
Postback URL: https://yourdomain.com/api/webhooks/zerodha/postback
```

---

## Roadmap

### Phase 1: Foundation Fixes ✅ COMPLETE
- [x] P&L calculation from BUY/SELL matching
- [x] Entry/Exit trade linkage (FIFO matching)
- [x] Fix pattern detection (now uses calculated P&L)
- [x] Blowup Shield rebrand

### Phase 2: Real-Time Intervention ✅ COMPLETE
- [x] Pre-trade check API
- [x] Cooldown system
- [x] Desktop/mobile push notifications
- [x] Enhanced guardian alerts
- [x] FOMO pattern detection
- [x] Tilt/Loss spiral detection

### Phase 3: User Types & Onboarding ✅ COMPLETE
- [x] User profile system
- [x] 5-step onboarding wizard
- [x] Adaptive experience based on profile
- [x] Risk management preferences
- [x] AI persona selection

### Phase 4: Engagement Features ✅ MOSTLY COMPLETE
- [x] Journal entries with emotion tracking
- [x] Emotion-P&L correlation analytics
- [ ] Community anonymous stats
- [ ] Accountability partner system
- [ ] Achievement/gamification

### Phase 5: AI Personalization ✅ COMPLETE
- [x] Known weaknesses tracking
- [x] Auto-detect trading style
- [x] Personal pattern learning (time-based) - YOUR danger hours/days
- [x] Symbol-specific weakness detection - YOUR problem symbols
- [x] Predictive alerts - Warn BEFORE your danger windows
- [x] AI-based intervention timing - YOUR optimal cooldown duration

### Phase 6: Scale & Monetization (PLANNED)
- [ ] Freemium/Subscription system
- [ ] Payment integration
- [ ] Multi-broker support (Upstox, Angel)
- [ ] Mobile app (React Native)
- [ ] B2B white-label

---

## File Structure

```
trade-psychology-ai/
├── backend/
│   ├── app/
│   │   ├── api/              # API endpoints
│   │   │   ├── alerts.py
│   │   │   ├── analytics.py
│   │   │   ├── behavioral.py
│   │   │   ├── coach.py
│   │   │   ├── cooldown.py       # NEW: Cooldown & pre-trade check
│   │   │   ├── goals.py
│   │   │   ├── journal.py        # NEW: Journal CRUD API
│   │   │   ├── notifications.py  # NEW: Push notification API
│   │   │   ├── personalization.py # NEW: AI personalization API
│   │   │   ├── positions.py
│   │   │   ├── profile.py        # NEW: Profile & onboarding API
│   │   │   ├── reports.py
│   │   │   ├── risk.py
│   │   │   ├── settings.py
│   │   │   ├── trades.py
│   │   │   ├── webhooks.py
│   │   │   ├── websocket.py
│   │   │   └── zerodha.py
│   │   ├── core/             # Core config
│   │   │   ├── celery_app.py
│   │   │   ├── config.py
│   │   │   ├── database.py
│   │   │   ├── market_hours.py
│   │   │   └── security.py
│   │   ├── models/           # SQLAlchemy models
│   │   │   ├── cooldown.py       # NEW
│   │   │   ├── journal_entry.py  # NEW
│   │   │   ├── push_subscription.py # NEW
│   │   │   └── user_profile.py   # NEW
│   │   ├── services/         # Business logic
│   │   │   ├── ai_personalization_service.py # Pattern learning
│   │   │   ├── daily_reports_service.py      # NEW: Post-market & morning reports
│   │   │   ├── pattern_prediction_service.py # NEW: Real-time predictions
│   │   │   ├── pnl_calculator.py    # FIFO P&L matching
│   │   │   ├── push_notification_service.py
│   │   │   └── risk_detector.py     # Enhanced with FOMO/Tilt
│   │   ├── tasks/            # Celery tasks
│   │   └── utils/            # Utilities
│   ├── migrations/           # SQL migrations
│   │   ├── 004_push_subscriptions.sql  # NEW
│   │   ├── 005_journal_entries.sql     # NEW
│   │   ├── 006_user_profiles.sql       # NEW
│   │   └── 007_cooldowns.sql           # NEW
│   ├── scripts/              # Helper scripts
│   └── requirements.txt
├── public/
│   └── sw.js                 # NEW: Service Worker for push
├── src/
│   ├── components/           # React components
│   │   ├── onboarding/
│   │   │   └── OnboardingWizard.tsx  # NEW: 5-step wizard
│   │   ├── settings/
│   │   │   └── NotificationSettings.tsx # NEW
│   │   └── dashboard/
│   │       └── TradeJournalSheet.tsx # Updated with API
│   ├── contexts/             # React contexts
│   ├── hooks/                # Custom hooks
│   │   └── useOnboarding.ts  # NEW
│   ├── lib/                  # Utilities
│   │   └── pushNotifications.ts # NEW
│   ├── pages/                # Page components
│   └── types/                # TypeScript types
├── PRODUCT_DOCUMENTATION.md  # This file
└── README.md
```

---

## Contributing

### Code Style

- **Backend:** Black formatter, isort imports
- **Frontend:** Prettier, ESLint

### Testing

```bash
# Backend tests
cd backend
pytest

# Frontend tests
npm test
```

---

## Support

- **Issues:** https://github.com/your-repo/issues
- **Email:** support@tradementor.ai

---

*Last updated: February 5, 2026*
