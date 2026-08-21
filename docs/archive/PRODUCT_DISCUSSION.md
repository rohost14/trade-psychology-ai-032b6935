> **ARCHIVED 22 Aug 2026 — do not use as a current reference.**
>
> June-17 log recommending a "60% behaviour score" - exactly the number deleted in 16d79ce and banned by DESIGN_SYSTEM.md:122.
>
> Live findings, if any, were rescued into `docs/ENGINE_BACKLOG.md`.

---

# Product Discussion Log
Running record of product decisions, problems raised, and recommendations given.
Format: Q = what user asked / raised. R = what I recommended.

---

## Session 1 — 2026-06-17

### Topic: Dashboard Structure

**Q:** Dashboard doesn't feel production-ready. Hero is mostly empty — only P&L and a small sparkline chart in top-right that's useless. Below that: full-width alerts, then open positions, then closed positions, with blowup shield on the right. What can be improved? What am I missing? No investor/entrepreneur will like it and no trader will use it.

**Current structure (from code):**
```
Banners (token expired / capital prompt / sync error) — conditional
Page header: "Dashboard" + tiny status line
SetupNudgeCard (new users, dismissable)
MorningIntentCard + EodComparisonCard (time-conditional)
SessionHeroCard
  Left: State pill + 44px P&L number + 1 description line + footer stats + VIX strip
  Right: 176px sparkline (too narrow to read)
RecentAlertsCard — full width
Two-column layout (62% / 38%)
  Left:  OpenPositionsTable
         ClosedTradesTable (last 3 days)
  Right: BlowupShieldCard
         HoldingsCard (only if holdings exist — invisible to pure F&O traders)
AiCoachFab (floating, bottom-right)
```

**R — Problems identified:**

1. **Hero is one-dimensional.** 44px P&L number + state pill is generic — every broker app shows this. The 176px sparkline is too narrow to be useful. No risk context, no daily limit progress, no behavioral signal.

2. **No risk gauges anywhere.** F&O traders need: "I've used 63% of my daily loss limit" and "I've taken 5/10 trades". These are the two guardrails that matter most intraday. Neither is visible on the dashboard.

3. **No margin utilization.** The margin card (`/api/zerodha/margins`) exists in the backend but is not on the dashboard. For F&O traders this is critical — knowing how much margin is deployed vs available.

4. **Behavioral signal buried.** The app's core USP (behavioral analysis) is only visible via the alerts feed. There's no score, streak, or summary anywhere on the hero. "3 days clean", "2 alerts heeded today", "60% behavior score this week" — none of this shows.

5. **Alerts take full width.** The `RecentAlertsCard` spans full width. On days with 5+ alerts this dominates the page. Better: collapse to a contextual strip (1-2 lines) with a link to `/alerts`.

6. **Sidebar is near-empty for the target user.** Pure F&O / MIS traders have no holdings → no `HoldingsCard` → right column is just `BlowupShieldCard` (one card in 38% width). That's a lot of blank space.

7. **Closed trades show last 3 days.** Dashboard should only show today's closed trades (5-8 rows max). Anything older belongs in Analytics.

8. **AI Coach FAB is hidden.** The coach is one of the highest-value features. A floating button tucked in the corner is the lowest-visibility placement. No trader discovers it naturally.

9. **Morning intent above the hero.** The first thing a trader sees when they open the app should be their live session state, not a pre-market card (which only shows 7–10 AM anyway). The intent card should be time-gated and placed below the hero or inline within it.

**R — Recommended dashboard structure:**

