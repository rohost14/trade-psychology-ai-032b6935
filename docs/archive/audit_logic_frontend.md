> **ARCHIVED 22 Aug 2026 — do not use as a current reference.**
>
> "The behavior engine has 22 patterns" - it is 27 detectors emitting 33 pattern types. Frontend rebuilt twice since.
>
> Live findings, if any, were rescued into `docs/ENGINE_BACKLOG.md`.

---

# Frontend Logic Audit
Generated: 2026-06-10 | Auditor: Claude Sonnet 4.6

---

## formatters.ts: formatCurrency double-applies sign prefix

**File**: `src/lib/formatters.ts:5-18`
**Status**: BUG
**Finding**: `formatCurrency` is supposed to format neutral currency (no forced `+/-` prefix), but line 7 declares `sign` and line 17 checks `amount >= 0` which implies it was supposed to show no sign on positive, yet `Intl.NumberFormat` already formats positive numbers without a sign. The declared `sign` variable is computed on line 7 but **never used** in the return value. Dead code in the formatter hints this was refactored incompletely and the intent is ambiguous.
**Evidence**:
```ts
const sign = amount < 0 ? '-' : amount > 0 ? '+' : '';  // declared but never used
return amount >= 0 ? formatted : `-${formatted.replace('₹', '₹')}`;
```
**Impact**: For negative numbers, `Intl.NumberFormat` formats `absAmount` (positive) as e.g. `₹13,000.00`, then the function prepends `-` producing `−₹13,000.00`. The replace `'₹'→'₹'` is a no-op (same string). Result is `−₹13,000.00` which is correct numerically but the dead `sign` variable and the confusing `replace` call indicate the code has a latent maintenance risk. The `+` sign for positive values is silently dropped — callers who want `+₹3,625` must use `formatCurrencyWithSign` instead; it's not clear `formatCurrency` is intentionally unsigned-only.
**Fix**: Delete the unused `sign` variable on line 7. Add a comment "No sign prefix — use formatCurrencyWithSign for +/- display."

---

## formatters.ts: formatCurrency produces wrong output for exactly zero

**File**: `src/lib/formatters.ts:17`
**Status**: MINOR_ISSUE
**Finding**: When `amount === 0`, `amount >= 0` is true so it returns the Intl-formatted string normally — this is `₹0.00`. Correct. However callers that call `formatCurrencyWithSign(0)` will get `+₹0.00` (sign is `'+' ` because `0 >= 0`). This is slightly wrong — zero P&L should be `₹0.00` or `±₹0.00`, not `+₹0.00`.
**Evidence**: `const sign = amount >= 0 ? '+' : '-';` in `formatCurrencyWithSign`
**Impact**: Dashboard session hero shows `+₹0.00` at session start instead of `₹0.00`.
**Fix**: `const sign = amount > 0 ? '+' : amount < 0 ? '-' : '';`

---

## formatters.ts: formatRelativeTime does not handle future dates or invalid strings

**File**: `src/lib/formatters.ts:67-85`
**Status**: MINOR_ISSUE
**Finding**: If `dateString` is an invalid ISO string, `new Date(dateString)` returns `Invalid Date`, then `diffMs` is `NaN`, and all comparisons with `NaN` are false. The function falls through to `date.toLocaleDateString(...)` which returns `"Invalid Date"` string — displayed to user.
**Evidence**: No guard like `if (isNaN(date.getTime())) return '—';`
**Impact**: Any alert or trade with a null/malformed timestamp renders "Invalid Date" in the UI.
**Fix**: Add `if (isNaN(date.getTime())) return '—';` after `const date = new Date(dateString);`

---

## formatters.ts: formatRelativeTime handles future dates incorrectly

**File**: `src/lib/formatters.ts:70-78`
**Status**: MINOR_ISSUE
**Finding**: If `dateString` is in the future (e.g. an alert from a slightly clock-skewed server), `diffMs` is negative. `diffMins < 1` is true (negative number), so it returns `"just now"`. This is technically harmless but slightly incorrect.
**Impact**: Backend timestamps ahead of client clock by even 1 second show "just now" forever.
**Fix**: `if (diffMs <= 0) return 'just now';` before computing `diffMins`.

---

## AlertContext: fetchAlerts missing dependency in WebSocket effect

**File**: `src/contexts/AlertContext.tsx:385-387`
**Status**: MINOR_ISSUE
**Finding**: The effect `if (lastAlertEvent) fetchAlerts(true)` suppresses the `fetchAlerts` dep with `eslint-disable-line`. This is safe because `fetchAlerts` is wrapped in `useCallback([])` (no deps), so its identity never changes. However, the pattern is fragile — if `fetchAlerts` ever gains deps, the suppress comment will hide a stale closure bug.
**Evidence**: `}, [lastAlertEvent]); // eslint-disable-line react-hooks/exhaustive-deps`
**Impact**: Currently safe but fragile. No user-facing bug today.
**Fix**: Add `fetchAlerts` to the deps array; it's stable so there's no perf cost.

---

## AlertContext: acknowledgeAll does not call the backend

**File**: `src/contexts/AlertContext.tsx:401-403`
**Status**: BUG
**Finding**: `acknowledgeAll` only updates local state — it never calls the API. There is no `POST /api/risk/alerts/acknowledge-all` or loop of individual calls. When the user presses "Mark all reviewed", the backend still considers all alerts unacknowledged. On the next page load or WebSocket event, `fetchAlerts` will return all alerts with `acknowledged: false`, and the UI will re-populate all alerts as unreviewed.
**Evidence**:
```ts
const acknowledgeAll = useCallback(() => {
  setAlerts(prev => prev.map(a => ({ ...a, acknowledged: true })));
}, []);
```
**Impact**: "Mark all reviewed" on the Alerts page appears to work, but after any refresh or WebSocket event all alerts revert to unreviewed. The badge count reappears. The user thinks they cleared alerts but they come back.
**Fix**: Either call `POST /api/risk/alerts/acknowledge-all` (if endpoint exists) or loop over all unacknowledged alert IDs and POST to each `/acknowledge` endpoint. Optimistically update local state, revert on failure.

---

## AlertContext: initial load summary toast fires even when isMarketOpen is false

**File**: `src/contexts/AlertContext.tsx:345-368`
**Status**: MINOR_ISSUE
**Finding**: The "initial load" summary toast fires regardless of market hours. The market-hours gate (`isMarketOpen`) is only applied on the real-time (WebSocket) path at line 307-308, not on the initial load summary toast path (lines 345-368).
**Impact**: User opens the app at 8 AM and sees a "3 danger alerts from today" toast even though the market hasn't opened yet. Minor annoyance but not data-incorrect.
**Fix**: Wrap the initial summary toast in `if (isMarketOpen('NSE'))`.

