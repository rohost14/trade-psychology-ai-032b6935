# TradeMentor AI — Design Overview

> This document defines the design philosophy, information architecture, navigation structure, and cross-platform strategy for TradeMentor AI. Read this before designing or implementing any screen.

---

## 1. The Design Contract

TradeMentor's core philosophy is **"Mirror, not Blocker."** This is not a motivational slogan — it is a design constraint that must be visible in every UI decision.

What it means in practice:

| Philosophy | Design implication |
|---|---|
| Show facts, not judgements | Data is always primary. Labels and colors describe; they do not warn or shame. |
| Never interrupt the flow | Alerts live in their designated space. Nothing pops up and blocks a trade. |
| Make it feel like a tool | Dense, workmanlike, predictable. A trader should feel like they're using a Bloomberg terminal, not a wellness app. |
| Trust the trader | The UI presents information at all severity levels equally. The trader decides what to do with it. |

**What this rules out immediately:**
- No "Are you sure you want to trade?" confirmation dialogs
- No red warning banners that dominate the screen
- No motivational copy ("You've got this! 💪")
- No streak gamification that rewards or shames
- No push notifications that say "Stop trading!"
- No progress bars that make a trader feel like they're failing a test

---

## 2. The Two Modes

Traders use TradeMentor in two distinct mental states. The design must serve both without switching context:

### Market Hours Mode (9:15 AM – 3:30 PM IST)
**User is: active, stressed, time-pressured, making fast decisions**

Design requirements:
- Information must be scannable in under 3 seconds
- P&L and position status must be immediately visible — no scrolling required
- Alerts are visible but not intrusive — a badge, not a modal
- Navigation must be unambiguous — no thinking required to get anywhere
- No animation delays on data that is changing live
- The app competes with the broker terminal for attention — it must earn every second of it

### Review Mode (after 3:30 PM, morning pre-market)
**User is: reflective, analytical, building habits**

Design requirements:
- Depth is appropriate — charts, tables, detailed pattern breakdowns
- The coach/chat interface gets more use
- Reports and journals are the primary destination
- Can afford slightly more visual richness — graphs, comparisons
- This is where the app builds long-term value

**Both modes use the same screens.** The design must not require mode switching. A screen that works for a stressed 9:30 AM check will also work for a 6 PM review.

---

## 3. Information Architecture

### The Hierarchy of User Questions

Every screen answers one primary question. This drives what information is most prominent:

| Screen | Primary question it answers |
|---|---|
| Dashboard | "How am I doing RIGHT NOW?" |
| Analytics | "How have I been performing overall?" |
| Alerts | "What behavioral patterns is the system flagging?" |
| My Patterns | "Who am I as a trader? What are my tendencies?" |
| AI Coach | "What should I think about this situation?" |
| Blowup Shield | "What has the system protected me from?" |
| Guardrails | "What rules have I set for myself?" |
| Danger Zone | "Am I in an active cooldown or circuit break right now?" |
| Goals | "Am I meeting the commitments I set for myself?" |
| Portfolio Radar | "Is my current exposure concentrated in risky ways?" |
| Portfolio Advisor | "What does AI think about my holdings position?" |
| Reports | "What happened this week/month? What's the summary?" |
| Settings | "Configure my profile, notifications, and risk limits" |

**Design rule:** If a piece of information does not answer the primary question of a screen, it belongs somewhere else. The current Dashboard violates this by containing 10+ distinct information types. The redesign fixes this.

### The Screen Map

```
TradeMentor AI
│
├── DAILY USE (in nav, always accessible)
│   ├── Dashboard ─────── "Right now" status
│   ├── Alerts ─────────── Behavioral flag feed
│   ├── Analytics ──────── Performance deep-dive (5 tabs)
│   └── AI Coach ───────── Psychology conversation
│
├── PROTECTION & GROWTH (in nav, secondary)
│   ├── My Patterns ────── Behavioral identity & trends
│   ├── Blowup Shield ──── Historical protection log
│   ├── Guardrails ─────── Self-imposed rules
│   ├── Danger Zone ────── Active cooldown status
│   └── Goals ──────────── Commitments & streaks
│
├── DATA & TOOLS (in nav, below fold / More sheet on mobile)
│   ├── Portfolio Radar ── Concentration analysis
│   ├── Portfolio Advisor ─ Holdings AI chat
│   └── Reports ─────────── Generated summaries
│
└── SYSTEM
    ├── Settings ───────── Profile, notifications, limits
    ├── Personalization ─── (merged into Settings / Onboarding)
    ├── Welcome ─────────── Landing / login
    └── Onboarding ─────── First-run wizard (modal)
```

### IA Decisions & Rationale

**Decision 1: Dashboard is stripped to "right now" only.**
The current dashboard has Closed Trades Table, Blowup Shield summary, Progress Tracking, Money Saved — all mixed with live positions. These move to their proper pages. Dashboard becomes a clean live status view.

**Decision 2: My Patterns vs Analytics → Behavior Tab**
These are distinct and both stay, but with a clear boundary:
- **My Patterns** = your identity, high-level insights, "you tend to revenge trade after big losses" — narrative
- **Analytics → Behavior tab** = the data behind those patterns — tables, charts, frequencies

