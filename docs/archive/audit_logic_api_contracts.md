> **ARCHIVED 22 Aug 2026 — do not use as a current reference.**
>
> June-10 contract sweep, superseded by docs/DEEP_REVIEW/.
>
> Live findings, if any, were rescued into `docs/ENGINE_BACKLOG.md`.

---

# API Contracts and Data Flow Logic Audit

**Audited:** 2026-06-10  
**Scope:** All frontend↔backend API contracts, field-name mismatches, type mismatches, missing fields, broken data flows, WebSocket contracts, pagination, error handling, and auth flow.  
**Files covered:** 30+ frontend and backend files across `src/`, `backend/app/api/`, `backend/app/schemas/`, `backend/app/services/`

---

## Contract: /api/analytics/dashboard-stats

**Frontend file**: `src/lib/guestMode.ts`  
**Backend file**: `backend/app/api/analytics.py:40-57`  
**Status**: BROKEN  
**Finding**: Backend returns `{ risk_score: score_data }` (a weekly risk/discipline score object). Frontend guest-mode mock returns `{ total_pnl, win_rate, trade_count, money_saved, behavioral_alerts }`. The `DashboardStats` interface in `src/types/api.ts` also defines `{ total_pnl, win_rate, total_trades, max_drawdown }` — none of these fields exist in the backend response.  
**Frontend expects**: `{ total_pnl: number, win_rate: number, total_trades: number, max_drawdown: number }`  
**Backend returns**: `{ risk_score: { score, max_score, level, breakdown, ... } }`  
**Impact**: Any component consuming this endpoint would render nothing or crash. Dashboard.tsx does not appear to call this endpoint directly — it calls `/api/risk/state` and `/api/positions/` instead. The endpoint is functionally orphaned.  
**Fix**: Either repurpose the endpoint to return the shape `DashboardStats` defines, or remove `DashboardStats` from `api.ts` and document that `dashboard-stats` now returns `risk_score`. Also update the guestMode mock accordingly.

---

## Contract: /api/analytics/unrealized-pnl

**Frontend file**: `src/lib/guestMode.ts`  
**Backend file**: `backend/app/api/analytics.py` (unrealized-pnl endpoint)  
**Status**: MISMATCH  
**Finding**: Frontend guest-mode mock returns `{ unrealized_pnl: number, positions_count: number }`. Backend returns `{ positions: Record<string, { unrealized_pnl, last_price, ... }>, total_unrealized: float }`. Field names differ: `unrealized_pnl` (mock) vs `total_unrealized` (backend); `positions_count` (mock) is absent from backend response.  
**Frontend expects**: `{ unrealized_pnl: number, positions_count: number }`  
**Backend returns**: `{ positions: object, total_unrealized: number }`  
**Impact**: Components that read `response.data.unrealized_pnl` will get `undefined`. Any component checking `positions_count` will get `undefined`.  
**Fix**: Align the mock with the actual backend response shape OR add `unrealized_pnl` and `positions_count` aliases to the backend response.

---

## Contract: /api/risk/state — status_message field

**Frontend file**: `src/types/api.ts:1-6`, `src/pages/Dashboard.tsx`  
**Backend file**: `backend/app/api/risk.py`, `backend/app/schemas/risk_alert.py`  
**Status**: MISMATCH (handled client-side)  
**Finding**: The `RiskState` interface in `api.ts` declares `status_message: string` as required. Backend `RiskStateResponse` schema does NOT include a `status_message` field. Dashboard.tsx constructs a status message locally from `risk_state` string (safe/caution/danger) rather than reading it from the API. No runtime crash because Dashboard does not actually read `response.data.status_message`.  
**Frontend expects**: `{ risk_state, status_message: string, active_patterns, last_updated }`  
**Backend returns**: `{ risk_state, active_patterns, recent_alerts, recommendations }` — no `status_message`, no `last_updated`  
**Impact**: `RiskState` type is inaccurate. If any future component reads `data.status_message` from the API response it will get `undefined`. `last_updated` field also missing from backend.  
**Fix**: Remove `status_message` and `last_updated` from the `RiskState` interface and document that those are derived client-side.

---

## Contract: /api/risk/alerts — acknowledged boolean field

