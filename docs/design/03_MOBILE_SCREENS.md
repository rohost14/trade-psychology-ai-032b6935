# TradeMentor AI — Mobile Screen Design Specification

> Complete UI/UX specification for the Android app (Capacitor wrapper around the React webapp). Every screen adapts the same data and logic from the web app into single-column mobile patterns. Mobile is not a reduced version — it has every feature, presented for a 390px viewport and thumb-first interaction.

---

## Mobile Design Premise

Mobile usage of TradeMentor happens in two very different contexts:

**During market hours:** The trader is sitting at their desk or monitor. Zerodha Kite is open on one screen, TradeMentor is on their phone for quick glances. The phone is picked up for 10–15 seconds at a time. Information must be readable without scrolling, without tapping, without thinking. The phone is put back down. Fast.

**After market close:** The trader is in review mode — on the couch, commuting, winding down. The phone is held for minutes at a time, reading and reflecting. Comfortable layout, readable text, smooth navigation.

Both contexts use the same screens. A screen that answers a market-hours glance question also works for a 10-minute post-market review session.

### The Journal is Still the Core Action on Mobile

Mobile is where journaling actually happens. After closing a trade in Zerodha Kite, the trader switches to TradeMentor on their phone and journals while the trade is fresh. The Home screen must make this one tap away. Every trade row has a journal icon. The recency of a trade in the trader's memory is the journal's value — if they need to navigate to Analytics → Trades → find the trade → tap journal, they will not journal consistently. If they open TradeMentor and see the trade at the top of the Home screen with a journal icon, they will.

### What the Behavioral Score Is and Is Not

The behavioral score (0–100) is a trend indicator — useful to see whether a trader is improving or regressing over 30 days. It is not useful as a moment-to-moment glance metric. A trader opening TradeMentor at 10:30 AM does not need to see "74/100 Disciplined." They need to see: have I been flagged today, how many trades have I placed, which trades need journaling. The score appears in the Analytics Behavior tab as a 30-day trend line chart (at the bottom of the tab, not as the hero). It does not appear on the Home screen. It does not appear as a badge on the bottom nav or the More sheet.

**The key mobile design constraint:** Everything critical must be visible without scrolling. Context is one tap away. Full data is two taps away.

---

## Mobile Navigation

### Bottom Navigation Bar

Fixed to the bottom of the screen. Height: 64px. Background: card color. Top border: subtle border. Safe area padding applied internally so content sits above the system home indicator.

```
  [🏠]        [⚡]        [📊]        [💬]        [⋯]
  Home       Patterns   Analytics    Coach       More
```

Five tabs. The fifth (More) opens a bottom sheet with all secondary screens.

**Tab labels:**
- **Home** = Dashboard
- **Patterns** = Behavioral Observations (labeled "Patterns" not "Alerts" — observations of behavioral patterns, not fire alarms)
- **Analytics** = Analytics
- **Coach** = AI Coach
- **More** = bottom sheet with all secondary screens

Active tab: brand primary color (teal). Inactive: muted gray. Unread badge: small filled circle above the Patterns tab icon when there are unacknowledged observations — count when ≥3, otherwise a plain dot.

### "More" Bottom Sheet

Opens with a slide-up animation from the bottom. Drag handle at the top. Backdrop tap or downward drag dismisses. Auto-height based on content.

```
─────────  ← drag handle

PROTECTION & INSIGHTS
  ▸ My Patterns
  ▸ Blowup Shield
  ▸ Session Limits
  ▸ Goals                [4d ●]  ← streak badge

TOOLS
  ▸ Portfolio Radar
  ▸ Reports

ACCOUNT
  ▸ Settings
```

No behavioral score badge next to My Patterns. The streak badge on Goals is informational only — current streak length.

---

## Screen Descriptions

**Home** — The active session hub on mobile. The first thing visible when the trader opens the app. Shows today's open positions and closed trades as a unified activity feed, with a journal icon on each row. The journal icon is the primary interactive element. Below the activity feed: today's behavioral observations, compact. A one-line session summary at the very top (trade count + net P&L as supporting context, not hero). No behavioral score. No margin display. The screen answers: "What have I done today and what has the system noticed?"

**Patterns** — The behavioral observation feed. Three tab pills: Recent, History, By Pattern. A horizontal row of scrollable filter chips narrows by pattern type. Each observation card is full-width with a full-width acknowledge button at the bottom. Swipe left on a card reveals quick-acknowledge. The unread count on the bottom nav tab decrements as observations are acknowledged.

**Analytics** — All five analytics tabs on mobile. Tabs are horizontally scrollable chips. The Behavior tab is the default and loads first — it contains pattern frequency breakdown, Emotional Tax analysis (win rate by journal-reported emotion), BTST activity, trading persona, and behavioral score trend at the bottom. Charts use touch-to-reveal tooltips. Tables become card stacks. "View full →" links open bottom sheets for expanded data.

**AI Coach** — Full-screen chat. A collapsed context bar at the top shows today's brief including journal-reported emotions from today's trades. Expandable on tap. Starter prompts are full-width chips when no conversation history exists. Input pinned above keyboard. Identical context and data access as web — not a lite version.

**My Patterns** — Vertical accordion of pattern cards. Each card collapses to a header row (pattern name, occurrence count, last seen). Tapping expands to show: narrative paragraph, emotional correlation from journal data, frequency sparkline, timing context, and worst instances. One card open at a time. Not-Detected patterns at the bottom in quieter styling.

**Blowup Shield** — Counterfactual protection record. Hero: total capital defended in large green type. Below: shield score, heeded streak. Per-event list shows each circuit break or cooldown with the full counterfactual breakdown — what the position was worth at alert time, what the market price was 30 minutes later, and the net difference. Honestly shows events where the market recovered and heeding cost opportunity.

**Session Limits** — Status-first screen. The status banner occupies the top of the content area: green-left-border when within bounds, amber-left-border when a limit is active. When active, the card explicitly says: "You can still trade in Zerodha Kite." A list of configured rules below. Recent events this week below that.

**Goals** — Full-width goal cards with weekly progress bar and streak. Each card shows goal text, this week's day-by-day compliance, and current/best streak. Goal changes are gated with a 24-hour cooldown — the three-dot menu shows "Request change" which applies the next day. The 30-day calendar heatmap sits below the last card.

**Portfolio Radar** — Score and risk label as hero. Total exposure below. Position cards show options-specific metrics where applicable: strike, breakeven price, gap to breakeven, premium decay per day, days to expiry. Concentration analysis as horizontal bar charts below. Positions list at the bottom with inline warnings.

**Reports** — A card list filtered by report type. Tapping a card opens a 90vh bottom sheet with the full report. Inside the EOD report: summary stats, Emotional Journey timeline (each trade with emoji + P&L in chronological order), key patterns, key lessons, and the AI behavioral narrative. The Morning Brief shows readiness score and pre-session checklist.

**Settings** — Standard Android settings pattern: grouped list of section rows, each navigating into a sub-screen with a back arrow. Save button fixed at the bottom of each sub-screen.

**Guardrails** — Read-only view of active rules. Rule list, today's compliance bar, edit link. Accessible from Session Limits or the More sheet.

