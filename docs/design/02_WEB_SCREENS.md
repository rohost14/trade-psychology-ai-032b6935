# TradeMentor AI — Web Screen Design Specification

> **STRUCTURE NOTE (updated 2026-04-02):** Pixel-level per-screen specs now live in [`screens/`](./screens/). Each file covers both web and mobile for one screen. This file contains high-level screen descriptions and design rationale — read it for context, then go to `screens/XX_screenname.md` for implementation-ready specs.
>
> | Screen | Spec file | Status |
> |--------|-----------|--------|
> | Dashboard | [`screens/01_dashboard.md`](./screens/01_dashboard.md) | ✅ Specced |
> | Behavioral Alerts | `screens/02_alerts.md` | ⬜ Pending |
> | Analytics | `screens/03_analytics.md` | ⬜ Pending |
> | AI Coach | `screens/04_coach.md` | ⬜ Pending |
> | My Patterns | `screens/05_my_patterns.md` | ⬜ Pending |
> | Blowup Shield | `screens/06_blowup_shield.md` | ⬜ Pending |
> | Session Limits | `screens/07_session_limits.md` | ⬜ Pending |
> | Goals | `screens/08_goals.md` | ⬜ Pending |
> | Portfolio Radar | `screens/09_portfolio_radar.md` | ⬜ Pending |
> | Reports | `screens/10_reports.md` | ⬜ Pending |
> | Settings | `screens/11_settings.md` | ⬜ Pending |
> | Welcome / Landing | `screens/12_welcome.md` | ⬜ Pending |

---

> Original high-level descriptions and design rationale below.

---

## Design Foundation

### What TradeMentor Actually Does (And What the Design Must Reflect)

TradeMentor does three distinct things that no other tool does:

**1. Journal-enriched behavioral analysis.** The trader attaches emotional and process context to every trade — what they felt, whether they followed their plan, why they exited, how good the setup was. This journal data is the raw material for understanding the "why" behind behavioral patterns. Without it, pattern detection is purely algorithmic. With it, the system can say: "9 of 12 overtrading events happened when you said you were feeling anxious." That is a genuinely different level of insight.

**2. Counterfactual protection tracking.** When a circuit break or cooldown activates, the system looks up the actual market price 30 minutes later and calculates what would have happened if the trader had continued. This is real data, not an estimate. The Blowup Shield shows this as capital defended — and crucially, if the market recovered and the trader would have made money by ignoring the alert, it shows that too. Honesty builds trust.

**3. Behavioral pattern detection across 22 specific patterns.** Each pattern is defined with precise algorithmic triggers, not fuzzy heuristics. Revenge trading requires re-entry on the same symbol within 10 minutes of a loss above average loss size. Martingale behavior requires 3+ size escalations in a losing sequence. The patterns are specific, arguable, and explainable — which is why the design must show the evidence behind each one, not just the label.

### The Dashboard Problem (And the Correct Solution)

The original design instinct was: "Zerodha Kite shows positions, so we shouldn't." That was wrong. The reason we show positions and closed trades on the dashboard is not to replicate what Kite shows — it is to make the **journal entry action one tap away from the trade it relates to.** The journal is the single most valuable input in the entire system. If the trader has to navigate to Analytics → Trades tab → find the trade → click journal, they will not journal consistently. If they see the trade on the dashboard and tap a journal icon immediately after closing it, they will. The recency of the trade in their mind is the journal's value.

So positions and today's closed trades appear on the dashboard. The P&L values are supporting context. The journal button is the primary action.

### The Behavioral Score Problem (And the Correct Solution)

The behavioral score (0–100) is a composite metric calculated from pattern frequency, severity, and cost over a rolling window. It is useful as a trend indicator — is this trader improving or regressing over 30 days? It is not useful as a moment-to-moment status display. A trader opening TradeMentor at 10:30 AM does not need to know their score is 74 — that number means nothing to them mid-session. What they need to know is: "I've been flagged for overtrading today" or "I've placed 8 trades in 2 hours."

The score appears in Analytics → Behavior tab as a trend line chart showing improvement/regression over time. It appears in Reports as a period metric. It does not appear on the Dashboard as a hero element. Instead, the Dashboard surfaces specific behavioral signals that are immediately actionable: pattern observations from today, trade pace relative to the trader's normal, un-journaled trades needing attention.

### The Journal is the Core Action

The design must make journaling:
- **Frictionless**: One tap from seeing a trade to the journal sheet
- **Fast**: The sheet uses chip selects for emotions, plan adherence, exit reason — not text forms
- **Contextually present**: The journal icon appears on every trade row, filled if journaled, empty if not
- **Non-mandatory**: The sheet can be dismissed in one tap without saving anything

The journal captures: emotion before entry (9 options, multi-select), plan adherence (Yes/Partially/No), deviation reason (conditional), exit reason (6 options), setup quality (5-star), would repeat (Yes/Maybe/No), market condition (5 options), and a free-text note.

This data feeds: the Emotional Tax analysis in Analytics, the AI Coach's understanding of the trader's mental state, the personalized narrative in My Patterns, and the Emotional Journey section in EOD reports.

---

## Screen Descriptions

**Welcome / Landing** — The public entry point. Explains TradeMentor's purpose and value to an unknown visitor. The goal is honest explanation followed by a clear invitation to try. Two paths: connect Zerodha for real data, or explore with demo data as a guest. Compliance consent required before either CTA activates. No sidebar or app navigation — this page stands alone before the trader becomes a user.

**Dashboard** — The active session hub. Shows today's open positions and closed trades with a journal button on each row — because journaling is the primary action during the session, and recency matters. Behavioral observations from today sit below the trade list. A compact session summary (trade count, net P&L as a single line) provides context. No behavioral score hero. No replication of Kite's margin display. The screen answers: "What have I done today and what have I noticed about how I'm trading?"

**Analytics** — The deep review screen for after-hours analysis. Five tabs. The Behavior tab is the default because behavioral insight is TradeMentor's primary value. The Behavior tab shows pattern frequency breakdown, emotional tax analysis (win rate by journal-reported emotion), BTST activity, and trading persona. The Trades tab shows every closed trade with pattern tags AND journal emotion tags inline. The Timing tab shows P&L and win rate by hour of day. The Progress tab shows goal streak history. The Summary tab shows overall P&L metrics last.

**Behavioral Observations** (route: /alerts) — The pattern observation feed. Three tabs: Recent, History, and By Pattern. Each observation card shows the evidence behind the detection, not just the label. The "Acknowledge" action marks an observation as reviewed — nothing else happens. No alarm aesthetics: severity is communicated only through the indicator dot, not through card size, color backgrounds, or visual weight.

**AI Coach** — A psychology-focused conversation with an AI that has read the trader's full behavioral history and today's journal entries before the conversation starts. The left context panel shows "Today's Brief" — not raw stats but narrative-adjacent context including journal-reported emotions from today's trades. The coach asks questions, reflects behavior back, and never gives trading advice. The coach can save insights to the journal from within the conversation.