**Frontend file**: `src/contexts/AlertContext.tsx`, `src/types/api.ts:123-140`  
**Backend file**: `backend/app/schemas/risk_alert.py`  
**Status**: MISMATCH (safely handled via fallback)  
**Finding**: The `Alert` interface declares `acknowledged?: boolean`. Backend `RiskAlertResponse` does NOT have a boolean `acknowledged` field. It has `acknowledged_at: Optional[datetime]`. AlertContext.tsx correctly falls back to `acknowledged_at != null` as the effective boolean. However any component that reads `alert.acknowledged` directly will always get `undefined`, evaluating to falsy — meaning unacknowledged and acknowledged alerts would both appear as "not acknowledged" unless the fallback logic is in place.  
**Frontend expects**: `acknowledged?: boolean`  
**Backend returns**: `acknowledged_at: string | null` (ISO datetime or null)  
**Impact**: Low — AlertContext uses the fallback correctly. Risk if any future component bypasses AlertContext and reads the raw alert object.  
**Fix**: Add `acknowledged: bool = Field(default=False)` as a `@computed_field` to `RiskAlertResponse`: `return self.acknowledged_at is not None`. This makes the contract explicit.

---

## Contract: /api/positions/ — current_value field

**Frontend file**: `src/types/api.ts:15-53`  
**Backend file**: `backend/app/schemas/position.py`  
**Status**: MISMATCH (handled at fetch boundary)  
**Finding**: `Position` interface declares `current_value: number` as required. Backend `PositionResponse` schema has `value: Optional[Decimal]` but NO `current_value` field. Dashboard.tsx explicitly transforms the position at the fetch boundary, computing `current_value = last_price * total_quantity` from Kite live data.  
**Frontend expects**: `current_value: number`  
**Backend returns**: `value: number | null` (+ optional `last_price`)  
**Impact**: Low — transform is in place. But if Dashboard.tsx's transform is bypassed or the position is used directly from a different page, `current_value` will be `undefined`, breaking any display relying on it. The `api.ts` comment on line 27 documents this mapping.  
**Fix**: Add `current_value` as a `@computed_field` on `PositionResponse` OR rename `value` to `current_value` in the backend schema. The frontend `api.ts` comment already acknowledges the gap.

---

## Contract: /api/trades/ — has_more stripped by response_model

**Frontend file**: `src/components/analytics/TradesTab.tsx`  
**Backend file**: `backend/app/api/trades.py`, `backend/app/schemas/trade.py`  
**Status**: MISMATCH (workaround in place)  
**Finding**: The `GET /api/trades/` handler returns a raw dict containing `has_more` but uses `response_model=TradeListResponse`. `TradeListResponse` schema has `{ trades, total, page, limit }` — no `has_more`. FastAPI's `response_model` strips fields not in the schema, so `has_more` is silently removed from the response. TradesTab.tsx works around this by computing `hasMore = offset < total` client-side.  
**Frontend expects**: Was designed to use `has_more` but falls back to `offset < total`  
**Backend returns**: `{ trades, total, page, limit }` — `has_more` stripped  
**Impact**: Low — the client-side fallback is functionally equivalent. However the raw dict intent suggests `has_more` was meant to be returned.  
**Fix**: Add `has_more: bool` to `TradeListResponse` schema so FastAPI includes it, and use it directly in TradesTab instead of recomputing.

---

## Contract: /api/trades/completed — has_more field

**Frontend file**: `src/components/analytics/TradesTab.tsx`  
**Backend file**: `backend/app/api/trades.py` — `/api/trades/completed`  
**Status**: CORRECT (by workaround)  
**Finding**: `GET /api/trades/completed` returns `CompletedTradeListResponse: { trades, total }` — no `has_more`. TradesTab.tsx computes pagination as `hasMore = offset < total`. This is correct.  
**Frontend expects**: Pagination via `offset < total`  
**Backend returns**: `{ trades: [...], total: number }`  
**Impact**: None.  
**Fix**: None needed.

---

## Contract: /api/trades/completed — pnl_pct field