```
BANNERS (keep, conditional)

MORNING INTENT (time-gated 7-10 AM, move below hero or inline in hero)

HERO — redesign from 1 big P&L to 3-panel grid:
  Panel A (left, 45%):
    - State pill (DANGER / CAUTION / SAFE)
    - Session P&L — big number (realized + unrealized split shown below)
    - Description line (e.g., "5 trades · 60% win rate · 3 alerts")
  Panel B (top-right, 55%): Risk gauges
    - Daily P&L limit bar: ₹15,700 / ₹25,000 (63%)
    - Trade count bar: 5 / 10 trades
    - Margin deployed: X% (fetch from margins endpoint)
  Panel C (footer, full-width):
    - Behavioral health row: "2 danger alerts | 3 heeded today | 4-day clean streak"
    - VIX inline (keep)

ALERTS STRIP (contextual, not full section):
  - 0 alerts → hidden or subtle "Clean session" line
  - 1-3 alerts → compact inline cards
  - 4+ → top 2 shown + "N more →" link
  - Move full list to /alerts page (it already exists)

OPEN POSITIONS (full width — most important real-time data)

TWO-COLUMN (65/35):
  Left:  Today's Closed Trades (max 8 rows, link to analytics for more)
  Right: Margin card (new — always visible)
         Blowup Shield (keep)
         Holdings summary (if exists — summary only, no full table)

EOD COMPARISON (time-gated after 15:30, keep)

AI COACH — make more prominent (e.g., inline card or sticky strip, not just FAB)
```

**R — What this achieves:**
- Hero is data-dense, immediately communicates risk state + limits
- Risk gauges make the "mirror not blocker" principle visible at a glance
- Margin gives F&O traders the one number they check constantly
- Behavioral health strip shows the app's USP on the main screen
- Alerts are contextual, not overwhelming
- Right sidebar always has content (margin + shield)
- Closed trades scoped to today (cleaner, less noise)

**Status:** Discussion only. Not implemented. Awaiting approval.

---

### Follow-up — Dashboard (mobile-first correction)

**Q:** Holdings card — don't add it, adds no value for F&O traders. On alerts, "2-3 line contextual" is unclear — what actually works for traders and design? Also: almost all users on mobile. And does margin require a new API call every page load?

**R — Holdings:** Confirmed removed. No value for F&O/MIS-only traders.

**R — Margin API:** Yes, a separate Zerodha API call (`/api/zerodha/margins`). But NOT polling — same event-driven pattern as positions: fetch on load + re-fetch on WebSocket trade event (margin changes exactly when a position opens/closes). One call per trade event, well within Zerodha rate limits. Cost is acceptable. Add it.

**R — Mobile changes everything:** Single column, vertical scroll, bottom nav fixed. Traders open app either from a push notification (want alert immediately) or to check P&L mid-session. Priority order must reflect this.

**R — Alerts corrected:** "Contextual strip" was a desktop idea. On mobile:
- 0 unacknowledged → section disappears (silence = clean signal)
- 1-3 unacked → show all as full-width cards, highest severity first
- 4+ unacked → show top 2 + "N more unacknowledged →" chip to /alerts
- Full list stays on /alerts page

**R — Revised mobile-first stack:**
```
1. SESSION HEADER (compact, sticky candidate)
   State chip (DANGER/CAUTION/SAFE) + P&L + sync button

2. MORNING INTENT (time-gated, 7–10 AM only)

3. HERO CARD (redesigned, data-dense)
   Large P&L (realized | unrealized split)
   Risk gauges: [Daily limit bar 63%] [Trade count 5/10]
   Margin row: ₹1.2L deployed / ₹2.5L available
   Footer: Win rate · Drawdown · Behavioral score chip

4. UNACKNOWLEDGED ALERTS (only if present)
   Top 2-3 by severity, full-width cards
   "N more →" overflow chip

5. OPEN POSITIONS (live P&L per row)

6. TODAY'S CLOSED TRADES (today only, max 8 rows)
   "View all in Analytics →" footer link

7. BLOWUP SHIELD summary card

8. EOD COMPARISON (time-gated, after 15:30)
```

Desktop = 2-col adaptation: main content left, margin card + shield right.

**Open question:** Should the session header (state chip + P&L) be sticky on mobile scroll?

**Status:** Discussion ongoing. Not implemented.