**My Patterns** — Longitudinal behavioral identity screen. Shows who the trader is across weeks and months — not just what patterns fired today, but which patterns are improving, worsening, or stable, and what journal data reveals about the emotional context for each pattern. The emotional correlation section is the unique value: "9 of 12 overtrading events you reported feeling Anxious." Includes the live behavioral status banner, streak tracker, and the pattern calendar heatmap.

**Blowup Shield** — Counterfactual protection record. When a circuit break or cooldown activates, the system records the position state and then looks up actual market prices 30 minutes later to calculate what would have happened. The result is shown per event: capital defended (or, honestly, capital not lost if the market recovered). Shield Score shows what percentage of protection events the trader respected. This is a verification system, not just a log.

**Session Limits** (renamed from Danger Zone) — Risk status and configuration. Shows the current state of all trader-configured limits: whether they are within bounds, approaching, or active. When a limit triggers, the screen shows a calm informational card stating what happened and that the trader can still trade in Zerodha. Includes threshold configuration and recent event history. Renamed from "Danger Zone" because these are the trader's own self-set rules — a fuel gauge, not an emergency room.

**Goals** — Behavioral commitment tracker. The trader sets behavioral goals (max trades per day, no trading in first 15 minutes, always use stop-losses) and tracks their weekly compliance and streak history. Includes a 30-day consistency calendar heatmap. Goal changes are gated with a 24-hour cooldown to prevent impulsive modification during emotional sessions.

**Portfolio Radar** — Position concentration and options risk analysis. Per-position cards show options-specific metrics where applicable: strike, breakeven price, gap to breakeven, premium decay percentage, and days to expiry. Concentration analysis shows exposure by expiry week and by underlying. Directional skew (long vs. short balance). GTT order summary. Used before adding a new position to check whether the existing book is already concentrated.

**Reports** — Generated periodic reports: Morning Brief, End of Day, and Weekly Summary. The EOD report includes an emotional journey timeline showing each trade with its journal-reported emotion as an emoji. The Morning Brief includes a readiness score and pre-trading checklist. The Weekly Summary shows behavioral trends. The AI narrative in each report synthesizes the behavioral story of the period. All reports downloadable as PDF.

**Settings** — Configuration hub with five tabs: Profile, Risk Limits, Notifications, Account, and Personalization. Saving happens per-tab, not globally.

**Onboarding Wizard** — A five-step modal shown once after OAuth connection. Captures name, trading style, capital range, segment, and initial risk preferences. Each step saves immediately. Skip allowed on steps 2–5.

---

## Individual Screen Specifications

---

## 1. Welcome / Landing

**Route:** `/welcome`
**Auth required:** No

### Purpose

A potential trader arrives here. They are skeptical — there is no shortage of trading tools making behavioral improvement claims. The page must explain the mechanism clearly (not vaguely), show real product UI (not illustrations), and make it low-friction to try.

Two types of visitors: those ready to connect their broker account immediately, and those who want to see the product before committing. The guest mode path must be equally prominent as the OAuth path.

### Layout and Sections

```
Fixed Navbar:
  [TM Logo]                              [Sign in]  [Connect Zerodha →]

HERO (100vh)
  Left:
    "Your trading, reflected back."               ← headline
    "Not judged. Not blocked. Just shown."         ← subhead
    "TradeMentor connects to your Zerodha account
     and builds a behavioral picture of how you
     trade — so you can see yourself clearly."     ← body
    [✓ I agree to Terms and Privacy Policy]        ← required checkbox
    [Connect Zerodha — primary CTA]
    [Continue as guest →]                          ← text link below

  Right:
    [3 rotating product cards — alert, score chart, journal sheet]
    Cards cycle every 3 seconds with 400ms fade

THE PROBLEM
  "Most F&O losses come from behavior, not analysis."
  [3 stats: 70% retail losses from behavioral patterns / etc.]

HOW IT WORKS  (3 steps horizontal)
  [1. Connect Zerodha] → [2. We track silently] → [3. You see patterns]

6 FEATURES  (2×3 grid)
  Behavioral Alerts       AI Coach
  Journal + Patterns      Blowup Shield
  Portfolio Radar         Daily Reports

PATTERNS SHOWCASE
  "The 22 patterns we track" — sample alert cards with real evidence

TESTIMONIALS  (3 cards)

PRICING  (3 tiers: Free / Pro ₹499 / Elite ₹999)
  Monthly / Yearly toggle

FAQ  (8 questions, accordion)

FOOTER
  Legal · Privacy · Terms · Compliance disclaimer
```

### Design Notes

- The three rotating product cards in the hero should show actual screenshots or very high-fidelity mockups. The product proves the point better than any copy.
- The compliance checkbox is required. Both CTAs remain disabled until checked. This is genuinely required (DPDP Act), not dark pattern friction.
- No autoplay video. No hero illustration. Clean, editorial, text-heavy. Credible, not excited.

---

## 2. Dashboard

**Route:** `/dashboard`
**Auth required:** Yes

### Purpose and Primary Action

The dashboard is open during the trading session. The trader checks it between trades or immediately after closing a position. The primary **action** is journaling — the trader sees a trade they just closed and taps the journal icon before the details fade from memory. The primary **read** is today's behavioral observations — has the system flagged anything?

The screen answers: "What have I done today and what has the system noticed?"

### What is NOT on the Dashboard

- Behavioral score (not useful mid-session; belongs in Analytics trends)
- Margin display (already in Kite; only surfaced in Portfolio Radar)
- RiskGuardian large widget (the risk state is shown as one quiet line when active, not a card)
- Blowup Shield summary card (belongs on its own screen)
- Progress tracking cards (belongs in Analytics → Progress tab)
- Holdings (belongs in Portfolio Radar)
- Separate closed trades card AND positions card — they are ONE unified today's activity feed

### Information Hierarchy

**During market hours:**
1. **Today's Activity feed** — open positions + closed trades today, unified list, journal button on each
2. **Today's Behavioral Observations** — what the system has flagged today, compact
3. **Session Summary** — one line: trade count and net P&L, informational context
4. **Session Limit status** — one line IF a limit is currently active, links to Session Limits
5. **AI Coach quick access** — persistent input at bottom

**After market close:**
1. **Today's Activity feed** — all closed trades, with journal status prominently shown
2. **Journaling prompt** — how many trades are un-journaled with direct link
3. **Today's Behavioral Summary** — plain language summary of what the system observed
4. **AI Coach debrief prompt** — suggested first message based on today

### Layout — Market Hours