**Frontend file**: `src/types/api.ts:99-121` (`CompletedTrade` interface)  
**Backend file**: `backend/app/schemas/trade.py` (`CompletedTradeResponse`)  
**Status**: MISMATCH (unused on frontend, harmless)  
**Finding**: Backend `CompletedTradeResponse` includes `pnl_pct: Optional[float]`. Frontend `CompletedTrade` interface does not declare `pnl_pct`. The field is returned by the backend but TypeScript will not expose it through the typed interface.  
**Frontend expects**: No `pnl_pct` field  
**Backend returns**: `pnl_pct: float | null`  
**Impact**: Harmless — field is ignored. But PnlPercentTab and any component that could use percentage P&L on completed trades misses this free field and recomputes it separately.  
**Fix**: Add `pnl_pct?: number` to the `CompletedTrade` interface so it can be used directly.

---

## Contract: /api/trades/completed — entry_time/exit_time optionality

**Frontend file**: `src/types/api.ts:99-121`  
**Backend file**: `backend/app/schemas/trade.py`  
**Status**: MISMATCH  
**Finding**: Frontend `CompletedTrade` interface declares `entry_time: string` and `exit_time: string` as required (non-optional). Backend `CompletedTradeResponse` has `entry_time: Optional[datetime]` and `exit_time: Optional[datetime]`.  
**Frontend expects**: `entry_time: string` (required), `exit_time: string` (required)  
**Backend returns**: `entry_time: string | null`, `exit_time: string | null`  
**Impact**: Medium — if a `CompletedTrade` is returned with `null` entry_time or exit_time, any TypeScript code calling `.toLocaleDateString()` or string operations on these fields will throw a runtime TypeError. This affects TradesTab.tsx (date display), BtstTab.tsx (entry date column), and PatternsTab.tsx (date/time format helpers).  
**Fix**: Change frontend interface to `entry_time: string | null` and `exit_time: string | null`, and add null guards in all display code.

---

## Contract: /api/trades/completed — created_at optionality

**Frontend file**: `src/types/api.ts:120`  
**Backend file**: `backend/app/schemas/trade.py`  
**Status**: MISMATCH  
**Finding**: Frontend `CompletedTrade` interface declares `created_at: string` as required. Backend `CompletedTradeResponse` has `created_at: Optional[datetime]`.  
**Frontend expects**: `created_at: string` (required)  
**Backend returns**: `created_at: string | null`  
**Impact**: Low — `created_at` is not visibly rendered in current components but the type contract is wrong.  
**Fix**: Change to `created_at?: string` in the frontend interface.

---

## Contract: /api/zerodha/sync/all — result shape consumed by BrokerContext

**Frontend file**: `src/contexts/BrokerContext.tsx`  
**Backend file**: `backend/app/api/zerodha.py:772-998`  
**Status**: CORRECT  
**Finding**: BrokerContext reads `result.results?.trades?.trades_synced`, `result.results?.trades?.positions_synced`, `result.results?.orders?.orders_synced`, and `result.results?.risk_alerts`. Backend `/sync/all` returns `{ success: true, results: { trades: trade_result, orders: orders_result, risk_alerts: added_count, ... } }`. The `trade_result` dict from `TradeSyncService.sync_trades_for_broker_account` is expected to have `trades_synced` and `positions_synced` keys.  
**Frontend expects**: `results.trades.trades_synced`, `results.trades.positions_synced`, `results.orders.orders_synced`, `results.risk_alerts`  
**Backend returns**: These fields are present if `TradeSyncService` returns them in the expected shape. The outer `results.risk_alerts` is set to `added_count` (integer). All optional-chained reads (`?.`) so silent `undefined` on missing fields.  
**Impact**: Low — all reads are optional-chained, so a missing field will silently show 0 or undefined in the sync result toast. Not a crash risk.  
**Fix**: Add TypeScript interface for the sync result shape and verify `TradeSyncService` always returns `{ trades_synced, positions_synced }`.

---

## Contract: /api/zerodha/accounts — account object shape

**Frontend file**: `src/contexts/BrokerContext.tsx`  
**Backend file**: `backend/app/api/zerodha.py:522-548`  
**Status**: CORRECT  
**Finding**: Frontend reads `accounts[0].id`, `.broker_name`, `.broker_user_id`, `.broker_email`, `.status`, `.connected_at`, `.last_sync_at`. Backend `/accounts` returns exactly these fields from `BrokerAccount`.  
**Frontend expects**: `{ id, broker_name, broker_user_id, broker_email, status, connected_at, last_sync_at }`  
**Backend returns**: Same shape  
**Impact**: None.  
**Fix**: None needed.

