# Analytics Screen — Full Redesign Plan v3
*Route: `/analytics` | File: `src/pages/Analytics.tsx`*
*Session 21 (2026-03-16) — Final plan. Addresses: tab structure, genuine out-of-the-box analytics, UI/UX design system, critical trades, production-grade principles.*

---

## What Zerodha Already Has (Don't Replicate)
- P&L calendar heatmap
- Instrument-level P&L
- Holdings / positions history
- Charges breakdown
- Equity curve

## What BlowupShield Already Does (Don't Replicate)
- Cost of behavioral mistakes in ₹
- Counterfactual P&L ("what you saved")
- "What if" calculations on ignored alerts

Everything we build in analytics must be different from both of these.

---

## Part 1: 5 Genuinely New Analytics Features

These don't exist anywhere in the product, don't exist on Zerodha, and are directly useful to a trader.

---

### Feature 1: Statistical Edge Confidence

**The question it answers:** "Is my win rate a real edge, or am I just lucky?"

Every trader knows their win rate. Nobody tells them whether it's statistically meaningful. A 60% win rate on 12 trades is almost certainly noise. A 58% win rate on 200 trades is a real edge. Traders make business decisions (sizing, capital allocation) based on a win rate that may not be real.

**What to show:**
```
Your Win Rate: 58.3%  (47 trades)
Edge Confidence: 68%

At 47 trades, your win rate could be anywhere between 44% and 72%.
You need 120+ trades to confirm this edge with 90% confidence.
```

**Implementation:** Binomial confidence interval. Given `n` trades at win rate `p`, the Wilson interval gives `[p_low, p_high]`. Confidence that true edge > 50% = `1 - CDF(0.5, n, p)`. Pure math, no extra data needed — entirely computable from existing `CompletedTrade`.

**Why it's not condescending:** It doesn't say "you're not good." It says "here's how much data you need to know if you're good." This is information a serious trader wants.

**Why no competitor has it:** Zerodha shows win rate as a static number. Nobody applies statistics to it. This treats the trader as a professional who cares about signal vs noise.

---

### Feature 2: Transaction Cost Reality

**The question it answers:** "How much is trading actually costing me in fees?"

Most retail traders dramatically underestimate this. Zerodha charges brokerage + STT + exchange charges + SEBI turnover + GST. On high-frequency F&O trading (7+ trades/day), this adds up to a meaningful monthly number that most traders have never seen in one place.

**What to show:**
```
This Month: Gross P&L vs Net P&L

Gross P&L (before fees):    +₹32,800
Total transaction costs:    -₹8,500
Net P&L (what you kept):    +₹24,300

Costs as % of gross:  26%
Cost per trade (avg):  ₹181
Trades needed to break even on fees: 47 (before making any profit)
```

**Why this is powerful:** A trader who made ₹24,300 net may not realize they generated ₹32,800 gross and paid 26% of it in fees. This doesn't tell them to stop trading — it tells them to trade fewer, better trades. The insight is about **trade selection quality**, not behavior.

