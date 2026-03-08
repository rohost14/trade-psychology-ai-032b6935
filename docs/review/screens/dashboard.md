# Dashboard Screen Review

**Status:** 12/14 FIXED (D10, D11 pending)
**Files:** `src/pages/Dashboard.tsx`, 12 child components, `BrokerContext.tsx`, `AlertContext.tsx`

---

## Combined Findings (User + Code Analysis)

### PRIORITY 1 — Data Correctness (Broken/Wrong)

#### D1. Hero stats show zero values despite having trades
**Source:** User report + code analysis
**Root Cause:** Dashboard.tsx:327-356 calculates stats from `closedTrades` filtered to today:
```typescript
const todayTrades = closedTrades.filter(t => new Date(t.exit_time) >= today);
```
- Only counts trades that EXITED today
- If only open positions exist (no closes), stats are all zero
- `Session PNL` should include unrealized P&L from open positions too

**Additional issue:** Backend `/api/analytics/dashboard-stats` and `/api/risk/state` use `Trade.pnl` (inconsistent — only closing fills have P&L) instead of `CompletedTrade.realized_pnl` (the authoritative source).

**Fix needed:**
- Session PNL = sum of (completed trades today P&L) + (unrealized P&L from open positions)
- Trades Today = count of completed trades exited today
- Win Rate = from completed trades today
- Stats should show non-zero when open positions have unrealized P&L

---

#### D2. Same-day closed positions P&L not being included
**Source:** User report + backend analysis
**Root Cause:** FIFO P&L calculation runs correctly, BUT:
- `CompletedTrade.realized_pnl` IS populated correctly after sync
- Issue may be TIMING: if frontend fetches before P&L calculation completes
- OR: date filtering uses UTC instead of IST (Indian Standard Time)
  - A trade exiting at 3:30 PM IST = 10:00 AM UTC = still "today" in UTC
  - But if filter uses `new Date()` which uses browser local time, this should be fine

**Verify:** Check if `/api/trades/completed` returns today's trades with non-zero `realized_pnl`

---

#### D3. Alerts/Notifications reappear after refresh
**Source:** User report + code analysis (CONFIRMED BUG)
**Root Cause (Two separate issues):**

**(A) RecentAlertsCard** (behavioral alerts):
- `acknowledgedIds` is a local `useState` Set — NOT persisted
- Backend DOES persist `acknowledged_at` via POST `/api/risk/alerts/{id}/acknowledge`
- But frontend never READS acknowledged state from backend on load
- On refresh, all alerts appear un-acknowledged

**(B) AlertContext** (pattern detection alerts):
- Uses `shownPatternIds` Set in localStorage — deduplication works
- But `alerts` array is re-generated fresh on each analysis run
- If trades data is refetched → signature changes → analysis re-runs → new alerts created
- Alerts appear to "recur" because pattern detection re-fires

**Fix needed:**
- Fetch alerts from backend with `acknowledged_at` status on mount
- Don't regenerate alerts that already exist in backend
- Separate backend-persisted alerts from client-side pattern detection

---

#### D4. `risk_used` is hardcoded and meaningless
**Source:** Code analysis
**Location:** Dashboard.tsx:352
```typescript
risk_used: Math.min(100, Math.max(0, (todayTrades.length / 10) * 100))
```
- 10 trades = 100% "risk used" regardless of actual capital exposure
- Should use margin utilization or capital at risk instead

---

### PRIORITY 2 — UX / Layout Issues

#### D5. "Connect Zerodha" redirects to Settings (extra click needed)
**Source:** User report
**Root Cause:** The Dashboard shows a "Connect Zerodha" button that navigates to `/settings` page, where user must click again. Should either:
- Connect directly from Dashboard (call `/api/zerodha/connect` and redirect)
- OR show the connect flow inline on Dashboard

---

#### D6. Layout: Margin Status/Insights too high, important data buried
**Source:** User report
**Current layout order:**
1. RiskGuardianCard (hero)
2. PredictiveWarningsCard
3. MarginStatusCard + MarginInsightsCard (side by side)
4. OpenPositionsTable
5. ClosedTradesTable
6. Sidebar: RecentAlerts, BlowupShield, ProgressTracking, Holdings

**Proposed layout:**
1. RiskGuardianCard (hero) — keep at top
2. Live Alerts/Notifications — move up
3. OpenPositionsTable — move up (most important during trading)
4. ClosedTradesTable
5. MarginStatusCard + MarginInsightsCard — move down
6. Sidebar rearranged