**Decision 3: Danger Zone stays separate from Blowup Shield**
Both are risk pages but serve different purposes:
- **Blowup Shield** = passive protection history ("here's what was saved")
- **Danger Zone** = active state ("you are currently in a 30-minute cooldown")
These must be visually distinct so a user in crisis immediately goes to the right place.

**Decision 4: Personalization absorbed into Settings**
Personalization (`/personalization`) contains time analysis and AI recommendations. On web it gets a dedicated tab in Settings. On mobile it's a section within Settings screen. The separate route remains (for deep links) but nav doesn't show it as primary.

**Decision 5: Portfolio Advisor and AI Coach remain separate**
They solve genuinely different problems and have different data contexts:
- AI Coach = trading psychology, behavioral patterns, mental state
- Portfolio Advisor = portfolio composition, holdings analysis, risk concentration
They should look similar in UI (both are chat) but be clearly labeled.

---

## 4. Navigation Architecture

### Web — Sidebar

```
Width: 208px (w-52) — consistent with Zerodha's compact sidebar
Background: bg-card
Border: border-r border-border
```

**Structure:**
```
┌──────────────────┐
│  [TM Logo + name] │  — clickable, goes to /dashboard
├──────────────────┤
│                   │
│  ● Dashboard      │  ← primary, bold when active
│                   │
│  DAILY            │  ← section label: text-xs uppercase muted
│    Analytics      │
│    Alerts    [3]  │  ← badge for unacknowledged
│    AI Coach       │
│                   │
│  PROTECTION       │
│    My Patterns    │
│    Shield         │
│    Guardrails     │
│    Danger Zone    │
│    Goals          │
│                   │
│  TOOLS            │
│    Portfolio Radar│
│    Advisor        │
│    Reports        │
│                   │
├──────────────────┤
│  Settings         │  ← at bottom always
│                   │
│  [ZA1234]  ●      │  ← user/connection status
│  Connected        │
└──────────────────┘
```

**Active state:** `bg-primary/10 text-primary` on the item, left border `border-l-2 border-primary`
**Inactive state:** `text-muted-foreground hover:bg-muted hover:text-foreground`
**Section labels:** `text-xs font-medium uppercase tracking-wide text-muted-foreground px-3 py-2`
**Badge:** Small `bg-danger text-white` pill, `text-xs font-bold`, only on Alerts

### Mobile — Bottom Navigation

```
5 permanent tabs: Home | Alerts | Analytics | Coach | More
```

**Tab specs:**
- Height: 64px fixed bottom
- Icon: 22px Lucide
- Label: `text-xs font-medium`
- Active: `text-primary`
- Inactive: `text-muted-foreground`
- Badge: `bg-danger` pill on Alerts, positioned top-right of icon

**"More" bottom sheet** (slides up from bottom, `animate-slide-in-up`):
```
┌─────────────────────────┐
│ ────────────────────── │  ← drag handle
│                          │
│  PROTECTION              │
│  ▸ My Patterns     [74] │  ← behavior score badge
│  ▸ Blowup Shield   [●]  │  ← risk level dot
│  ▸ Guardrails           │
│  ▸ Danger Zone          │
│  ▸ Goals          [7d🔥]│  ← streak badge
│                          │
│  TOOLS                   │
│  ▸ Portfolio Radar      │
│  ▸ Portfolio Advisor    │
│  ▸ Reports              │
│                          │
│  ACCOUNT                 │
│  ▸ Settings             │
│                          │
└─────────────────────────┘
```

---

## 5. Cross-Platform Design Split

The question is not "should mobile have all features?" (it should) but "how is each feature presented?"

| Feature | Web presentation | Mobile presentation |
|---|---|---|
| Dashboard | 4 metric tiles + full positions table + 2 sections below | P&L hero + 2 small tiles + compact positions list + alert strip |
| Analytics | Full 5-tab layout, all charts visible | 5 tabs, charts simplified, tables behind "View full →" |
| Alerts | 3-tab feed with filter sidebar | Vertical feed, filter chips at top |
| AI Coach | Chat with left context panel showing live stats | Full-screen chat, stats in collapsible top bar |
| Blowup Shield | Timeline visualization + full table | Score card + compact timeline list |
| My Patterns | Side-by-side: patterns list + detail panel | Single-column cards, tap to expand |
| Portfolio Radar | Chart + full breakdown table | Gauge/score + top holdings list |
| Reports | Table with preview panel | Card list, tap to view |
| Settings | Section-based with all fields visible | Grouped sections, each opens a sub-screen |
| Goals | Dashboard-like layout with multiple cards | Card stack, one primary goal in focus |

**The progressive disclosure rule for mobile:**
- First visible: the critical number or status (can I see it in one glance?)
- One tap: the context (why is that number what it is?)
- Two taps: the full data (the table, the chart, the details)

No mobile screen should require the user to scroll past 3 full screen-heights to find something important.

---

## 6. Visual Design Principles (App-Specific)

These extend the SKILL.md rules with TradeMentor-specific applications:

### Color Hierarchy in Context