---

### Follow-up 2 — Dashboard deep dive

**Q:** Where is the predictive alert feature? What does it actually show/do? Is current dashboard UI elegant, minimal, production-ready million-dollar SaaS? Design it on Google Stitch (project: TradeMentor Production). What does Blowup Shield actually show? Do we need it on dashboard? What else is missing?

**R — Predictive context strip:**
`PredictiveContextStrip.tsx` exists and is built. Was REMOVED from dashboard in session 36 — folded into a morning push notification (8:30 AM Celery task). Still in codebase, just unwired.

What it shows:
- **Danger hour warning** — "You historically lose at 14:00. Trade smaller or wait it out." (from ML pattern: `danger_hours` list)
- **Danger day warning** — "Win rate below 35% on Fridays historically." (from `danger_days` list)
- **Revenge window** — "You typically enter within 8 min of a loss. Step back." (real-time check via `/api/personalization/predictive-check`)

Each row is dismissable per session (sessionStorage). Shows nothing if no patterns learned yet.

What it does NOT do: send notifications during session. The 8:30 AM push is a morning briefing. The strip was the only live-session predictive element — and it was removed.

**R — What predictive alerts actually fire (and when):**

| Trigger | Condition | Channel | Built? |
|---|---|---|---|
| Morning danger briefing | 8:30 AM Celery | Push/WhatsApp | Yes |
| Early warning P&L | 70% daily loss limit hit | Push/WhatsApp | Yes |
| Early warning trade count | 80% daily trade count hit | Push/WhatsApp | Yes |
| Danger hour (in-session) | Currently in your historical danger hour | In-app strip (unwired) | Yes, unwired |
| Danger day (in-session) | Today is your historical danger day | In-app strip (unwired) | Yes, unwired |
| Revenge window (in-session) | Currently in post-loss window | In-app strip (unwired) | Yes, unwired |

The in-session predictive strip was killed because "too static/generic" (session 36 note). Should be reconsidered — it's genuinely useful live data that no brokerage shows.

**R — Blowup Shield card (dashboard):**
Shows: heed rate % (what % of behavioral alerts you acted on in last 30 days) + P&L lost after ignored alerts + consecutive heed streak. Separate API call to `/api/shield/summary`.

**Verdict: Remove from dashboard.** Reasons:
1. New users: shows "No alerts yet this period" — empty card on day 1
2. It's a 30-day lagging metric, not live session data
3. Doesn't answer "should I trade right now"
4. Takes up 38% sidebar space that should go to Margin card + predictive context
5. The heed rate belongs in MyPatterns / weekly summary, not main dashboard

**R — Honest assessment of current dashboard:**
No. Not production-ready. Not million-dollar SaaS quality. Problems:
- Hero = 44px P&L number + 176px sparkline no one can read. Generic. Every broker app has this.
- App's core USP (behavioral analysis) is invisible until you scroll past empty hero
- New user day 1: 3 empty cards (BlowupShield, alerts, hero sparkline)
- No risk gauges, no margin, no daily limit visible
- Predictive context strip removed — nothing live and forward-looking remains
- Right sidebar (38%) is nearly empty for F&O-only traders (no holdings)
- Closed trades show 3 days of history — too much noise on dashboard

**R — What should replace Blowup Shield on dashboard:**
- Margin card (already built: `MarginStatusCard.tsx`) — always useful
- Predictive context strip (re-wire it) — live, actionable, differentiator

