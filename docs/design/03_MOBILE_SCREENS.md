# TradeMentor AI — Mobile Screens

> Mobile-specific screen specs for the Android app (Capacitor wrapper around the React webapp). Every screen here is the same codebase as web — responsive Tailwind classes handle the layout shift. Mobile is not a stripped-down version of the web app; it has all the same features, presented with progressive disclosure.

**Guiding principle:** The critical number is always visible without scrolling. Context is one tap. The full table or chart is two taps.

**Viewport assumption:** 390px width (Pixel 7 / mid-range Android equivalent). Bottom nav is 64px fixed. Safe area padding applied for notch and home indicator.

---

## Mobile Navigation

```
Bottom nav (fixed, h-16, bg-card border-t border-border):

   [🏠]        [🔔]       [📊]        [💬]        [⋯]
  Home        Alerts    Analytics    Coach       More
  active                                       (sheet)
```

Active tab: `text-primary`. Inactive: `text-muted-foreground`.
Alerts badge: `bg-danger` pill, 16px, top-right of icon.

### "More" Bottom Sheet

Opens with a drag-up gesture or tap on the More tab.

```
─────────────────────  ← drag handle

PROTECTION
▸ My Patterns      [74]  ← behavior score badge
▸ Blowup Shield     [●]  ← risk level dot
▸ Guardrails
▸ Danger Zone
▸ Goals            [4d]  ← streak

TOOLS
▸ Portfolio Radar
▸ Reports

ACCOUNT
▸ Settings
```

---

## Screen Descriptions

A plain-language guide to what every mobile screen is, what it contains, and how it should look and feel on a phone. These are the same screens as the web app but adapted for a single column, touch interaction, and glanceability. Read this before the detailed wireframes below.

**Home (Dashboard)** — The screen a trader opens when they want to know where they stand. On mobile the entire hierarchy is vertical. The biggest number on the screen is the session P&L — it is always visible without scrolling. Two smaller tiles beneath it show margin available and unread alert count. Below the tiles, open positions appear as compact two-line rows: instrument name and quantity on the first line, P&L and percentage change on the second. Tapping a position row opens a bottom sheet with the full detail. A short strip at the bottom shows two recent alerts with a "View all" link. During market hours a small live indicator pulses in the header. After close the tiles update to show final numbers.

**Alerts** — A vertical feed of behavioral alerts. Three tab pills at the top switch between Live (unacknowledged), History, and Patterns. A row of horizontally scrollable filter chips above the feed lets the user filter by severity. Each alert is a full-width card with generous spacing so it's easy to tap. The acknowledge button sits at the bottom of each card and is tall enough to hit reliably with a thumb. Unread alerts have a faint highlight. Swiping left on a card reveals a quick-acknowledge action. The badge count on the Alerts tab in the bottom nav updates as alerts are acknowledged.

**Analytics** — All five analytics tabs accessible on mobile. Tab labels are a horizontal row of chips that scroll if they don't all fit. Each tab adapts its content: the Summary tab shows a two-by-two KPI grid with a simplified line chart below it. The Behavior tab puts the behavior score as the largest element with pattern rows below. The Trades tab replaces the web table with bordered cards — one per trade — that can be tapped to open a detail sheet. The Timing tab shows a simplified bar chart by hour. The Progress tab shows the calendar heatmap as a compact grid of dots. A "View full breakdown" link in each tab opens a bottom sheet with the complete data.

**AI Coach** — A full-screen chat layout. The web's left context panel becomes a single collapsed line at the top of the screen showing P&L, trade count, and behavior score. Tapping it expands to a few more stats. The chat fills the rest of the screen. When no conversation history exists, full-width starter prompt chips suggest what to ask. The keyboard pushes the input field up from the bottom so it is always visible when typing. AI responses stream in word by word. The new chat button is a small icon in the header. It behaves exactly like the web coach — same backend, same data context.

**My Patterns** — A vertical accordion of pattern cards. Each card starts collapsed showing just the pattern name, severity, and how many times it has occurred. Tapping a card expands it to show the narrative description, a small frequency chart, and the worst recent instance. Only one card is expanded at a time — opening a new one closes the previous one. Patterns that have never fired appear at the bottom in a quieter collapsed group. The screen is meant for reading and reflection after trading hours. There is no editing here — it is a mirror.

