# Frontend Update Implementation Plan

## Goal

Update the frontend to consume all existing backend features that are currently not displayed in the UI. This includes Margins Dashboard, Holdings View, Order Analytics, Margin Insights, Token Validation, and Real-time Price Streaming integration.

---

## User Review Required

> [!IMPORTANT]
> **Dashboard Layout Change**: This plan adds 2-3 new cards to the Dashboard page. Please confirm the preferred layout:
> - **Option A**: Grid layout with RiskGuardian + MarginStatus on top row, Holdings + Positions below
> - **Option B**: Add a new "Portfolio" tab to the dashboard for Holdings/Margins

> [!WARNING]
> **Real-time Price Streaming**: Enabling WebSocket streaming will increase server load. Currently only activates when user views positions.

---

## Proposed Changes

### Phase 1: Core Infrastructure

---

#### [NEW] [useMargins.ts](file:///d:/trade-psychology-ai/src/hooks/useMargins.ts)

Custom hook for fetching margin data from the API.

**Functionality:**
- Fetch margin status from `/api/zerodha/margins`
- Fetch margin insights from `/api/zerodha/margins/insights`
- Polling every 30 seconds when visible
- Loading, error, and refetch states

**Design Pattern:**
```typescript
interface UseMargins {
  margins: MarginStatus | null;
  insights: MarginInsightsResponse | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}
```

---

#### [NEW] [useHoldings.ts](file:///d:/trade-psychology-ai/src/hooks/useHoldings.ts)

Custom hook for fetching CNC/delivery holdings.

**Functionality:**
- Fetch holdings from `/api/zerodha/holdings`
- Calculate total portfolio value
- Loading and error states

---

#### [NEW] [useOrderAnalytics.ts](file:///d:/trade-psychology-ai/src/hooks/useOrderAnalytics.ts)

Custom hook for order behavioral analytics.

**Functionality:**
- Fetch from `/api/zerodha/order-analytics?days=30`
- Transform data for charts
- Loading and error states

---

#### [MODIFY] [BrokerContext.tsx](file:///d:/trade-psychology-ai/src/contexts/BrokerContext.tsx)

**Changes Required:**
1. Add `validateToken()` method calling `/api/zerodha/token/validate`
2. Add `tokenStatus` state: `'valid' | 'expired' | 'checking'`
3. Update `syncTrades()` to call `/api/zerodha/sync/all` instead of `/api/trades/sync`
4. Check token validity on mount and show reconnect prompt if expired

---

### Phase 2: Dashboard Components

---

#### [NEW] [MarginStatusCard.tsx](file:///d:/trade-psychology-ai/src/components/dashboard/MarginStatusCard.tsx)

**Visual Design:**
```
┌─────────────────────────────────────────────────────────────┐
│ 🎯 Margin Status                              ●LIVE  [↻]    │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │ EQUITY           │  │ COMMODITY        │                 │
│  │ ₹2,45,431        │  │ ₹1,00,661        │                 │
│  │ ▓▓▓▓▓░░░░  45%   │  │ ▓▓░░░░░░░  18%   │                 │
│  └──────────────────┘  └──────────────────┘                 │
├─────────────────────────────────────────────────────────────┤
│  Cash: ₹1,50,000   Collateral: ₹50,000   Used: ₹95,000     │
└─────────────────────────────────────────────────────────────┘
```

**UI/UX Specifications:**
- Use `card-premium` with `hover-glow-success/warning/danger` based on risk level
- Animated progress bars using `framer-motion` (like RiskGuardianCard)
- Segment cards with glassmorphism effect (`glass-subtle`)
- Risk-state border (`border-risk-safe/caution/danger`)
- Tabular numbers for all currency values
- Shimmer loading state

**Colors:**
- Safe (< 60%): `text-success`, `bg-success/10`
- Warning (60-80%): `text-warning`, `bg-warning/10`
- Danger (> 80%): `text-destructive`, `bg-destructive/10`

**Props:**
```typescript
interface MarginStatusCardProps {
  brokerAccountId: string;
  onRefresh?: () => void;
}
```

---