```
Dashboard                                              ● LIVE  10:34 AM
─────────────────────────────────────────────────────────────────────

  8 trades today · Net: +₹1,240             ← one-line session summary, muted
  [!]  Cooldown active — daily limit reached  [Details →]   ← only if active, quiet

─────────────────────────────────────────────────────────────────────
TODAY'S ACTIVITY
─────────────────────────────────────────────────────────────────────

Symbol            Type    Qty    P&L        Hold     Pattern    Journal
NIFTY 24500CE     OPEN    50     +₹1,100    22m      —          ✎
BANKNIFTY PE      OPEN    25     -₹550      14m      [Revenge]  ✎ (filled)
RELIANCE EQ       CLOSED  100    +₹210      45m      —          ✎
NIFTY 24400PE     CLOSED  75     -₹975      8m       [FOMO]     ✎

3 trades not yet journaled.  [Journal them now →]     ← prompt, amber if >0
─────────────────────────────────────────────────────────────────────

TODAY'S OBSERVATIONS                                   [View all →]

  ⬤  Overtrading · 8 trades in 2h · first observed at 10:34 AM
  ⬤  Revenge trade risk · Re-entry on BANKNIFTY 4 min after loss · 09:58 AM
─────────────────────────────────────────────────────────────────────

┌─────────────────────────────────────────────────────────────────┐
│  Ask TradeMentor anything...                                  →  │
└─────────────────────────────────────────────────────────────────┘
```

### Layout — Market Closed

```
Dashboard                                              Market Closed
─────────────────────────────────────────────────────────────────────

  8 trades today · Final P&L: +₹3,450 · Win rate: 67%

─────────────────────────────────────────────────────────────────────
TODAY'S ACTIVITY
─────────────────────────────────────────────────────────────────────

Symbol            Type    Qty    P&L        Hold     Pattern    Journal
NIFTY 24500CE     CLOSED  50     +₹1,100    22m      —          ✎ (filled)
BANKNIFTY PE      CLOSED  25     -₹550      14m      [Revenge]  ✎ (filled)
NIFTY 24400PE     CLOSED  75     -₹975      8m       [FOMO]     ✎
RELIANCE EQ       CLOSED  100    +₹210      45m      —          ✎

⚠  2 trades not yet journaled. Journal now while the session is fresh.
   [Journal: NIFTY 24400PE]  [Journal: RELIANCE EQ]            ← direct links
─────────────────────────────────────────────────────────────────────

TODAY'S BEHAVIORAL SUMMARY

  2 patterns observed: Overtrading (10:34 AM) and Revenge trade risk
  (09:58 AM). You placed 8 trades — above your 6-trade daily average.
  [View full observations →]
─────────────────────────────────────────────────────────────────────

DEBRIEF WITH YOUR COACH

  "How was your trading behavior today?"    ← suggested prompt, clickable chip
  "What patterns did I show today?"
  "Help me process the BANKNIFTY revenge trade"

┌─────────────────────────────────────────────────────────────────┐
│  Or ask anything...                                           →  │
└─────────────────────────────────────────────────────────────────┘
```

### Trade Activity Row Design

```
Each row (compact, h-10):
  Symbol (truncated if needed)   Type badge   Qty   P&L (colored)   Hold   [Pattern chip]   [✎ or ✎filled]

Pattern chip: small amber pill, pattern name abbreviated
Journal icon: ✎ outline = not journaled. ✎ filled = journaled. Tap either → TradeJournalSheet
```

Clicking anywhere on a trade row (not the journal icon) expands an inline detail row:
- Entry price · Exit price · Entry time · Exit time · Strategy (if detected, e.g., "Bull Put Spread")

### Session Limit Status Line

This line only appears when a limit is currently active. When all limits are within bounds it does not appear at all.

```
[⬤]  Cooldown active — daily loss limit reached.  Active until: market close.  [Details →]
```

The dot is amber. The text is regular weight, same size as the session summary line above it. This is not a card, not a banner — just an informational line. Clicking "Details →" opens the Session Limits page.

### Empty State (No Trades Today)

```
TODAY'S ACTIVITY
  No trades today yet. Your session activity will appear here as you trade.
  [Sync trades →]
```

If user is new (fewer than 3 trades ever):

```
┌────────────────────────────────────────────────────────────────┐
│  Getting Started                                           [×]  │
│  ✓ Connect Zerodha    ○ Set trading capital                    │
│  ○ Complete profile   ○ Enable notifications                   │
└────────────────────────────────────────────────────────────────┘
```

### Design Notes

- The journal icon (✎) is the most important interactive element on this screen. It should be visually distinct, consistently placed, and immediately recognizable.
- Pattern chips on trade rows are amber pill labels. They identify trades that triggered an observation — they are context, not alarms.
- The session summary line (trade count + P&L) is informational, not hero. It uses regular body text size, muted color for the label, regular for the number.
- "3 trades not yet journaled" prompt uses amber text — the only amber on the screen — to draw attention without alarming.

---

## 3. Analytics

**Route:** `/analytics`
**Auth required:** Yes

### Purpose

Post-market deep review. The trader uses this to understand their behavioral patterns and performance over time. The Behavior tab is the default — behavioral insight is TradeMentor's unique value. The screen is appropriately dense; the trader has time here.

### Global Controls

Date range selector (top right): Today / Last 7 days / Last 30 days / Last 90 days / Custom. Applies to all tabs simultaneously.

### Layout

```
Analytics                                         [Last 30 days  ▼]
─────────────────────────────────────────────────────────────────
 [Behavior]  [Trades]  [Timing]  [Progress]  [Summary]
─────────────────────────────────────────────────────────────────
[Tab content — all lazy loaded]
```

---

### Tab: Behavior (default)

The behavioral intelligence center. This tab contains the unique analysis that only TradeMentor can provide because it combines trade data with journal entries.

```
DETECTED PATTERNS
Pattern               Occurrences    Est. Cost      Trend
─────────────────────────────────────────────────────────
Overtrading           12×            -₹4,200        ↓ Improving
Revenge trading        4×            -₹2,800        → Stable
No stop-loss           8×            -₹1,100        ↑ Worsening
FOMO entry             3×            -₹900          ↓ Improving
Opening 5-min trap     2×            -₹380          → Stable
─────────────────────────────────────────────────────────

EMOTIONAL TAX  (powered by your journal entries)
  ┌──────────────────────────────────────────────────────────────┐
  │  Total estimated behavioral cost this month: -₹9,480         │
  │                                                              │
  │  Win rate by emotion you reported:                           │
  │  Calm           68%  ████████████████  (41 trades)          │
  │  Confident       71%  █████████████████ (18 trades)         │
  │  Neutral         61%  ██████████████    (24 trades)         │
  │  Anxious         28%  ██████             (12 trades)        │
  │  FOMO            19%  ████               (8 trades)         │
  │  Revenge         11%  ██                 (5 trades)         │
  │                                                              │
  │  Note: trades with no journal entry excluded from analysis.  │
  └──────────────────────────────────────────────────────────────┘

TRADING PERSONA
  ┌──────────────────────────────────────────────────────────────┐
  │  Your persona: "Reactive Scalper"                            │
  │  You react quickly to price movement and trade in short      │
  │  bursts. When sessions go well you execute cleanly. When     │
  │  sessions turn against you, the trade frequency increases.   │
  │                                                              │
  │  Strengths:  · Fast execution  · Good win rate when calm    │
  │  Watch out:  · Revenge risk    · Overtrading after losses   │
  └──────────────────────────────────────────────────────────────┘

BTST ACTIVITY  (if any BTST trades in period)
  ┌──────────────────────────────────────────────────────────────┐
  │  4 overnight trades this period                              │
  │  Overnight reversal: 2/4   Avg hold: 14h   Win rate: 25%   │
  │  Avg P&L: -₹620                                             │
  │  [View BTST trades ↓]  ← expands a trade table              │
  └──────────────────────────────────────────────────────────────┘

BEHAVIOR SCORE TREND  (secondary, at the bottom of this tab)
  Score over last 90 days: [line chart]
  Note: This is a trend indicator for self-tracking, not a grade.
```