**Blowup Shield** — A short screen that communicates one thing: how much the system has protected this trader. A large green number at the top shows total capital saved. Two smaller stats on the row below show saves this month and the largest single save. Below that, a short vertical list of protection events shows type, date, and amount defended. A "View full history" link at the bottom opens a complete list in a bottom sheet. The screen is calm and positive. Nothing here is red or alarming — it is entirely about protection that already happened.

**Danger Zone** — The active-state status screen. A bordered status card occupies most of the visible screen. When everything is normal the card has a green left border and says "No active restrictions" in calm text. When a cooldown or circuit break is active the card has an amber left border, shows what triggered it, when it started, and when it ends. Below the card a short explanation clarifies that this is informational only and the trader can still place orders in Zerodha. A short history of the past week's events sits below. The screen must be immediately readable under stress — generous text size, no clutter.

**Goals** — A stack of goal cards with a small calendar heatmap at the bottom. Each card shows the goal description, a progress bar for the current week, and current and best streaks. The streak counter is in the page header as a subdued secondary stat. Adding a new goal opens an inline form that slides in below the last card. Tapping a goal card's header reveals edit, pause, and delete options without navigating away. The calendar heatmap shows the last 30 days as a grid of small colored dots — green for met, gray for missed. No badges, no level-ups. Just the record.

**Portfolio Radar** — A concentration risk screen built for a quick glance. The score and risk label are the largest elements at the top, with total exposure shown below. Two stacked bar charts follow — one for sector concentration and one for symbol concentration — showing the top three or four entries each. A "View full breakdown" link opens a bottom sheet with all entries. Below the charts a compact list shows each open position with its concentration percentage and a warning chip if it is high. The whole screen stacks cleanly in one column with no horizontal scrolling.

**Reports** — A vertical list of report cards filtered by type at the top with three pill tabs: EOD, Weekly, Monthly. Each card shows the date, headline P&L, and trade count. Tapping a card opens a tall bottom sheet that fills nearly the full screen. Inside the sheet the full report renders: summary stats at the top, key patterns, notable trades, comparison to previous period, and the AI narrative in readable body text. A PDF download button sits at the top of the sheet next to the report title. Pulling the sheet down dismisses it.

**Settings** — A grouped list screen using the standard Android settings pattern. Section headers divide the list into logical groups: profile, risk limits, notifications, account, and appearance. Each row shows a label and the current value or an arrow. Tapping a row navigates to a sub-screen specific to that section. Sub-screens have a back arrow in the header and a save button at the bottom. Destructive actions like disconnecting Zerodha or deleting data are in the Account sub-screen, visually separated from the rest, and shown in a red text color so they are clearly distinct.

**Guardrails** — A short read-only screen showing all active risk rules. Section headers group the rules: daily rules, cooldown rules, and high-risk time windows. Each rule shows its value and a status dot on the right. A compliance bar at the bottom shows how many rules were respected today as a filled progress bar with a fraction. A text link at the bottom directs the user to Settings to change any rule. The screen is designed to be read at a glance — it should fit on one screen without scrolling for most traders.

---

## Screen Index