---

#### D7. MarginInsights bar confusing, "refreshes like new day"
**Source:** User report
**Root Cause:** The bar chart shows last 14 days of max utilization. Each bar = one day.
- Animation plays on mount, making it look like "increasing"
- No label explaining what bars represent
- No refresh during session — stale data
- User may think bars are live-updating during the day

**Fix needed:**
- Add clear labels: "Daily Max Margin Utilization (Last 14 Days)"
- Remove/reduce mount animation that makes it look like it's "filling up"
- Add timestamp showing when data was last fetched

---

#### D8. Open Positions / Closed Trades need to scroll externally, not internally
**Source:** User report
**Current behavior:** Components have internal scroll (max-height with overflow-y)
**Desired:** Components should expand to full height, page scrolls naturally

---

#### D9. Overall UI/UX: Make more like Zerodha/Sensibull/Tickertape
**Source:** User report
**Key characteristics of those platforms:**
- Clean, data-dense tables with minimal decoration
- Compact rows, no cards-within-cards
- Green/red P&L coloring (no extra badges)
- Monospace numbers for easy scanning
- Minimal animations — data-first design
- Fixed header with scrolling body
- Tab-based views rather than all-at-once

---

### PRIORITY 3 — Trade Journal

#### D10. Trade journal: proper DB save, trade mapping, feed into AI analysis
**Source:** User report + code analysis
**Current state:** Saves to `journal_entries` table via POST `/api/journal/` with `trade_id` linkage.
**User requirement:**
- NO offline sync / localStorage fallback — save to DB, period
- Journal data MUST be mapped to the trade and used for AI analysis
- Emotions, lessons, notes should feed into behavioral pattern detection
- This data is critical for analysis — needs proper storage + retrieval

---

### PRIORITY 4 — Performance

#### D11. Slow initial load
**Source:** User report
**Root Cause:** Dashboard fires 6+ API calls on mount:
1. `/api/positions/`
2. `/api/trades/completed`
3. `/api/risk/state`
4. `/api/analytics/money-saved`
5. `/api/margins/status` (via useMargins hook)
6. `/api/margins/insights` (via useMargins hook)
7. `/api/holdings/` (via useHoldings hook)
8. `/api/analytics/progress` (ProgressTrackingCard)
9. `/api/personalization/insights` (PredictiveWarningsCard)

Plus auto-sync on first load (POST `/api/zerodha/sync/all` → takes seconds)

**Fix needed:**
- Show skeleton/loading state immediately
- Stagger non-critical calls (margins, holdings, progress can load after main data)
- Cache sync results (if synced < 5 min ago, skip)
- Consider single dashboard endpoint that returns all data in one call

---

### PRIORITY 5 — Minor Issues

#### D12. Token expiry event dispatched but never handled
**Source:** Code analysis
**Location:** api.ts:36 dispatches `tradementor:token-expired` event
**Issue:** No listener in BrokerContext or Layout — 401 errors aren't surfaced to user
- TokenExpiredBanner component exists but relies on separate detection

#### D13. "View all" buttons in ClosedTradesTable and HoldingsCard have no handler
**Source:** Code analysis
- Buttons exist but don't navigate anywhere or trigger modals

#### D14. CompletedTrade→Trade mapping for pattern analysis loses context
**Source:** Code analysis (Dashboard.tsx:311-323)
- Maps exit_price as "price" and exit_time as "traded_at"
- Pattern detector analyzes exits as if they were entries

---

## User Corrections & Priorities

- D10-D14 are NOT low priority — they are important for production quality
- Journal: NO offline sync. Save to DB table, map to trade, use for AI analysis
- Pattern analysis: Should use BOTH entry AND exit data dynamically, not just exit
  - Should combine AI layer + math rules for behavioral detection
  - Self-analyze based on trade context (entry timing, exit timing, P&L, duration)
- All calculations should follow industry standards (Zerodha, Sensibull, Tickertape)
- P&L calculation: Match how brokers display it on their apps

## Implementation Status

