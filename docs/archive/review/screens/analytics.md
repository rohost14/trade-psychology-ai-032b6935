# Analytics Screen Review

**Status:** ALL DONE — Build + Deep Enhancement Pass Complete
**Files:** `src/pages/Analytics.tsx`, `src/components/analytics/*`, `backend/app/api/analytics.py`

---

## Problems Found (ALL FIXED)

| # | Problem | Status |
|---|---------|--------|
| P1 | Wrong data source (raw Trade fills) | **FIXED** — Uses CompletedTrade lifecycle |
| P2 | Hardcoded best/worst day | **FIXED** — Calculated from daily aggregation |
| P3 | Broken import in ProfitCurveChart | **FIXED** — Component removed, replaced by OverviewTab |
| P4 | No period filters | **FIXED** — 7D/14D/30D/90D selector |
| P5 | Missing analytics features | **FIXED** — 4 tabs with full features |
| P6 | Client-side stat calculation | **FIXED** — All calculations server-side |
| P7 | Plain UI | **FIXED** — Data-dense professional design |

---

## Implementation — Phase 1: Core Rebuild (Session 3)

### Backend (4 new endpoints in analytics.py)

| # | Endpoint | What It Returns | Status |
|---|----------|----------------|--------|
| B1 | `GET /api/analytics/overview?days=30` | KPIs, equity curve, daily P&L, streaks | **DONE** |
| B2 | `GET /api/analytics/performance?days=30` | By instrument, direction, product, hour, day, size | **DONE** |
| B3 | `GET /api/analytics/risk-metrics?days=30` | Drawdown, VaR, daily volatility, streaks | **DONE** |
| B4 | `GET /api/analytics/journal-correlation?days=30` | Emotion → P&L mapping | **DONE** |

### Frontend (rewrite + 4 new tab components)

| # | Component | Tab | Status |
|---|-----------|-----|--------|
| F1 | `Analytics.tsx` rewrite (shell + tabs + period) | — | **DONE** |
| F2 | `OverviewTab.tsx` (KPIs + equity curve + daily P&L) | Overview | **DONE** |
| F3 | `BehaviorTab.tsx` (patterns + journal + AI persona) | Behavior | **DONE** |
| F4 | `PerformanceTab.tsx` (instrument/time/size) | Performance | **DONE** |
| F5 | `RiskTab.tsx` (drawdown + VaR + streaks + alerts) | Risk | **DONE** |
| F6 | Cleanup unused old components | — | **DONE** |

---

## Implementation — Phase 2: Deep Enhancement (Session 3 continued)

### Backend Fixes & Enhancements

| # | Fix | Status |
|---|-----|--------|
| E1 | Journal correlation: join with Trade table for accurate P&L (was using stale string) | **DONE** |
| E2 | Overview: added avg_duration, win/loss days, trading_days, largest_win/loss | **DONE** |
| E3 | Performance: enhanced product breakdown with wins/losses/avg_pnl | **DONE** |
| E4 | New endpoint: `GET /api/analytics/ai-insights` — personalization, pattern frequency, trading intensity | **DONE** |
| E5 | ExportReportButton: fixed calling non-existent `/api/behavioral/patterns` → uses `/api/behavioral/analysis` | **DONE** |

### Frontend Enhancements

| # | Enhancement | Component | Status |
|---|-------------|-----------|--------|
| E6 | Richer KPI strip: 3 rows, expectancy, avg duration, trades/day, largest win/loss | OverviewTab | **DONE** |
| E7 | Equity curve: dynamic gradient color (green/red based on profit) | OverviewTab | **DONE** |
| E8 | Daily P&L table: inline data table for ≤20 days | OverviewTab | **DONE** |
| E9 | Emotional tax breakdown: pie chart + cost-per-pattern table | BehaviorTab | **DONE** |
| E10 | AI personalized insights: danger hours, best hours, problem/strong symbols, trading intensity | BehaviorTab | **DONE** |
| E11 | Fixed empty array check in BehaviorTab (was failing on empty patterns_detected) | BehaviorTab | **DONE** |
| E12 | Pattern table sorted by severity (critical first) | BehaviorTab | **DONE** |
| E13 | Product type breakdown table (MIS vs NRML with full stats) | PerformanceTab | **DONE** |
| E14 | Hour/Day data tables below charts for data density | PerformanceTab | **DONE** |
| E15 | Best/worst hour and day indicators in chart headers | PerformanceTab | **DONE** |
| E16 | Size analysis insight: "You perform best with X positions" | PerformanceTab | **DONE** |
| E17 | Drawdown chart: area chart showing distance from equity peak | RiskTab | **DONE** |
| E18 | Discipline score components displayed | RiskTab | **DONE** |
| E19 | Risk-reward ratio contextual labels | RiskTab | **DONE** |
| E20 | Alert summary total count | RiskTab | **DONE** |
| E21 | Top strength + focus area CTAs | BehaviorTab | **DONE** |

---

## Backend Endpoints Summary (all in analytics.py)

| Endpoint | Purpose | Data Source |
|----------|---------|-------------|
| `GET /analytics/overview?days=N` | KPIs, equity curve, daily P&L, streaks | CompletedTrade |
| `GET /analytics/performance?days=N` | Instrument/direction/product/hour/day/size | CompletedTrade + CompletedTradeFeature |
| `GET /analytics/risk-metrics?days=N` | Drawdown, VaR, volatility, streaks, alerts | CompletedTrade + RiskAlert |
| `GET /analytics/journal-correlation?days=N` | Emotion → P&L (joined with Trade for accurate P&L) | JournalEntry + Trade |
| `GET /analytics/ai-insights?days=N` | Personalization, pattern frequency, trading intensity | CompletedTrade + RiskAlert + PersonalizationService |
| `GET /analytics/risk-score` | Weekly discipline score | (existing) |
| `GET /analytics/progress` | Week-over-week comparison | (existing) |
| `GET /analytics/money-saved` | Estimated losses prevented | (existing) |

### Existing Endpoints Reused
- `GET /api/behavioral/analysis?time_window_days=N` — 17 patterns + AI persona
- `GET /api/analytics/risk-score` — Weekly discipline score

### Components Kept
- `ExportReportButton.tsx` — Fixed endpoint call
- `OrderAnalyticsCard.tsx` — In Performance tab

### Components Removed (10 total)
- PerformanceSummaryCard, BehavioralInsightsCard, TimeAnalysisCard, ProfitCurveChart
- AIInsightsCard, RadarChart, DangerZoneCard, StrengthZoneCard
- ExpandablePatternCard, TradingTimeline

---

## Verification

- `npm run build` — **PASSES** (14s, no errors)
- Backend syntax — **PASSES** (ast.parse OK)
- All 4 tabs render with loading → data → empty states
- Period selector (7/14/30/90 days) correctly filters all tabs