---

## Screen Index

1. [Home (Dashboard)](#1-home-dashboard)
2. [Patterns (Observations)](#2-patterns-observations)
3. [Analytics](#3-analytics)
4. [AI Coach](#4-ai-coach)
5. [My Patterns](#5-my-patterns)
6. [Blowup Shield](#6-blowup-shield)
7. [Session Limits](#7-session-limits)
8. [Goals](#8-goals)
9. [Portfolio Radar](#9-portfolio-radar)
10. [Reports](#10-reports)
11. [Settings](#11-settings)
12. [Guardrails](#12-guardrails)

---

## 1. Home (Dashboard)

**What it is:** The active session hub on mobile. The trader opens TradeMentor after closing a trade, checks what the system has noticed, and journals the trade before the details fade. The screen shows today's activity as a unified feed (open positions + closed trades), with a journal icon on every row. Behavioral observations from today sit below. Session summary at the top is one quiet line of supporting context.

**What is NOT on this screen:**
- Behavioral score as hero or any prominently displayed number
- Margin / available funds (that's in Kite, not our job)
- Blowup Shield summary card (has its own screen)
- Progress tracking (belongs in Analytics → Progress tab)
- RiskGuardian / risk level widget (shown as one quiet line only when active)

**Information hierarchy:**
1. Session summary — one line at top: trade count + net P&L (context, not hero)
2. Session limit status — one line IF a limit is currently active, links to Session Limits
3. TODAY'S ACTIVITY — unified feed: open positions + closed trades, journal icon on each row
4. TODAY'S OBSERVATIONS — compact strip of what the system flagged today
5. AI Coach quick access — persistent input at bottom

### Live (Market Hours)

```
┌────────────────────────────────┐
│  TradeMentor          ● LIVE  │
├────────────────────────────────┤
│                                │
│  8 trades · Net: +₹1,240       │  ← one-line summary, muted text
│                                │
├────────────────────────────────┤
│  TODAY'S ACTIVITY          [⟳] │
│  ──────────────────────────── │
│                                │
│  NIFTY 24500CE  OPEN   +₹1,100 │  [✎]
│  MIS · 50 qty · 22m hold       │
│  ──────────────────────────── │
│  BANKNIFTY 52000PE OPEN -₹550  │  [✎filled]
│  MIS · 25 qty · [Revenge]      │
│  ──────────────────────────── │
│  NIFTY 24400PE CLOSED  -₹975   │  [✎]
│  MIS · 75 qty · [FOMO]         │
│  ──────────────────────────── │
│  RELIANCE  CLOSED      +₹210   │  [✎]
│  EQ · 100 qty · 45m hold       │
│  ──────────────────────────── │
│                                │
│  3 trades not yet journaled.   │  ← amber text
│  [Journal now →]               │
│                                │
├────────────────────────────────┤
│  TODAY'S OBSERVATIONS      [2] │  [View all →]
│  Overtrading · 10:34 AM        │
│  Revenge risk · 09:58 AM       │
├────────────────────────────────┤
│  ┌──────────────────────────┐  │
│  │  Ask TradeMentor...    → │  │
│  └──────────────────────────┘  │
└────────────────────────────────┘
     [Home] [Patterns] [Analytics] [Coach] [More]
```

### Market Closed

After 3:30 PM, open positions become closed. The session summary shows final P&L. A journal prompt appears for un-journaled trades. The AI Coach section surfaces suggested debrief prompts.

```
┌────────────────────────────────┐
│  TradeMentor   Market Closed  │
├────────────────────────────────┤
│                                │
│  8 trades · Final P&L: +₹3,450 · Win rate: 67%
│                                │
├────────────────────────────────┤
│  TODAY'S ACTIVITY              │
│  ──────────────────────────── │
│  NIFTY 24500CE  CLOSED +₹1,100 │  [✎filled]
│  MIS · 50 qty                  │
│  BANKNIFTY PE   CLOSED  -₹550  │  [✎filled]
│  MIS · 25 qty · [Revenge]      │
│  NIFTY 24400PE  CLOSED  -₹975  │  [✎]       ← empty = not journaled
│  MIS · 75 qty · [FOMO]         │
│  RELIANCE       CLOSED  +₹210  │  [✎]
│  EQ · 100 qty                  │
│  ──────────────────────────── │
│  ⚠ 2 trades not yet journaled. │  ← amber text
│  [Journal: NIFTY 24400PE]      │  ← direct tap → journal sheet
│  [Journal: RELIANCE]           │
├────────────────────────────────┤
│  TODAY'S BEHAVIORAL SUMMARY    │
│  2 patterns: Overtrading and   │
│  Revenge risk. 8 trades placed │
│  — above your 6-trade avg.     │
│  [View full observations →]    │
├────────────────────────────────┤
│  DEBRIEF                       │
│  ┌──────────────────────────┐  │
│  │How was my behavior today?│  │  ← tappable chip → Coach
│  └──────────────────────────┘  │
│  ┌──────────────────────────┐  │
│  │ What patterns did I show?│  │
│  └──────────────────────────┘  │
│  ┌──────────────────────────┐  │
│  │  Ask TradeMentor...    → │  │
│  └──────────────────────────┘  │
└────────────────────────────────┘
```

### Trade Activity Row Design

Each row is a two-line compact block inside the TODAY'S ACTIVITY section:
```
Line 1:  Symbol + Type badge + P&L (colored)        [✎ journal icon]
Line 2:  Product · Qty · [Pattern chip if any]
```

Journal icon: ✎ outline = not journaled. ✎ filled = journaled. Tap either → TradeJournalSheet slides up. Pattern chip: small amber pill, abbreviated pattern name. Pattern chips are context, not alarms — they label the row, they do not dominate it.

Tapping the trade row itself (not the journal icon) opens a bottom sheet with full detail: entry/exit prices, entry/exit times, hold duration, strategy (if detected). Journal icon appears at the top of this sheet as well.

### Session Limit Status Line

Only appears when a limit is currently active. When all limits are within bounds: this line does not exist.

```
⬤  Cooldown active — daily loss limit reached.  [Details →]
```

The dot is amber. Text is regular body size, same line as session summary area. One tap → Session Limits screen.

### Empty State (No Trades Today)

```
TODAY'S ACTIVITY
  No trades yet today.
  Activity appears here as you trade in Zerodha.
  [Sync trades →]
```

If new user (fewer than 3 trades ever):

```
┌──────────────────────────────┐
│  Getting Started         [×] │
│  ✓ Connected Zerodha          │
│  ○ Set trading capital        │
│  ○ Complete profile           │
│  ○ Enable notifications       │
└──────────────────────────────┘
```

### Touch Interactions

- Tap journal icon (✎) → TradeJournalSheet slides up
- Tap trade row body → bottom sheet with full trade detail
- Tap observation in TODAY'S OBSERVATIONS strip → Patterns screen with that observation expanded
- Tap "View all →" (observations) → Patterns screen
- Tap "Ask TradeMentor..." input → navigates to Coach with input focused
- Tap debrief chip → Coach with that message pre-filled
- Pull to refresh → refreshes positions + behavioral data
- Tap [⟳] → manual sync trades

---

## 2. Patterns (Observations)

**What it is:** The behavioral observation feed on mobile. Three tabs: Recent (unread + last 7 days), History (all time with date filter), and By Pattern (one summary card per pattern type). Named "Patterns" in the bottom nav — observational, not alarming.

**UI/UX (mobile-specific):** Three tab pills at the very top, full-width pill style. Below the tabs: horizontal row of scrollable filter chips. Each observation card is full-width with generous vertical padding. The Acknowledge button spans the full width of the card footer — 48px height, thumb-accessible. Unread cards have a barely perceptible background tint (5% opacity). Swiping left on a card reveals a green "✓ Acknowledge" action (80px wide). Badge on the Patterns tab decrements as observations are acknowledged.

```
┌────────────────────────────────┐
│  Behavioral Observations   [2] │
├────────────────────────────────┤
│  [Recent]  [History]  [Pattern]│
├────────────────────────────────┤
│  [All] [Overtrading] [Revenge] │  ← horizontal scroll chips
│  [No Stop-Loss] [FOMO] ...     │
├────────────────────────────────┤
│                                │
│  ┌──────────────────────────┐  │
│  │ ● NEW                    │  │
│  │ Overtrading              │  │
│  │ 8 trades in a 2-hour     │  │
│  │ window. 40% above your   │  │
│  │ daily average of 6.      │  │
│  │ NIFTY CE × 5 · BNKFTY ×3 │  │
│  │ 10:34 AM · Est: -₹1,200  │  │
│  ├──────────────────────────┤  │
│  │ [Acknowledge]            │  │  ← full-width, h-12
│  └──────────────────────────┘  │
│                                │
│  ┌──────────────────────────┐  │
│  │ ✓ Acknowledged           │  │
│  │ Revenge trade risk       │  │
│  │ Re-entered 4 min after   │  │
│  │ ₹800 loss on BANKNIFTY.  │  │
│  │ 09:58 AM today           │  │
│  └──────────────────────────┘  │
│                                │
└────────────────────────────────┘
```

### Severity Dot

- Low: muted gray dot
- Medium: amber dot
- High: orange dot
- Critical: orange dot (slightly larger, same color as high)

Critical and High look nearly identical. Intentional — the severity difference is shown in the evidence, not the visual alarm level.

### By Pattern Tab

```
OVERTRADING
12 this month · ↓ Improving · Est. cost: -₹4,200
Last seen: 2 days ago
[See all →]

REVENGE TRADING
4 this month · → Stable · Est. cost: -₹2,800
Last seen: today
[See all →]

NO STOP-LOSS
8 this month · ↑ Worsening · Est. cost: -₹1,100
Last seen: 3 days ago
[See all →]
```

### Empty State

"No observations in this period. No behavioral patterns were detected."

### Touch Interactions

- Swipe left on card → reveals green "✓ Acknowledge" (dismisses with checkmark animation)
- Tap card body → expands card with additional evidence detail
- Long-press card → quick-acknowledge without expanding
- Tap "See all →" on a pattern type → History tab filtered to that pattern

---

## 3. Analytics

**What it is:** All five analytics tabs on mobile. Behavior tab is the default. Used primarily after market close for review sessions. The Behavior tab contains the unique analysis only TradeMentor can provide: it combines trade data with journal entries to show emotional context.

**UI/UX (mobile-specific):** Five tab chips in a horizontally scrollable row below the page header. The Behavior tab is leftmost and selected by default. Charts use fewer tick marks and touch-to-reveal tooltips (tap a bar or data point to see the exact value). Tables become cards. "View full →" links open bottom sheets with expanded data for traders who want depth. Date range selector in the header applies to all tabs simultaneously.

### Tab: Behavior (default)

The behavioral intelligence center. This tab's content combines pattern detection data with journal-reported emotional data. The behavioral score trend line is at the **bottom** of this tab — it is a secondary context indicator, not the hero.

```
┌────────────────────────────────┐
│  Analytics  [Last 30 days ▼]  │
├────────────────────────────────┤
│  [Behavior][Trades][Timing]   │  ← scrollable tab chips
│  [Progress][Summary]           │
├────────────────────────────────┤
│                                │
│  DETECTED PATTERNS             │
│  ────────────────────────────  │
│  Overtrading    12×  -₹4,200 ↓ │
│  Revenge          4×  -₹2,800 → │
│  No stop-loss     8×  -₹1,100 ↑ │
│  FOMO             3×  -₹900   ↓ │
│  [See all observations →]      │
│                                │
├────────────────────────────────┤
│  EMOTIONAL TAX                 │
│  (from your journal entries)   │
│  ────────────────────────────  │
│  Total behavioral cost: -₹9,480│
│                                │
│  Win rate by emotion:          │
│  Calm      68%  ████████  41t  │
│  Confident 71%  █████████ 18t  │
│  Neutral   61%  ███████   24t  │
│  Anxious   28%  ███        12t  │
│  FOMO      19%  ██          8t  │
│  Revenge   11%  █           5t  │
│                                │
│  Based on journaled trades only│
│  [View full breakdown →]       │
│                                │
├────────────────────────────────┤
│  TRADING PERSONA               │
│  ────────────────────────────  │
│  "Reactive Scalper"            │
│  You react quickly to price    │
│  movement and trade in bursts. │
│  Watch out: Revenge risk,      │
│  overtrading after losses.     │
│                                │
├────────────────────────────────┤
│  BTST ACTIVITY                 │
│  ────────────────────────────  │
│  4 overnight trades · 25% WR   │
│  Avg P&L: -₹620 · 2 reversals  │
│  [View BTST trades →]          │
│                                │
├────────────────────────────────┤
│  BEHAVIOR SCORE TREND          │
│  ────────────────────────────  │
│  [Line chart — 90-day history] │
│  Current: 74 · Trend: ↑        │
│  This is a trend indicator for │
│  self-tracking, not a grade.   │
│                                │
└────────────────────────────────┘
```

**Score null state (< 5 trades):** "Behavioral analysis needs 5+ trades. — shown when available."

### Tab: Trades

```
┌────────────────────────────────┐
│  [All ▼]  [30d ▼]  [Pattern ▼] │
├────────────────────────────────┤
│                                │
│  ┌──────────────────────────┐  │
│  │ Mar 27 · NIFTY 24500CE   │  │
│  │ +₹1,100 · 22m · 50 qty   │  │
│  │ Emotion: Calm ·           │  [✎filled]
│  └──────────────────────────┘  │
│                                │
│  ┌──────────────────────────┐  │
│  │ Mar 27 · BANKNIFTY PE    │  │
│  │ -₹550 · 14m · 25 qty     │  │
│  │ [Revenge] · Anxious ·    │  [✎filled]
│  └──────────────────────────┘  │
│                                │
│  ┌──────────────────────────┐  │
│  │ Mar 26 · NIFTY 24400PE   │  │
│  │ -₹975 · 8m · 75 qty      │  │
│  │ [FOMO] ·                 │  [✎]  ← not journaled
│  └──────────────────────────┘  │
│                                │
│  [Load more]                   │
└────────────────────────────────┘
```

Tapping a trade card opens a bottom sheet with full detail (entry/exit prices, times, strategy if detected) and the journal icon at the top of the sheet.

### Tab: Timing

```
┌────────────────────────────────┐
│  P&L BY HOUR OF DAY            │
│  [Bar chart — tap for value]   │
│                                │
│  09:15 09:30 10  11  12  13   │
│                                │
│  Your best window: 10:00–11:30 │
│  First 15 min: -₹2,400/month   │
│                                │
│  WIN RATE BY HOUR              │
│  [Bar chart]                   │
│                                │
│  P&L BY DAY OF WEEK            │
│  [Compact bar chart]           │
└────────────────────────────────┘
```

### Tab: Progress

```
┌────────────────────────────────┐
│  Max 10 trades/day             │
│  ██████████  5/5 this week     │
│  Streak: 7d · Best: 12d        │
│                                │
│  No trading 9:15–9:30          │
│  ████████░░  4/5 this week     │
│  Missed: Tuesday               │
│  Streak: 4d · Best: 9d         │
│                                │
│  LAST 30 DAYS                  │
│  Mo Tu We Th Fr                │
│  ●  ●  ●  ●  ●                │
│  ●  ●  ○  ●  ●                │
│  ●  ●  ●  ●  ●                │
│  ●  ●  ●  ●  —                │
│                                │
│  [View / edit goals →]         │
└────────────────────────────────┘
```

### Tab: Summary

Last tab — P&L overview is available in Kite. This satisfies traders who want it without leading with it.

```
┌────────────────────────────────┐
│  ┌───────────┬───────────┐     │
│  │ Total P&L │ Win Rate  │     │
│  │ +₹45,200  │ 64%       │     │
│  ├───────────┼───────────┤     │
│  │ Trades    │ Avg Hold  │     │
│  │ 142       │ 38m       │     │
│  └───────────┴───────────┘     │
│                                │
│  P&L OVER TIME                 │
│  [Line chart — tap for value]  │
│                                │
│  F&O: 78%  ·  Equity: 22%     │
│  MIS: 61%  ·  NRML: 39%       │
│                                │
│  [View full breakdown →]       │
└────────────────────────────────┘
```

---

## 4. AI Coach

**What it is:** Full-screen chat on mobile. Identical data context and AI capabilities as web — this is not a reduced version. The web's left context panel condenses into a collapsible context bar at the top. The bar is collapsed by default during market hours (the trader is typing, not reviewing stats). The emotions section in the expanded context is the key differentiator — it shows the coach has read the trader's own journal entries.

**UI/UX (mobile-specific):** Single-line context bar collapsed by default. Tap to expand to the full Today's Brief (4–5 lines including journal-reported emotions). Starter prompt chips are full-width when no conversation history exists. Input pinned above keyboard via Capacitor adjustResize mode — never buried. User messages: right-aligned bordered bubbles, max 75% screen width. AI responses: full-width left-aligned plain text with [TM] avatar circle. Streaming renders word-by-word. "New chat" is a "+" icon in the header.

```
┌────────────────────────────────┐
│  AI Coach      [▾ Brief]   [+] │
├────────────────────────────────┤
│  6 trades · +₹1,240 · 2 alerts │  ← collapsed context, 1 line
├────────────────────────────────┤
│                                │
│  [when no history:]            │
│  ┌──────────────────────────┐  │
│  │ How was my behavior today│  │
│  └──────────────────────────┘  │
│  ┌──────────────────────────┐  │
│  │ What patterns am I showing  │
│  └──────────────────────────┘  │
│  ┌──────────────────────────┐  │
│  │ I just made a bad trade  │  │
│  └──────────────────────────┘  │
│  ┌──────────────────────────┐  │
│  │ Help me prep for tomorrow│  │
│  └──────────────────────────┘  │
│                                │
│  ─────── [conversation] ─────  │
│                                │
│          ┌────────────────┐    │
│          │ Why do I keep  │    │  ← user, right-aligned
│          │ overtrading?   │    │
│          └────────────────┘    │
│                                │
│  [TM]  Looking at your data,   │  ← AI, left-aligned
│        I see that 9 of 12      │
│        overtrading events      │
│        happened on days where  │
│        your first trade was a  │
│        loss. Does that match   │
│        your experience? [📎]   │
│                                │
├────────────────────────────────┤
│  ┌──────────────────────────┐  │
│  │  Ask anything...       ↑ │  │  ← pinned above keyboard
│  └──────────────────────────┘  │
└────────────────────────────────┘
```

### Expanded Context Bar

Tap the collapsed bar to expand Today's Brief. Contains journal-reported emotions — this shows the coach is reading from the trader's own words.

```
┌────────────────────────────────┐
│  AI Coach      [▴ Collapse][+] │
│  ────────────────────────────  │
│  6 trades since 9:15 AM        │
│  Net P&L: +₹1,240 (unrealized) │
│  2 observations today          │
│                                │
│  Emotions from your journal:   │
│  Calm (3) · Anxious (2)        │
│  (Anxious trades: 28% win rate)│
│                                │
│  Context: 30-day history +     │
│  your journal entries loaded   │
├────────────────────────────────┤
│  [conversation area]           │
```

### Save to Journal

Each AI message has a bookmark icon ([📎]). Tapping saves the insight as a coach session note. Icon changes to ✓ when saved.

### Touch Interactions

- Tap context bar → expands/collapses
- Tap starter prompt chip → sends that message
- Tap "+" in header → new chat session (previous preserved)
- Long-press a message → copy text to clipboard

---

## 5. My Patterns

**What it is:** Behavioral identity screen on mobile. The web's two-panel layout (list + detail side by side) collapses to a vertical accordion of pattern cards. The emotional correlation section inside each expanded card — powered by journal data — is the most valuable content on this screen.

**UI/UX (mobile-specific):** Single-column card layout. Each pattern card has a header row (severity dot, pattern name, occurrence count, last seen). Collapsed by default. Tapping expands to show: the narrative paragraph, emotional correlation from journal data, frequency sparkline (7 weeks), timing context, and worst instances. One card open at a time — opening a new card closes the previous one. Not-Detected section at the bottom uses lighter type weight and smaller text — present but not prominent.

A live status banner at the very top of the screen shows current risk state in minimal form.

```
┌────────────────────────────────┐
│  My Patterns                   │
├────────────────────────────────┤
│  ┌──────────────────────────┐  │
│  │ ● Safe · 8 trades · 0    │  │  ← live status banner
│  │ consecutive losses        │  │
│  └──────────────────────────┘  │
├────────────────────────────────┤
│                                │
│  ┌──────────────────────────┐  │  ← collapsed card
│  │ ● Overtrading  12×  2d  │  │
│  │                    [▸]   │  │
│  └──────────────────────────┘  │
│                                │
│  ┌──────────────────────────┐  │  ← expanded card
│  │ ● Revenge Trading  4×    │  │
│  │                    [▾]   │  │
│  │                          │  │
│  │ "You tend to re-enter    │  │
│  │  within minutes of a     │  │
│  │  loss, especially in     │  │
│  │  high-volatility F&O.    │  │
│  │  In the last 30 days,    │  │
│  │  4 of 4 events followed  │  │
│  │  a loss ≥ ₹500."         │  │
│  │                          │  │
│  │  EMOTIONAL CORRELATION   │  │
│  │  (from your journal)     │  │
│  │  Anxious    · 4 of 4 ×  │  │
│  │  Revenge f. · 3 of 4 ×  │  │
│  │  FOMO       · 1 of 4 ×  │  │
│  │                          │  │
│  │  Frequency (90 days):    │  │
│  │  ▁▂▁▃▂▄▂▁  (weekly)      │  │
│  │                          │  │
│  │  Usually: post 10:00 AM  │  │
│  │                          │  │
│  │  Worst: Mar 15  -₹2,800  │  │
│  │  [See related trades →]  │  │
│  └──────────────────────────┘  │
│                                │
│  NOT DETECTED (3)              │  ← lighter text
│  ○ Position Sizing             │
│  ○ Winning Streak OC           │
│  ○ Strategy Pivot              │
│                                │
└────────────────────────────────┘
```

### Emotional Correlation Note

If fewer than 5 journal entries exist for a pattern: "Add journal entries to see emotional correlation for this pattern."

The Not-Detected section is labeled "Not Detected (3)" — not "N/A" or empty. These are positive signals: the system has not found these patterns in the trader's behavior.

### Touch Interactions

- Tap card header → toggles expansion (auto-closes any other open card)
- Tap "See related trades →" → Analytics → Trades tab filtered to that pattern
- Tap a not-detected pattern → brief explanation of what the pattern looks like when triggered

---

## 6. Blowup Shield

**What it is:** Counterfactual protection record. The screen answers: "What has the system's protection actually done for me?" Not estimates — actual market prices 30 minutes after each alert, compared to what would have happened. Includes honest disclosure when the market recovered and heeding the alert cost opportunity. No red anywhere on this screen.

**UI/UX (mobile-specific):** "Total Capital Defended" in large green type at the top. Shield Score and Heeded Streak as two secondary tiles. A compact vertical list of protection events below. Each event is a collapsed card that expands to show the full counterfactual breakdown. This is one of the few screens where depth is appropriate even on mobile — the trader is reading this in review mode, not in a 10-second glance.

```
┌────────────────────────────────┐
│  Blowup Shield                 │
├────────────────────────────────┤
│                                │
│  Total Capital Defended        │
│  ₹41,200                       │  ← large, success green
│  across 12 events              │
│                                │
│  ┌────────────┬────────────┐   │
│  │ Shield Score│ Heeded     │   │
│  │ 73%         │ Streak: 8  │   │
│  │ 9/12 heeded │ consecutive│   │
│  └────────────┴────────────┘   │
│                                │
│  9 of 12 events verified with  │
│  real T+30 market data.        │
│                                │
├────────────────────────────────┤
│  PROTECTION EVENTS             │
│                                │
│  ┌──────────────────────────┐  │
│  │ Mar 27 · CIRCUIT BREAK   │  │
│  │ [Heeded ✓]  [Verified ✨] │  │
│  │ Session Meltdown          │  │
│  │ 42% of daily capital lost │  │
│  │                          │  │  ← tap to expand
│  │ [Expand counterfactual ▸] │  │
│  └──────────────────────────┘  │
│                                │
│  ┌──────────────────────────┐  │  ← expanded
│  │ Mar 22 · COOLDOWN        │  │
│  │ [Heeded ✓]  [Verified ✨] │  │
│  │ Consecutive Loss Streak  │  │
│  │ 3rd consecutive loss.    │  │
│  │                          │  │
│  │  Your P&L (realized):    │  │
│  │  -₹5,400                 │  │
│  │  If held to T+30:        │  │
│  │  -₹9,600                 │  │
│  │  Net defended:           │  │
│  │  +₹4,200  ✨             │  │  ← success green
│  └──────────────────────────┘  │
│                                │
│  ┌──────────────────────────┐  │
│  │ Mar 15 · COOLDOWN        │  │
│  │ [Ignored ✗]  [Verified ✨]│  │
│  │ Revenge Trade            │  │
│  │ Re-entry BANKNIFTY 6m    │  │
│  │ after loss.              │  │
│  │                          │  │
│  │  P&L (continued trading):│  │
│  │  -₹3,200                 │  │
│  │  If stopped at alert:    │  │
│  │  -₹1,400                 │  │
│  │  Additional loss from    │  │
│  │  ignoring: -₹1,800       │  │  ← regular text, not red
│  └──────────────────────────┘  │
│                                │
│  ┌──────────────────────────┐  │
│  │ Mar 10 · COOLDOWN        │  │
│  │ [Heeded ✓]  [Verified ✨] │  │
│  │ Opening 5-min Trap       │  │
│  │                          │  │
│  │  Your P&L (realized):    │  │
│  │  -₹2,100                 │  │
│  │  If held to T+30:        │  │
│  │  -₹800 (market recovered)│  │
│  │                          │  │
│  │  Note: Heeding this alert│  │
│  │  cost ₹1,300 vs holding. │  │
│  │  This is shown honestly. │  │
│  │  Not all alerts are right.│  │
│  └──────────────────────────┘  │
│                                │
│  [View full history →]         │
└────────────────────────────────┘
```

### Design Notes

- No red anywhere on this screen. "Additional loss from ignoring" is displayed in regular text weight, regular color — it is information, not alarm.
- The honesty note ("This is shown honestly. Not all alerts are right.") is a design requirement. It builds trust. Removing it turns the screen into marketing.
- "Capital Defended" in large success green is the one place on the entire screen where color communicates outcome.
- Shield Score uses: green ≥70%, amber 40–69%, no specific alarmed treatment for low scores.

### Touch Interactions

- Tap event card → expands counterfactual detail
- Tap [View full history →] → full history list in a bottom sheet with date filters

---

## 7. Session Limits

**What it is:** Status screen for the trader's self-set rules. Renamed from "Danger Zone" — these are the trader's own guardrails, not an emergency room. Shows whether configured limits are within bounds or active. Calm and factual regardless of state.

**UI/UX (mobile-specific):** The status banner is the first thing visible. When within bounds: green-left-border, one short line. When a limit is active: amber-left-border card with the explicit statement that the trader can still trade in Zerodha. Below the banner: configured rules as a compact list. Below that: this week's events. No tab bar on mobile — all three sections stack vertically (status → limits → history), same screen, scroll to see all.

```
┌────────────────────────────────┐
│  Session Limits                │
├────────────────────────────────┤
│                                │
│  ┌──────────────────────────┐  │
│  │ ● All limits within     │  │  ← green-left-border
│  │ bounds today.           │  │
│  └──────────────────────────┘  │

When a limit is active:

│  ┌──────────────────────────┐  │
│  │  Cooldown Active         │  │  ← amber-left-border
│  │  Daily loss limit reached│  │
│  │  Triggered: 11:23 AM     │  │
│  │  Until: market close     │  │
│  │                          │  │
│  │  You can still trade in  │  │
│  │  Zerodha Kite.           │  │
│  └──────────────────────────┘  │
│                                │
├────────────────────────────────┤
│  YOUR LIMITS                   │
│  ─────────────────────────    │
│  Daily max loss   ₹5,000   ●  │  ← green dot = within bounds
│  Max trades/day   15       ●  │
│  Max position     ₹50k     ●  │
│  Cooldown rule    30 min   ●  │
│                                │
│  Daily loss:  ₹4,980 / ₹5,000  │
│  ████████████████████░  99%   │  ← this line only when approaching
│                                │
├────────────────────────────────┤
│  THIS WEEK                     │
│  ─────────────────────────    │
│  Mar 27 · Cooldown · 3 losses  │
│  Mar 25 · Circuit Break        │
│                                │
│  [Edit in Settings →]          │
└────────────────────────────────┘
```

### Design Notes

- The amber-left-border card is the only visual treatment for an active limit. No full-screen warning, no red, no pulsing. A bordered card with calm text.
- "You can still trade in Zerodha Kite." — this line is required when a limit is active. It prevents the screen from feeling like a restriction.
- Progress bars on the limits list only appear for limits that are >60% approached. Below that threshold, just a green dot.

---

## 8. Goals

**What it is:** Behavioral commitment tracker. The trader's self-set goals, weekly progress, and 30-day consistency calendar. Goal changes are gated with a 24-hour cooldown — this prevents impulsive mid-session modifications.

**UI/UX (mobile-specific):** Full-width goal cards. Each card shows: goal text, this week's day-by-day status (Mon–Fri checkmarks), progress bar for the month, current/best streak. The three-dot menu on each card opens a bottom sheet with Edit, Pause, and Delete options. Editing shows a reason input and displays a pending-change notice instead of applying immediately. The 30-day calendar heatmap is a compact grid at the bottom of the screen.

```
┌────────────────────────────────┐
│  Goals                         │
│                          [+Add]│
├────────────────────────────────┤
│                                │
│  ┌──────────────────────────┐  │
│  │ Max 10 trades/day    [⋯] │  │
│  │ Mo ✓  Tu ✓  We ✓  Th ✓  │  │
│  │ ██████████  5/5 this wk  │  │
│  │ Streak: 7d · Best: 12d   │  │
│  └──────────────────────────┘  │
│                                │
│  ┌──────────────────────────┐  │
│  │ No trades 9:15–9:30  [⋯] │  │
│  │ Mo ✓  Tu ✓  We ✗  Th ✓  │  │  ← ✗ shows the miss
│  │ ████████░░  4/5 this wk  │  │
│  │ Missed: Wednesday        │  │
│  │ Streak: 4d · Best: 9d    │  │
│  └──────────────────────────┘  │
│                                │
│  [+ Add commitment]            │
│                                │
├────────────────────────────────┤
│  LAST 30 DAYS                  │
│  Mo Tu We Th Fr                │
│  ●  ●  ●  ●  ●                │
│  ●  ●  ○  ●  ●                │
│  ●  ●  ●  ●  ●                │
│  ●  ●  ●  ●  —                │
└────────────────────────────────┘
```

### 24-Hour Cooldown Gate

Tapping [⋯] → "Request change" shows:
```
Change "Max 10 trades/day" to:
[8                         ]

Why are you changing this?
[Too many impulse trades    ]

[Request change]

This will apply from tomorrow.
Changes take 24 hours to prevent
impulsive mid-session adjustments.
```

After requesting: a notice appears on the goal card:
```
⏱ Change pending: Max 10 → Max 8
   Applies: tomorrow (Mar 29)
```

### Touch Interactions

- Tap [⋯] on card → bottom sheet: View history / Request change / Pause / Delete
- Tap [+ Add commitment] → inline form slides in below
- Long-press calendar dot → tooltip showing which goals were missed that day

---

## 9. Portfolio Radar

**What it is:** Position concentration and options risk analysis. Used before adding a new position to check if the book is already too concentrated, and to monitor options-specific risks. Shows strike, breakeven, gap to breakeven, premium decay, and days to expiry per position.

**UI/UX (mobile-specific):** Single-column layout. Position cards come first — each card shows the standard P&L data AND the options-specific metrics below it. Concentration analysis follows as horizontal bar charts. A brief warnings section shows any thresholds exceeded. Directional skew and margin utilization at the bottom.

```
┌────────────────────────────────┐
│  Portfolio Radar       [⟳ Sync]│
├────────────────────────────────┤
│                                │
│  Total exposure: ₹1.8L · 8 pos │
│                                │
├────────────────────────────────┤
│  POSITIONS                     │
│                                │
│  ┌──────────────────────────┐  │
│  │ NIFTY 24500 CE · Long    │  │
│  │ 50 qty · MIS             │  │
│  │ Entry: ₹140 · LTP: ₹162  │  │
│  │ P&L: +₹1,100 (+15.7%)    │  │
│  │ ──────────────────────── │  │
│  │ Strike: 24500            │  │
│  │ Breakeven: ₹154          │  │
│  │ Gap to BE: -₹8 (ITM) ✓  │  │  ← green = favorable
│  │ Premium decay: -₹12/day  │  │
│  │ Expiry: 3d  ⚠            │  │  ← amber = close to expiry
│  └──────────────────────────┘  │
│                                │
│  ┌──────────────────────────┐  │
│  │ BANKNIFTY 52000 PE · Long│  │
│  │ 25 qty · MIS             │  │
│  │ Entry: ₹220 · LTP: ₹198  │  │
│  │ P&L: -₹550 (-10.0%)      │  │
│  │ ──────────────────────── │  │
│  │ Strike: 52000            │  │
│  │ Breakeven: ₹194          │  │
│  │ Gap to BE: +₹4 (OTM)    │  │
│  │ Premium decay: -₹18/day  │  │
│  │ Expiry: 3d  ⚠            │  │
│  └──────────────────────────┘  │
│                                │
├────────────────────────────────┤
│  CONCENTRATION                 │
│  ─────────────────────────    │
│  BY EXPIRY WEEK                │
│  Mar 28  ████████ 45%  ⚠      │
│  Apr 4   ██████   32%          │
│  Apr 11  ████     23%          │
│                                │
│  BY UNDERLYING                 │
│  BANKNIFTY  ████████ 38%  ⚠   │
│  NIFTY      █████    22%       │
│  RELIANCE   ████     18%       │
│  [View all →]                  │
│                                │
│  ⚠ 45% in one expiry week      │
│  ⚠ 38% in BANKNIFTY            │
│                                │
├────────────────────────────────┤
│  Long: 65%  ·  Short: 35%     │
│  Margin: ₹94K / ₹1.6L  =  59% │
│                                │
│  GTT ORDERS: 3 active          │
│  [View →]                      │
└────────────────────────────────┘
```

### Days to Expiry Color

- ≥5 days: green
- 3–4 days: amber ⚠
- ≤2 days: red ⚠⚠ — one of the few justified uses of red in the app (actual financial urgency)

### Touch Interactions

- Tap position card → expands to show GTT orders linked to that position
- Tap [View all →] in concentration charts → full breakdown in a bottom sheet
- Tap "View →" on GTT orders → full GTT list in a bottom sheet

---

## 10. Reports

**What it is:** Generated periodic reports. Three types: Morning Brief (pre-session readiness), End-of-Day (behavioral narrative + emotional journey), Weekly Summary (trend overview). Tapping a report opens a 90vh bottom sheet with full content. The Emotional Journey timeline and the AI behavioral narrative are the most important content — the mobile sheet gives them space.

**UI/UX (mobile-specific):** Three tab pills at the top: EOD, Morning, Weekly. Report cards below show date, P&L, and trade count — no behavioral score on the card. Tapping a card opens a 90vh bottom sheet. Inside the EOD report sheet: summary stats line, Emotional Journey timeline (each trade with emoji + P&L in chronological order), key patterns, key lessons, then the AI behavioral narrative in comfortable reading type. The Morning Brief sheet shows readiness score and pre-session checklist.

```
┌────────────────────────────────┐
│  Reports                       │
├────────────────────────────────┤
│  [EOD]  [Morning]  [Weekly]    │
├────────────────────────────────┤
│                                │
│  ┌──────────────────────────┐  │
│  │ Today · Mar 28           │  │
│  │ +₹3,450  ·  8 trades     │  │  ← no score on the card
│  └──────────────────────────┘  │
│                                │
│  ┌──────────────────────────┐  │
│  │ Yesterday · Mar 27       │  │
│  │ -₹1,200  ·  12 trades    │  │
│  └──────────────────────────┘  │
│                                │
│  ┌──────────────────────────┐  │
│  │ Weekly · Mar 24–28       │  │
│  │ +₹8,600  ·  38 trades    │  │
│  └──────────────────────────┘  │
└────────────────────────────────┘
```

### EOD Report — Bottom Sheet

```
[90vh bottom sheet slides up]

┌────────────────────────────────┐
│  ─────  ← drag handle          │
│  Mar 28 — End of Day  [PDF ↓] │
│  ─────────────────────────    │
│  +₹3,450  ·  8 trades  ·  67% WR
│                                │
│  TODAY'S EMOTIONAL JOURNEY     │
│  ─────────────────────────    │
│  09:23 AM  😤 FOMO entry        │
│             NIFTY CE:  -₹975   │
│                                │
│  09:58 AM  😤 Revenge trade     │
│             BANKNIFTY: -₹550   │
│                                │
│  10:45 AM  😎 Calm entry        │
│             RELIANCE:  +₹210   │
│                                │
│  11:12 AM  😊 Confident         │
│             NIFTY CE:  +₹1,100 │
│                                │
│  ─────────────────────────    │
│  PATTERNS DETECTED TODAY       │
│  Overtrading  ·  10:34 AM      │
│  Revenge risk ·  09:58 AM      │
│                                │
│  KEY LESSONS                   │
│  💡 Calm trades won 3/4 (75%)  │
│  ⚠  Opening FOMO cost -₹975   │
│  → Tomorrow: wait 15 min       │
│                                │
│  BEHAVIORAL NARRATIVE          │
│  ─────────────────────────    │
│  Today showed a clear pattern: │
│  your opening-session trades   │
│  were emotionally driven (FOMO │
│  and Revenge entries), while   │
│  your mid-session trades were  │
│  controlled and profitable...  │
│                                │
│  [full narrative continues]    │
│  [reads comfortably, 15px/1.6] │
└────────────────────────────────┘
```

### Morning Brief — Bottom Sheet

```
┌────────────────────────────────┐
│  ─────  ← drag handle          │
│  Mar 28 — Morning Brief        │
│  ─────────────────────────    │
│  READINESS SCORE               │
│  82/100  ●  Good session pred. │
│                                │
│  PRE-TRADING CHECKLIST         │
│  ✓ Reviewed yesterday's journal│
│  ○ Watch: Overtrading risk     │
│  ○ Watch: Revenge risk         │
│  ○ Set max trades: 10          │
│  ○ Today is weekly expiry day  │
│                                │
│  WATCH OUT TODAY               │
│  · Expiry day — volatile 14–15h│
│  · Overtraded 3 of 4 recent    │
│    expiry days                 │
│  · 9:15–9:30 win rate: 23%     │
│                                │
│  YESTERDAY                     │
│  -₹1,200 · 12 trades           │
│  Erratic afternoon session     │
└────────────────────────────────┘
```

### Touch Interactions

- Tap report card → opens 90vh bottom sheet
- Swipe left on report card → reveals "↓ Download PDF" action (blue, 80px)
- Drag down on bottom sheet → dismisses
- Tap [PDF ↓] in sheet header → generates and downloads PDF

---

## 11. Settings

**What it is:** Configuration hub on mobile. Standard Android settings pattern — grouped list, each item navigates into a sub-screen.

**UI/UX (mobile-specific):** Single-column grouped list. Section headers in small uppercase muted text. Each row: label on the left, current value or right arrow on the right, 48px minimum tap target. Tapping navigates to a sub-screen that slides in from the right. Each sub-screen has a "Save" button fixed at the bottom of the content area. Back arrow in top-left returns to the settings list. Destructive actions (Disconnect Zerodha, Delete all data) live in the Account sub-screen, separated by a divider, shown in destructive red text.

```
┌────────────────────────────────┐
│  Settings                      │
├────────────────────────────────┤
│  ACCOUNT                       │
│  Profile                ZA1234 │  ▸
│  Risk Limits              5 set│  ▸
│  Notifications         Push ON │  ▸
│  ──────────────────────────    │
│  PREFERENCES                   │
│  Account                       │  ▸
│  Appearance        Light mode  │  ▸
│  Personalization               │  ▸
│  ──────────────────────────    │
│  LEGAL                         │
│  Privacy Policy                │  ▸
│  Terms of Service              │  ▸
└────────────────────────────────┘
```

**Risk Limits sub-screen:**
```
┌────────────────────────────────┐
│  ←  Risk Limits                │
├────────────────────────────────┤
│                                │
│  Max daily loss                │
│  [₹5,000                     ] │
│  ~4.2% of your trading capital │
│                                │
│  Max trades per day            │
│  [15                          ]│
│                                │
│  Max position size             │
│  [₹50,000                    ] │
│                                │
│  Cooldown after N losses       │
│  [3 losses → 30 min          ▼]│
│                                │
│  High-risk time warnings       │
│  [● ON]  9:15 AM – 9:30 AM    │
│  [● ON]  3:00 PM – 3:30 PM    │
│                                │
├────────────────────────────────┤
│  [Save]                        │
└────────────────────────────────┘
```

**Notifications sub-screen:**
```
┌────────────────────────────────┐
│  ←  Notifications              │
├────────────────────────────────┤
│  Push notifications     [● ON] │
│  In-app toasts          [● ON] │
│  Sound                  [○ OFF]│
│                                │
│  WHATSAPP (Alert Guardian)     │
│  WhatsApp alerts        [○ OFF]│
│  Guardian number               │
│  [+91                        ] │
│                                │
│  QUIET HOURS                   │
│  Quiet after    [10:00 PM   ▼] │
│  Until          [ 8:00 AM   ▼] │
├────────────────────────────────┤
│  [Save]                        │
└────────────────────────────────┘
```

---

## 12. Guardrails

**What it is:** Read-only view of all configured limits. Shows what rules are set and whether they're being met today. Accessible from Session Limits ("View configured rules →") or from the More sheet.

**UI/UX (mobile-specific):** Simple list screen. No visual drama. Section headers group the rules. Each rule: description on the left, configured value in the center, green dot on the right (amber if approaching). A compliance bar shows how many rules were met today. Edit link at the bottom sends to Settings → Risk Limits.

```
┌────────────────────────────────┐
│  Guardrails                    │
├────────────────────────────────┤
│  DAILY RULES                   │
│  Max daily loss   ₹5,000   ●  │
│  Max trades/day   15       ●  │
│  Max position     ₹50k     ●  │
│                                │
│  COOLDOWN RULES                │
│  After 3 losses → 30 min   ●  │
│  After max loss → paused   ●  │
│                                │
│  HIGH-RISK WINDOWS             │
│  9:15 AM – 9:30 AM         ●  │
│  3:00 PM – 3:30 PM         ●  │
│                                │
│  TODAY: 5 of 5 rules met       │
│  ████████████████████          │
│                                │
│  [Edit rules in Settings →]    │
└────────────────────────────────┘
```

---

## Journal Sheet (TradeJournalSheet)

The journal sheet is not a separate navigation screen — it is a bottom sheet that slides up from any screen where trade rows appear (Home, Analytics → Trades tab). The trade context is locked at the top of the sheet.

```
┌────────────────────────────────┐
│  ─────  ← drag handle          │
│  NIFTY 24400PE · -₹975 · 8m   │  ← locked trade context
│  ─────────────────────────    │
│                                │
│  How did you feel before?      │
│  (multi-select up to 3)        │
│  [Calm] [Anxious] [Confident]  │
│  [Distracted] [Fearful]        │
│  [FOMO] [Revenge] [Euphoric]   │
│  [Neutral]                     │
│                                │
│  Did you follow your plan?     │
│  [Yes]  [Partially]  [No]      │
│                                │
│  If No/Partially — why?        │
│  [Fear of loss] [Impulse]      │
│  [News event]   [FOMO]         │
│                                │
│  Why did you exit?             │
│  [Target hit] [Stop hit]       │
│  [Intuition]  [Fear]           │
│  [Boredom]    [FOMO]           │
│                                │
│  Setup quality                 │
│  ★ ★ ★ ☆ ☆  (tap to rate)    │
│                                │
│  Would repeat this trade?      │
│  [Yes]  [Maybe]  [No]          │
│                                │
│  Market condition               │
│  [Trending] [Ranging] [Volatile│
│  [Opening]  [Closing]          │
│                                │
│  Notes (optional)              │
│  [Type anything...          ]  │
│                                │
│  ─────────────────────────    │
│  [Skip]              [Save →] │
└────────────────────────────────┘
```

The journal takes 30–60 seconds to fill. All fields except the first emotion select are optional. Chip selects require one tap each. Skip discards without saving and closes the sheet. Save stores via API and shows a "Journal saved" toast. The trade row journal icon changes to filled (✎ → ✎filled) immediately after save.

---

## Touch Interaction Patterns

### Bottom Sheets

Used for: trade detail + journal, report reading, More nav sheet, position detail, full history views, expanded chart breakdowns, GTT orders.

```
Opens: slides up from bottom, 280ms ease-out cubic
Drag handle: 4×36px, centered at top, rounded
Dismiss: drag down past 35% of height, or tap backdrop
Heights:
  Default: 65vh — for detail views
  Report / journal: 90vh — for reading-heavy content
  More sheet: auto-height (content determines)
Backdrop: rgba(0,0,0,0.4), tap to dismiss
Spring physics: slight overshoot on open, snap back on dismiss
```

### Pull-to-Refresh

Supported on: Home, Patterns, Analytics, Reports.

```
Standard native gesture via Capacitor plugin
Brand-colored spinner (16px) appears at top during refresh
Triggers full data fetch from backend
No full page reload — component-level refresh only
Minimum visible time: 400ms (prevents flash for instant responses)
```

### Swipe Actions

- Observation card: swipe left → reveals "✓ Acknowledge" (green, 80px wide)
- Report card: swipe left → reveals "↓ Download" (blue, 80px wide)
- Protection event card (Blowup Shield): swipe right → reveals "↓ Download details" (not critical, secondary)

### Long-Press

- Trade card: copy symbol name to clipboard, "Copied" toast
- Observation card: quick-acknowledge without opening
- Position card on Home: "View in Kite" shortcut
- Calendar dot on Goals: tooltip showing which goals were missed that day

---

## Responsive Breakpoints

| Width | Navigation | Layout | Data display | Overlays |
|-------|-----------|--------|-------------|---------|
| < 768px (mobile) | Bottom nav 5 tabs | Single column | Cards, 2-line rows | Bottom sheets |
| 768–1023px (tablet) | Icon sidebar 56px | 2-column grid where applicable | Simplified tables | Bottom sheets |
| ≥ 1024px (desktop) | Full sidebar 208px | Multi-column with panels | Full tables | Right-side panels |

The Capacitor Android build targets the mobile breakpoint exclusively. The 768–1023 breakpoint handles Android foldables (Z Fold, OnePlus Open) and large-screen Android devices.

---

## Android-Specific Notes

### Safe Areas

```css
padding-top: env(safe-area-inset-top);        /* camera cutout */
padding-bottom: env(safe-area-inset-bottom);  /* home indicator */
```

The bottom navigation bar adds `padding-bottom: env(safe-area-inset-bottom)` internally so its content sits above the system home indicator bar.

### Back Button Behavior

- Sub-screens (Settings sub-screens, drill-down views): back = navigate up one level
- Bottom sheets open: back = dismiss the sheet
- On a main tab (Home, Patterns, Analytics, Coach): back = minimize app (Android default)
- Modals (journal sheet, confirmation dialogs): back = close modal

### Keyboard Behavior

All text input fields use `adjustResize` via Capacitor — the content area resizes and the input field stays visible above the keyboard. The AI Coach input, journal notes field, and Settings text inputs all use this. Never use `adjustPan` (it shifts the entire page and breaks fixed elements like the bottom nav).

### WebSocket Background Behavior

Capacitor apps are throttled or suspended when backgrounded. On foreground restore:
1. App checks if WebSocket is still connected
2. If disconnected: silent reconnect attempt
3. On reconnect: replay missed Redis Streams events from the last known cursor
4. Dashboard refreshes silently (no loading spinner unless the refresh takes >1 second)

The amber pulsing dot in the header (WebSocket reconnect indicator) appears only when reconnect takes >3 seconds.

### Performance Notes

- Analytics tabs are lazy-loaded — the Behavior tab loads on first open of Analytics, other tabs load on first selection
- Home screen positions table uses `React.memo` per row — only changed rows re-render on WebSocket updates
- Journal sheet is pre-mounted off-screen after the first open to eliminate the first-open delay
- Bottom sheets use `will-change: transform` and `translateZ(0)` for GPU-accelerated slide animations

---

*Web screen specifications: [02_WEB_SCREENS.md](./02_WEB_SCREENS.md)*
*User flows: [01_USER_FLOWS.md](./01_USER_FLOWS.md)*
*Components: [04_COMPONENTS.md](./04_COMPONENTS.md)*