**Behavior score null state (< 5 trades):**
"Behavioral analysis requires 5+ completed trades. — currently displayed."

---

### Tab: Trades

The fullest trade-by-trade view in the app. The key differentiator from Kite's order history: pattern tags AND journal emotion tags appear inline on each row.

```
Filters: [Segment ▼] [Product ▼] [Result ▼] [Pattern ▼] [Emotion ▼]
                                                             [Search symbol...]  [Export CSV]

Date      Symbol           Qty   P&L       Hold   Pattern     Emotion    📝
──────────────────────────────────────────────────────────────────────────────
Mar 27    NIFTY 24500CE    50    +₹1,100   22m    —           Calm       ✎ filled
Mar 27    BANKNIFTY PE     25    -₹550     14m    [Revenge]   Anxious    ✎ filled
Mar 26    NIFTY 24400PE    75    -₹975     8m     [FOMO]      FOMO       ✎ filled
Mar 26    RELIANCE EQ      100   +₹210     45m    —           —          ✎ (empty)
──────────────────────────────────────────────────────────────────────────────

Page 1 of 6   [← Prev]  [Next →]
```

Clicking the journal icon (✎) on any row opens the TradeJournalSheet. Clicking the pattern chip opens a tooltip explaining the detection evidence. Clicking anywhere else on the row expands inline detail (entry/exit times, prices, strategy if detected).

---

### Tab: Timing

Reveals the trader's performance patterns across the trading day.

```
P&L BY HOUR OF DAY  (bar chart)
  [Bar chart: 9:15 to 15:30, P&L on y-axis, hours on x-axis]
  Bars colored green (positive avg P&L for that hour) or red (negative)

  INSIGHT: Your 9:15–9:30 trades are net -₹2,400 this month.
           Your best window is 10:00–11:30 (net +₹8,200).
           You lose money on average in the last 30 minutes.

WIN RATE BY HOUR  (bar chart)
  [Same x-axis, win rate % on y-axis]

P&L BY DAY OF WEEK  (bar chart)
  Mon    Tue    Wed    Thu    Fri

  INSIGHT: [Best/worst day with reasoning if detectable]
```

---

### Tab: Progress

Shows goal adherence and streak tracking over the selected period.

```
GOAL ADHERENCE
┌──────────────────────────────────────────────────────────────────┐
│  Max 10 trades per day                                           │
│  14/30 days met this month    ████████████░░░░░░  47%           │
│  Current streak: 3 days    Best streak: 7 days                  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  No trading 9:15–9:30 AM                                        │
│  22/30 days met    █████████████████████░░░░░  73%             │
│  Current streak: 5 days    Best streak: 12 days                 │
└──────────────────────────────────────────────────────────────────┘

CONSISTENCY CALENDAR (last 90 days)
  [Heatmap: dark = all goals met, light = partial, empty = no trading]
  [View / edit goals →]  ← links to Goals page
```

---

### Tab: Summary

Last tab because P&L overview is available in Kite. This tab satisfies traders who want it — it just doesn't lead with it.

```
┌──────────┬──────────┬──────────┬──────────┐
│ Total P&L│ Win Rate │ Profit F │ Trades   │
│ +₹45,200 │ 64%      │ 1.8      │ 142      │
└──────────┴──────────┴──────────┴──────────┘

P&L OVER TIME  (line chart, date range)
  [Cumulative realized P&L line with daily P&L bars behind it]

┌────────────────────────┬───────────────────────┐
│  By Segment            │  By Product           │
│  F&O: 78%  Equity: 22% │  MIS: 61%  NRML: 39%  │
└────────────────────────┴───────────────────────┘
```

---

## 4. Behavioral Observations

**Route:** `/alerts`
**Auth required:** Yes

### Purpose

Every behavioral pattern the system detects lands here. The feed is the trader's record of what the system noticed and when. Acknowledging an observation does not trigger anything — it simply marks it as reviewed.

The design challenge: observations should feel like notes from a coach, not fire alarms. A "Critical" observation should not look dramatically different from a "Low" one in terms of card size, weight, or background color. The trader decides what matters. The dot color is the severity cue — nothing else.

### Layout

```
Behavioral Observations                   [Mark all read]  3 unread
─────────────────────────────────────────────────────────────────
 [Recent]  [History]  [By Pattern]
──────────────────────────────────────────────────────┬──────────────
  Feed (70%)                                          │ Filter (30%)
                                                      │
  ┌─────────────────────────────────────────────────┐ │  Pattern type:
  │ ● NEW                                           │ │  ☑ All
  │ Overtrading                                     │ │  ☐ Overtrading
  │ 8 trades placed in a 2-hour window.             │ │  ☐ Revenge
  │ 40% above your daily average of 6.              │ │  ☐ No stop-loss
  │ Trades: NIFTY CE ×5, BANKNIFTY ×3             │ │  ☐ FOMO
  │ 10:34 AM today  ·  Est. cost: -₹1,200          │ │  ☐ ...all 22
  │ [Acknowledge]  [See trades →]                  │ │
  └─────────────────────────────────────────────────┘ │  Severity:
                                                      │  ☑ All
  ┌─────────────────────────────────────────────────┐ │  ☑ Critical
  │ ✓ Acknowledged                                  │ │  ☑ High
  │ Revenge trade risk                              │ │  ☑ Medium
  │ Re-entered BANKNIFTY CE 4 minutes after a       │ │  ☑ Low
  │ ₹800 loss at 09:54 AM. Entry at 09:58 AM.       │ │
  │ Typical revenge pattern: same underlying,       │ │  Date range:
  │ opposite direction.                             │ │  [Today  ▼]
  │ 09:58 AM today                                  │ │
  └─────────────────────────────────────────────────┘ │
──────────────────────────────────────────────────────┴──────────────
```

### Observation Card Anatomy

```
┌──────────────────────────────────────────────────────────────────┐
│  [●]  Pattern Name                                      [Time]   │
│       Evidence line — specific, factual, numbers-based           │
│       Context line — why this matters for this trader            │
│       Affected instruments: [NIFTY CE ×5]  [BANKNIFTY ×3]       │
│       Estimated cost: -₹1,200                                    │
│       [Acknowledge]   [See trades →]                             │
└──────────────────────────────────────────────────────────────────┘
```