```
P&L values          → text-success / text-danger (highest priority, always semantic)
Active alerts       → text-warning (amber) — informational, not alarming
Danger/critical     → text-destructive (red) — used sparingly, means "action needed now"
Primary actions     → text-primary / bg-primary (teal) — connect, sync, chat
Everything else     → text-foreground / text-muted-foreground / text-muted
```

**Rule:** Never put red on the screen for anything other than actual financial loss or a critical behavioral alert. Red means money. If red appears for a UI state (error message), it must be clearly different in size/weight from P&L red to avoid false alarm.

### Density Calibration by Screen

```
HIGH DENSITY (Sensibull-level):
  Analytics tables, Alerts history, Reports list
  → Compact rows (h-10), small type (text-xs/sm), tight padding

MEDIUM DENSITY (Tickertape-level):
  Dashboard, My Patterns, Shield
  → Standard rows (h-11/12), body text (text-sm), comfortable padding

LOW DENSITY (Stripe docs-level):
  Settings, Onboarding, Goals, Chat
  → Relaxed spacing, larger type for readability
```

### The "No Decoration" Rule for Data Screens

Any screen that contains a data table or live P&L must have:
- No gradient backgrounds
- No illustration assets (charts only — no decorative SVGs)
- No card with >1 level of visual elevation (max: border + 1px shadow)
- No rounded corners >8px
- No colored backgrounds on the page itself (only on the surface/card)

Any screen that is "first-time" or "empty state" can have:
- A single centered illustration (monochrome, geometric)
- Slightly warmer/lighter feel

### Market Hours vs Review Mode — Subtle Differences

When market is OPEN (`is_market_open = true`):
- Dashboard positions table shows a live indicator (●  LIVE in header, pulsing amber dot)
- P&L numbers update silently (no animation per Section 8 of SKILL.md)
- AI Coach header shows "Market Open" badge

When market is CLOSED:
- Dashboard shows a "Market Closed" state on the positions section — data is final, not live
- The live badge is absent
- Color of the status indicator changes to muted

This is a small but important distinction. It tells the trader whether the numbers they're seeing are final or still changing.

---

## 7. Onboarding Strategy

### Entry Points
```
New visitor  → /welcome → "Connect Zerodha" or "Continue as Guest"
Guest mode   → Full app with demo data, amber banner "You're viewing demo data"
OAuth return → /dashboard + OnboardingWizard modal (5-step)
Returning    → /dashboard directly
```

### First Run Experience (post-OAuth)
The onboarding wizard is a **focused, interruptive experience** — the one place where we DO interrupt, because it's a one-time setup. Design it as:
- Full-screen modal (not a corner sidebar)
- Progress bar visible (5 steps, you can see where you are)
- Skip allowed on every step except step 1 (name is required)
- Saving happens per-step, not all at end
- Completion lands on Dashboard with a brief "You're set up" toast

### Getting Started Card
After onboarding, the Dashboard shows a `GettingStartedCard` with 4 steps:
1. Connect Zerodha (check if done)
2. Complete profile (check if done)
3. Set your risk limits (link to Settings → Risk)
4. Enable alerts (link to Settings → Notifications)

This card auto-hides once: onboarding complete AND ≥3 trades synced.
On mobile: this is a slim banner at the top of Home, not a full card.

---

## 8. What This App Is NOT

To prevent regression, document what we explicitly avoid:

- **Not a trading terminal.** We don't show order books, depth charts, or real-time market data. Those live in Zerodha Kite.
- **Not a portfolio tracker.** We don't show net worth, SIP performance, or stock fundamentals. That's Tickertape.
- **Not a social app.** No sharing, no community feed, no leaderboards, no "compare with other traders."
- **Not a gamified habit tracker.** Streaks are informational, not gamified. No badges, achievements, or level-ups.
- **Not a compliance tool.** We show behavioral data. The trader decides what to do with it.

---

## 9. What TradeMentor AI Is

TradeMentor AI is a trading psychology and behavioral analysis platform built for Indian retail traders, primarily those active in F&O (futures and options) markets. Most retail trading losses are not caused by poor market knowledge — they are caused by repeated behavioral mistakes: overtrading after a win, revenge trading after a loss, holding losing positions too long, entering in panic. TradeMentor connects to a trader's Zerodha account, silently observes every trade, and surfaces behavioral patterns as they emerge — without interrupting, judging, or blocking. The product's philosophy is "Mirror, not Blocker": show the trader an accurate picture of their own behavior, and trust them to decide what to do with that information. It is used in two contexts: during market hours for live awareness, and after market hours for reflection and review.

---

*Screen-by-screen descriptions and UI/UX specs live in [02_WEB_SCREENS.md](./02_WEB_SCREENS.md) and [03_MOBILE_SCREENS.md](./03_MOBILE_SCREENS.md).*

---

*Next: [01_USER_FLOWS.md](./01_USER_FLOWS.md) | [02_WEB_SCREENS.md](./02_WEB_SCREENS.md) | [03_MOBILE_SCREENS.md](./03_MOBILE_SCREENS.md) | [04_COMPONENTS.md](./04_COMPONENTS.md)*