**R — Final proposed dashboard structure (mobile-first):**
```
1. STICKY STATUS BAR (44px)
   State pill (DANGER/CAUTION/SAFE) | P&L in DM Mono | Sync button + "Xm ago"

2. MORNING INTENT CARD (7–10 AM only)

3. HERO CARD (data-dense, not one big number)
   Main: Large P&L + realized/unrealized chips
   Row 2: [Daily Limit progress bar 63%] [Trades 5/10 progress bar]
   Row 3: Margin: ₹1.2L deployed · ₹2.5L free (DM Mono)
   Footer strip: "2 danger alerts · 3 heeded · 4-day clean streak"

4. PREDICTIVE CONTEXT STRIP (re-wire existing component)
   Danger hour / danger day / revenge window — dismissable per session
   Hidden when nothing firing. ZERO new backend work needed.

5. ACTIVE ALERTS (unacknowledged only)
   0 unacked → section hidden
   1-3 → full cards with acknowledge button
   4+ → top 2 by severity + "N more →" chip to /alerts

6. OPEN POSITIONS (full width, live P&L per row)

7. TODAY'S CLOSED TRADES (today only, max 8 rows)
   Each row: symbol | hold time | P&L | optional behavior chip
   "View all in Analytics →" footer link

8. MARGIN CARD (compact — already built MarginStatusCard.tsx)
   Available | Used | % bar

9. EOD COMPARISON (15:30+ only)
```

Desktop: 2-col adaptation — content left, margin card right.

**Removed from dashboard:** BlowupShieldCard (→ move to MyPatterns), HoldingsCard (→ not relevant for F&O), SetupNudgeCard after first week.

**R — Google Stitch:**
Attempted to create project "TradeMentor Production" and generate dashboard screen. Stitch API timed out on 3 attempts (different models: Gemini 3.1 Pro, Gemini 3 Flash, shorter prompts). Service issue. Try manually at labs.google/stitch with the spec above.

---

### Follow-up 3 — Blowup Shield deep dive + dashboard vision

**Q:** What is the T+30 position tracking feature (track position 15 and 30 mins after alert to calculate money saved)? Is that part of Blowup Shield? Is it useful or should it be improved? What should the dashboard actually be to feel like a million-dollar SaaS?

**R — T+30 feature (AlertCheckpoints):**
Was called `AlertCheckpoints`. Deliberately removed — code comment in `shield_service.py`: *"No T+30 counterfactuals. No 'capital defended' performance claims. No AlertCheckpoints."* Was planned, partially or fully built, then stripped before current version.

What it would do: snapshot option price at alert time, schedule Celery tasks at T+15 and T+30, compare prices, show "You saved ₹500 in next 30 minutes."

**R — Should we build it? NO. Reasons:**
1. **Infrastructure**: Celery tasks at T+15 and T+30 per alert, Kite API calls for option quotes, DB storage of price snapshots. High cost.
2. **Backfires when market reverses**: Alert fires, you exit at ₹15. Price goes to ₹20 in 30 mins. Now it shows "you missed ₹500" — alert looks like bad advice. Cannot control market direction. Actively undermines alert trust.
3. **Current approach is better**: Looking at actual CompletedTrades after the alert (what you actually DID) is more honest and more behaviorally relevant than a market counterfactual.

**R — What Blowup Shield actually tracks (current):**
For each alert: looks at CompletedTrades with `entry_time > alert.detected_at` within same session (before 15:30 IST). If no new positions → "heeded". If new positions → "continued" + shows P&L of those trades. Factual behavior, not market prediction.