Evidence line must be specific. "Overtrading" is a label. "8 trades in a 2-hour window, 40% above your daily average of 6" is evidence. The design must accommodate this length — the card height adjusts to content.

Severity dot:
- Low: muted gray
- Medium: amber
- High: orange
- Critical: orange (same as high but slightly larger dot — not dramatically different)

Critical and High look almost identical. This is intentional.

### Tab: By Pattern

Aggregated view. One card per pattern type that has ever triggered.

```
OVERTRADING
  12 observations this month
  Estimated total cost: -₹4,200
  Trend: ↓ Improving (was 18 last month)
  Last: 2 days ago    [See all →]

REVENGE TRADING
  4 observations this month
  Estimated total cost: -₹2,800
  Trend: → Stable
  Last: today    [See all →]
```

### Empty State

"No observations in this period. No behavioral patterns were detected in the selected date range."

---

## 5. AI Coach

**Route:** `/coach`
**Auth required:** Yes

### Purpose

The trader comes here to process — not to get information, but to think out loud with a knowledgeable observer who has full context. "Why did I trade like that today?" "What should I be watching tomorrow?" "I'm frustrated — help me understand what I'm seeing."

The left context panel communicates that the coach is prepared. It shows not just stats but journal-reported emotions from today's trades — so the conversation starts with shared understanding, not from zero.

The coach asks questions. It reflects observations. It never gives securities advice. It may say: "I see you reported feeling anxious on 4 of today's 6 trades. Your win rate on anxious-labeled trades over 30 days is 28%. Is that something you want to explore?" That is genuine coaching.

### Layout

```
AI Coach                                            ● Market Open
─────────────────────────────────────────────────────────────────
┌──────────────────────────────┬──────────────────────────────────┐
│  Today's Brief               │                                  │
│  ──────────────────────────  │  [Starter prompts when no        │
│  6 trades since 9:15 AM      │   conversation history:]         │
│  Net unrealized: +₹1,240     │                                  │
│                              │  "How was my behavior today?"   │
│  Emotions today:             │  "What patterns am I showing?"  │
│  Calm (3)  Anxious (2)       │  "I just made a bad trade —     │
│  (from your journal entries) │   help me think it through"     │
│                              │  "Help me prepare for tomorrow" │
│  2 observations flagged:     │  "Why do I keep overtrading?"   │
│  Overtrading  10:34 AM       │                                  │
│  Revenge risk 09:58 AM       │  ───────────────────────────── │
│                              │                                  │
│  Context loaded:             │  [Conversation history]         │
│  30-day behavioral data      │                                  │
│  + journal entries           │                                  │
│                              │  ┌────────────────────────────┐ │
│  [New chat  +]               │  │  Ask anything...         ↑ │ │
│                              │  └────────────────────────────┘ │
└──────────────────────────────┴──────────────────────────────────┘
```

### AI Message Feature: Save to Journal

Each AI message has a bookmark icon on hover. Clicking it saves the insight to a coach session record. When saved, the icon changes to a checkmark with "Saved." This gives the trader a way to capture valuable coach observations.

### Message Format

```
User (right-aligned, bordered box):
                        ┌────────────────────────────────┐
                        │  Why do I keep overtrading?    │
                        └────────────────────────────────┘

AI (left-aligned, [TM] avatar, plain text):
[TM]  Looking at your data, I can see a pattern: 9 of 12
      overtrading events this month occurred on days where
      your first trade was a loss. Does that match your
      experience? [📎 Save]
```

Response text auto-formats bold, bullet lists, and numbered lists from markdown. Always includes a question or reflection at the end — the coach is a conversation partner, not a monologue.

### Design Notes

- The context panel line "from your journal entries" under the emotions section is an important trust signal — it shows the coach is working from the trader's own words, not just algorithmic data.
- "New chat +" creates a new session. Previous session is preserved in history.
- The coach page does not show a behavioral score anywhere.

---

## 6. My Patterns

**Route:** `/patterns`
**Auth required:** Yes

### Purpose

This is where the trader comes to understand who they are as a trader over time. Not what happened today — what tends to happen. The unique depth here: journal entries allow the system to connect emotional context to pattern occurrences. "You overtrade after losses" is algorithmic. "You overtrade after losses, and in those cases you most often reported feeling Anxious or Revenge" is a combination of algorithmic detection and journal data.

The screen also serves as the behavioral status hub — it shows the live danger status, streak tracker, and pattern calendar.

### Layout

```
My Patterns
─────────────────────────────────────────────────────────────────

[Live Status Banner — always visible]
┌──────────────────────────────────────────────────────────────────┐
│  ● Safe — No active limits triggered today                      │
│  Daily loss: 18%   Trades today: 6   Consecutive losses: 0      │
└──────────────────────────────────────────────────────────────────┘

[Streak Card + Pattern Calendar — horizontal pair]
┌──────────────────────────────┬───────────────────────────────────┐
│  Streak: 4 clean days        │  PATTERN CALENDAR (30 days)       │
│  Best: 12 days               │  [Calendar heatmap — dark = clean │
│  Milestones: 3d ✓  7d ✓      │   light = observation day]        │
│              14d ✗  21d ✗   │                                   │
└──────────────────────────────┴───────────────────────────────────┘

[Pattern Detail — 2 panel layout]
┌───────────────────────────────┬─────────────────────────────────┐
│  Pattern list (left)          │  Detail (right)                 │
│  ─────────────────────────    │  ──────────────────────────     │
│  ● Overtrading         12×   │  Overtrading                    │
│    2 days ago          ←sel   │  ─────────────────────────      │
│                               │  "You tend to overtrade on      │
│  ● Revenge Trading      4×   │  days where your first trade    │
│    today                      │  was a loss. In the last 30     │
│                               │  days, 9 of 12 overtrading      │
│  ● No Stop-Loss         8×   │  events followed an early       │
│    3 days ago                 │  session loss."                 │
│                               │                                 │
│  ● FOMO Entry           3×   │  EMOTIONAL CORRELATION          │
│    8 days ago                 │  (from your journal entries)    │
│                               │  Anxious  · 9 of 12 events     │
│  ● Early Exit           6×   │  Revenge  · 6 of 12 events     │
│    5 days ago                 │  FOMO     · 3 of 12 events     │
│                               │                                 │
│  ─────────────────────────    │  Frequency last 90 days:        │
│  Not Detected (3):            │  [Weekly bar sparkline]         │
│  ○ Position Sizing            │                                 │
│  ○ Winning Streak OC          │  Usually occurs:                │
│  ○ Strategy Pivot             │  10:30 AM – 11:30 AM            │
│                               │                                 │
│                               │  Worst instances:               │
│                               │  Mar 15: 12 trades  -₹3,200    │
│                               │  Mar 8:  9 trades   -₹1,800    │
│                               │                                 │
│                               │  Estimated cost this month:     │
│                               │  -₹4,200                        │
│                               │  [See related trades →]         │
└───────────────────────────────┴─────────────────────────────────┘

EMOTIONAL TAX CARD
  [Same as Analytics Behavior tab — monthly cost + emotion breakdown]
```