---

## AlertContext: unacknowledgedCount includes all alerts, not just today's

**File**: `src/contexts/AlertContext.tsx:409`
**Status**: MINOR_ISSUE
**Finding**: `unacknowledgedCount` is a count of ALL unacknowledged alerts across the 7-day fetch window. The Dashboard header, sidebar badge, and mobile nav badge all use this count. A trader who had 4 alerts last week and acknowledged none will see badge `4` every day, even in a new session.
**Evidence**: `const unacknowledgedCount = alerts.filter(a => !a.acknowledged).length;`
**Impact**: The alert badge count is inflated by old alerts. The "4 alerts" shown in the nav counts week-old alerts, not just today's. Users may think they have active current alerts when they're all from last week.
**Fix**: For the badge count, only count alerts from the last 24 hours: `alerts.filter(a => !a.acknowledged && new Date(a.shown_at ?? 0).getTime() > Date.now() - 86400000).length`. The full `unacknowledgedCount` can remain for the Alerts page stats strip.

---

## Dashboard.tsx: IST midnight cutoff calculation is wrong

**File**: `src/pages/Dashboard.tsx:331-334`
**Status**: BUG
**Finding**: The IST midnight cutoff computation for `mergedAlerts` is incorrect. The code computes `nowIST` as a Date shifted by +5:30 hours, calls `setUTCHours(0,0,0,0)` to zero it, then subtracts the IST offset to get a UTC timestamp. However, `nowIST` is a local Date object whose value was shifted, but `setUTCHours` zeroes the UTC fields of the already-shifted date. The net result is not guaranteed to be midnight IST in UTC.
**Evidence**:
```ts
const IST_OFFSET_MS = 5.5 * 60 * 60 * 1000;
const nowIST = new Date(Date.now() + IST_OFFSET_MS);
nowIST.setUTCHours(0, 0, 0, 0);
const cutoff = nowIST.getTime() - IST_OFFSET_MS;
```
The correct formula for "IST midnight as UTC timestamp" is:
```ts
const istMidnightUTC = Date.now() - ((Date.now() + IST_OFFSET_MS) % 86400000);
```
Or more readably: use `toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' })` to get today's date in IST, then construct `new Date(date + 'T00:00:00+05:30').getTime()`.
**Impact**: `mergedAlerts` (shown on Dashboard) may include alerts from the previous day or miss alerts from the current day, depending on browser timezone offset. For a user in UTC, the cutoff may be 5:30 PM yesterday instead of midnight IST.
**Fix**: Use `new Date(new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' }) + 'T00:00:00+05:30').getTime()`.

---

## Dashboard.tsx: `recentTrades` shows 3-day window but `unjournaled` counts only today

**File**: `src/pages/Dashboard.tsx:354-367`
**Status**: MINOR_ISSUE
**Finding**: `recentTrades` is all trades from the last 3 days (line 355-357). But the `unjournaled` count (line 364-367) filters `recentTrades` to only today's exits. The `ClosedTradesTable` receives `recentTrades` (3 days), but the "X to journal" stat in the header only reflects today. If yesterday has 5 unjournaled trades, the header shows `0 to journal` but the table shows those trades with journal prompts.
**Impact**: User sees `0 to journal` in the header but sees unjournaled prompts in the table below. Confusing inconsistency.
**Fix**: Either compute `unjournaled` from all `recentTrades` (3 days) or restrict `ClosedTradesTable` to today only.

---

## Dashboard.tsx: `sessionPnlDisplay` stored in riskState as `unrealized_pnl` — wrong field name

**File**: `src/pages/Dashboard.tsx:271`
**Status**: MINOR_ISSUE
**Finding**: `setRiskState(prev => prev ? { ...prev, unrealized_pnl: sessionPnl } : prev)` stores `sessionPnl` (realized + unrealized) in the `unrealized_pnl` field of `riskState`. The field is named `unrealized_pnl` but is being given the session total P&L. `riskState.unrealized_pnl` is never read in the rendering code (the Dashboard uses `sessionPnlDisplay` directly), so there's no user-visible bug today — but if `riskState.unrealized_pnl` is ever accessed, it will return the wrong value.
**Impact**: Latent data incorrectness. No current user-facing bug.
**Fix**: Rename the `riskState.unrealized_pnl` field to `session_pnl` to match what it actually holds, or remove this field from riskState entirely since Dashboard reads it from `sessionPnlDisplay`.

---

## Dashboard.tsx: journal auto-prompt timer not cleared on unmount properly