**R — How to make Blowup Shield compelling (it currently isn't):**
The feature is valuable. The framing and presentation are weak. It should show:
- Comparative stat: "When you heed alerts, next trade avg +₹420. When you ignore: -₹2,800."
- Per-pattern breakdown: Revenge Trade | 3 alerts | 2 heeded (67%) | ignored → -₹4,200
- Streak + spiral sessions

But this is a report, not a live signal. Keep it on the dedicated `/blowup-shield` page. Remove it from the dashboard card. Move heed rate + streak into MyPatterns page instead.

**R — What makes a million-dollar SaaS dashboard:**
The problem isn't individual features — it's no narrative structure. The dashboard should tell one story every time it's opened: "Here is where you stand → here is your risk → here is what you're doing wrong right now → here are your positions." Sequential. Like a sentence.

Current dashboard reads like a dictionary — all the words present but in random order.

**Three highest-impact changes that need zero new backend work:**
1. **Replace empty hero with data-dense session card**: P&L + daily limit gauge + trade count gauge + margin in one card. Tells the whole session story in 2 seconds.
2. **Re-wire PredictiveContextStrip** (already built, just unwired): "You historically lose at 14:00 — 47 minutes left in your danger hour." No brokerage shows this. Single feature that differentiates the product for investors.
3. **Make alerts conditional**: Zero alerts = minimal clean dashboard. Three danger alerts = alert cards dominate. Dashboard should feel different on a clean day vs a danger day. Currently looks identical regardless.

**Status:** Discussion ongoing. Not implemented. Awaiting approval.

Dashboard spec for Stitch prompt: See "Stitch Dashboard Prompt" section below.

**Status:** Discussion ongoing. Not implemented. Awaiting approval before any code changes.

---

### Stitch Dashboard Prompt (use at labs.google/stitch)

```
Dark theme mobile trading psychology dashboard for TradeMentor (Indian F&O options trader app).

COLORS: Background #0F0F1A. Cards #1C1C2E, 1px border rgba(255,255,255,0.08). Teal #0D9488. Profit green #2F9E68. Loss red #D94F43. Amber warning #E09B17. No gradients, no blur, no glassmorphism.
FONTS: Geist headings. Inter body. DM Mono tabular-nums for ALL numbers.
Cards: 12px border-radius. Progress bars: 6px height rounded. Alert left borders: 3px.

[1] STICKY STATUS BAR (44px)
Left: red pill "● DANGER" | Center: "-₹15,700" DM Mono red | Right: sync icon + "2m ago" gray

[2] HERO CARD (#1C1C2E)
Large "-₹15,700" red DM Mono 38px
Chips row: "Realized -₹16,485" red chip | "Unrealized +₹785" green chip
Progress bars row: [Daily Limit: 63% amber bar] [Trades: 5/10 teal bar]
Margin: "₹1.2L deployed · ₹2.5L free" DM Mono small gray
Footer strip (slightly darker): "2 danger alerts · 3 heeded today · 4-day clean streak"

[3] PREDICTIVE WARNING (thin row, 3px amber left border)
Clock icon + "Danger hour — You historically lose at 14:00. Trade smaller." + X button

[4] ACTIVE ALERTS — header "Active Alerts" red badge "3"
Alert card (3px red left border): "Revenge Trade" bold + "HIGH" red chip
  Body: "NIFTY CE entry 25min after ₹13,000 loss" | "Est. ₹2,700" + Acknowledge outline button
Alert card: "No Stop-Loss" HIGH | "FINNIFTY CE open 47min, unrealised -₹3,200" | "Est. ₹5,800" + Ack
Alert card: "Size Escalation" HIGH | "BANKNIFTY 100 lots — 4× avg size after loss" | "Est. ₹4,200" + Ack
"2 more alerts →" teal link

[5] OPEN POSITIONS — header "Open Positions" teal badge "2"
Row: "NIFTY 23000 CE" bold / "NFO · MIS" gray — right: "+₹785" green | "50 qty" gray
Row: "BANKNIFTY 48500 PE" bold / "NFO · MIS" gray — right: "-₹345" red | "15 qty" gray

[6] TODAY'S TRADES — header "Today's Trades" gray badge "3 closed"
Row: "NIFTY PE" | 85m | +₹3,625 green
Row: "SOLARINDS" | 3h 17m | -₹13,000 red | amber chip "Held too long"
Row: "NIFTY CE" | 35m | -₹2,700 red | red chip "Revenge"
"View all in Analytics →" teal link

[7] MARGIN CARD (compact)
"Margin" label + pie icon | Available ₹2.5L | Used ₹1.2L | 35% green progress bar

[8] BOTTOM NAV (5 icons, dark bar)
Home (teal active) | Analytics | Alerts (red badge "7") | Patterns | Chat
```

---