### Live Status Banner States

```
Safe (green left border):
  ● Safe — No active limits triggered today
  Daily loss: 18%   Trades: 6   Consecutive losses: 0

Caution (amber left border):
  ◐ Caution — Approaching daily loss limit
  Daily loss: 72%   Trades: 9   Consecutive losses: 2
  [Alert Guardian →]   ← WhatsApp notification option

Danger/Critical (same amber border — no red siren):
  ⬤ Limit Active — Daily loss limit reached
  Circuit break triggered at 11:23 AM
  [Alert Guardian →]   [Details →]
```

The "Alert Guardian" button connects WhatsApp notifications for the trader's own risk state — it lets them set up a check-in with someone who can hold them accountable.

### Design Notes

- The emotional correlation section in the pattern detail is the highest-value design element on this page. It requires journal data to populate. If fewer than 5 journal entries exist for a pattern, show: "Add journal entries to see emotional correlation data."
- The Not Detected section at the bottom of the pattern list communicates what the trader is doing right. It is not empty data — it is positive signal. Design it as such: "3 patterns never detected" not "3 patterns: N/A."
- Pattern narratives are written in second-person, specific to the trader's actual data, not generic. Generic text here breaks the screen's value entirely.

---

## 7. Blowup Shield

**Route:** `/shield`
**Auth required:** Yes

### Purpose

The Blowup Shield answers: "What has the system's protection actually done?" This screen is unique because it shows **counterfactual financial data** — not estimates, but actual market prices 30 minutes after an alert was triggered, compared to what the trader's position would have been.

This builds trust in two ways: (1) it shows real verified numbers when the protection worked, and (2) it honestly shows when the market recovered after an alert — when following the alert would have cost opportunity. That honesty is the feature's credibility.

### Key Metrics

```
Blowup Shield
─────────────────────────────────────────────────────────────────

┌──────────────────┬─────────────────────┬────────────────────────┐
│ Capital Defended │  Shield Score        │  Heeded Streak         │
│ ₹41,200          │  73%                 │  8 consecutive         │
│ from 12 events   │  heeded/total        │  (without ignoring)    │
└──────────────────┴─────────────────────┴────────────────────────┘

DATA QUALITY
  9 of 12 events verified with real market data  ████████████░░░  75%
  3 still calculating (T+30 price not yet available)
  [Verified ✨] [Calculating ⏱] [No position (auto-squared)]

─────────────────────────────────────────────────────────────────
PROTECTION TIMELINE
─────────────────────────────────────────────────────────────────
```

### Per-Event Display

```
Mar 27 · 11:23 AM                          CIRCUIT BREAK  [Heeded ✓]

  Pattern: Session Meltdown                              [Verified ✨]
  "You had realized losses of 42% of daily capital."

  Long 10 NIFTY 24000 CE @ ₹180. LTP at alert: ₹162

  You exited ✓                  [Expand counterfactual ↓]

    ├── Your P&L (realized):             -₹18,000
    ├── If held to T+30 (market data):   -₹36,500
    └── Net difference:                  +₹18,500 defended  ✨

─────────────────────────────────────────────────────────────────
Mar 22 · 10:42 AM                          COOLDOWN  [Heeded ✓]

  Pattern: Consecutive Loss Streak                       [Verified ✨]
  "3rd consecutive loss. Cooldown triggered."

  Net difference:                          +₹4,200 defended  ✨

─────────────────────────────────────────────────────────────────
Mar 15 · 14:05 PM                          COOLDOWN  [Ignored ✗]

  Pattern: Revenge Trade                                 [Verified ✨]
  "Re-entry BANKNIFTY 6 min after loss."

  You continued trading ✗                 [Expand counterfactual ↓]

    ├── Your P&L (continued trading):     -₹3,200
    ├── If stopped at alert time (T+30):  -₹1,400
    └── Additional loss from ignoring:    -₹1,800
```

**Honestly showing when the alert would have been wrong:**
```
Mar 10 · 09:45 AM                          COOLDOWN  [Heeded ✓]

  Pattern: Opening 5-min Trap                            [Verified ✨]
  "Entry at 09:17 on first 5-min trap."

  You exited ✓                  [Expand counterfactual ↓]

    ├── Your P&L (realized):             -₹2,100
    ├── If held to T+30 (market data):   -₹800  (market recovered)
    └── Note: Heeding this alert cost you ₹1,300 vs. holding.
             This is shown honestly. Not all alerts will be correct.
```

### Pattern Breakdown Table

```
Pattern               Alerts   Heeded %   Avg Saved   Total Saved
─────────────────────────────────────────────────────────────────
Session Meltdown       2        100%        ₹18,500      ₹37,000
Revenge Trading        4         75%         ₹4,200      ₹12,600
Overtrading            5         60%         ₹1,800       ₹5,400
Cooldown Violation     1        100%         ₹4,200       ₹4,200
```

### Design Notes

- No red anywhere on this screen. Green for defended amounts. The "Additional loss from ignoring" row uses regular text weight, not red — it is information, not alarm.
- The honesty note on events where heeding cost opportunity ("This is shown honestly") is a design requirement. Remove it and the screen becomes marketing. Keep it and it becomes a credible tool.
- The shield score (73%) is displayed with a muted color indicator — green ≥70%, amber 40–69%, not specifically red for low scores.

---

## 8. Session Limits

**Route:** `/danger-zone` (display name: Session Limits)
**Auth required:** Yes

### Purpose

This screen shows the trader the status of the risk rules they have set for themselves. It has three tabs: Status (current state), Thresholds (configuration), and History (recent events). The name "Session Limits" replaces "Danger Zone" because the design must communicate: these are your own rules, and reaching them is not a failure — it is the system working as designed.

### Tab: Status

```
Session Limits
─────────────────────────────────────────────────────────────────
 [Status]  [Thresholds]  [History]
─────────────────────────────────────────────────────────────────

CURRENT STATE

┌──────────────────────────────────────────────────────────────────┐
│  ● All session limits within bounds today.              Active   │
└──────────────────────────────────────────────────────────────────┘

    When a limit triggers, this card becomes:

┌──────────────────────────────────────────────────────────────────┐
│  Cooldown active                                                 │
│  Triggered by: Daily loss limit reached (₹4,980 / ₹5,000)      │
│  Triggered at: 11:23 AM today                                   │
│  Active until: Market close (3:30 PM)                           │
│                                                                  │
│  This is informational. You can continue to trade in            │
│  Zerodha Kite if you choose to.                                 │
└──────────────────────────────────────────────────────────────────┘

CURRENT VALUES
  Daily loss            ₹4,980 / ₹5,000   ████████████████████░  99%
  Trades today          9 / 15             ████████████░░░░░░░░░   60%
  Consecutive losses    1 / 3              ██████░░░░░░░░░░░░░░░   33%
  Open positions        2 / unlimited      —
```