| # | Fix | Status | What Changed |
|---|-----|--------|-------------|
| D1 | Session PNL = realized + unrealized | **FIXED** | Combined trade stats + position unrealized PNL in single effect |
| D2 | IST date boundary for today filter | **FIXED** | Uses browser local time (IST), no early return when closedTrades=0 |
| D3 | Alert persistence across refresh | **FIXED** | Fetches backend alerts with acknowledged_at, merges with client patterns |
| D4 | Real margin utilization | **FIXED** | Uses `margins.overall.max_utilization_pct` from Kite API |
| D5 | Direct Zerodha connect | **FIXED** | Calls `connect()` directly instead of Link to /settings |
| D6 | Layout reorder | **FIXED** | Hero → Positions+Trades (8col) + Alerts sidebar (4col) → Margins (bottom) |
| D7 | MarginInsights bar labels | **FIXED** | Clear "Daily max margin utilization" label, removed mount animation |
| D8 | Tables page-level scroll | **FIXED** | Tables already expand naturally, no internal max-height scroll |
| D9 | Data-dense Zerodha-style UX | **FIXED** | Compact rows (py-2.5), smaller headers, minimal animations, removed icon circles |
| D10 | Journal DB save + AI analysis | PENDING | Needs frontend+backend changes for proper journal→trade→AI pipeline |
| D11 | Load performance optimization | PENDING | Needs staggered API calls, skeleton states, cache-aware sync |
| D12 | Token expiry event handler | **FIXED** | Added listener in BrokerContext for `tradementor:token-expired` event |
| D13 | "View all" buttons | **FIXED** | Toggle expand/collapse in ClosedTradesTable and HoldingsCard |
| D14 | Pattern analysis entry+exit | **FIXED** | Creates both entry and exit Trade events from each CompletedTrade |
| D15 | Alert notification explosion (40-50 alerts) | **FIXED** | 4 root causes fixed: today-only analysis, deterministic IDs, 24h expiry, dedup windows |
| D16 | Double fetch on manual sync | **FIXED** | handleSync no longer calls fetchAllData manually — lets syncStatus effect handle it |
| D17 | MarginInsightsCard crash on null statistics | **FIXED** | Added optional chaining + fallbacks for danger_occurrences/warning_occurrences |
| D18 | TradeJournalSheet P&L undefined for break-even positions | **FIXED** | Changed `||` to `??` for unrealized_pnl fallback |
| D19 | Unused imports in ClosedTradesTable | **FIXED** | Removed unused Target, TrendingUp, TrendingDown imports |

---

### D15. Alert notification explosion — 40-50 notifications on closed market day
**Source:** User report (Session 2)
**Root Causes (4 identified):**
1. Dashboard passed ALL 50 historical trades to `runAnalysis()` — generated patterns for old trades
2. `detectLossAversion()` used `new Date().toISOString()` making pattern ID non-deterministic — created a new alert on EVERY page load
3. Alerts stored in localStorage never expired — accumulated across days/weeks
4. Overlapping 30-min windows in `detectOvertrading()` generated near-duplicate patterns

**Fixes Applied:**
- `Dashboard.tsx`: Filter `closedTrades` to today-only before passing to `runAnalysis()`. Skip if no today trades.
- `patternDetector.ts`: Use latest trade timestamp instead of `new Date()` for loss_aversion pattern ID
- `patternDetector.ts`: Track used trade indices in overtrading detector to prevent overlapping window duplicates
- `AlertContext.tsx`: Prune alerts older than 24 hours on load from localStorage
- `AlertContext.tsx`: Reduce max stored alerts from 100 to 30

---

## Files Involved

**Frontend:**
- `src/pages/Dashboard.tsx` (708 lines)
- `src/contexts/BrokerContext.tsx` (313 lines)
- `src/contexts/AlertContext.tsx` (232 lines)
- `src/lib/api.ts` (54 lines)
- `src/components/dashboard/RiskGuardianCard.tsx`
- `src/components/dashboard/OpenPositionsTable.tsx`
- `src/components/dashboard/ClosedTradesTable.tsx`
- `src/components/dashboard/RecentAlertsCard.tsx`
- `src/components/dashboard/TradeJournalSheet.tsx`
- `src/components/dashboard/MarginStatusCard.tsx`
- `src/components/dashboard/MarginInsightsCard.tsx`
- `src/components/dashboard/BlowupShieldCard.tsx`
- `src/components/dashboard/PredictiveWarningsCard.tsx`
- `src/components/dashboard/HoldingsCard.tsx`
- `src/components/dashboard/ProgressTrackingCard.tsx`
- `src/components/dashboard/MoneySavedCard.tsx`

**Backend:**
- `backend/app/api/trades.py`
- `backend/app/api/positions.py`
- `backend/app/api/risk.py`
- `backend/app/api/analytics.py`
- `backend/app/api/journal.py`
- `backend/app/services/pnl_calculator.py`
- `backend/app/services/analytics_service.py`
- `backend/app/services/risk_detector.py`