---

## Contract: /api/zerodha/auth/exchange — code exchange response

**Frontend file**: `src/contexts/BrokerContext.tsx`  
**Backend file**: `backend/app/api/zerodha.py` (auth/exchange endpoint)  
**Status**: CORRECT  
**Finding**: Frontend calls `POST /api/zerodha/auth/exchange { code }` and reads `{ token, broker_account_id }`. Backend stores a one-time auth code in Redis (30s TTL), exchanges it for JWT on this call, returns `{ token, broker_account_id }`.  
**Frontend expects**: `{ token: string, broker_account_id: string }`  
**Backend returns**: `{ token: string, broker_account_id: string }`  
**Impact**: None.  
**Fix**: None needed.

---

## Contract: /api/risk/alerts — response envelope

**Frontend file**: `src/contexts/AlertContext.tsx`  
**Backend file**: `backend/app/api/risk.py`  
**Status**: CORRECT  
**Finding**: AlertContext calls `GET /api/risk/alerts?hours=168` and reads `response.data.alerts`. Backend `RiskAlertListResponse` returns `{ alerts, total_count, unacknowledged_count }`. Frontend only reads `alerts` array — other fields are ignored.  
**Frontend expects**: `{ alerts: BackendAlert[] }` (reads only this)  
**Backend returns**: `{ alerts: [...], total_count: number, unacknowledged_count: number }`  
**Impact**: None — frontend only destructures `alerts`.  
**Fix**: None needed. Consider reading `unacknowledged_count` for badge display optimization.

---

## Contract: /api/risk/alerts/{id}/acknowledge — response shape

**Frontend file**: `src/contexts/AlertContext.tsx`  
**Backend file**: `backend/app/api/risk.py`  
**Status**: CORRECT  
**Finding**: Frontend calls `POST /api/risk/alerts/{alertId}/acknowledge` and does not read the response body (only checks for success). Backend returns `{ success: True }`.  
**Frontend expects**: Any 2xx response  
**Backend returns**: `{ success: true }`  
**Impact**: None.  
**Fix**: None needed.

---

## Contract: /api/shield/summary — ShieldSummary shape

**Frontend file**: `src/types/api.ts:148-159`, `src/pages/BlowupShield.tsx`  
**Backend file**: `backend/app/services/shield_service.py:107-119`  
**Status**: CORRECT  
**Finding**: Frontend `ShieldSummary` interface declares `{ total_alerts, danger_count, caution_count, heeded_count, continued_count, post_alert_pnl_continued, heeded_streak, spiral_sessions }`. Backend `get_shield_summary()` returns exactly these fields with the same names.  
**Frontend expects**: `ShieldSummary` interface  
**Backend returns**: Matching dict  
**Impact**: None.  
**Fix**: None needed.

---

## Contract: /api/shield/timeline — ShieldTimelineItem shape

**Frontend file**: `src/types/api.ts:161-178`, `src/pages/BlowupShield.tsx`  
**Backend file**: `backend/app/services/shield_service.py:171-184`  
**Status**: CORRECT  
**Finding**: Frontend `ShieldTimelineItem` declares `{ id, detected_at, pattern_type, severity, message, trigger_symbol, outcome, post_alert_trade_count, post_alert_pnl, post_alert_trades[{tradingsymbol, realized_pnl, exit_time}], narrative, details }`. Backend `get_intervention_timeline()` builds each dict with exactly these fields. `trigger_symbol` is extracted from `alert.details.get("trigger_symbol", "")`.  
**Frontend expects**: `ShieldTimelineItem` interface  
**Backend returns**: Matching dict  
**Impact**: None. Note: `trigger_symbol` will be empty string `""` if `details` is null or doesn't contain the key — frontend should handle empty string as "no symbol".  
**Fix**: None needed functionally. Consider documenting that `trigger_symbol` may be `""`.

---

## Contract: /api/shield/patterns — PatternBreakdown shape