#### [NEW] [HoldingsCard.tsx](file:///d:/trade-psychology-ai/src/components/dashboard/HoldingsCard.tsx)

**Visual Design:**
```
┌─────────────────────────────────────────────────────────────┐
│ 💼 Holdings                        Portfolio: ₹4,52,000     │
├─────────────────────────────────────────────────────────────┤
│ SYMBOL     QTY    AVG      LTP        P&L        CHANGE     │
│ ─────────────────────────────────────────────────────────── │
│ RELIANCE   10    ₹2,450   ₹2,520   +₹700    🟢 +2.8%       │
│ INFY       50    ₹1,340   ₹1,298   -₹2,100  🔴 -3.1%       │
│ TCS        25    ₹3,200   ₹3,280   +₹2,000  🟢 +2.5%       │
├─────────────────────────────────────────────────────────────┤
│            Total P&L: +₹5,600 (+1.2%)                       │
└─────────────────────────────────────────────────────────────┘
```

**UI/UX Specifications:**
- Match `OpenPositionsTable` styling exactly
- Gradient header with `bg-gradient-to-r from-primary/6`
- Table with `table-header`, `table-cell-mono` classes
- Day change percentage with colored badges
- Mobile-responsive card layout (like OpenPositionsTable)
- Animated row entrance with staggered delays
- T1 quantity indicator badge (if > 0): "T1: 5"
- Collateral indicator badge (if pledged)

**Empty State:**
- Centered icon with subtle animation
- "No holdings yet" message
- "Buy CNC to see holdings" subtext

---

#### [NEW] [MarginInsightsCard.tsx](file:///d:/trade-psychology-ai/src/components/dashboard/MarginInsightsCard.tsx)

**Visual Design:**
```
┌─────────────────────────────────────────────────────────────┐
│ 📊 Margin Insights                                          │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────┐   │
│  │     Margin Utilization (7 days)                      │   │
│  │  80%─┼─────────────────────────────                  │   │
│  │  60%─┼────────●───────────●──────                    │   │
│  │  40%─┼──●─────────●───────────────●                  │   │
│  │  20%─┼───────────────────────────────                │   │
│  │      └──Mon──Tue──Wed──Thu──Fri──Sat                 │   │
│  └──────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│ 💡 Avg: 42%   Max: 68%   ⚠️ Warning: 2 times              │
├─────────────────────────────────────────────────────────────┤
│ [🟢] Great margin discipline! Avg below 50%                │
│ [🟡] Consider reducing position size on volatile days       │
└─────────────────────────────────────────────────────────────┘
```

**UI/UX Specifications:**
- Simple line chart using CSS or a lightweight chart lib (Recharts)
- Gradient area fill under the line
- Insight cards with risk-state badges
- Insight types: positive (green), warning (yellow), danger (red), info (blue)
- Collapsible insights section on mobile
- Animated number transitions

---

### Phase 3: Analytics Components

---

#### [NEW] [OrderAnalyticsCard.tsx](file:///d:/trade-psychology-ai/src/components/analytics/OrderAnalyticsCard.tsx)

**Visual Design:**
```
┌─────────────────────────────────────────────────────────────┐
│ 📈 Order Analytics                          Last 30 days    │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │  TOTAL   │ │ FILLED   │ │ CANCEL   │ │ REJECT   │        │
│  │   142    │ │   128    │ │    12    │ │     2    │        │
│  │          │ │  90.1%   │ │   8.5%   │ │   1.4%   │        │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
├─────────────────────────────────────────────────────────────┤
│  Trading Activity by Hour                                   │
│  ░░░▓▓▓▓▓▓░░░░░░░░▓▓▓▓░░░ ← Peak: 9-10 AM                  │
├─────────────────────────────────────────────────────────────┤
│  💡 Insights                                                │
│  [🟢] Low cancellation rate (8.5%) - good execution        │
│  [🟡] High trading activity at market open - watch slippage│
│  [🔴] 2 margin-related rejections - increase buffer         │
└─────────────────────────────────────────────────────────────┘
```

