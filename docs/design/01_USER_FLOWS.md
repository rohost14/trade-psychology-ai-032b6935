# TradeMentor AI — User Flows

> This document maps all significant user journeys through the app — first-time setup, daily usage patterns, and edge cases. Each flow has a diagram and design notes. Read this before designing or building any interactive behavior.

---

## Flow Index

1. [First Visit (New User)](#1-first-visit-new-user)
2. [First Visit (Guest)](#2-first-visit-guest)
3. [Morning Pre-Market Routine](#3-morning-pre-market-routine)
4. [Active Trading Session (Market Hours)](#4-active-trading-session-market-hours)
5. [Alert Received During Trading](#5-alert-received-during-trading)
6. [Post-Market Review](#6-post-market-review)
7. [Journal Entry Flow](#7-journal-entry-flow)
8. [AI Coach Conversation](#8-ai-coach-conversation)
9. [Setting Up Risk Rules](#9-setting-up-risk-rules)
10. [Returning User (Token Expired)](#10-returning-user-token-expired)
11. [Report Generation & Reading](#11-report-generation--reading)

---

## 1. First Visit (New User)

**Trigger:** User lands on app URL for the first time. No session, no Zerodha connection.

```
[Browser] → / or /welcome

  /welcome
  ├── User reads landing page
  ├── Clicks "Connect Zerodha"
  │     ↓
  │   [OAuth redirect → Zerodha Kite login]
  │     ↓
  │   [Zerodha returns to /api/zerodha/callback]
  │     ↓
  │   [Backend creates BrokerAccount, issues JWT]
  │     ↓
  │   [Frontend receives ?token= → stores in localStorage]
  │     ↓
  │   /dashboard + OnboardingWizard modal opens (5 steps)
  │
  │   ONBOARDING WIZARD:
  │   Step 1: Your name (required — cannot skip)
  │   Step 2: Trading experience (years, style)
  │   Step 3: Capital size (range, not exact)
  │   Step 4: Primary segment (F&O / Equity / Both)
  │   Step 5: Risk preferences (set initial alert thresholds)
  │         ↓
  │   [Each step saves immediately via API]
  │         ↓
  │   Completion → Dashboard with "You're set up" toast
  │         ↓
  │   GettingStartedCard appears (4-step checklist)
  │   (auto-hides when onboarding complete + ≥3 trades synced)
  │
  └── OR: User clicks "Continue as Guest"
        → See Flow 2
```

**Design notes:**
- The OnboardingWizard is the ONE place where we interrupt — it's intentional and one-time only
- No step should take more than 30 seconds — short inputs, selects, sliders
- Progress bar at top (1/5, 2/5, etc.) — never ambiguous where you are
- Skip is allowed on Steps 2–5; grayed out "Skip for now" link, not prominent
- Error saving a step: show inline error, let user retry — don't lose their input
- First Dashboard view: positions table will be empty — show onboarding state, not empty state error

---

## 2. First Visit (Guest)

**Trigger:** User clicks "Continue as Guest" on /welcome or on the token-expired banner.

```
[/welcome]
  └── Click "Continue as Guest"
        ↓
  [guestMode.ts sets isGuest = true, injects demo data via API adapter]
        ↓
  /dashboard (guest mode)
  ├── Amber banner: "You're viewing demo data — Connect Zerodha to see your trades"
  ├── All navigation visible and functional
  ├── All pages work with demo data
  ├── AI Coach works (may use simplified responses or same backend)
  ├── Settings → shows "Connect Zerodha" CTA instead of account settings
  │
  ├── User clicks "Connect Zerodha" on banner or Settings
  │     → Goes to /welcome → OAuth flow (Flow 1)
  │
  └── User closes tab — no account created, nothing saved
```

**Design notes:**
- Guest banner must be visible but not dominate — amber bar, 40px tall, at top of main content area
- Every page that would show "no data" in real mode shows demo data in guest mode — no empty states
- The demo data should look realistic: 15–20 trades, mix of P&L, a few behavioral alerts
- Guest users should be able to experience the AI Coach — the value prop is clearest there

---

## 3. Morning Pre-Market Routine

**Trigger:** User opens app between 8:00–9:15 AM IST (pre-market). Has existing account.

```
[App opens]
  ↓
[Auth check: valid JWT → /dashboard]
  ↓
Dashboard (market CLOSED state)
├── P&L shows: "Yesterday: +₹3,450" (previous day's final)
├── Positions: "No open positions" OR yesterday's carry-forward
├── Status indicator: "Market opens in 1h 12m" (subtle, not prominent)
│
├── User checks Alerts page
│   └── Reviews overnight behavioral alerts (if any)
│       → Acknowledges what's relevant
│
├── User opens AI Coach
│   ├── Sees "Pre-market" context in header
│   ├── May ask: "What patterns should I watch today?"
│   └── Coach responds with personalized pre-session prep
│
├── User checks My Patterns
│   └── Reviews recent pattern trends before market opens
│
└── Market opens at 9:15 → Dashboard auto-updates
    ├── Status: "● LIVE" pulse indicator appears
    ├── Positions begin showing live data via WebSocket
    └── User transitions to Flow 4
```

**Design notes:**
- Pre-market state should feel calm and analytical — not urgent
- No visual noise before market opens. This is review time.
- If WebSocket disconnected overnight, reconnect silently on app open

---

## 4. Active Trading Session (Market Hours)

**Trigger:** User opens app or switches to it during 9:15–3:30 PM IST.

```
Dashboard (LIVE state)
├── Positions table: live prices via WebSocket
│   ├── Unrealized P&L updating silently (no flash/blink)
│   ├── Color: green/red based on P&L (not pulsing, not animated)
│   └── Each row: instrument | qty | avg | LTP | P&L | change%
│
├── Session P&L tile: running total (realized only during session)
├── Margin tile: available margin (updates on each trade)
│
├── User makes a trade in Zerodha Kite (separate window)
│   ↓
│   [Zerodha sends webhook → backend processes → Redis event]
│   ↓
│   [WebSocket pushes update to dashboard]
│   ↓
│   Dashboard: position appears/updates within 2 seconds
│
├── Behavioral alert triggered (e.g., overtrading)
│   → See Flow 5
│
├── User glances at Alerts tab (badge shows count)
│   └── Quick scroll, acknowledges or ignores
│   → Returns to Dashboard
│
└── Market closes at 3:30 PM
    ├── Status: "Market Closed" replaces live indicator
    ├── Final session P&L shown
    └── User transitions to Flow 6
```

**Design notes:**
- Every second counts during market hours. The app must never hijack focus.
- No modals, no forced attention. Everything is ambient.
- Tab switching must be instant — no loading spinners visible to market-hours users
- The positions table is the heart of the Dashboard. Everything else is secondary.

---

## 5. Alert Received During Trading

**Trigger:** BehaviorEngine detects a pattern (e.g., revenge trading, overtrading). WebSocket pushes alert.

```
[WebSocket event: new_alert]
  ↓
AlertContext receives event
  ↓
[Toast notification appears — top-right, 4 seconds]
├── Toast: small, dark, non-blocking
│   Example: "Overtrading detected · 8 trades in 2h"
│   [View details] link in toast
│   Disappears automatically after 4 seconds
│
├── Alerts tab in nav: badge count increments
│
├── User ignores toast (most common during market hours)
│   └── Alert saved, badge stays until acknowledged
│
└── User clicks toast or Alerts nav link
      ↓
    /alerts page
    ├── Alert appears at top of Live feed
    ├── Shows: pattern name, severity, evidence, timestamp
    ├── [Acknowledge] button — marks as read, badge decrements
    ├── User reads, decides what to do (their choice, not our business)
    └── Returns to Dashboard
```

**Critical design constraints:**
- The toast MUST NOT block any interactive element
- The toast MUST NOT auto-scroll the page
- The toast MUST NOT require a click to dismiss
- The toast MUST NOT play a sound by default (notification permission flow is in Settings)
- The alert severity (low/medium/high/critical) only affects the alert's icon in the feed — NOT the toast's visual weight. All toasts look the same. A "critical" alert does not scream louder.

---

## 6. Post-Market Review

**Trigger:** User opens app after 3:30 PM IST for daily review.

```
Dashboard (post-market)
├── Final session P&L: prominent, settled number
├── Positions: any overnight holds (NRML/MTF products)
├── Status: "Market Closed"
│
├── User navigates to Analytics
│   ├── Summary tab: today's performance vs. 30-day average
│   ├── Behavior tab: behavior score, flagged patterns
│   ├── Trades tab: all today's trades with timing breakdown
│   ├── Timing tab: P&L by hour analysis
│   └── Progress tab: goal progress for the week
│
├── User opens Reports
│   ├── Today's EOD report (if generated)
│   └── Downloads or reads summary
│
├── User journalizes trades
│   → See Flow 7
│
├── User talks to AI Coach
│   └── "How was today?" / "What patterns did I show today?"
│   → See Flow 8
│
└── User sets/reviews goals for tomorrow
    └── /goals — adjusts targets if needed
```

**Design notes:**
- Post-market is the app's best moment for depth and reflection. Allow it.
- Analytics can be more complex here — charts, tables, breakdowns
- This is when the app proves its long-term value. Design for return visits.

---

## 7. Journal Entry Flow

**Trigger:** User decides to journal a trade — either from the Trades tab or via the Journal icon on a trade row.

```
[Trades tab / Closed trades table]
  ↓
User clicks journal icon on a trade row
  ↓
TradeJournalSheet slides in from right (not a full-page nav)
├── Trade context locked at top: symbol, P&L, time
├── Chip-select fields:
│   ├── Emotion before: Calm / Anxious / Confident / Distracted / Fearful
│   ├── Plan followed: Yes / No / Partially
│   ├── Exit reason: Target hit / Stop hit / Intuition / Fear / Boredom / FOMO
│   └── Setup quality: A / B / C
├── Free-text note (optional, no minimum length)
├── Tags (optional: expiry day / news event / high volatility / etc.)
│
├── [Save] button
│   ↓
│   Saves via API, sheet closes
│   Trade row shows journal indicator (pencil icon filled)
│
└── [Skip] / close button — discards, no prompt
```

**Design notes:**
- Sheet, not a page navigation — user stays in context (Analytics → Trades tab still visible behind)
- Chip selects are one-tap answers. No free-text required.
- The journal is for the trader's own reflection — no analytics run on it automatically in V1
- Keep it fast: 30 seconds to fill. The moment the market is fresh in memory is fleeting.

---

## 8. AI Coach Conversation

**Trigger:** User navigates to AI Coach page, or clicks "Ask Coach" from anywhere.

```
/coach
├── Left panel (web only): live context sidebar
│   ├── Today's P&L + trade count
│   ├── Behavior score
│   ├── Active alerts (top 3)
│   └── Current risk state
│
├── Chat interface (center/full on mobile)
│   ├── Starter prompts if no conversation history:
│   │   "How was my trading today?"
│   │   "What patterns should I be aware of?"
│   │   "I'm feeling frustrated — what do you see in my trades?"
│   │   "Help me prepare for tomorrow"
│   │
│   ├── User types or taps a starter prompt
│   ↓
│   [POST /api/coach/chat — SSE stream response]
│   ↓
│   Response streams in word-by-word
│   ├── Coach never gives explicit buy/sell advice
│   ├── Coach references actual trade data
│   └── Coach asks follow-up questions
│
├── Session persists (restored on next visit)
│   [User leaves and returns → conversation still there]
│
└── User can start new conversation via "New chat" button
    (previous saved in history — future feature)
```

**Design notes:**
- The left panel on web is the competitive advantage — it shows the coach has context
- On mobile: top collapsible bar shows the same 3–4 context stats
- Streaming response must render smoothly — no jitter, no layout shift
- The coach header shows "Market Open" / "Market Closed" badge to set context
- Input field must autofocus on page load on desktop

---

## 9. Setting Up Risk Rules

**Trigger:** User navigates to Settings → Risk Limits (or from GettingStartedCard step 3).

```
/settings → Risk Limits tab
├── Max daily loss (₹ or % of capital)
│   [Slider + text input — either works]
│
├── Max trades per day (integer)
├── Max position size (₹ or % of capital)
├── Cooldown period after consecutive losses (minutes)
├── High-risk window warnings (on/off toggle)
│   └── Defaults to: ON for 9:15–9:30, ON for 15:00–15:30
│
├── [Save changes] button
│   ↓
│   Saves via API
│   Toast: "Risk limits updated"
│
└── Guardrails page (/guardrails) shows these rules in effect
    → User can also edit from there
```

**Design notes:**
- No validation pop-ups. Just save and show what was saved.
- If a value seems extreme (e.g., max loss = ₹1,00,000), no warning. Trust the trader.
- Use the trader's actual capital (from profile) to show %-equivalent next to ₹ value

---

## 10. Returning User (Token Expired)

**Trigger:** Zerodha access token expires (daily, after market close). User opens app next morning.

```
[App loads] → [API call fails with 401]
  ↓
TokenExpiredBanner appears at top of page (amber)
├── "Your Zerodha session expired. Re-connect to see live data."
├── [Reconnect] button
├── App still shows yesterday's cached data (not blank)
│
├── User clicks Reconnect
│   ↓
│   OAuth flow (same as first-time, but faster — Zerodha remembers)
│   ↓
│   New token stored → banner disappears
│   ↓
│   Dashboard refreshes with live data
│
└── User ignores banner (guest-like experience with stale data)
    ├── All pages still work with cached/stale data
    └── Banner persists until reconnected
```

**Design notes:**
- NEVER log the user out and show a blank screen. Always show something.
- The banner is the only persistent amber color in the app — its meaning is always "attention needed, but not critical"
- Re-connecting should be one click, not a multi-step re-onboarding

---

## 11. Report Generation & Reading

**Trigger:** User navigates to Reports page, or a report notification arrives.

```
/reports
├── Report list (newest first):
│   ├── EOD Report — Today, March 28
│   ├── EOD Report — Yesterday, March 27
│   ├── Weekly Summary — Week of March 24
│   └── ... older reports
│
├── User clicks a report
│   ↓
│   Report opens in right panel (web) or new view (mobile)
│   ├── Summary section: P&L, trades, behavior score
│   ├── Key patterns detected this period
│   ├── Notable trades (best + worst)
│   ├── Comparison to previous period
│   └── AI narrative (2–3 paragraphs of behavioral insight)
│
├── [Download PDF] button (generates on demand)
│
└── Empty state (no reports yet):
    "Reports generate after your first trading day.
     Connect Zerodha and trade to see your first report."
```

**Design notes:**
- Reports are retrospective, not live. They can be heavier on text and charts.
- The AI narrative in a report is the most valuable text in the entire app — design it to be readable
- Reports page on mobile: card list, tap to open full report in a scrollable sheet

---

## Error & Edge Case Flows

### WebSocket Disconnects
```
[WS drops] → reconnect indicator (amber pulsing dot in header)
           → silent reconnect attempt every 5s
           → reconnects → dot disappears
           → missed events replayed from Redis Streams
```

### No Trades Yet (Empty State)
```
Dashboard → empty positions table
         → GettingStartedCard visible
         → "Sync your first trades" CTA
         → No error, no broken layout
```

### Maintenance Mode
```
[Backend returns 503] → /maintenance page
                     → "TradeMentor is under maintenance. Check back soon."
                     → No infinite loading, no crash
```

### Network Offline
```
[Navigator.onLine = false] → subtle banner: "You're offline"
                           → Cached data still visible
                           → Reconnects silently when network returns
```

---

*Next: [02_WEB_SCREENS.md](./02_WEB_SCREENS.md) | [03_MOBILE_SCREENS.md](./03_MOBILE_SCREENS.md) | [04_COMPONENTS.md](./04_COMPONENTS.md)*