**Frontend file**: `src/types/api.ts:180-188`, `src/pages/BlowupShield.tsx`  
**Backend file**: `backend/app/services/shield_service.py:227-243`  
**Status**: CORRECT  
**Finding**: Frontend `PatternBreakdown` interface: `{ pattern_type, display_name, alerts, heeded, continued, heeded_pct, post_alert_pnl }`. Backend `get_pattern_breakdown()` returns exactly these fields.  
**Frontend expects**: `PatternBreakdown[]`  
**Backend returns**: Matching list of dicts  
**Impact**: None.  
**Fix**: None needed.

---

## Contract: /api/danger-zone/status — DangerZoneStatus shape

**Frontend file**: `src/types/api.ts:472-485`, `src/pages/MyPatterns.tsx`  
**Backend file**: `backend/app/api/danger_zone.py:34-48, 77-111`  
**Status**: CORRECT  
**Finding**: Frontend `DangerZoneStatus` interface exactly matches backend `DangerZoneResponse` model: `{ level, intervention, triggers, message, cooldown_active, cooldown_remaining_minutes, daily_loss_used_percent, trade_count_today, consecutive_losses, patterns_active, recommendations, checked_at }`.  
**Frontend expects**: `DangerZoneStatus`  
**Backend returns**: `DangerZoneResponse` (Pydantic model with same fields)  
**Impact**: None.  
**Fix**: None needed.

---

## Contract: /api/danger-zone/summary — cooldown_history_7d field

**Frontend file**: `src/types/api.ts:543-562`, `src/pages/MyPatterns.tsx`  
**Backend file**: `backend/app/api/danger_zone.py:242-293`  
**Status**: CORRECT  
**Finding**: Frontend `DangerZoneSummary` interface reads `cooldown_history_7d: CooldownRecord[]`. Backend `/summary` endpoint returns `cooldown_history_7d: cooldown_history[:10]` where `cooldown_history` comes from `cooldown_service.get_cooldown_history(days=7)`. The shape of each `CooldownRecord` needs the service to return matching fields.  
**Frontend expects**: `cooldown_history_7d: CooldownRecord[]` with `{ id, broker_account_id, reason, duration_minutes, started_at, expires_at, is_active, remaining_minutes, remaining_seconds, can_skip, skipped, acknowledged, message, meta_data }`  
**Backend returns**: `cooldown_history[:10]` from cooldown_service — shape depends on `cooldown_service.get_cooldown_history()` implementation  
**Impact**: Medium — if `cooldown_service.get_cooldown_history()` doesn't return all fields in `CooldownRecord`, accessing them will silently return `undefined`. Not audited here: `cooldown_service.py` implementation.  
**Fix**: Audit `cooldown_service.get_cooldown_history()` return shape against `CooldownRecord` interface.

---

## Contract: /api/analytics/pnl-attribution — attribution_window_minutes

**Frontend file**: `src/components/analytics/AttributionCard.tsx:7-18`  
**Backend file**: `backend/app/api/analytics.py:2215-2291`  
**Status**: MISMATCH (harmless)  
**Finding**: Backend response includes `attribution_window_minutes: 30` (a constant). Frontend `AttributionData` interface does not declare this field — it is silently ignored.  
**Frontend expects**: `{ has_data, clean_pnl, clean_count, clean_wr, clean_avg_pnl, flagged_pnl, flagged_count, flagged_wr, flagged_avg_pnl, total_pnl }` — 10 fields  
**Backend returns**: Same 10 fields + `attribution_window_minutes: 30`  
**Impact**: None — extra field is ignored. The 30-minute window is hardcoded in the UI description text ("alert ≤30 min before entry") so it's implicitly correct.  
**Fix**: Optionally add `attribution_window_minutes?: number` to `AttributionData` for display purposes.

---

## Contract: /api/analytics/pnl-attribution — param name

**Frontend file**: `src/components/analytics/AttributionCard.tsx:26`  
**Backend file**: `backend/app/api/analytics.py:2218`  
**Status**: CORRECT  
**Finding**: Frontend sends `{ params: { days_back: days } }`. Backend declares `days_back: int = Query(default=90)`. Names match.  
**Frontend expects**: `days_back` query param  
**Backend returns**: Accepts `days_back`  
**Impact**: None.  
**Fix**: None needed.

---

## Contract: /api/analytics/pnl-percent — param name