**File**: `src/pages/Dashboard.tsx:234-244`
**Status**: MINOR_ISSUE
**Finding**: The `useEffect` for journal auto-prompt returns a cleanup function that clears `journalPromptTimerRef.current`. However the cleanup only runs when `closedTrades` changes (it's in the dep array via the eslint-disable), not when the component unmounts in the middle of the 45-second wait. Actually the cleanup does run on unmount since it's a useEffect — but the `eslint-disable` comment suppresses the correct deps (`dataLoaded`, `journaledIds`, `journalOpen`), meaning stale closures for `journalOpen` and `journaledIds` could cause the prompt to fire even when the journal is already open or the trade was already journaled.
**Evidence**: `}, [closedTrades]); // eslint-disable-line react-hooks/exhaustive-deps` — `journalOpen` is read inside the effect but not in deps.
**Impact**: After a trade closes, if the user manually opens the journal within 45s and then closes it, the timer fires and re-opens the journal 45s later because `journalOpen` was stale (false) at effect creation time.
**Fix**: Add `journalOpen` and `journaledIds` to the dep array.

---

## Dashboard.tsx: WebSocket trade re-fetch ignores stale closure

**File**: `src/pages/Dashboard.tsx:217-221`
**Status**: MINOR_ISSUE
**Finding**: `useEffect(() => { ... fetchTrades(); fetchPositions(); }, [lastTradeEvent])` suppresses deps with eslint-disable. `fetchTrades` and `fetchPositions` are in `useCallback([])`, so they're stable — this is technically safe. But `isConnected` and `isTokenExpired` are read inside the effect body yet not in deps. If the token expires between renders, this effect could still trigger a fetch that results in a 401.
**Impact**: On token expiry, a WS trade event could trigger a failed fetch. Low severity since the 401 handler clears credentials gracefully.
**Fix**: Add `isConnected` and `isTokenExpired` to deps array (they're already captured correctly via `useBroker` but stale closures on unmount could misfire).

---

## Dashboard.tsx: sync error guard triggers during first load with no data

**File**: `src/pages/Dashboard.tsx:399-417`
**Status**: MINOR_ISSUE
**Finding**: The "Sync Failed" full-page error guard fires when `syncStatus === 'error' && !dataLoaded && !positionsLoading && !tradesLoading`. On first load, the auto-sync fires immediately and `syncStatus` can become `'error'` before `dataLoaded` is true. The guard then shows the full-page sync failure screen instead of letting positions/trades fetches try independently.
**Impact**: If the initial Zerodha sync fails (e.g. rate limited by Zerodha), the user sees a full-page error and cannot see any previously-cached data at all, even though positions might have loaded from the DB.
**Fix**: The positions/trades fetches (`fetchAllData`) should still run even if the initial sync fails. The guard should be removed or changed to show an inline banner instead of a full-page block.

---

## PnlSparkline.tsx: sparkline zero-line drawn at wrong position

**File**: `src/components/dashboard/PnlSparkline.tsx:25-29`
**Status**: BUG
**Finding**: `zeroY = toY(0)`. If all trades are profitable (all positive points), `min > 0` and `zeroY = toY(0)` would compute a Y coordinate below the chart's visible area (`zeroY > H`), since `0 < min`. The zero-reference line and area fill close at a position outside the SVG, clipping the area or not rendering properly.
**Evidence**:
```ts
const toY = (v: number) => H - ((v - min) / range) * (H * 0.85) - H * 0.075;
const zeroY = toY(0);
const areaPath = `${linePath} L${W},${zeroY.toFixed(1)} L0,${zeroY.toFixed(1)} Z`;
```
If `min = 1000`, `toY(0) = H - ((0 - 1000) / range) * H*0.85 - H*0.075`, which could easily exceed `H` (clipped) or go negative (also clipped by SVG viewport). The area fill will then visually break.
**Impact**: Profitable-only session sparkline shows incorrect or broken area fill behind the line.
**Fix**: Clamp `zeroY = Math.max(0, Math.min(H, toY(0)))` so the zero line stays within the SVG bounds.

---

## OpenPositionsTable.tsx: live P&L calculation ignores SHORT positions

**File**: `src/components/dashboard/OpenPositionsTable.tsx:91-99`
**Status**: BUG
**Finding**: `getLivePnl` computes `(live.last_price - p.average_entry_price) * p.total_quantity * mult`. For a SHORT position, `p.total_quantity` is negative (Zerodha sends negative qty for short). The formula `(LTP - entry) * negative_qty` correctly inverts the sign for a SHORT — a rising price gives a negative P&L. This is mathematically correct. However the fallback `return p.unrealized_pnl` (used when no live price) already has the sign right from the DB. So actually the logic appears correct but only if `p.total_quantity` is reliably negative for shorts. If the backend ever stores `total_quantity` as absolute and uses `direction` to determine sign, this formula would be wrong.
**Status**: CORRECT (conditional on backend contract) — but see related issue below.
**Fix**: Add a comment documenting the assumption that `total_quantity` is signed (negative for SHORT).

---

## OpenPositionsTable.tsx: subscription effect uses `.length` instead of full array dep

**File**: `src/components/dashboard/OpenPositionsTable.tsx:84-88`
**Status**: MINOR_ISSUE
**Finding**: `useEffect(() => { subscribe(openPositions.map(p => p.tradingsymbol)); }, [openPositions.length, isConnected, subscribe])`. The dependency is `openPositions.length` not the array itself. If positions are replaced by a completely different set of symbols but the count stays the same, the subscription won't update (e.g. closed NIFTY CE and opened BANKNIFTY PE — still 1 position).
**Impact**: After a position change with same count, prices for the old symbol continue to stream and the new position may show no live price.
**Fix**: Compute a stable key from the symbol set: `openPositions.map(p => p.tradingsymbol).join(',')` and use that as a dep, or use `JSON.stringify(openPositions.map(p => p.tradingsymbol))`.

---

## ClosedTradesTable.tsx: `recentTrades` computed as 3-day window but displayed as "Closed Trades" (today implied)

**File**: `src/pages/Dashboard.tsx:354-357` + `src/components/dashboard/ClosedTradesTable.tsx:73-76`
**Status**: MINOR_ISSUE
**Finding**: The table receives trades from the last 3 days, but the header says "Closed Trades" with `trades.length` count, W/L stats, and P&L aggregation. The P&L shown in the header is the sum of all 3-day trades, but the Session Hero shows today-only P&L. The user sees mismatched numbers: Dashboard hero says `+₹7,990` (today), but the Closed Trades header shows a higher/lower number covering 3 days.
**Impact**: User confusion — "why does the closed trades P&L differ from the session P&L above?"
**Fix**: Either restrict `recentTrades` to today's trades, or add a date range label to the Closed Trades card header (e.g. "Closed Trades · Last 3 days").

---

## Alerts.tsx (HistoryTab): duplicate pattern name formatting — different from AlertContext

**File**: `src/pages/Alerts.tsx:207`
**Status**: MINOR_ISSUE
**Finding**: `HistoryTab` maps raw backend alerts to `AlertNotification` locally, using a simple split/capitalize for the pattern name: `a.pattern_type.split('_').map(...).join(' ')`. `AlertContext.mapBackendAlert` uses `formatPatternName()` which has a curated name map (e.g. `consecutive_loss_streak` → "Consecutive Loss Streak"). The History tab bypasses this and produces generic capitalized names that may differ from the Live tab.
**Evidence**: In History tab, `consecutive_loss_streak` → "Consecutive Loss Streak" (correct by coincidence). But `iv_crush_behavior` → "Iv Crush Behavior" instead of "IV Crush". `fomo_entry` → "Fomo Entry" instead of "FOMO Entry".
**Impact**: Alert names in History tab look inconsistently formatted vs Live tab. "Fomo Entry" vs "FOMO Entry".
**Fix**: Import and use `formatPatternName()` from AlertContext in HistoryTab's mapping function, or extract it to a shared utility.

---

## Alerts.tsx (PatternsTab): "last 48 hours" label hardcoded but data is from AlertContext 7-day window

**File**: `src/pages/Alerts.tsx:363`
**Status**: BUG
**Finding**: The Patterns tab label says "X distinct patterns detected in the last 48 hours" but it uses `alerts` from `AlertContext` which fetches a 7-day (168h) window.
**Evidence**: `AlertContext` line 290: `api.get('/api/risk/alerts', { params: { hours: 168 } })` and Patterns tab line 363: `{summaries.length} distinct pattern{...} detected in the last 48 hours`.
**Impact**: User sees "3 patterns in the last 48 hours" but the patterns may include ones from 5 days ago. The time claim is factually wrong.
**Fix**: Change the label to "last 7 days" to match the actual data window.

---

## BtstTab.tsx: win rate from backend vs recomputed locally will diverge

**File**: `src/components/analytics/BtstTab.tsx:101-102`
**Status**: MINOR_ISSUE
**Finding**: The `btst_win_rate` is from the backend (line 83, `btst_win_rate`), but the "winners" sub-label is recomputed on the frontend: `trades.filter(t => t.realized_pnl > 0).length`. If backend win rate counts breakeven trades (P&L = 0) as wins or uses a different threshold, the displayed percentage won't match the "X winners" count below it.
**Evidence**:
```ts
{ label: 'Win Rate', value: `${btst_win_rate}%`,
  sub: `${trades.filter(t => t.realized_pnl > 0).length} winners`, ... }
```
**Impact**: User may see "Win Rate: 60%" but "2 winners" out of 5 trades (= 40%), if backend uses a different win calculation.
**Fix**: Compute win rate consistently: `const winners = trades.filter(t => t.realized_pnl > 0).length; const winRateFE = total > 0 ? Math.round(winners / total * 100) : 0;` and use `winRateFE` for display instead of `btst_win_rate`.

---

## PnlPercentTab.tsx: RR ratio display shows "—" when rr_ratio is 0 (edge case)

**File**: `src/components/analytics/PnlPercentTab.tsx:154-158`
**Status**: MINOR_ISSUE
**Finding**: `rr_ratio !== null ? rr_ratio.toFixed(2) : '—'` — displays `0.00` when `rr_ratio` is exactly 0 (all losses, no wins). This is technically correct but the sub-label logic `rr_ratio >= 1 ? 'Avg win > avg loss' : 'Avg win < avg loss'` will say "Avg win < avg loss" even when there are no wins at all. The color also shows `text-tm-obs` (amber) for `rr_ratio < 1`, which is misleading when `rr_ratio = 0`.
**Impact**: A trader with 0 wins in the period sees "R:R ratio: 0.00 / Avg win < avg loss" — the framing implies some wins but they're all smaller, when actually there are zero wins.
**Fix**: Add a `rr_ratio === 0` or `win_count === 0` check: show "No winning trades" as the sub-label.

---

## PnlPercentTab.tsx: trade list sorted worst-to-best (ascending pnl_pct) without indication

**File**: `src/components/analytics/PnlPercentTab.tsx:291`
**Status**: MINOR_ISSUE
**Finding**: `[...trades].sort((a, b) => a.pnl_pct - b.pnl_pct)` sorts worst-first (most negative at top). There's no sort-order label or sort button. User sees their biggest loss at the top without understanding why.
**Impact**: Minor UX confusion — looks like the data is arbitrary, and the user's biggest loss appears front-and-center without context.
**Fix**: Add a label "Sorted by worst performance first" or provide a sort toggle.

---

## Discipline.tsx: trendData week labels are reversed

**File**: `src/pages/Discipline.tsx:108-111`
**Status**: BUG
**Finding**: 
```ts
const trendData = data.weekly_trend.map((s, i) => ({
  week: `W-${data.weekly_trend.length - i}`,
  score: s,
})).reverse();
```
`weekly_trend` is assumed to be oldest-first (index 0 = oldest). The mapping assigns labels `W-4, W-3, W-2, W-1` (counting down), then `.reverse()` flips both the data order and the labels. After reverse: index 0 has `W-1` (was last), index 1 has `W-2`, etc. So labels are now `W-1, W-2, W-3, W-4` left to right — which shows the most recent week on the left and oldest on the right. Timelines should flow left (old) to right (new).
**Impact**: The 4-week trend chart shows time going right-to-left. The most recent week appears on the left instead of the right. A score improvement looks like a decline visually.
**Fix**: Remove `.reverse()` and change the label formula to `W-${i + 1}` (or use actual week dates). The original order (oldest first) with labels `W-1, W-2, W-3, W-4` left to right is the correct time-series layout.

---

## Discipline.tsx: ScoreGauge percentage thresholds use `pct` (0–100 scale) correctly

**File**: `src/pages/Discipline.tsx:31-33`
**Status**: CORRECT
**Finding**: `const pct = Math.min(100, (score / max) * 100)`. If `max = 100` and `score = 68`, `pct = 68`. Thresholds `>= 70`, `>= 45`, `< 45` are applied correctly. The circumference math `2 * Math.PI * 45` and `dashOffset = circumference * (1 - pct/100)` are correct SVG circle logic.
**Impact**: No bug.

---

## MyPatterns.tsx: streak calculation counts all 30 days, including weekends and non-trading days

**File**: `src/pages/MyPatterns.tsx:229-246`
**Status**: MINOR_ISSUE
**Finding**: The streak iterates `for (let i = 0; i < 30; i++)` over the last 30 calendar days. `trading_day` is set to `!!alertsByDate[dateStr]` — true only if there was an alert on that day. So Saturday and Sunday will have `trading_day = false` and `all_goals_followed = true` (no alerts). The streak counts these as "clean" days. A trader who had no alerts last week and is now on a 7-day streak is actually on a 5-trading-day streak, but the UI shows 7.
**Impact**: Streak inflated by weekends. "7-day clean streak" actually includes 2 weekend days. Misleading for traders who care about trading-day streaks.
**Fix**: Mark `trading_day = false` for weekends using `new Date(dateStr).getDay()` check (0=Sun, 6=Sat), and count streak only over `trading_day === true` days.

---

## MyPatterns.tsx: milestone achieved_at is always today's date

**File**: `src/pages/MyPatterns.tsx:255-257`
**Status**: BUG
**Finding**: `milestones_achieved` uses `daily_status[0]?.date ?? ''` for `achieved_at`. `daily_status[0]` is today's date (i=0 in the loop). So all achieved milestones are labeled as achieved today, regardless of when they were actually reached.
**Evidence**: `map(d => ({ days: d, achieved_at: daily_status[0]?.date ?? '', label: MILESTONE_LABELS[d] }))`
**Impact**: If a trader achieved their "7-day clean" milestone 3 days ago, it shows as achieved today. Streak milestone dates are all wrong.
**Fix**: Find the actual date when the streak first reached `d` days long by scanning `daily_status` to find the `d`-th consecutive clean day.

---

## MyPatterns.tsx: emotionalTax calculated from alert patterns but no trades passed

**File**: `src/pages/MyPatterns.tsx:285`
**Status**: MINOR_ISSUE
**Finding**: `calculateEmotionalTax(patterns as any, [])` passes an empty trades array. The calculator uses `trades` for week/month bucketing (`weekAgo`, `monthAgo` filtering in `emotionalTaxCalculator.ts`). Without trades, the time-bucketed cost breakdowns will all be zero, even though `patterns` (from alerts) have timestamps. The total cost is still summed from patterns' `estimated_cost` but the `thisWeek`/`thisMonth` breakdowns are incorrect.
**Impact**: EmotionalTaxCard shows `₹0` for "This Week" and "This Month" even when alerts from this week have estimated costs.
**Fix**: Either pass trades from the dashboard fetch, or make `calculateEmotionalTax` work purely from pattern timestamps when the trades array is empty.

---

## BrokerContext.tsx: `isGuest` computed at render time from localStorage, not from state

**File**: `src/contexts/BrokerContext.tsx:366`
**Status**: BUG
**Finding**: `isGuest: isGuestMode()` calls `localStorage.getItem(GUEST_MODE_KEY)` directly on every render. This is not reactive — it's a direct read that doesn't cause re-render when guest mode changes. When `exitGuestMode()` is called (line 352), it calls `disableGuestMode()` (removes localStorage key) and `setAccount(null)`. The `isGuest` value in the context will only update after the next render triggered by `setAccount(null)`. This is likely fine in practice because `setAccount` triggers re-render, but it's an anti-pattern.
**Impact**: Minimal risk today because `setAccount` always accompanies guest mode changes. But if `isGuestMode()` is called in a stale context value before the re-render propagates, components can briefly show `isGuest: true` after exit or vice versa.
**Fix**: Store guest mode in React state: `const [isGuest, setIsGuest] = useState(isGuestMode())`, and update it in `enterGuestMode`/`exitGuestMode`.

---

## BrokerContext.tsx: disconnect clears all `tradementor_*` localStorage keys including guest mode key

**File**: `src/contexts/BrokerContext.tsx:253-256`
**Status**: MINOR_ISSUE
**Finding**: `disconnect()` deletes all `localStorage` keys starting with `tradementor`. This includes `tradementor_guest_mode` and `tradementor_seen_alerts`. In practice, `disconnect` is only called when actually connected (not guest), so removing the guest key is harmless. But `tradementor_seen_alerts` is also deleted, meaning that after a reconnect, all historical alerts will be re-toasted as "new" on the next load.
**Impact**: After disconnect + reconnect, the initial page load summary toast will fire for all unacknowledged alerts in the last 24h (even if the user saw them before disconnect).
**Fix**: Preserve `tradementor_seen_alerts` in the disconnect cleanup. Only clear session-specific keys.

---

## BrokerContext.tsx: token expiry warning timer does not cancel when account changes to null

**File**: `src/contexts/BrokerContext.tsx:301-327`
**Status**: MINOR_ISSUE
**Finding**: The `useEffect` for proactive expiry warning depends on `[account]`. When `account` changes, the cleanup cancels the old timer. However, if `account` becomes `null` (after disconnect), the effect re-runs, reads `localStorage.getItem(AUTH_TOKEN_KEY)` (which was just cleared), gets `null`, and returns early — correct. But if disconnect clears the token in storage but doesn't null `account` immediately (async edge case), the timer could still fire. The sequence is safe in practice but worth noting.
**Impact**: Low risk. No current user-facing bug.

---

## WebSocketContext.tsx: connect() called on each reconnect attempt creates new closure over stale `account`

**File**: `src/contexts/WebSocketContext.tsx:122-277`
**Status**: MINOR_ISSUE
**Finding**: `connect` is wrapped in `useCallback([account?.id, isTokenExpired, ...])`. On reconnect (timeout fires), it calls `connect()` which has the correct account from the closure. However `reconnectRef.current = setTimeout(() => { if (mountedRef.current) { ...; connect(); } }, delay)` captures `connect` from the outer scope at the time the timeout is scheduled, not at the time it fires. Since `connect` is stable for a given `account?.id`, this is fine unless the account changes during the reconnect window.
**Impact**: Safe in practice. No current user-facing bug.

---

## WebSocketContext.tsx: ping interval not cleared when auth fails (close code 4001)

**File**: `src/contexts/WebSocketContext.tsx:253-270`
**Status**: BUG
**Finding**: In `ws.onclose`, the check is `if (event.code !== 1000 && event.code !== 4001)` — code 4001 (auth failure) skips reconnect scheduling. But `pingRef.current` is cleared on line 256 inside the handler. This is correct. However, if the WS close happens before `auth_ok` (e.g. server rejects auth immediately with close code 4001), the ping interval set in `ws.onopen` (line 151) was already started. The `onclose` handler clears it — this is correct. But there's a window between `onopen` and auth rejection where the ping interval runs and sends pings on an unauthenticated connection. Not a critical bug but sends unnecessary traffic.
**Impact**: Minor — sends up to 1-2 ping frames before auth rejection. No data corruption.

---

## WebSocketContext.tsx: `isReconnecting` never reset to false after token expiry closes socket

**File**: `src/contexts/WebSocketContext.tsx:258-269`
**Status**: BUG
**Finding**: When the socket closes with code 4001 (auth failure / token expired), the code skips reconnect scheduling. But `isReconnecting` is never set back to `false` in this path. If `hasConnectedRef.current` is true and the connection closes with 4001, `setIsReconnecting(true)` was set at line 261, but no code path within the 4001 branch sets it back to false. The amber "Reconnecting" indicator will show indefinitely even though the socket is not actually trying to reconnect.
**Evidence**: Code path for `event.code === 4001`: enters `ws.onclose`, line 255 `setIsConnected(false)`, line 256 clears ping. Then falls into `if (event.code !== 1000 && event.code !== 4001)` which is FALSE — so the `setIsReconnecting(true)` on line 261 is NOT reached. Actually re-reading: the condition is `event.code !== 1000 && event.code !== 4001` — when code IS 4001, this is false, so `setIsReconnecting(true)` is NOT called. The `isReconnecting` would remain at its previous value. If it was `true` from a previous reconnect attempt and the socket closed with 4001, it stays true.
**Impact**: If the user had a brief network interruption (isReconnecting=true) and then the new connection fails auth (4001), the "Reconnecting" amber dot stays on screen indefinitely even though TradeMentor has stopped trying to reconnect.
**Fix**: Add `setIsReconnecting(false)` in the `else` branch (when code is 1000 or 4001).

---

## Layout.tsx: "My Patterns" nav label links to `/personalization` not `/my-patterns`

**File**: `src/components/Layout.tsx:33`
**Status**: BUG
**Finding**: In `mobileMoreGroups`, the "My Patterns" item links to `href: '/personalization'`. But the route registered in `App.tsx` for `<MyPatterns />` is `path="my-patterns"`. The Personalization page is a separate page at `path="personalization"`. These are two different pages with different content.
**Evidence**:
- `Layout.tsx:33`: `{ name: 'My Patterns', href: '/personalization', icon: Brain }`
- `App.tsx:85`: `<Route path="personalization" element={<Personalization />} />`
- `App.tsx:84`: `<Route path="my-patterns" element={<MyPatterns />} />`
**Impact**: On mobile, tapping "My Patterns" in the More sheet navigates to the Personalization page (personalized insights) instead of the My Patterns / Risk Monitor page. The `/my-patterns` route is inaccessible from the mobile navigation.
**Fix**: Change `href: '/personalization'` to `href: '/my-patterns'`. Add a separate entry for Personalization if needed, or check whether the mobile nav was intentionally merging them.

---

## Layout.tsx: isOverflowActive checks exact pathname match only, misses sub-paths

**File**: `src/components/Layout.tsx:250`
**Status**: MINOR_ISSUE
**Finding**: `const isOverflowActive = mobileMoreItems.some(i => location.pathname === i.href)`. This only matches exact paths. If any overflow item ever has child routes (e.g. `/settings/notifications`), the "More" tab won't highlight as active.
**Impact**: Minor cosmetic — "More" tab not highlighted when on a settings sub-page. Low priority.

---

## App.tsx: PortfolioRadar and PortfolioChat pages have no routes registered

**File**: `src/App.tsx`
**Status**: BUG
**Finding**: `PortfolioRadar.tsx` and `PortfolioChat.tsx` exist as pages but have no `<Route>` registered in `App.tsx`. They are importable files with full content but are unreachable via any URL.
**Evidence**: `App.tsx` has no `path="portfolio-radar"` or `path="portfolio-chat"` Route. The Sidebar likely has links to these, making them dead links.
**Impact**: Any user or sidebar link to `/portfolio-radar` or `/portfolio-chat` will hit the `<NotFound>` page.
**Fix**: Add routes: `<Route path="portfolio-radar" element={<PortfolioRadar />} />` and `<Route path="portfolio-chat" element={<PortfolioChat />} />`.

---

## App.tsx: root route authentication check reads localStorage directly, not from BrokerContext

**File**: `src/App.tsx:65-73`
**Status**: MINOR_ISSUE
**Finding**: The root `index` route uses `localStorage.getItem(AUTH_TOKEN_KEY) || isGuestMode()` to decide whether to redirect to `/dashboard` or `/welcome`. This is a synchronous localStorage read done during routing. If the token exists but is expired, the user is sent to `/dashboard` where `BrokerContext` will detect the expiry and show the expired-token banner. This is acceptable behavior. However, reading localStorage directly in the route element (not inside a component effect) means the redirect is fixed at initial render and won't update if guest mode is entered after the router mounts.
**Impact**: Low risk in practice. No current user-facing bug since `enterGuestMode` causes a re-render that triggers navigation.

---

## guestMode.ts: catch-all returns `{}` (empty object) for unmocked routes — may cause shape errors

**File**: `src/lib/guestMode.ts:234-236`
**Status**: MINOR_ISSUE
**Finding**: The catch-all at the end returns `{}` (empty object) for any unmocked URL. This means real API calls are intercepted and return `{}` instead of failing or falling through. Components that check `res.data?.someField` will get `undefined`, which may be handled by null guards. But components that destructure the response directly (e.g. `const { accounts } = res.data`) will fail silently.
**Evidence**: `return {};` — any unmocked guest route returns empty object
**Impact**: Any new API endpoint added to the app but not listed in `guestMode.ts` will silently return `{}` in guest mode. The component may show a blank state instead of demo data or a clear "guest mode" message.
**Fix**: Return `undefined` for unmocked routes instead of `{}`, so the real network call falls through. Only return `{}` or `{ success: true }` for mutation endpoints (POST/DELETE/PATCH) where success stubbing is intentional.

---

## guestMode.ts: `/api/trades/completed` not mocked, only `/api/trades/`

**File**: `src/lib/guestMode.ts:74`
**Status**: BUG
**Finding**: `if (path === '/api/trades/completed' || path === '/api/trades/')` — this handles both. Dashboard fetches `/api/trades/completed` (line 119 of Dashboard.tsx). This appears handled. However the catch confirms it's correct — no bug here. Confirmed CORRECT.

---

## guestMode.ts: `/api/analytics/behavioral` not mocked but `/api/behavioral/analysis` is

**File**: `src/lib/guestMode.ts:128`
**Status**: MINOR_ISSUE
**Finding**: Guest mode maps `/api/behavioral/analysis` to `DEMO_BEHAVIORAL_ANALYSIS`. If `BehaviorTab` calls `/api/analytics/behavioral-analysis` or a slightly different URL, it gets `{}` instead of demo data. Need to verify the exact URL in `BehaviorTab`. Likely safe if URLs match, but worth a double-check.

---

## demoData.ts: DEMO_COMPLETED_TRADES P&L verification (ct-002 SOLARINDS)

**File**: `src/lib/demoData.ts:47-56`
**Status**: MINOR_ISSUE
**Finding**: ct-002 SOLARINDS: `avg_entry_price: 8420`, `avg_exit_price: 8290`, `total_quantity: 100`, `realized_pnl: -13000`. Expected P&L: `(8290 - 8420) * 100 = -13000`. Correct.

ct-004 BANKNIFTY PE: `avg_entry_price: 340`, `avg_exit_price: 490`, `total_quantity: 15`, `realized_pnl: 2250`. Expected: `(490 - 340) * 15 = 2250`. Correct.

ct-005 FORTIS CE: `avg_entry_price: 14.5`, `avg_exit_price: 19.2`, `total_quantity: 1100`, `realized_pnl: 5170`. Expected: `(19.2 - 14.5) * 1100 = 4.7 * 1100 = 5170`. Correct.

ct-007 NIFTY CE: `avg_entry_price: 102`, `avg_exit_price: 148`, `total_quantity: 50`, `realized_pnl: 2300`. Expected: `(148 - 102) * 50 = 46 * 50 = 2300`. Correct.

ct-008 NIFTY PE: `avg_entry_price: 55`, `avg_exit_price: 30`, `total_quantity: 150`, `realized_pnl: -3750`. Expected: `(30 - 55) * 150 = -25 * 150 = -3750`. Correct.
**Status**: CORRECT — all demo P&Ls are mathematically consistent.

---

## SummaryTab.tsx: `groupByUnderlying` win rate calculation uses rounding that accumulates error

**File**: `src/components/analytics/SummaryTab.tsx:76`
**Status**: MINOR_ISSUE
**Finding**: `map[u].wins += Math.round(instr.trades * instr.win_rate / 100)`. For each instrument, wins are computed by rounding `trades * winRate`. When multiple instruments with the same underlying are aggregated, the rounded wins are summed. This introduces rounding errors that compound — a 0.5 round-up on each of 5 instruments can overcount wins by up to 5. The final `win_rate` for the underlying could be off by several percentage points.
**Example**: 3 instruments, each with 1 trade and 0% win rate. `Math.round(1 * 0 / 100) = 0` each. Correct. But: 3 instruments, each 3 trades, 33% win rate. `Math.round(3 * 33/100) = Math.round(0.99) = 1`. Aggregated: 3 wins out of 9 trades = 33%. Correct in this case. The rounding is low-risk but imprecise.
**Impact**: Minor display inaccuracy in the underlying win rate breakdown. Off by ≤ 1-2% in most cases.
**Fix**: Store exact wins as a float `instr.trades * instr.win_rate / 100` and only round at display time.

---

## Dashboard.tsx: `fetchRiskState` closures over `lastSyncAt` but this dep is in useCallback

**File**: `src/pages/Dashboard.tsx:151-172`
**Status**: MINOR_ISSUE
**Finding**: `fetchRiskState` is defined with `useCallback([lastSyncAt])`. Every time `lastSyncAt` changes (after each sync), a new `fetchRiskState` function is created. This in turn causes `fetchAllData` (which depends on `fetchRiskState`) to also be recreated. Which then triggers the `prevSyncStatus` effect to call `fetchAllData` again — this creates a chain of recreation on every sync. While React handles this without infinite loops (effects compare by reference), it results in unnecessary function recreation on every sync.
**Impact**: No user-facing bug. Slight performance overhead.
**Fix**: Remove `lastSyncAt` from `fetchRiskState` deps and read it via a ref instead.

---

## Dashboard.tsx: `handleJournalClose` marks all trades as journaled on close, regardless of save

**File**: `src/pages/Dashboard.tsx:319-323`
**Status**: BUG
**Finding**: `handleJournalClose` adds `selectedTrade.id` to `journaledIds` whenever the journal sheet closes with `open=false`. This happens even if the user closes the journal without saving (pressed X or dismissed). The trade is marked as journaled in the UI, the journal dot disappears, and the "X to journal" counter decrements — but no journal entry was actually saved.
**Evidence**:
```ts
const handleJournalClose = (open: boolean) => {
  if (!open && selectedTrade) {
    setJournaledIds(prev => new Set([...prev, selectedTrade.id]));
  }
  setJournalOpen(open);
};
```
**Impact**: User opens journal, decides not to write anything, closes it. The trade is now marked as "journaled" with a green checkmark. The user no longer gets prompted to journal this trade. The actual journal entry is empty.
**Fix**: Only add to `journaledIds` when the journal sheet emits a "saved" event. Pass an `onSaved` callback to `TradeJournalSheet` and call it after successful API save.

---

## BlowupShield.tsx: cache invalidation on visibility change always re-fetches (ignores TTL)

**File**: `src/pages/BlowupShield.tsx:174-178`
**Status**: MINOR_ISSUE
**Finding**: The `visibilitychange` listener calls `fetchShieldData()` without passing `force=true`, so it will use the cache if within TTL. This is actually correct — the cache check inside handles it. On re-reading: `onVisible` calls `fetchShieldData()` (no args, so `force=false`), and the cache check correctly applies. This is CORRECT.
**Status**: CORRECT

---

## BlowupShield.tsx: `shieldCache` is a module-level variable (shared across all renders)

**File**: `src/pages/BlowupShield.tsx:16-20`
**Status**: MINOR_ISSUE
**Finding**: `shieldCache` is declared at module scope, not inside a React context or ref. If two tabs are open with different accounts, both tabs share the same `shieldCache` variable (since it's in module memory of each tab separately — actually each tab is a separate JS environment, so this is fine). Within a single tab, the cache is correctly keyed by `accountId`. This is safe.
**Status**: CORRECT — module-level cache is per-tab. The `accountId` check prevents cross-account stale data.

---

## AlertDetailSheet.tsx: `PATTERN_EXPLANATIONS` only covers ~12 patterns out of 22 detected

**File**: `src/components/alerts/AlertDetailSheet.tsx:10-24`
**Status**: MINOR_ISSUE
**Finding**: `PATTERN_EXPLANATIONS` maps 12 pattern types. The behavior engine has 22 patterns. Missing entries: `burst_trading`, `overtrading`, `consecutive_loss` (different from `consecutive_loss_streak`), `fomo_entry`, `winning_streak_overconfidence`, `session_meltdown`, `profit_giveaway`, `rapid_flip`, `options_direction_confusion`, `options_premium_avg_down`, `expiry_day_overtrading`, `post_loss_recovery_bet` (present), `iv_crush_behavior`.
**Impact**: The "Why this happens" explanation box shows an empty string or nothing for ~10 patterns. Users get no educational context for alerts like `winning_streak_overconfidence` or `session_meltdown`.
**Fix**: Add explanation entries for all 22 patterns.

---

## AlertDetailSheet.tsx: `buildFacts` returns empty array for most patterns — no detail shown

**File**: `src/components/alerts/AlertDetailSheet.tsx:37-onwards`
**Status**: MINOR_ISSUE
**Finding**: `buildFacts` has cases for `revenge_trade`, `rapid_reentry`, `panic_exit`, `size_escalation`, `martingale_behaviour`, `post_loss_recovery_bet`, `consecutive_loss_streak`, `overtrading`, `burst_trading`, `profit_giveaway`. Many patterns like `fomo_entry`, `session_meltdown`, `winning_streak_overconfidence`, `opening_5min_trap`, `end_of_session_mis_panic`, `expiry_day_overtrading`, `options_direction_confusion`, `options_premium_avg_down`, `iv_crush_behavior`, `no_stoploss` have no `buildFacts` case and will show no detail rows.
**Impact**: Alert detail sheets for these patterns show no trade-specific data — just the description text. Less informative than intended.
**Fix**: Add `buildFacts` cases for remaining patterns using their known detail fields from `behavior_engine.py`.

---

## useCountUp.ts: animation starts from 0 on every target change, not from current value

**File**: `src/hooks/useCountUp.ts:15`
**Status**: MINOR_ISSUE
**Finding**: `startVal.current = 0` on every effect re-run. If `sessionPnlDisplay` goes from `+7990` to `+8200` (new trade), the counter animates from 0 to 8200 instead of from 7990 to 8200. The user sees the number drop to zero and count back up, which is visually jarring during an active trading session.
**Impact**: Every time a new trade closes, the session P&L hero counter resets to 0 and counts back up. For a trader with large P&L, this causes a "flash to zero" effect.
**Fix**: Set `startVal.current = value` (the current animated value) before resetting the animation, so it animates incrementally from the current position.

---

## Chat.tsx: SSE streaming uses raw API_URL, bypassing the guest-mode axios interceptor

**File**: `src/pages/Chat.tsx:26`
**Status**: BUG
**Finding**: `const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'` is used directly with `fetchWithAuth`. The `fetchWithAuth` function in `api.ts` does not check `isGuestMode()` — it goes directly to the network. The guest-mode axios interceptor in `api.ts` intercepts axios requests, not native `fetch`. So in guest mode, the chat SSE request will hit the real backend (or fail with a network error).
**Evidence**: `guestMode.ts` intercepts via `config.adapter` in the axios request interceptor — this only applies to axios. `fetchWithAuth` uses native `fetch`.
**Impact**: Guest users who click on a chat prompt will get a network error or 401 from the real backend. The chat page fails silently or shows an error for guests.
**Fix**: In `Chat.tsx`, check `isGuestMode()` before sending the fetch request and return a canned demo response instead. Or add guest-mode support to `fetchWithAuth`.

---

## Reports.tsx and Guardrails.tsx: using `useQuery` from React Query but QueryClient is provided in App.tsx

**File**: `src/pages/Guardrails.tsx:1`
**Status**: CORRECT
**Finding**: `Guardrails.tsx` uses `useQuery` and `useMutation` from `@tanstack/react-query`. `App.tsx` wraps with `QueryClientProvider`. This is correct.

---

## Guardrails.tsx: `conditionLabel` uses `Math.abs(rule.condition_value)` but shows "alert if loss exceeds"

**File**: `src/pages/Guardrails.tsx:75-87`
**Status**: MINOR_ISSUE
**Finding**: For `loss_threshold`, the condition value is expected to be negative (e.g. `-5000`). `conditionLabel` shows `Alert if loss exceeds ₹${Math.abs(value)}`. The hint says "Enter negative amount". But if a user enters `5000` (positive) instead of `-5000`, the condition_value stored is `5000`. `Math.abs(5000) = 5000` so the label looks correct. But the backend condition check (`position_pnl < condition_value`) would check `pnl < 5000` which means "alert when you have any P&L less than +5000 profit", not a loss limit at all.
**Impact**: If a user enters a positive value for a loss threshold, the guardrail fires incorrectly (triggers at any P&L below +5000 profit, including all losses but also when P&L hasn't reached +5000). The UI doesn't validate or auto-negate the value.
**Fix**: In the form handler, auto-negate the value for `loss_threshold` and `total_pnl_drop` if a positive number is entered.

---

## BehaviorTab.tsx: local SEV_DOT/SEV_LABEL redeclared instead of importing from alertSeverity.ts

**File**: `src/components/analytics/BehaviorTab.tsx:65-78`
**Status**: MINOR_ISSUE
**Finding**: `BehaviorTab` declares its own `SEV_DOT` and `SEV_LABEL` constants locally instead of importing from `src/lib/alertSeverity.ts`. The local versions have slightly different keys: `alertSeverity.ts` has `SEV_DOT.high = 'bg-tm-loss/70'` but `BehaviorTab`'s local `SEV_DOT.high = 'bg-tm-loss'` (no opacity). Minor visual inconsistency between the Alerts page (uses the shared version) and the Analytics Patterns tab (uses the local version).
**Impact**: High-severity alerts show a slightly lighter dot on Alerts page vs Analytics page — minor visual inconsistency.
**Fix**: Import `SEV_DOT` and `SEV_LABEL` from `@/lib/alertSeverity` and remove local redeclarations.

---

## Personalization.tsx: the "My Patterns" page in nav points here, but page is labeled "Personalization"

**File**: `src/pages/Personalization.tsx` (nav label in `Layout.tsx:33`)
**Status**: BUG (duplicate of Layout.tsx finding above)
**Finding**: Already reported under Layout.tsx. The mobile "My Patterns" link points to `/personalization`. The Personalization page is "Personal Insights & Learning", not the Risk Monitor / Behavioral Patterns page. Users navigating from the nav label "My Patterns" land on the wrong page.

---

## Welcome.tsx: Google Fonts loaded via HTTP link tag — CSP/HTTPS issue in production

**File**: `src/pages/Welcome.tsx:17-18`
**Status**: MINOR_ISSUE
**Finding**: Welcome page injects a `<link>` tag for Google Fonts via `document.head.appendChild`. In production on HTTPS, this makes a cross-origin request to `fonts.googleapis.com`. This is fine for the welcome page but if the app ever enforces a strict CSP, this injection will be blocked without a `font-src` policy.
**Impact**: Low risk. Fonts fall back to system fonts if blocked. No data bug.

---

## Summary of Issues by Severity

| Severity | Count | Examples |
|----------|-------|---------|
| CRITICAL_BUG | 0 | — |
| BUG | 9 | acknowledgeAll no backend call, IST cutoff wrong, journal close marks as journaled, sparkline zero-line, isReconnecting never reset, mobile nav My Patterns wrong route, PortfolioRadar/Chat unrouted, Chat SSE bypasses guest mode |
| MINOR_ISSUE | 24 | formatters null safety, trendData reversed, BTST win rate inconsistency, streak counts weekends, AlertContext unacknowledgedCount 7-day window, etc. |
| CORRECT | 6 | ScoreGauge math, demo P&L calculations, blowup shield cache, symbol regexes |

---

## Top 5 Fix Priority

1. **`acknowledgeAll` does not call backend** — alerts come back after any refresh. Core UX feature is broken.
2. **Mobile nav "My Patterns" → wrong page** — takes users to Personalization instead of Risk Monitor. Route `/my-patterns` is unreachable on mobile.
3. **PortfolioRadar + PortfolioChat pages have no routes** — entire pages unreachable.
4. **IST midnight cutoff calculation wrong** — today's alerts may not appear on Dashboard for users in non-IST timezone browsers.
5. **Chat SSE bypasses guest mode** — guest users hit real backend, get 401 or network error on chat.