**UI/UX Specifications:**
- Stat cards in grid with animated counters
- Hourly heatmap visualization (bar chart or blocks)
- Insight cards with action buttons
- Severity colors matching risk states
- Period selector dropdown (7/14/30 days)
- Expandable rejection reasons section

---

### Phase 4: Real-time Integration

---

#### [MODIFY] [OpenPositionsTable.tsx](file:///d:/trade-psychology-ai/src/components/dashboard/OpenPositionsTable.tsx)

**Changes Required:**
1. Import and use `usePriceStream` hook
2. Subscribe to instrument tokens when positions load
3. Display live `last_price` with pulse animation on update
4. Show real-time P&L calculation
5. Add "LIVE" indicator with pulsing animation

**Visual Enhancement:**
- When price updates: brief green/red flash on the price cell
- Subtle pulse animation on the entire row when P&L changes significantly
- Add `last_price` column between Avg Price and Value

---

#### [MODIFY] [usePriceStream.ts](file:///d:/trade-psychology-ai/src/hooks/usePriceStream.ts)

**Changes Required:**
1. Add auto-connect when broker is connected
2. Add heartbeat/ping to keep connection alive
3. Add reconnection logic on disconnect
4. Expose `subscribe(instrumentTokens: number[])` method

---

### Phase 5: Page Updates

---

#### [MODIFY] [Dashboard.tsx](file:///d:/trade-psychology-ai/src/pages/Dashboard.tsx)

**Layout Changes:**
```
┌───────────────────────────────────────────────────────────────────┐
│                         RISK GUARDIAN                             │
│                    (Full width, priority)                         │
├─────────────────────────────────┬─────────────────────────────────┤
│       MARGIN STATUS             │          HOLDINGS               │
│       (Half width)              │         (Half width)            │
├─────────────────────────────────┴─────────────────────────────────┤
│                       OPEN POSITIONS                              │
│                      (Full width)                                 │
├───────────────────────────────────────────────────────────────────┤
│         CLOSED TRADES           │       RECENT ALERTS             │
│         (Half width)            │       (Half width)              │
└─────────────────────────────────┴─────────────────────────────────┘
```

**Import New Components:**
```typescript
import MarginStatusCard from '@/components/dashboard/MarginStatusCard';
import HoldingsCard from '@/components/dashboard/HoldingsCard';
```

---

#### [MODIFY] [Analytics.tsx](file:///d:/trade-psychology-ai/src/pages/Analytics.tsx)

**Add OrderAnalytics Component:**
- Insert above or parallel to existing analytics
- Add tabs: "Performance" | "Orders" | "Margins"
- Import MarginInsightsCard for the Margins tab

---

### Phase 6: Token Validation UI

---

#### [NEW] [TokenExpiredBanner.tsx](file:///d:/trade-psychology-ai/src/components/alerts/TokenExpiredBanner.tsx)

**Visual Design:**
```
┌─────────────────────────────────────────────────────────────────┐
│ ⚠️ Your Zerodha session has expired. [Reconnect] to continue.  │
└─────────────────────────────────────────────────────────────────┘
```

**UI/UX Specifications:**
- Fixed banner at top of Layout (below header)
- Warning color scheme with gradient background
- Animated entrance (slide down)
- Dismissible but reappears after 5 minutes
- Reconnect button triggers OAuth flow

---

#### [MODIFY] [Layout.tsx](file:///d:/trade-psychology-ai/src/components/Layout.tsx)

**Changes:**
1. Add token validation check using BrokerContext
2. Render `TokenExpiredBanner` when token is expired
3. Auto-hide when user reconnects

---

## Files Summary

### Files to Create (8)