**Frontend file**: `src/components/analytics/PnlPercentTab.tsx:113`  
**Backend file**: `backend/app/api/analytics.py` (pnl-percent endpoint)  
**Status**: CORRECT  
**Finding**: Frontend sends `{ params: { days_back: days } }`. Backend accepts `days_back`. Match.  
**Impact**: None.  
**Fix**: None needed.

---

## Contract: /api/analytics/btst — redundant broker_account_id param

**Frontend file**: `src/components/analytics/BtstTab.tsx:54`  
**Backend file**: `backend/app/api/analytics.py` (btst endpoint)  
**Status**: MISMATCH (harmless)  
**Finding**: Frontend sends `{ params: { days, broker_account_id: account.id } }`. Backend gets `broker_account_id` from JWT via `Depends(get_verified_broker_account_id)` — the query param is ignored entirely. Sending it in the URL is harmless but misleading; it could also leak account ID in server logs or browser history.  
**Frontend expects**: Backend uses the `broker_account_id` from query  
**Backend returns**: Ignores query param, uses JWT  
**Impact**: Low — no functional impact. Minor security concern: account ID exposed in URL query string.  
**Fix**: Remove `broker_account_id: account.id` from the BtstTab query params.

---

## Contract: /api/analytics/overview — param name

**Frontend file**: `src/components/analytics/SummaryTab.tsx`  
**Backend file**: `backend/app/api/analytics.py` (overview endpoint)  
**Status**: CORRECT  
**Finding**: Frontend sends `{ params: { days } }`. Backend accepts `days` param. Match.  
**Impact**: None.  
**Fix**: None needed.

---

## Contract: /api/analytics/performance — PerfData type completeness

**Frontend file**: `src/components/analytics/SummaryTab.tsx` (`PerfData` interface)  
**Backend file**: `backend/app/api/analytics.py` (performance endpoint)  
**Status**: MISMATCH (harmless — extra backend fields ignored)  
**Finding**: Backend `/api/analytics/performance` returns `{ has_data, period_days, total_trades, by_instrument, by_direction, by_product, by_hour, by_day_of_week, size_analysis }`. Frontend `PerfData` interface declares only `{ has_data, by_instrument, by_product, by_hour }` — it is missing `by_direction`, `by_day_of_week`, `size_analysis`, `total_trades`, `period_days`.  
**Frontend expects**: 4 fields  
**Backend returns**: 9 fields  
**Impact**: None — TypeScript will accept the extra fields at runtime (structural typing). The missing fields are simply not used in the UI, but represent analytics that could be displayed.  
**Fix**: Optional — add missing fields to `PerfData` interface and consider adding UI panels for `by_day_of_week` and `size_analysis`.

---

## Contract: /api/analytics/critical-trades — flag_reasons vs reasons

**Frontend file**: `src/components/analytics/PatternsTab.tsx:183-186`, `src/components/analytics/TradesTab.tsx`  
**Backend file**: `backend/app/api/analytics.py` (critical-trades endpoint)  
**Status**: CORRECT (resolved at consumption point)  
**Finding**: Backend `critical-trades` returns trade objects with field `reasons: list`. Frontend `FlaggedTrade` interface in PatternsTab.tsx declares `flag_reasons: { type, label }[]`. This looks like a name mismatch. However: TradesTab.tsx (which fetches critical-trades) builds a `qualityMap` and a `flagMap` by reading `ct.reasons` directly, then passes it to PatternsTab as the `flagged` prop under the `flag_reasons` key after transformation. PatternsTab.tsx receives pre-mapped data — it never calls the API directly for critical trades data.  
**Frontend expects**: `flag_reasons` in the component prop  
**Backend returns**: `reasons` in the API response  
**Impact**: None — TradesTab transforms `reasons` → `flag_reasons` before passing to PatternsTab.  
**Fix**: None needed functionally. Add a comment in PatternsTab noting that data comes pre-transformed from TradesTab.

---

## Contract: /api/analytics/discipline-summary

**Frontend file**: `src/pages/Discipline.tsx` (`DisciplineData` interface)  
**Backend file**: `backend/app/api/analytics.py:2955` (discipline-summary endpoint)  
**Status**: CORRECT  
**Finding**: Frontend `DisciplineData` interface and backend response both include `{ has_data, score, max_score, week_start, danger_alerts, caution_alerts, trades_this_week, revenge_free_days, weekly_trend, breakdown: { alerts_score, quality_score } }`. All field names match.  
**Frontend expects**: `DisciplineData`  
**Backend returns**: Matching dict  
**Impact**: None.  
**Fix**: None needed.