### Tab: Thresholds

```
LOSS LIMITS
  Warning level (amber):  [──────●────]  70% of daily loss limit
  Danger level (trigger): [───────────●]  85% of daily loss limit

CONSECUTIVE LOSS LIMITS
  Warning:   [─●─────]  2 consecutive losses
  Trigger:   [──●────]  3 consecutive losses

[Save Thresholds]   [Reset to defaults]
```

### Tab: History

```
This week:
Date        Event                    Trigger              Duration
Mar 27      Cooldown triggered       Daily loss limit     Market close
Mar 25      Circuit break triggered  3 consecutive losses  30 min
Mar 22      Cooldown triggered       Daily loss limit     Market close

[View all history]
```

---

## 9. Goals

**Route:** `/goals`
**Auth required:** Yes

### Purpose

The trader sets behavioral commitments here. The screen tracks whether those commitments are being kept. Goal changes are gated with a 24-hour cooldown — this prevents a trader from modifying their limits in the middle of an emotional session.

### Layout

```
Goals — My Commitments                               Streak: 4 days
─────────────────────────────────────────────────────────────────

┌──────────────────────────────────────────────────────────────────┐
│  Max 10 trades per day                                  [⋯]     │
│  This week:  Mon ✓  Tue ✓  Wed ✓  Thu ✓  Fri —                 │
│  ██████████████████░░  14/30 days met this month   47%          │
│  Current streak: 7 days    Best: 12 days                        │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  No trading 9:15 AM – 9:30 AM                           [⋯]     │
│  This week:  Mon ✓  Tue ✓  Wed ✗  Thu ✓  Fri —                 │
│  ██████████████████████░░  22/30 days met   73%                 │
│  Current streak: 4 days    Best: 9 days    (Missed: Wednesday)  │
└──────────────────────────────────────────────────────────────────┘

[+ Add commitment]

COMMITMENT LOG
  Mar 28 — Modified "Max trades" from 12 to 10 (Reason: too many impulse trades)
  Mar 14 — Added "No trading 9:15–9:30 AM"

CONSISTENCY CALENDAR (last 30 days)
  [30-day heatmap — green = all met, gray = missed at least one]
```

### Goal Change Cooldown

The three-dot menu (⋯) on each goal card shows: View history, Request change, Pause, Delete. "Request change" opens a form asking for a reason. The change is applied after a 24-hour cooldown. A pending change shows as a notice on the card: "Change pending: Max 10 trades → Max 8 trades. Applies tomorrow."

---

## 10. Portfolio Radar

**Route:** `/portfolio-radar`
**Auth required:** Yes

### Purpose

Position concentration and options risk analysis. The trader uses this before entering a new position to check whether the book is already too concentrated, and to monitor options-specific risks (premium decay, days to expiry, breakeven gaps).

### Layout

```
Portfolio Radar                                        [Sync ⟳]
─────────────────────────────────────────────────────────────────

POSITION CARDS  (one per open position)

┌─────────────────────────────────────────────────────────────────┐
│  NIFTY 24500 CE  ·  Long  ·  50 qty                    MIS      │
│  Entry: ₹140    LTP: ₹162    P&L: +₹1,100   +15.7%            │
│                                                                  │
│  Strike: 24500    Breakeven: ₹154    Gap to BE: -₹8 (ITM) ✓   │
│  Premium decay: -₹12/day    Days to expiry: 3d  (amber)        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  BANKNIFTY 52000 PE  ·  Long  ·  25 qty                 MIS     │
│  Entry: ₹220    LTP: ₹198    P&L: -₹550    -10.0%             │
│                                                                  │
│  Strike: 52000    Breakeven: ₹194    Gap to BE: +₹4 (OTM)     │
│  Premium decay: -₹18/day    Days to expiry: 3d  (amber)        │
└─────────────────────────────────────────────────────────────────┘

─────────────────────────────────────────────────────────────────
CONCENTRATION ANALYSIS
─────────────────────────────────────────────────────────────────

Total capital at risk: ₹1.8L across 8 positions

BY EXPIRY WEEK                        BY UNDERLYING
Week Mar 28:  ████████  45%  ⚠       BANKNIFTY   ████████  38%  ⚠
Week Apr 4:   ██████    32%           NIFTY       █████     22%
Week Apr 11:  ████      23%           RELIANCE    ████      18%
                                       Others      ████      22%

Warnings triggered:
  [⚠ Expiry concentration: 45% in single expiry week — above 40% threshold]
  [⚠ Underlying concentration: 38% in BANKNIFTY — above 30% threshold]

DIRECTIONAL SKEW
  Long: 65%   Short: 35%   — Mildly long-biased

MARGIN UTILIZATION
  Used: ₹94,000  /  Available: ₹1,60,000  =  59%  (within bounds)

─────────────────────────────────────────────────────────────────
GTT ORDERS
─────────────────────────────────────────────────────────────────

  Total active: 3    Honored: 12    Overridden: 2

  Symbol            Trigger Price    Qty    Created
  NIFTY 24500CE     ₹130             50     Mar 26
  BANKNIFTY PE      ₹210             25     Mar 26
  RELIANCE          ₹2,780           100    Mar 25
```

### Design Notes

- Days to expiry on position cards: green if ≥5 days, amber if 3–4 days, red if ≤2 days. This is one of the few justified uses of red on position data.
- Concentration warning chips appear inline in the concentration table — not as a banner above the entire page.
- GTT override count (2) is displayed neutrally. It is not flagged as a behavioral pattern — it is operational data.

---

## 11. Reports

**Route:** `/reports`
**Auth required:** Yes

### Purpose

Generated periodic reports: Morning Brief (pre-session readiness), End-of-Day (behavioral narrative + emotional journey), and Weekly Summary (trend overview). The AI narrative and the Emotional Journey timeline are the most valuable content — design around them.

### Layout

