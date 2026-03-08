# Session 001 — Dashboard Screen Review & Fixes

**Date:** 2026-02-07
**Context:** All 42 audit issues fixed. Trade architecture overhaul complete. Starting feature review.

---

## Work Done

### Dashboard Deep Dive (14 issues identified)
- Deep research via 3 parallel agents: frontend components, backend APIs, data flow
- Created `docs/review/screens/dashboard.md` with detailed findings
- User corrections applied: all items P1, no offline sync, proper industry-standard calculations

### Dashboard Fixes Implemented (12 of 14)

**Data Correctness:**
- **D1**: Session PNL = realized (today's completed trades) + unrealized (open positions) — broker standard
- **D2**: Date boundary uses browser local time (IST), no early return when closedTrades is empty
- **D4**: `risk_used` now uses real margin utilization from Kite API (`margins.overall.max_utilization_pct`)

**UX/Layout:**
- **D5**: "Connect Zerodha" calls `connect()` directly — no redirect to Settings
- **D6**: Layout reordered: Hero → Positions/Trades (8-col) + Alerts sidebar (4-col) → Margins at bottom
- **D7**: MarginInsights: clear "Daily max margin utilization" label, removed confusing mount animation
- **D8**: Tables already expand naturally (no internal scroll was present)
- **D9**: Data-dense Zerodha-style: compact rows (py-2.5), smaller headers, minimal animations, removed heavy icon containers

**Alert System:**
- **D3**: Fetches backend alerts with `acknowledged_at` state, merges with client-side patterns, persists across refresh
- **D12**: Token expiry event listener wired in BrokerContext

**Functionality:**
- **D13**: "View all" buttons functional in ClosedTradesTable and HoldingsCard (toggle expand/collapse)
- **D14**: Pattern analysis creates both entry AND exit events from each CompletedTrade

### Files Modified
- `src/pages/Dashboard.tsx` — D1, D2, D3, D4, D5, D6, D9, D14 (major changes)
- `src/components/dashboard/RiskGuardianCard.tsx` — no changes needed (already reads margin data)
- `src/components/dashboard/RecentAlertsCard.tsx` — D3 (uses acknowledged from alert data)
- `src/components/dashboard/OpenPositionsTable.tsx` — D9 (compact rows, data-dense)
- `src/components/dashboard/ClosedTradesTable.tsx` — D9, D13 (compact rows, View all toggle)
- `src/components/dashboard/MarginInsightsCard.tsx` — D7 (label, animation removed)
- `src/components/dashboard/HoldingsCard.tsx` — D13 (View all toggle)
- `src/contexts/BrokerContext.tsx` — D12 (token expiry listener)

### Build Status
- Frontend: PASSES (`npm run build` successful)

---

## Decisions Made

1. Session PNL follows broker standard: realized (today's closes) + unrealized (open positions)
2. Pattern analysis creates entry+exit events per CompletedTrade for proper overtrading/revenge detection
3. Backend alerts merged with client-side patterns, deduped by ID
4. Layout prioritizes positions and alerts over margins
5. Data-dense UX: compact rows, minimal animations, smaller headers — like Zerodha/Sensibull

---

## Session 2 Continuation — Alert Explosion Fix

**D15**: User reported 40-50 notifications appearing on closed market day with no positions.

**Root causes found (4):**
1. Dashboard passed ALL 50 historical trades to `runAnalysis()`, not just today's
2. `detectLossAversion()` used `new Date().toISOString()` → non-deterministic ID → new alert every page load
3. AlertContext localStorage alerts never expired → accumulated across days
4. Overlapping 30-min windows in overtrading detector generated near-duplicate patterns

**Files modified:**
- `src/pages/Dashboard.tsx` — Filter closedTrades to today-only before runAnalysis
- `src/lib/patternDetector.ts` — Deterministic loss_aversion ID + track used indices in overtrading
- `src/contexts/AlertContext.tsx` — 24h expiry on load, max 30 alerts (was 100)

**Build:** PASSES

---

## Pending for Next Session

- **D10**: Journal proper DB save, trade mapping, feed into AI analysis (frontend+backend)
- **D11**: Optimize load performance (stagger API calls, skeleton states, cache-aware sync)
- Move to next screen review (Analytics, Goals, Chat, Settings, etc.)
- Commit all accumulated changes (~150+ files)