---

## Contract: /api/analytics/quality-breakdown — per_trade shape

**Frontend file**: `src/components/analytics/TradesTab.tsx`  
**Backend file**: `backend/app/api/analytics.py:2924-2943`  
**Status**: CORRECT  
**Finding**: TradesTab reads `qualityRes.value.data.per_trade` as an array of `{ trade_id, score, tier }`. Backend returns exactly this shape in `per_trade`.  
**Frontend expects**: `per_trade: [{ trade_id: string, score: number, tier: string }]`  
**Backend returns**: Same  
**Impact**: None.  
**Fix**: None needed.

---

## Contract: RiskAlertResponse — pattern_name and timestamp aliases

**Frontend file**: `src/types/api.ts:123-140` (`Alert` interface)  
**Backend file**: `backend/app/schemas/risk_alert.py`  
**Status**: CORRECT  
**Finding**: Frontend `Alert` interface reads `pattern_name` (primary) and `timestamp` (primary). Backend `RiskAlertResponse` exposes both `pattern_name` (computed_field alias for `pattern_type`) and `timestamp` (computed_field alias for `detected_at`), plus the originals. All four fields are available.  
**Frontend expects**: `pattern_name`, `timestamp`, optionally `pattern_type`, `detected_at`  
**Backend returns**: All four  
**Impact**: None.  
**Fix**: None needed.

---

## Contract: /api/zerodha/connect — login_url field

**Frontend file**: `src/contexts/BrokerContext.tsx`  
**Backend file**: `backend/app/api/zerodha.py`  
**Status**: CORRECT  
**Finding**: Frontend reads `response.data.login_url`. Backend `GET /api/zerodha/connect` returns `{ login_url: str }`.  
**Frontend expects**: `{ login_url: string }`  
**Backend returns**: `{ login_url: string }`  
**Impact**: None.  
**Fix**: None needed.

---

## Contract: WebSocket messages — alert events

**Frontend file**: `src/contexts/AlertContext.tsx`  
**Backend file**: `backend/app/api/websocket.py`  
**Status**: PARTIALLY VERIFIED  
**Finding**: AlertContext listens for WebSocket messages where `data.type === 'alert'` and reads `data.data` as an alert object. Backend `manager.push_behavioral_event()` and alert push mechanisms broadcast to the WebSocket. The exact message envelope format `{ type: 'alert', data: { ... } }` is expected by AlertContext. Full WebSocket event type audit not completed in this pass.  
**Frontend expects**: `{ type: 'alert', data: BackendAlert }`  
**Backend returns**: Depends on `push_behavioral_event` implementation  
**Impact**: If the WS message envelope format doesn't match, new alerts won't show as toasts. The existing alert fetch on page load is a safe fallback.  
**Fix**: Audit `backend/app/api/websocket.py:push_behavioral_event()` to confirm it sends `{ type: 'alert', data: { id, pattern_type, severity, message, detected_at, ... } }`.

---

## Contract: /api/profile/ — capital field for AlertContext

**Frontend file**: `src/contexts/AlertContext.tsx`  
**Backend file**: `backend/app/api/profile.py` (or similar)  
**Status**: PARTIALLY VERIFIED  
**Finding**: AlertContext calls `GET /api/profile/` and reads `profileRes.data.trading_capital` to determine daily loss threshold for behavioral context. If `trading_capital` is null/missing, it falls back to margins data. Not fully audited here.  
**Frontend expects**: `{ trading_capital: number | null }`  
**Backend returns**: Unknown without full profile schema audit  
**Impact**: If `trading_capital` is absent from the profile response, capital-based alerts will always use the margins fallback, which may be less accurate.  
**Fix**: Audit `backend/app/schemas/profile.py` to confirm `trading_capital` is included in the profile GET response.

---

## Contract: /api/analytics/instrument — param names

**Frontend file**: `src/components/analytics/InstrumentPanel.tsx`  
**Backend file**: `backend/app/api/analytics.py` (instrument endpoint)  
**Status**: CORRECT  
**Finding**: Frontend sends `{ params: { underlying, days } }`. Backend accepts `underlying: str` and `days: int`. Match.  
**Impact**: None.  
**Fix**: None needed.