```
Reports
─────────────────────────────────────────────────────────────────
┌──────────────────────────────┬──────────────────────────────────┐
│  [EOD] [Morning] [Weekly]    │  Mar 28 — End of Day    [PDF ↓] │
│  ──────────────────────────  │  ──────────────────────────────  │
│  EOD  Today, Mar 28          │                                  │
│  +₹3,450 · 8 trades · B:74   │  +₹3,450  8 trades  67% WR     │
│  ──────────────────────────  │                                  │
│  Morning  Today, Mar 28      │  TODAY'S EMOTIONAL JOURNEY      │
│  Readiness: 82/100           │  ───────────────────────────     │
│  ──────────────────────────  │  09:23 AM  😤 FOMO entry        │
│  EOD  Yesterday, Mar 27      │             NIFTY CE:  -₹975    │
│  -₹1,200 · 12 trades · B:61  │  09:58 AM  😤 Revenge trade     │
│  ──────────────────────────  │             BANKNIFTY: -₹550    │
│  Weekly  Week of Mar 24      │  10:45 AM  😎 Calm entry        │
│  +₹8,600 · 38 trades         │             RELIANCE:  +₹210    │
│  ──────────────────────────  │  11:12 AM  😊 Confident         │
│                              │             NIFTY CE:  +₹1,100  │
│                              │                                  │
│                              │  PATTERNS DETECTED TODAY        │
│                              │  Overtrading  · 10:34 AM       │
│                              │  Revenge risk · 09:58 AM       │
│                              │                                  │
│                              │  KEY LESSONS                    │
│                              │  💡 Your calm trades won 3/4   │
│                              │  ⚠  Opening FOMO cost -₹975    │
│                              │  → Tomorrow: wait 15 min       │
│                              │                                  │
│                              │  BEHAVIORAL NARRATIVE           │
│                              │  ───────────────────────────    │
│                              │  Today showed a clear pattern:  │
│                              │  your opening-session trades    │
│                              │  were emotionally driven (FOMO  │
│                              │  + Revenge entries), while      │
│                              │  your mid-session trades were   │
│                              │  controlled and profitable...   │
└──────────────────────────────┴──────────────────────────────────┘
```

### Morning Brief Report (When Selected)

```
READINESS SCORE: 82/100   ● Good session predicted

Day warning:  ✗  No historical pattern for today being a danger day

PRE-TRADING CHECKLIST
  ✓  Reviewed yesterday's journal entries
  ○  Identified 2 patterns to watch (Overtrading, Revenge risk)
  ○  Set today's maximum trade count: 10
  ○  Checked expiry calendar (Mar 28 — weekly expiry day, CAUTION)

WATCH OUT TODAY
  · Expiry day — volatility will spike around 14:00–15:00
  · You've overtraded on 3 of last 4 expiry days
  · Your 9:15–9:30 win rate is 23% — wait for cleaner setups

YESTERDAY RECAP
  -₹1,200 · 12 trades · Score: 61 · Behavior was erratic in the afternoon
```

### Design Notes

- The Emotional Journey timeline is the most visually distinctive element in the reports. The emoji + trade + P&L format tells the session story faster than any text. This is unique to TradeMentor.
- The "Key Lessons" section uses three visual types: lightbulb (💡) for wins, warning (⚠) for patterns, arrow (→) for tomorrow's focus. Keep these consistent across all reports.
- The behavioral narrative should be displayed at a comfortable reading size — 15px line height 1.6. It is meant to be read slowly, not scanned.

---

## 12. Settings

**Route:** `/settings`
**Auth required:** Yes

### Tabs

**Profile**: Name, email, trading style (scalper/swing/positional), experience in years, primary segment (F&O/Equity/Both), trading capital (₹ range bracket), trading since (year).

**Risk Limits**: Daily loss limit (₹ with % equivalent shown), max trades per day, max position size (₹), cooldown after N consecutive losses (slider: 15/30/45/60 min), circuit break at X% of capital.

**Notifications**: Push notifications (toggle + permission request if not granted), WhatsApp notifications (toggle + guardian phone number input), in-app toast toggle, quiet hours setting.

**Account**: Connected broker (account ID, status, last sync timestamp), Reconnect Zerodha button, API key configuration (for per-user Zerodha keys), Disconnect Zerodha (destructive), Delete all my data (destructive, requires typing confirmation phrase).

**Personalization**: AI coach tone (analytical/empathetic/direct), default Analytics tab (Behavior/Trades/Timing/Progress/Summary), alert frequency (all alerts / daily summary only / critical only).

### Layout

```
Settings
─────────────────────────────────────────────────────────────────
 [Profile]  [Risk Limits]  [Notifications]  [Account]  [Personalization]
─────────────────────────────────────────────────────────────────
[Form fields — labels above inputs]

[Save changes]  ← bottom of tab, only enabled when form is dirty
```

---

## 13. Onboarding Wizard

**Route:** Modal on `/dashboard` post-OAuth
**Auth required:** Yes (freshly authenticated)

### Steps

```
Step 1 of 5  ████░░░░░░

What should we call you?
[First name    ]

Required — used to personalize your experience.

                                              [Next →]
─────────────────────────────────────────────────────
Step 2 of 5  ████████░░░░

How long have you been trading?
[0–1 year]  [1–3 years]  [3–5 years]  [5+ years]

How would you describe your style?
[Scalper]  [Day trader]  [Swing]  [Positional]

                              [Skip for now]  [Next →]
─────────────────────────────────────────────────────
Step 3 of 5  ████████████░░

Approximately how much capital do you trade with?
[Under ₹1L]  [₹1–5L]  [₹5–25L]  [Over ₹25L]

This helps calibrate your behavioral alerts.
                              [Skip for now]  [Next →]
─────────────────────────────────────────────────────
Step 4 of 5  ████████████████░░

What do you primarily trade?
[F&O — Futures & Options]  [Equity]  [Both]

                              [Skip for now]  [Next →]
─────────────────────────────────────────────────────
Step 5 of 5  ████████████████████

Set your initial risk limits:
  Max daily loss:  [₹ ________]
  Max trades/day:  [________  ]

These are your personal guardrails. You can change
them anytime in Settings → Risk Limits.

                                         [Finish →]
```

### Design Notes

- Each step saves immediately on Next/Finish click.
- Error saving: inline error below the field, retain user's input, retry on next click.
- The skip link is small muted text, not a button. Not prominent, but present.
- Step 1 cannot be skipped — name is required.
- Completion: modal closes, "You're all set" toast, dashboard loads.

---

## Empty States Reference

| Screen | Condition | Message |
|--------|-----------|---------|
| Dashboard — Activity | No trades today | "No trades today yet. Your activity will appear here as you trade." |
| Dashboard — Observations | No observations today | *(no empty state shown — absence of observations is normal, requires no message)* |
| Observations | No observations in period | "No behavioral patterns were detected in this period." |
| Analytics — Trades | No trades in range | "No completed trades in the selected date range." |
| Analytics — Behavior | <5 trades | "Behavioral analysis requires 5+ completed trades." |
| My Patterns | <10 trades | "Your behavioral patterns will appear after 10+ completed trades." |
| My Patterns — Emotional Correlation | <5 journal entries for pattern | "Add journal entries to unlock emotional correlation data." |
| Blowup Shield | No protection events | "Your shield is active and monitoring. Events will appear here after the system first activates." |
| Reports | No reports generated | "Reports generate at the end of each trading day." |
| Goals | No goals set | "Add your first behavioral commitment below." |
| Portfolio Radar | No open positions | "No open positions to analyze." |

---

*Previous: [01_USER_FLOWS.md](./01_USER_FLOWS.md) | Next: [03_MOBILE_SCREENS.md](./03_MOBILE_SCREENS.md)*