**Implementation:** Zerodha F&O fee structure is public and fixed:
- Options: ₹20/order + 0.0625% STT (exercised only, not square-off) + 0.053% exchange charges + 0.0001% SEBI + 18% GST on brokerage
- Futures: ₹20/order + 0.01% STT + 0.002% exchange charges + same GST
- Estimate from `CompletedTrade.avg_entry_price × total_quantity × instrument_type` → apply rates
- Show as estimate (not exact, since we don't have the final Zerodha ledger data)

**Backend:** New endpoint `/analytics/cost-analysis` that computes estimated charges per trade and aggregates them.

---

### Feature 3: Conditional Performance Map

**The question it answers:** "Under exactly which conditions do I trade well?"

Win rate alone means little. The interesting question is: what combination of conditions predicts a winning trade for *this specific trader*? We have all the context in `CompletedTradeFeature`:

- `entry_after_loss` (True/False)
- `consecutive_loss_count` (0, 1, 2, 3+)
- `entry_hour_ist` (9, 10, 11... 15)
- `size_relative_to_avg` (< 0.8, 0.8–1.2, > 1.2)
- `is_expiry_day` (True/False)
- `session_pnl_at_entry` (positive, negative)

Cross-tabulate any two of these against win rate. The patterns that emerge are specific, personal, and directly actionable.

**What to show:**

A 2-3 row insight list (not a complex matrix — just the top findings):

```
When You Perform Best:
  Entry before 11AM + not after a loss  →  71% win rate  (28 trades)
  Session P&L positive at entry         →  68% win rate  (31 trades)
  First 3 trades of the day             →  63% win rate  (42 trades)

When You Struggle:
  Entry after 1PM + after a loss        →  29% win rate  (14 trades)
  Size > 1.5× your average              →  33% win rate  (9 trades)
```

**Why this is not condescending:** It doesn't say "stop doing X." It says "your data shows you perform best in these conditions." Completely neutral — the data is just showing patterns.

**Why no competitor has it:** Requires per-trade feature data that only we have (`CompletedTradeFeature`). Zerodha has none of this context.

**Implementation:** Simple GROUP BY queries on `completed_trade_features` joined to `completed_trades`. Find the top 3 positive and top 3 negative condition combinations ranked by win rate, filtered to minimum 8 trades (statistical floor).

---

### Feature 4: P&L Concentration (Trade Pareto)

**The question it answers:** "How concentrated is my P&L? Am I consistent or do I depend on a few lucky trades?"

This is a Pareto/concentration analysis. For many retail traders, 2-3 lucky trades account for their entire profitable month. If those trades hadn't happened, they'd be in the red. This matters because:
- High concentration = fragile P&L, dependent on luck
- Low concentration = consistent edge, repeatable

**What to show:**

```
P&L Concentration This Month

Top 5 trades:     +₹21,400  (87% of your total P&L)
Remaining 42 trades: +₹2,900

Your P&L is highly concentrated in a few trades.
Remove your 3 best trades → net P&L becomes: -₹6,800

For context: profitable traders typically have their
top 5 trades representing 40-60% of monthly P&L.
```

A visual: stacked horizontal bar showing the contribution of each trade to total P&L, sorted by contribution. Top trades are tall, the rest thin.

**Why this is useful:** A trader who sees this understands their edge is concentrated, not consistent. This is valuable self-knowledge for capital allocation decisions. It's also genuinely surprising — most traders think they're consistently profitable across trades when they're actually dependent on outliers.

**Why it's not condescending:** Pure data. No prescriptions. "Here's what your P&L distribution looks like" is a fact, not a judgment.

**Implementation:** Sort `CompletedTrade.realized_pnl` descending, compute cumulative sum, find what % of trades account for 80% of P&L. No new data needed.

---

### Feature 5: Expiry Day Deep Dive (India-Specific)

**The question it answers:** "How does my trading change on expiry day — and should it?"

Indian F&O traders know expiry day (weekly Thursday, monthly last Thursday) is different. Volatility spikes, theta accelerates, liquidity thins in the last hour. But no trader has ever seen a clean breakdown of their own expiry day performance vs normal days.

**What to show:**

```
Expiry Day vs Normal Days (This Month)

              Expiry (8 days)    Normal (14 days)
Trades/day:       8.2                4.1
Win rate:        44%               61%
Avg P&L/trade:  -₹220             +₹480
Total P&L:      -₹1,450          +₹25,750

Time of day on expiry:
  9:15–11:00 AM:   58% WR  +₹320/trade   (good)
  11:00 AM–2PM:    41% WR  -₹90/trade    (marginal)
  2:00 PM–3:30 PM: 28% WR  -₹780/trade  (poor — theta acceleration)
```

**Why this matters for India:** The last 90 minutes of expiry day is when theta decays fastest. Options buyers holding positions into this window suffer disproportionate losses. This analysis, specific to the trader's own data, answers "should I be trading in the last 90 minutes of expiry day?"

**Why no competitor has it:** Requires `is_expiry_day` flag (we have it in `CompletedTradeFeature`) + time-of-day breakdown. Zerodha has no concept of expiry day in their analytics.

**Implementation:** Filter `CompletedTradeFeature.is_expiry_day = True`, split by `entry_hour_ist` into three time buckets, compute win rate + avg P&L per bucket.

---

## Part 2: Per-Trade Critical Trades Analysis

This is not covered anywhere in the product. The Behavior tab shows aggregate patterns ("14 overtrading events"). The Trades tab shows a list. Neither shows: **which specific trade was a behavioral event, with full context.**

### What "Critical Trades" Means

A trade is critical if it meets any of these (prioritized, not all at once):

1. A behavioral pattern alert fired during its holding window (`entry_time → exit_time`)
2. Loss > 30% of the user's daily loss limit in one trade
3. `size_relative_to_avg > 2.0` (surprise outsized position)
4. Held < 5 minutes at a loss (panic exit)
5. `entry_after_loss = True AND minutes_since_last_round < 5` (likely revenge)

Show these in the **Trades tab** (5th tab). Not all trades — just the ones that matter.

### How Each Critical Trade Card Looks

```
┌──────────────────────────────────────────────────────────────────┐
│  NIFTY25400CE   ·  13 Feb  ·  9:47–9:51 AM  (4 min)  ·  LONG   │
│  50 qty  ·  Entry ₹92  →  Exit ₹71  ·  -₹1,050        ⚠ HIGH  │
├──────────────────────────────────────────────────────────────────┤
│  Revenge Trade — entered 3 min after a ₹2,100 loss              │
│  6th trade of the day. Consecutive losses: 2.                    │
│  Historical: 78% of your trades in this context lose.           │
└──────────────────────────────────────────────────────────────────┘
```

No preaching. No "you should have done X." Just: what happened, what context existed, what the historical pattern is for *this trader*.

### Backend: Time-Based Join (No Migration Needed)

```sql
SELECT ct.*,
       array_agg(be.event_type) AS alert_types,
       array_agg(be.message) AS alert_messages,
       ctf.entry_after_loss, ctf.consecutive_loss_count,
       ctf.size_relative_to_avg, ctf.minutes_since_last_round,
       ctf.is_expiry_day, ctf.entry_hour_ist
FROM completed_trades ct
JOIN completed_trade_features ctf ON ctf.completed_trade_id = ct.id
LEFT JOIN behavioral_events be ON
    be.broker_account_id = ct.broker_account_id AND
    be.detected_at BETWEEN ct.entry_time AND (ct.exit_time + INTERVAL '10 min')
WHERE ct.broker_account_id = :id AND ct.exit_time >= :start
  AND (be.id IS NOT NULL OR ct.realized_pnl < :loss_threshold
       OR ctf.size_relative_to_avg > 2.0 OR ct.duration_minutes < 5)
GROUP BY ct.id, ctf.id
ORDER BY ct.exit_time DESC
LIMIT 50
```

---

## Part 3: Final Tab Structure

| # | Tab | Core Question | Unique to TradeMentor |
|---|-----|---------------|----------------------|
| 1 | **Summary** | "How did I perform?" | Equity curve + Transaction Cost Reality + P&L Concentration |
| 2 | **Behavior** | "What patterns fired?" | Behavioral Day Quality + Pattern insight cards + Behavioral Calendar |
| 3 | **Timing** | "When do I trade best?" | Hour×Day grid + Expiry Day Deep Dive + Instrument leaderboard |
| 4 | **Progress** | "Am I improving?" | Period comparison + Conditional Performance + Edge Confidence |
| 5 | **Trades** | "Which trades mattered?" | Critical trades with behavioral annotations |

The five features above are distributed across tabs:
- **Statistical Edge Confidence** → Progress tab (forward-looking: "do I have a real edge?")
- **Transaction Cost Reality** → Summary tab (it directly affects your net P&L headline)
- **Conditional Performance Map** → Progress tab (understanding your edge conditions)
- **P&L Concentration** → Summary tab (alongside equity curve — it's a performance characteristic)
- **Expiry Day Deep Dive** → Timing tab (it's the most India-specific timing insight)

---

## Part 4: UI/UX Design System

### Core Principle

**Every element earns its space.** If it doesn't answer a specific question a trader is asking, it doesn't go in. No decorative charts. No widgets that look good but don't inform a decision.

**Spacious, not crowded.** Current design: equal-sized cards stacked vertically. New design: cards with different levels of emphasis, generous padding, breathing room between sections.

---

### Color System

```
Page background:   #0C0C0E
Card background:   #141416
Card elevated:     #1A1A20   (hero/primary cards)
Border (subtle):   #1E1E24   (use sparingly)

Profit:            #22C55E   (green-500)
Loss:              #EF4444   (red-500)
Caution:           #F59E0B   (amber-500)
Neutral data:      #3B82F6   (blue-500)
Behavioral:        #8B5CF6   (violet — distinct from profit/loss)

Text primary:      #F0F0F2
Text secondary:    #888896
Text muted:        #55555F

Chart grid:        #1E1E24   (barely visible)
```

**Violet for behavioral metrics** — keeps a clear visual separation between "financial performance" (green/red) and "behavioral patterns" (violet). A trader immediately learns: green/red is P&L, violet is behavior. Consistent throughout.

---

### Typography

```
Hero number (main P&L):   36px, weight 700, tabular-nums
Section heading:           12px, weight 600, uppercase, letter-spacing 0.08em, text-muted
Card headline (insight):   16px, weight 600
Supporting text:           13px, weight 400, line-height 1.6
Chart labels:              11px, weight 500
Delta / comparison:        13px, colored arrow icon
```

---

### Layout: Variable Card Sizes

The current design stacks equal-height cards — everything feels the same importance. The redesign uses **variable sizes**:

- **Full-width** cards: equity curve, critical trades list
- **2/3 + 1/3 split**: equity curve (2/3) + Transaction Cost card (1/3)
- **1/2 + 1/2 split**: two related cards side by side
- **3-column stat row**: for secondary KPIs

This creates natural hierarchy without adding noise.

**Summary tab layout:**

```
┌──────────────────────────────────────────────────────────────────┐
│  Net P&L [hero, left]     Win Rate   Profit Factor               │
│  +₹24,300 ↑₹8,500        58.3% ↑   1.42 ↑                      │
└──────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────┬───────────────────────────┐
│  Equity Curve  (full interactive)    │  Transaction Cost Reality  │
│                                      │  Gross: ₹32,800           │
│  [Cumulative P&L toggle]             │  Fees: -₹8,500  (26%)     │
│                                      │  Net:   ₹24,300           │
└──────────────────────────────────────┴───────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│  P&L Concentration                                                │
│  Top 5 trades = 87% of P&L  ████████████████████░░░             │
│  Remove top 3: net P&L becomes -₹6,800                           │
└──────────────────────────────────────────────────────────────────┘
┌─────────────────┬─────────────────┬──────────────────────────────┐
│  Avg Win        │  Avg Loss       │  Best Day   /   Worst Day    │
│  +₹1,840 ↑     │  -₹2,100 ↑     │  ₹8,200    /   -₹4,100       │
└─────────────────┴─────────────────┴──────────────────────────────┘
```

---

### Component Design Patterns

**Hero Stat Card:**
```
  NET P&L THIS PERIOD               ← 12px uppercase muted label
  +₹24,300                          ← 36px green
  ↑ ₹8,500 better than last month   ← 13px green, delta
```

**Insight Card (Behavioral — violet accent):**
```
  ●  Overtrading                    ← violet dot + pattern name 16px
  You exceeded 7 trades on 6 days.  ← 13px body text, 2-3 sentences max
  Those days averaged -₹1,400/day.
  Your controlled days: +₹320/day.

  ─────────────────────  6 events   ← count right-aligned
```

**Conditional Performance Row:**
```
  ✓  Entry before 11AM + first session   71% win rate   (28 trades)
  ✓  Session P&L positive at entry       68% win rate   (31 trades)
  ✗  After 1PM + after a loss            29% win rate   (14 trades)
```

**Critical Trade Card:**
```
  NIFTY25400CE  ·  13 Feb  9:47 AM  ·  4 min  ·  -₹1,050  ⚠ HIGH
  Revenge entry · 6th trade · 2 consecutive losses · 3 min after loss
  Historical win rate in this context: 22%
```

---

### Chart Principles

1. **One question per chart.** The chart title is the question. "When do you trade best?" is better than "P&L by Hour."
2. **No chart without a takeaway.** Below each chart, one sentence: "Your best hour is 9–10 AM (+₹X avg)."
3. **Minimal decoration.** No gridlines (or faint). No chart borders. Clean axes.
4. **Crosshair + tooltip on all charts.** Hover shows the exact data point.
5. **Recharts only** — already in the bundle, no new charting library.

---

### Interaction Design

**Period selector**: Single selector, sticky at top. 7D / 14D / 30D / 90D. All 5 tabs react. No component has its own period selector.

**Tab bar**: Sticky below period selector. The Trades tab shows a count badge (e.g., "Trades (14)" showing critical trade count for the period).

**Loading**: Skeleton screens (gray animated blocks in the exact shape of the content that will appear). Not spinners. For hero numbers: count up from 0 over 350ms.

**Empty states**: Not blank cards. "No trades in this 7-day period" with brief context about what appears here when they trade. Every tab has a designed empty state.

**Chart interaction**: Click a day in the equity curve → shows a panel of the trades from that day. Click a critical trade card → expands to show the full session timeline for that day.

---

## Part 5: Removed From Final Plan

| Removed | Why |
|---------|-----|
| P&L calendar heatmap | Zerodha already has it |
| Mistake Ledger / "What If" | BlowupShield already does this |
| Trading DNA radar | Trader looks at it, walks away. No action. |
| NIFTY overlay | Interesting trivia, not actionable |
| "Good version of you" | Feels patronizing. Not the product's philosophy. |
| VaR 95%, Daily Volatility | Institutional metrics. Meaningless to retail F&O. |
| OrderAnalyticsCard (fill rates, cancel ratios) | Unrelated to the product question |
| Emotion pie chart | Abstract category labels. Not actionable. |
| AI narrative at TOP of each tab | A conclusion shouldn't open the page. Moved to bottom or removed. |
| 20-row sortable instrument table | Replaced by leaderboard (top 5 + bottom 5) |
| Export Report in analytics header | Move to Settings. Clutters analytics header. |

---

## Part 6: Backend Endpoints Needed

| Endpoint | Data | Tab | Priority |
|----------|------|-----|----------|
| `/analytics/overview` + `vs_prior_period` | All KPI deltas | Summary | P0 |
| `/analytics/cost-analysis` | Estimated transaction costs | Summary | P0 |
| `/analytics/pnl-concentration` | Pareto: top N trades % of total | Summary | P0 |
| `/analytics/critical-trades` | Behavioral-annotated trade list | Trades | P0 |
| `/analytics/behavioral-day-quality` | Per-day behavioral score | Behavior | P0 |
| `/analytics/conditional-performance` | Context cross-tab win rates | Progress | P1 |
| `/analytics/edge-confidence` | Binomial CI on win rate | Progress | P1 |
| `/analytics/expiry-analysis` | Expiry day time-slot breakdown | Timing | P1 |
| `/analytics/timing-heatmap` | 2D: hour × day-of-week win rate | Timing | P1 |

### Data Available Without New Endpoints (reshape on frontend or backend)
- `by_instrument` → leaderboard (top 5 + bottom 5, already exists)
- `by_direction` → visual cards (already exists)
- `equity_curve` → already exists, needs toggle modes
- `drawdown_periods` → already exists
- `by_hour` + `by_day_of_week` → combine for 2D hour×day grid

---

## Part 7: Open Decisions

**D1. Tab names**: Summary / Behavior / Timing / Progress / Trades — approved? Or rename any?

**D2. Critical trade criteria**: The 5 criteria listed — remove or add any?

**D3. Transaction cost calculation**: Show as estimate with disclaimer ("approximate based on Zerodha published rates") or skip if not confident in accuracy?

**D4. Conditional Performance**: Show as 3 best + 3 worst conditions (narrative style) or as a small grid table?

**D5. P&L Concentration**: Show the "remove top 3 trades → P&L becomes X" calculation? Or keep it purely observational (concentration % only)?

**D6. Expiry day breakdown**: By time slot (3 buckets) or just expiry vs non-expiry comparison?

**D7. AI narrative**: Remove from all tabs except Progress? Or keep 1-sentence insight at bottom of each tab?