---

## Summary of Findings

| # | Endpoint / Contract | Status | Severity |
|---|---|---|---|
| 1 | `/api/analytics/dashboard-stats` response shape | BROKEN | High — endpoint is orphaned; `DashboardStats` type never satisfied |
| 2 | `/api/analytics/unrealized-pnl` field names | MISMATCH | Medium — `unrealized_pnl` vs `total_unrealized`, `positions_count` missing |
| 3 | `RiskState.status_message` + `last_updated` in api.ts | MISMATCH | Low — handled client-side, type is inaccurate |
| 4 | `Alert.acknowledged` boolean missing from backend | MISMATCH | Low — AlertContext fallback covers it |
| 5 | `Position.current_value` not in backend schema | MISMATCH | Low — computed at fetch boundary in Dashboard |
| 6 | `has_more` stripped by `response_model` on `/api/trades/` | MISMATCH | Low — client-side workaround works |
| 7 | `CompletedTrade.pnl_pct` absent from frontend type | MISMATCH | Low — field ignored |
| 8 | `CompletedTrade.entry_time/exit_time` non-optional in frontend | MISMATCH | Medium — runtime TypeError risk on null timestamps |
| 9 | `CompletedTrade.created_at` non-optional in frontend | MISMATCH | Low — not rendered |
| 10 | `/sync/all` result shape consumed via optional chaining | CORRECT | — |
| 11 | `/api/zerodha/accounts` shape | CORRECT | — |
| 12 | Auth exchange `{ token, broker_account_id }` | CORRECT | — |
| 13 | `/api/risk/alerts` envelope | CORRECT | — |
| 14 | `/api/shield/summary` — ShieldSummary | CORRECT | — |
| 15 | `/api/shield/timeline` — ShieldTimelineItem | CORRECT | — |
| 16 | `/api/shield/patterns` — PatternBreakdown | CORRECT | — |
| 17 | `/api/danger-zone/status` — DangerZoneStatus | CORRECT | — |
| 18 | `/api/danger-zone/summary` — cooldown_history_7d | PARTIALLY VERIFIED | Medium — cooldown_service shape not audited |
| 19 | `/api/analytics/pnl-attribution` extra field | MISMATCH | None — harmless |
| 20 | BtstTab sends redundant `broker_account_id` in query | MISMATCH | Low — harmless, minor security concern |
| 21 | `/api/analytics/performance` PerfData missing fields | MISMATCH | None — extra fields ignored |
| 22 | `critical-trades` reasons → flag_reasons transformation | CORRECT | — |
| 23 | `/api/analytics/discipline-summary` | CORRECT | — |
| 24 | `/api/analytics/quality-breakdown` per_trade | CORRECT | — |
| 25 | WebSocket alert message envelope | PARTIALLY VERIFIED | Medium — needs websocket.py audit |

### Priority Fixes (by impact)

**P0 — Fix immediately:**
- Finding #8: `entry_time/exit_time` in `CompletedTrade` must be `string | null` with null guards — current type is wrong and will crash on real data where timestamps are missing.

**P1 — Fix soon:**
- Finding #1: `/api/analytics/dashboard-stats` is effectively dead. Either rewrite to serve the fields the type declares, or remove the `DashboardStats` type and guestMode mock entry.
- Finding #2: `/api/analytics/unrealized-pnl` field mismatch will silently return `undefined` for any component using it.

**P2 — Fix when convenient:**
- Finding #4: Add `acknowledged: bool` computed field to `RiskAlertResponse` to make contract explicit.
- Finding #5: Add `current_value` as computed field to `PositionResponse`.
- Finding #6: Add `has_more` to `TradeListResponse` schema.
- Finding #3: Clean up `RiskState` interface to match backend reality.
- Finding #20: Remove `broker_account_id` from BtstTab query params.

**Needs follow-up audit:**
- `cooldown_service.get_cooldown_history()` return shape vs `CooldownRecord` interface
- `backend/app/api/websocket.py` — confirm alert push message envelope format
- `backend/app/api/profile.py` — confirm `trading_capital` in GET response