1. [Home (Dashboard)](#1-home-dashboard)
2. [Alerts](#2-alerts)
3. [Analytics](#3-analytics)
4. [AI Coach](#4-ai-coach)
5. [My Patterns](#5-my-patterns)
6. [Blowup Shield](#6-blowup-shield)
7. [Danger Zone](#7-danger-zone)
8. [Goals](#8-goals)
9. [Portfolio Radar](#9-portfolio-radar)
10. [Reports](#10-reports)
11. [Settings](#11-settings)
12. [Guardrails](#12-guardrails)

---

## 1. Home (Dashboard)

**What it is:** The first screen the trader sees when opening the app. On mobile it does the same job as the web Dashboard — "How am I doing right now?" — but with a single-column layout and strong vertical hierarchy. The most critical number (session P&L) is the largest text on the screen and visible without any scrolling. Open positions appear immediately below. Recent alerts sit at the bottom. During market hours this is the screen a trader glances at between orders in Zerodha Kite.

**UI/UX (mobile-specific):** The P&L hero is a full-width row at the top — `text-3xl font-mono font-semibold` — with trade count and time as secondary text below it in `text-xs text-muted-foreground`. Two smaller tiles (Margin, Alerts) sit in a 2-column grid beneath the hero. Positions use a 2-line card format instead of a table: instrument name + quantity on line 1, P&L + percentage change on line 2. Tap a position row to open a bottom sheet with full detail. The Recent Alerts strip shows 2 compact rows with a "View all" link — it never expands inline. During market hours the amber pulsing dot + "LIVE" text appear in the header. No horizontal scrolling. No tables. Everything stacks vertically and flows naturally.

### Live (Market Hours)

```
┌────────────────────────────────┐
│  TradeMentor          ● LIVE  │  ← h-11 header
├────────────────────────────────┤
│                                │
│  Session P&L          +₹1,240  │  ← text-3xl font-mono
│  6 trades · 09:42 AM           │  ← text-xs text-muted-foreground
│                                │
├──────────────┬─────────────────┤
│  Margin      │  Alerts         │  ← 2 compact tiles
│  ₹42,500     │  [3] unread     │
│  available   │                 │
├──────────────┴─────────────────┤
│                                │
│  OPEN POSITIONS            2   │  ← section header
│  ──────────────────────────    │
│  NIFTY 24500CE                │
│  50 qty · +₹1,125   +15.9%   │  ← 2-line position row
│  ──────────────────────────    │
│  BANKNIFTY 52000PE            │
│  25 qty · -₹562    -10.2%    │
│                                │
│  RECENT ALERTS             2   │
│  ──────────────────────────    │
│  ⚡ Overtrading · 10:34 AM    │
│  ⚠  Revenge risk · 09:58 AM  │
│  [View all →]                  │
│                                │
└────────────────────────────────┘
       [Home] [Alerts] [Analytics] [Coach] [More]
```

### Market Closed

```
┌────────────────────────────────┐
│  TradeMentor      Market Closed│
├────────────────────────────────┤
│  Today P&L                     │
│  +₹3,450                       │  ← hero P&L
│  8 trades · Final              │
├──────────────┬─────────────────┤
│  This Week   │  Win Rate       │
│  +₹12,800    │  67%            │
├──────────────┴─────────────────┤
│  TODAY'S TRADES            8   │
│  [compact trade rows]          │
│  [View all in Analytics →]     │
│                                │
│  BEHAVIORAL FLAGS          2   │
│  [same alert rows]             │
└────────────────────────────────┘
```

**Touch interactions:**
- Tap position row → bottom sheet with full detail (LTP, unrealized P&L, product type)
- Pull to refresh → refreshes positions from backend
- Tap "View all" in alerts → navigates to Alerts tab

---

## 2. Alerts

**What it is:** The behavioral alert feed on mobile. Same three tabs as web (Live, History, Patterns), but the filter panel from the web becomes a row of horizontally scrollable chip filters at the top. Every alert is a full-width card. The experience on mobile is optimized for quickly reviewing and acknowledging alerts — tapping is the primary interaction, not hovering or clicking small buttons.

**UI/UX (mobile-specific):** Filter chips replace the right-side filter panel — they scroll horizontally above the feed in a single row. Alert cards are full-width with generous tap targets. The "Acknowledge" button is full-width at the bottom of each card (min-height 44px), making it easy to hit on mobile. Unacknowledged cards have the same faint `bg-primary/5` tint as web. Swipe-left on an alert card reveals a quick "Acknowledge" action. The unread count badge appears on the Alerts tab icon in the bottom nav. The Patterns tab shows summary cards stacked vertically, one per pattern type.

```
┌────────────────────────────────┐
│  Alerts                   [3]  │  ← badge count in header
├────────────────────────────────┤
│  [Live] [History] [Patterns]   │  ← 3 tab pills
├────────────────────────────────┤
│  Severity: [All][Crit][High][Med][Low]  ← horizontal scroll chips
├────────────────────────────────┤
│                                │
│  ┌──────────────────────────┐  │
│  │ ● NEW                    │  │
│  │ Overtrading              │  │
│  │ 8 trades in 2h           │  │
│  │ [NIFTY CE] [BANKNIFTY]   │  │
│  │ 10:34 AM · Est: -₹1,200  │  │
│  │ [Acknowledge]            │  │  ← full-width, h-11
│  └──────────────────────────┘  │
│                                │
│  ┌──────────────────────────┐  │
│  │ ✓ Acknowledged           │  │
│  │ Revenge trade risk       │  │
│  │ After -₹800 loss         │  │
│  │ 09:58 AM                 │  │
│  └──────────────────────────┘  │
│                                │
└────────────────────────────────┘
```

---

## 3. Analytics

**What it is:** The full analytics experience condensed for a single-column mobile layout. All five tabs are present. Charts are simplified (fewer tick marks, no chart legend inline — moved below). Tables become vertical cards. The date range selector sits in the page header. "View full breakdown →" links in each tab open a bottom sheet with the complete data for users who want to go deeper.

**UI/UX (mobile-specific):** Five tab pills in a horizontally scrollable row at the top (they don't all fit at 390px without scrolling). KPI tiles become a 2×2 grid. Charts are simplified — same data, fewer decorative elements, touch to reveal exact data point. Trade cards replace the web table: each completed trade is a bordered card with symbol, P&L, hold time, and quantity on 2 lines. The Behavior score card is the full-width focal element on its tab. The calendar heatmap in Progress tab shrinks to a 4×7 grid of dots.

### Tab: Summary

```
┌────────────────────────────────┐
│  Analytics  [Last 30 days ▼]  │
├────────────────────────────────┤
│  [Summary][Behavior][Trades]   │
│  [Timing][Progress]            │  ← scrollable chip tabs
├────────────────────────────────┤
│  ┌───────────┬────────────┐   │
│  │ Total P&L  │ Win Rate   │   │  ← 2×2 KPI grid
│  │ +₹45,200   │ 64%        │   │
│  ├───────────┼────────────┤   │
│  │ Trades     │ Avg Hold   │   │
│  │ 142        │ 38m        │   │
│  └───────────┴────────────┘   │
│                                │
│  P&L Over Time                 │
│  [simplified line chart]       │
│  [touch to see data point]     │
│                                │
│  [View full breakdown →]       │
└────────────────────────────────┘
```

### Tab: Behavior

```
┌────────────────────────────────┐
│  Behavior Score                │
│  74 / 100   "Disciplined"      │  ← focal element, text-3xl
│  ↑ +6 vs last month            │
│                                │
│  Patterns detected:            │
│  Overtrading        12×  MED   │
│  Revenge trading     4×  HIGH  │
│  No stop-loss        8×  LOW   │
│  [All patterns →]              │
└────────────────────────────────┘
```

### Tab: Trades

```
┌────────────────────────────────┐
│  [All ▼] [30d ▼]               │  ← filter chips
│                                │
│  ┌─────────────────────────┐   │
│  │ Mar 27 · NIFTY 24500CE  │   │  ← trade card
│  │ +₹1,100  ·  22 min hold │   │
│  │ 50 qty  ·  ₹140 → ₹162  │   │
│  └─────────────────────────┘   │
│                                │
│  ┌─────────────────────────┐   │
│  │ Mar 27 · BANKNIFTY PE   │   │
│  │ -₹562  ·  14 min hold   │   │
│  │ 25 qty  ·  ₹220 → ₹198  │   │
│  │ [📝 Revenge]            │   │  ← pattern chip when detected
│  └─────────────────────────┘   │
│                                │
│  [Load more]                   │
└────────────────────────────────┘
```

Tap a trade card → bottom sheet with full detail + journal icon.

---

## 4. AI Coach

**What it is:** The full AI Coach experience in a full-screen chat layout. The web's left context panel becomes a collapsible top bar on mobile — collapsed by default during market hours (the trader doesn't need it visible while actively trading), expandable for review sessions. The conversation, streaming, and starter prompts all work identically to web.

**UI/UX (mobile-specific):** Full-screen chat with a `border-b border-border` collapsible context strip at the top. The strip shows P&L, trade count, behavior score on a single line when collapsed; tapping `[▾]` expands to 3–4 stat rows. Collapsed by default — most market-hours users don't need context stats visible while chatting. Starter prompts appear as full-width chip buttons when no conversation history exists. The keyboard-aware layout pushes the input field up above the software keyboard when it opens. Messages are sized for a small screen: user bubbles `max-w-[75%]`, AI responses full-width with no bubble. The "New chat" button is a ghost icon (`Plus`) in the header, not a labeled button.

```
┌────────────────────────────────┐
│  AI Coach   [▾ Context]   [+] │  ← "+" = new chat
├────────────────────────────────┤
│  P&L +₹1,240 · Trades 6 · B:74│  ← collapsed context (1 line)
│  [▾ to expand]                 │
├────────────────────────────────┤
│                                │
│  [starter prompts — when       │
│   no conversation history]     │
│                                │
│  "How was my trading today?"   │  ← full-width chip buttons
│  "What patterns am I showing?" │
│  "Help me prep for tomorrow"   │
│                                │
│  ────────────────────────────  │
│                                │
│  [User message, right-aligned] │
│                                │
│  [TM]  AI response, streaming  │
│                                │
├────────────────────────────────┤
│  ┌──────────────────────────┐  │
│  │  Ask anything...       ↑ │  │  ← sticky above keyboard
│  └──────────────────────────┘  │
└────────────────────────────────┘
```

---

## 5. My Patterns

**What it is:** The behavioral identity screen on mobile. The two-panel web layout collapses into a vertical accordion of pattern cards. Each card is collapsed by default showing the summary; tap to expand and see the full narrative, frequency sparkline, and worst instances. The "Not Detected" section sits at the bottom as a quieter group of collapsed cards.

**UI/UX (mobile-specific):** Single-column card layout. Each pattern card has a header row (pattern name, severity badge, occurrence count) and a tap-to-expand body. Only one card is expanded at a time — expanding a new card collapses the previous one. The expanded state shows the narrative paragraph, a mini sparkline, and a condensed worst-instances list. "See all trades →" link opens Analytics → Trades filtered by that pattern. "Not Detected" cards use lighter weight text and reduced visual prominence — they reassure without taking attention.

```
┌────────────────────────────────┐
│  My Patterns                   │
├────────────────────────────────┤
│                                │
│  ┌──────────────────────────┐  │
│  │ Overtrading        HIGH  │  │  ← collapsed card header
│  │ 12 occurrences · 2d ago  │  │
│  │ [▸ tap to expand]        │  │
│  └──────────────────────────┘  │
│                                │
│  ┌──────────────────────────┐  │  ← expanded card
│  │ Revenge Trading    HIGH  │  │
│  │ 4 occurrences · 5d ago   │  │
│  │                          │  │
│  │ "You tend to re-enter    │  │
│  │  quickly after a loss,   │  │
│  │  especially in F&O."     │  │
│  │                          │  │
│  │ [sparkline — 90 days]    │  │
│  │ Worst: Mar 15, -₹2,800   │  │
│  │ [See all trades →]       │  │
│  └──────────────────────────┘  │
│                                │
│  NOT DETECTED (3)              │
│  ○ Position Sizing             │
│  ○ Winning Streak OC           │
│  ○ Strategy Pivot              │
│                                │
└────────────────────────────────┘
```

---

## 6. Blowup Shield

**What it is:** The same retrospective protection log as web. On mobile the 4-tile row compresses into a hero number (Total Saved) with two secondary stats below it. History is a vertical list of event rows instead of a table. The timeline visualization is simplified or omitted on very small screens.

**UI/UX (mobile-specific):** The headline "Total Capital Saved" number is the largest element — `text-4xl font-semibold text-success`. Below it, "Saves this month" and "Worst save" appear as two smaller inline stats on the same row. The event list is compact: date + event type on line 1, capital defended on line 2. "View full history →" at the bottom opens a full scrollable sheet. The overall page is short — it fits on one screen for most users. No red anywhere on this screen.

```
┌────────────────────────────────┐
│  Blowup Shield                 │
├────────────────────────────────┤
│                                │
│  Total Capital Saved           │
│  ₹41,200                       │  ← text-4xl text-success
│  across 12 events              │
│                                │
│  3 saves this month  ·  ₹18,500 largest
│                                │
│  Status: ● Active              │
│                                │
├────────────────────────────────┤
│  RECENT EVENTS                 │
│  ──────────────────────────    │
│  Mar 27 · Circuit Break        │
│  ₹18,500+ defended             │
│                                │
│  Mar 22 · Cooldown             │
│  ₹4,200 defended               │
│                                │
│  Mar 18 · Margin Warning       │
│  ₹8,000+ defended              │
│                                │
│  [View full history →]         │
└────────────────────────────────┘
```

---

## 7. Danger Zone

**What it is:** The active-state status screen. Same content as web — what triggered, when, how long. On mobile the status card is the dominant element and should fill the majority of the visible screen. Must be immediately readable under stress.

**UI/UX (mobile-specific):** The status card fills nearly the full width with `mx-4 border-l-4`. In the active state the amber left border is prominent at mobile width. The four text lines inside use generous padding (`p-5`) so the text is not cramped. Below the card, the "What this means" explanation fits on 2–3 lines of `text-sm text-muted-foreground`. The history table is replaced with a short event list (3 rows max). In the safe state the card is visually quiet — green left border, two lines of text, no emphasis.

```
┌────────────────────────────────┐
│  Danger Zone                   │
├────────────────────────────────┤
│                                │
│  ┌──────────────────────────┐  │
│  │  ⬤  ACTIVE              │  │  ← border-l-4 border-warning
│  │  Circuit Breaker         │  │
│  │                          │  │
│  │  Reason:                 │  │
│  │  Daily loss -₹5,240      │  │
│  │  Limit was ₹5,000        │  │
│  │                          │  │
│  │  Triggered: 11:23 AM     │  │
│  │  Until: Market close     │  │
│  └──────────────────────────┘  │
│                                │
│  This is informational only.   │
│  You can still trade in        │
│  Zerodha Kite.                 │
│                                │
│  HISTORY (this week)           │
│  [3 compact event rows]        │
└────────────────────────────────┘
```

---

## 8. Goals

**What it is:** The commitment-tracking screen on mobile. The layout is a single column of goal cards with a compact calendar heatmap below them. All functionality present — adding, editing, viewing streaks. The calendar is smaller on mobile but still readable as a pattern indicator.

**UI/UX (mobile-specific):** The 3-tile summary row from web becomes a single "Streak: X days" header stat inline in the page header (subdued, not prominent). Goal cards are full-width bordered boxes with the progress bar below the description. The calendar heatmap is a 5×7 grid of 8px dots — compact enough to fit in one horizontal span. "+ Add" opens an inline form that slides in below the last goal card. Tap a goal card header to expand edit options (edit target, pause, delete) without navigating away.

```
┌────────────────────────────────┐
│  Goals       Streak: 4d  [+ Add]
├────────────────────────────────┤
│                                │
│  ┌──────────────────────────┐  │
│  │ Max 10 trades/day        │  │
│  │ ██████████ 5/5 days ✓   │  │
│  │ Streak: 7d · Best: 12d   │  │
│  └──────────────────────────┘  │
│                                │
│  ┌──────────────────────────┐  │
│  │ No trades 9:15–9:30 AM   │  │
│  │ ████████░░ 4/5 days      │  │
│  │ Missed: Tuesday          │  │
│  │ Streak: 4d · Best: 9d    │  │
│  └──────────────────────────┘  │
│                                │
│  LAST 30 DAYS                  │
│  Mo Tu We Th Fr Sa Su          │
│  ● ● ● ● ● ○ ○                │  ← green/gray dots
│  ● ● ○ ● ● ○ ○                │
│  ...                           │
└────────────────────────────────┘
```

---

## 9. Portfolio Radar

**What it is:** The concentration risk screen on mobile. The score is the primary focal element. The web's two side-by-side bar charts stack vertically. The positions table becomes a compact list.

**UI/UX (mobile-specific):** Score + risk level label are hero-sized at the top. Total exposure below as a secondary stat. The two bar charts stack vertically with a divider between them — each chart shows 3–4 bars (top holdings/sectors only). "View full breakdown →" opens a bottom sheet with all bars. The positions list below shows symbol, P&L, concentration %, and a warning chip inline. Everything stacks naturally without horizontal scrolling.

```
┌────────────────────────────────┐
│  Portfolio Radar               │
├────────────────────────────────┤
│  Concentration Score           │
│  62 / 100   ◐ Moderate         │  ← focal element
│  Total exposure: ₹1.8L         │
│                                │
├────────────────────────────────┤
│  BY SECTOR                     │
│  BFSI    ████████ 42%          │
│  IT      ██████   28%          │
│  Energy  ████     18%          │
│                                │
├────────────────────────────────┤
│  BY SYMBOL                     │
│  BANKNIFTY  ████████ 38%  ⚠   │
│  RELIANCE   █████    22%       │
│  NIFTY      ████     18%       │
│                                │
│  [View full breakdown →]       │
└────────────────────────────────┘
```

---

## 10. Reports

**What it is:** The reports library on mobile. The two-panel web layout collapses to a vertical card list. Tapping a report opens the full content in a scrollable bottom sheet (90vh height). All report content is present — just delivered differently.

**UI/UX (mobile-specific):** Report cards are full-width with date, headline P&L, and trade count visible. The type filter (EOD / Weekly / Monthly) sits at the top as pill tabs. Tapping a card opens a full-height bottom sheet with a close button at the top-right. Inside the sheet the report renders with generous padding and readable `text-sm leading-relaxed` for the AI narrative. The PDF download button is a compact secondary button at the top of the sheet next to the report title. The sheet can be pulled down to dismiss.

```
┌────────────────────────────────┐
│  Reports                       │
├────────────────────────────────┤
│  [EOD] [Weekly] [Monthly]      │
├────────────────────────────────┤
│                                │
│  ┌──────────────────────────┐  │
│  │ Today · Mar 28           │  │  ← report card
│  │ +₹3,450  ·  8 trades     │  │
│  │ Score: 74  ·  2 patterns │  │
│  └──────────────────────────┘  │
│                                │
│  ┌──────────────────────────┐  │
│  │ Yesterday · Mar 27       │  │
│  │ -₹1,200  ·  12 trades    │  │
│  │ Score: 61  ·  4 patterns │  │
│  └──────────────────────────┘  │
│                                │
└────────────────────────────────┘

[On tap → 90vh bottom sheet]:
┌────────────────────────────────┐
│  ───── (drag handle)           │
│  Mar 28 — EOD Report [PDF ↓]  │
│  ──────────────────────────    │
│  P&L +₹3,450  ·  8 trades     │
│  Behavior score: 74/100        │
│                                │
│  Key patterns:                 │
│  · Overtrading (2 instances)   │
│  · No stop-loss (1 instance)   │
│                                │
│  [AI narrative text — readable,│
│   leading-relaxed, text-sm]    │
└────────────────────────────────┘
```

---

## 11. Settings

**What it is:** The configuration hub on mobile. The tab layout from web becomes a list of section rows, each navigating to its own sub-screen. This is the standard iOS/Android settings pattern — each row shows the section name and the primary current value (e.g., "Profile → ZA1234"). Settings sub-screens use back navigation.

**UI/UX (mobile-specific):** A single-column list with grouped sections separated by dividers. Each row is a standard settings cell: label on the left, current value or arrow on the right, 48px minimum tap height. Navigation to sub-screens uses slide-in animation (Capacitor native transition). Each sub-screen has a back arrow in the top-left and its own Save button at the bottom. Form fields in sub-screens use the same top-label pattern as web. Destructive actions (Delete data, Disconnect) are in the Account sub-screen, visually separated and in `text-destructive`.

```
┌────────────────────────────────┐
│  Settings                      │
├────────────────────────────────┤
│  ▸  Profile           ZA1234  │  ← current value shown
│  ▸  Risk Limits               │
│  ▸  Notifications             │
│  ──────────────────────────    │
│  ▸  Account                   │
│  ▸  Appearance    Light mode  │
│  ──────────────────────────    │
│  Privacy Policy               │
│  Terms of Service             │
└────────────────────────────────┘
```

**Sub-screen example (Risk Limits):**

```
┌────────────────────────────────┐
│  ←  Risk Limits                │
├────────────────────────────────┤
│                                │
│  Max daily loss                │
│  [₹5,000                     ] │
│  ~4.2% of your capital         │
│                                │
│  Max trades per day            │
│  [15                          ]│
│                                │
│  Max position size             │
│  [₹50,000                    ] │
│                                │
│  Cooldown after 3 losses       │
│  [30 min ▼]                    │
│                                │
│  High-risk warnings [●  ON]    │
│                                │
│                       [Save]   │
└────────────────────────────────┘
```

---

## 12. Guardrails

**What it is:** The read-only rules summary on mobile. Same content as web — daily rules, cooldown rules, high-risk windows, today's compliance. Compact list format fits well in a single-column mobile layout.

**UI/UX (mobile-specific):** Section cards are full-width. Each rule row shows the rule on the left and a status dot on the right. Today's compliance bar is a full-width `<progress>` element with the fraction count above it. "Edit rules in Settings →" is a text link at the bottom. The entire screen should be readable at a glance with no scrolling on a typical device (it is short content).

```
┌────────────────────────────────┐
│  Guardrails                    │
├────────────────────────────────┤
│  DAILY RULES                   │
│  Max daily loss   ₹5,000  ●   │
│  Max trades/day   15      ●   │
│  Max position     ₹50k    ●   │
│                                │
│  COOLDOWN                      │
│  After 3 losses → 30 min  ●   │
│  After max loss → paused  ●   │
│                                │
│  HIGH-RISK WINDOWS             │
│  9:15–9:30 AM             ●   │
│  3:00–3:30 PM             ●   │
│                                │
│  TODAY: 3 of 5 rules met       │
│  ████████░░░░                  │
│                                │
│  [Edit in Settings →]          │
└────────────────────────────────┘
```

---

## Touch Interaction Patterns

### Bottom Sheets
Used for: position detail, trade detail + journal, report reading, "More" nav, full history views.

```
Opens: slides up from bottom over 250ms ease-out
Drag handle: visible, 4×36px, centered at top
Dismiss: drag down past 30% height, or tap backdrop
Heights: 60vh default, 90vh for report/history content
Backdrop: rgba(0,0,0,0.4) — tap to dismiss
```

### Pull-to-Refresh
Supported on: Home, Alerts, Analytics, Reports

```
Standard native gesture via Capacitor plugin
Spinner appears at top (16px, text-primary)
Triggers fresh fetch from backend
No full page reload
```

### Swipe Actions
- Alert card: swipe left → reveals "Acknowledge" action (green)
- Report card: swipe left → reveals "Download" action

### Long-Press
- Trade card: reveals contextual actions (journal, copy symbol)
- Alert card: quick-acknowledge without opening

---

## Responsive Breakpoints Summary

| Width | Nav | Layout | Tables | Panels |
|-------|-----|--------|--------|--------|
| < 768px (mobile) | Bottom nav | Single column | Cards | Bottom sheets |
| 768–1023px (tablet) | Icon sidebar (56px) | 2-col grid | Simplified tables | Bottom sheets |
| ≥ 1024px (desktop) | Full sidebar (208px) | Multi-column | Full tables | Right panels |

The Capacitor Android build targets the mobile breakpoint. Tablet breakpoint handles foldables and large-screen Android devices.

---

## Android-Specific Notes

### Safe Areas
```css
padding-top: env(safe-area-inset-top);
padding-bottom: env(safe-area-inset-bottom); /* home indicator */
```
Bottom nav: add `pb-safe` (`padding-bottom: env(safe-area-inset-bottom)`) so the nav bar doesn't sit behind the system home indicator.

### Back Button
- Sub-screens (Settings sub-screens, drill-down views): back = navigate up
- More sheet open: back = closes sheet
- Home screen: back = exits app (standard Android behavior)
- Bottom sheet open: back = dismisses sheet

### WebSocket on Background/Foreground
When the app moves to background:
- WebSocket connection drops (OS-level constraint)
- No reconnect attempts in background

When app returns to foreground:
- Reconnect within 1–2 seconds
- Re-subscribe to all event streams
- Replay missed events from Redis Streams (up to last 30 minutes)
- Show stale data until first WebSocket event arrives — never blank

### Keyboard Handling
All input screens (Coach, Journal, Settings forms):
- Use `adjustResize` window soft input mode (Capacitor default on Android)
- Input field scrolls into view when keyboard opens
- Chat input stays pinned above keyboard at all times

### Status Bar
- Light theme: dark status bar icons (dark text on light background)
- Dark theme: light status bar icons
- Set via Capacitor StatusBar plugin on app launch and theme toggle

---

*Previous: [02_WEB_SCREENS.md](./02_WEB_SCREENS.md) | Next: [04_COMPONENTS.md](./04_COMPONENTS.md)*