| File | Purpose |
|------|---------|
| [useMargins.ts](file:///d:/trade-psychology-ai/src/hooks/useMargins.ts) | Hook for margin API calls |
| [useHoldings.ts](file:///d:/trade-psychology-ai/src/hooks/useHoldings.ts) | Hook for holdings API calls |
| [useOrderAnalytics.ts](file:///d:/trade-psychology-ai/src/hooks/useOrderAnalytics.ts) | Hook for order analytics API |
| [MarginStatusCard.tsx](file:///d:/trade-psychology-ai/src/components/dashboard/MarginStatusCard.tsx) | Margin status display |
| [HoldingsCard.tsx](file:///d:/trade-psychology-ai/src/components/dashboard/HoldingsCard.tsx) | Holdings table/cards |
| [MarginInsightsCard.tsx](file:///d:/trade-psychology-ai/src/components/dashboard/MarginInsightsCard.tsx) | Margin history chart |
| [OrderAnalyticsCard.tsx](file:///d:/trade-psychology-ai/src/components/analytics/OrderAnalyticsCard.tsx) | Order flow analytics |
| [TokenExpiredBanner.tsx](file:///d:/trade-psychology-ai/src/components/alerts/TokenExpiredBanner.tsx) | Session expiry alert |

### Files to Modify (6)

| File | Changes |
|------|---------|
| [BrokerContext.tsx](file:///d:/trade-psychology-ai/src/contexts/BrokerContext.tsx) | Add token validation, update sync |
| [Dashboard.tsx](file:///d:/trade-psychology-ai/src/pages/Dashboard.tsx) | Add new cards to layout |
| [Analytics.tsx](file:///d:/trade-psychology-ai/src/pages/Analytics.tsx) | Add order analytics |
| [Layout.tsx](file:///d:/trade-psychology-ai/src/components/Layout.tsx) | Add token banner |
| [OpenPositionsTable.tsx](file:///d:/trade-psychology-ai/src/components/dashboard/OpenPositionsTable.tsx) | Integrate price streaming |
| [usePriceStream.ts](file:///d:/trade-psychology-ai/src/hooks/usePriceStream.ts) | Add auto-subscribe |

---

## Verification Plan

### Automated Tests

There's a basic test setup in `src/test/`. The existing test is an example file.

**Command to run tests:**
```bash
npm run test
```

**New tests to create:**
- `useMargins.test.ts` - Mock API responses, verify state management
- `useHoldings.test.ts` - Mock API responses, verify calculations
- `MarginStatusCard.test.tsx` - Render tests for different risk states

### Manual Verification

#### Step 1: Token Validation
1. Run the app: `npm run dev`
2. Open browser to `http://localhost:8080`
3. Connect to Zerodha through Settings
4. Manually expire the token (disconnect from backend)
5. Refresh the page - expect to see TokenExpiredBanner
6. Click Reconnect - banner should disappear after OAuth

#### Step 2: Margin Status
1. Navigate to Dashboard after connecting
2. Verify MarginStatusCard appears below RiskGuardian
3. Check equity and commodity segments display correctly
4. Verify risk colors match utilization percentage
5. Click refresh button - should update data

#### Step 3: Holdings
1. Navigate to Dashboard with connected account
2. Verify HoldingsCard displays next to MarginStatusCard
3. Check all holdings appear with correct data
4. Verify P&L colors (green for profit, red for loss)
5. Test mobile responsive view (resize browser)

#### Step 4: Order Analytics
1. Navigate to Analytics page
2. Verify OrderAnalyticsCard appears
3. Check summary stats are correct
4. Verify hourly distribution chart renders
5. Check behavioral insights display with correct colors

#### Step 5: Real-time Prices
1. Navigate to Dashboard with open positions
2. Verify LIVE indicator is present
3. Watch for price updates (may take a few seconds)
4. Verify P&L updates when prices change
5. Check price flash animation on update

### Browser/Device Testing

Test the responsive design on:
- Desktop Chrome/Firefox (1920x1080)
- Tablet portrait (768x1024)
- Mobile (375x812 - iPhone X size)

---

## Implementation Order

1. **Phase 1**: Core hooks (useMargins, useHoldings, useOrderAnalytics)
2. **Phase 2**: Dashboard components (MarginStatusCard, HoldingsCard)
3. **Phase 3**: Analytics components (OrderAnalyticsCard, MarginInsightsCard)
4. **Phase 4**: Token validation (BrokerContext update, TokenExpiredBanner)
5. **Phase 5**: Real-time integration (OpenPositionsTable update)
6. **Phase 6**: Testing and polish

Estimated time: 4-6 hours for full implementation.
