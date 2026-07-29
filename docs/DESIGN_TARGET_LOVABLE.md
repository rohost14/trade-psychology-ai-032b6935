# Design Target — Lovable mockup ("Trade Guardian AI" / TradeMentor)

Captured 2026-07-29 by walking the full Lovable preview (landing + all 7 app pages). This is the **visual/UX target** for the TradeMentor redesign. Screens: Dashboard, Alerts, Patterns, Journal, Analytics, AI Mentor, Settings, + marketing landing.

## Design system

**Theme:** near-black background (dark, faint green-black), cards slightly elevated with subtle 1px borders + generous radius. Dark-first.

**Accent = teal/emerald** (~#2dd4bf). Primary CTAs, active nav, toggles-on, positive values, "listened"/"improving", highlights. This is the signature — the current app leans indigo/muted; **target = teal**.

**Color semantics (consistent everywhere):**
- Green/teal = profit · good · listened · improving · rule-followed
- Red = loss · danger · ignored · worsening
- Amber = warning/caution

**Typography:** heavy bold grotesk headlines (large, tight leading, e.g. "Most losing days are made of 3 bad trades"); muted-gray body; UPPERCASE letter-spaced micro-labels ("HOW IT WORKS", "COST LEAKS", "PAST COST"); **monospace tabular for ALL numbers, ₹ amounts, times, percentages**.

**The core visual language = money on everything.** Every alert, pattern, and rule carries: a ₹ cost + an occurrence count + a trend. "PAST COST −₹4,200", "cost you −₹18,400 across 12 occurrences", "−₹769/hit". Behaviour→money is the whole aesthetic. (Aligns with our rule: RAW realized P&L of flagged trades, never counterfactual.)

**Tone:** "Observation only · you decide the next click", "no advice, no signals", "from your own tape". Calm, factual, rupee-denominated. This IS "mirror, not blocker" — matches our philosophy exactly.

## Component vocabulary
- **Stat cards:** tiny uppercase label + big colored mono number + one-line sub. Used as 4-up rows (Dashboard, Alerts, Analytics, Patterns detail).
- **Category pills:** uppercase colored tags on alerts/patterns — PACE / EMOTIONAL / SIZE / POSITION / RISK.
- **Severity dots:** red (critical) / amber (warning) beside each alert.
- **Trend arrows:** ↗ Worsening (red) / ↘ Improving (green) / — Stable (grey).
- **Threshold sliders + toggles:** rules as on/off + a slider with current value + usage ("4× this week · last 2h ago").
- **Master-detail:** Patterns = left list (ranked cost leaks) + right detail (stats, trend analysis, triggers, related trades).
- **Tabbed analytics:** Overview / Symbols / Timing / Behavior / Discipline / Mood.
- **Daily-P&L calendar strip:** colored per-day tiles (+/− with trade count).
- **Timeline replay:** vertical event timeline, color-coded draggable dots (FILL teal / ALERT red), selected = teal ring.
- **Habit progress bars:** Days planned 3/3, Reviewed 3/3, Calm 1/3.
- **Outcome tags on trades:** IGNORED (red) / LISTENED (green).
- **Header:** market-status clock ("CLOSED 22:50:58").

## Page-by-page (target vs current)
- **Dashboard "Trading Desk":** Intraday P&L + % + Session-stats dropdown · Live Alerts (rich story cards) · Open Positions table ("tap a row to journal").
- **Alerts:** ⚠️ **MERGES Alerts + Rules into one screen** — left = alert stream (ACTIVE/HISTORY, severity filter, PAST COST per card); right = live RULES panel (toggles + threshold sliders). Top = 4 money stats (Active / Preserved 30D / **Cost of ignoring** / Ack rate).
- **Patterns:** master-detail cost-leak browser (per-pattern cost, freq, trend, triggers, related trades w/ IGNORED/LISTENED).
- **Journal:** Today's Intent + Lesson · Last-30-days habit bars · Lesson Library · entries with emotion tags + type filter + "+New".
- **Analytics:** 6 tabs · ranked cost leaks · 4 hero KPIs · Performance-Snapshot metric grid · Daily-P&L strip.
- **AI Mentor** (= Chat/Coach): grounded-in-your-data chat, suggested prompts, "observation only — no advice", SEBI disclaimer.
- **Settings:** Profile · **Accountability Partner** (WhatsApp — "they never see your P&L or positions") · Alert Rules.

## ⚠️ Conflicts to resolve BEFORE implementing (decisions needed)
1. **Alerts + My Rules merged** in the mockup, but our current page-ownership rule keeps Analytics/Alerts/My Patterns separate (no story recomputed twice). Decide: adopt the merge, or keep separate.
2. **No "My Record" page** in the mockup; it still references the retired **"Blowup Shield score"**. Our app replaced Blowup Shield → My Record (a strong, on-philosophy page). Decide: keep My Record and drop the Blowup Shield naming, or re-add a blowup score.
3. **Journal leans manual** (+New, intent/lesson typing) — conflicts with our hard constraint "zero manual-input adoption". Mitigated by the landing promise "AI drafts the entry from what actually happened" → keep entries AI-drafted, manual optional.
4. **Nav renames:** Chat→**AI Mentor**, My Patterns→**Patterns**. Cosmetic; adopt if desired.
5. Demo/aspirational values in mockup (loss cap ₹10,000, etc.) are cosmetic — real data wires to our engine.

## Not a redesign of logic
This is a **skin + IA** change. The backend engine, detectors, real-time pipeline, and money-truth stay. The mockup's data model (cost-per-pattern, occurrence counts, ignored/listened, trend) maps cleanly onto what the BehaviorEngine + RiskAlerts already produce.
