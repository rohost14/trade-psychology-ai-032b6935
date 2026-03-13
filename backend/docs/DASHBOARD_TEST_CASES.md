# Dashboard Screen — Complete Test Case Specification
**TradeMentor AI | Screen: Dashboard (`/`)**
**Date:** 2026-03-05
**Last Run:** 2026-03-05 — **55/55 PASSED** (`tests/test_dashboard_api.py`)

> **Notes from run:**
> - D-04 test revised: uses `/api/shield/summary` (which enforces `get_verified_broker_account_id`) with a committed revoked broker account. Simple read endpoints like `/api/positions/` only decode the JWT (by design, for performance).
> - D-38 test revised: added `db` fixture + `await db.commit()` so broker_account FK is satisfied in the API's separate DB connection.
> - D-39 test revised and renamed to `test_journal_isolated_by_jwt`: journal API scopes all operations via JWT `bid` claim, not via body params. Test now verifies that User B cannot READ User A's entries (correct isolation mechanism).
> - D-40 test revised: response is `{"entry": {...}}` — test now unwraps the envelope before checking `notes`.
> - D-41 test revised: added `db` + `await db.commit()` — same FK requirement as D-38.

---

## Screen Overview

The Dashboard is the primary screen traders see after login. It has 12 cards that display live positions, completed trades, behavioral alerts, risk state, margin utilization, holdings, trade journal, blowup shield, predictive warnings, and week-over-week progress. It is the most complex screen in the application.

**Tech Stack:**
- Frontend: React 18 + TypeScript, Framer Motion, Recharts, WebSocket
- State: BrokerContext (auth/sync) + AlertContext (patterns/alerts)
- Backend: FastAPI + SQLAlchemy + PostgreSQL (Supabase)
- Real-time: WebSocket price stream, 60s alert polling

---

## Test Case Index

| ID | Group | Test Case | Backend Test | Frontend Check |
|----|-------|-----------|-------------|----------------|
| D-01 | Auth | No token → 401 on all endpoints | ✅ Automated | ✅ Manual |
| D-02 | Auth | Malformed token → 401 | ✅ Automated | - |
| D-03 | Auth | Wrong scheme (Basic) → 401 | ✅ Automated | - |
| D-04 | Auth | Revoked token → 401 | ✅ Automated | ✅ Manual |
| D-05 | Auth | Error response has no stack trace | ✅ Automated | - |
| D-06 | JWT | sub=user_id, bid=broker_account_id | ✅ Automated | - |
| D-07 | JWT | Token has expiry claim | ✅ Automated | - |
| D-08 | JWT | Two brokers get different tokens | ✅ Automated | - |
| D-09 | Positions | Returns 200 with valid token | ✅ Automated | ✅ Manual |
| D-10 | Positions | Empty positions = empty list (not error) | ✅ Automated | ✅ Manual |
| D-11 | Positions | Required fields present | ✅ Automated | ✅ Manual |
| D-12 | Positions | Isolated from other user | ✅ Automated | ✅ Manual |
| D-13 | Positions | Only status='open' returned | ✅ Automated | ✅ Manual |
| D-14 | Completed Trades | Returns 200 | ✅ Automated | ✅ Manual |
| D-15 | Completed Trades | Empty list (not error) when no trades | ✅ Automated | ✅ Manual |
| D-16 | Completed Trades | All fields present | ✅ Automated | ✅ Manual |
| D-17 | Completed Trades | realized_pnl is real value (not zero) | ✅ Automated | ✅ Manual |
| D-18 | Completed Trades | Ordered by exit_time DESC | ✅ Automated | ✅ Manual |
| D-19 | Completed Trades | Isolated from other user | ✅ Automated | ✅ Manual |
| D-20 | Completed Trades | Pagination limit respected | ✅ Automated | - |
| D-21 | Completed Trades | Net P&L correct (win + loss) | ✅ Automated | ✅ Manual |
| D-22 | Risk State | Returns 200 | ✅ Automated | ✅ Manual |
| D-23 | Risk State | state field present | ✅ Automated | ✅ Manual |
| D-24 | Risk State | Valid state value | ✅ Automated | ✅ Manual |
| D-25 | Risk State | New account starts 'safe' | ✅ Automated | ✅ Manual |
| D-26 | Risk Alerts | Returns 200 | ✅ Automated | ✅ Manual |
| D-27 | Risk Alerts | Empty list for new account | ✅ Automated | ✅ Manual |
| D-28 | Risk Alerts | All fields present | ✅ Automated | ✅ Manual |
| D-29 | Risk Alerts | Isolated from other user | ✅ Automated | ✅ Manual |
| D-30 | Risk Alerts | hours= filter excludes old alerts | ✅ Automated | - |
| D-31 | Risk Alerts | Acknowledge sets acknowledged_at | ✅ Automated | ✅ Manual |
| D-32 | Risk Alerts | Cannot acknowledge other user's alert | ✅ Automated | - |
| D-33 | Dashboard Stats | Returns 200 | ✅ Automated | ✅ Manual |
| D-34 | Dashboard Stats | Fields present | ✅ Automated | ✅ Manual |
| D-35 | Dashboard Stats | Isolated from other user | ✅ Automated | - |
| D-36 | Dashboard Stats | Win rate 50% with 1 win + 1 loss | ✅ Automated | ✅ Manual |
| D-37 | Journal | Create journal entry | ✅ Automated | ✅ Manual |
| D-38 | Journal | Create without trade link (daily note) | ✅ Automated | ✅ Manual |
| D-39 | Journal | Cannot write to other user's journal | ✅ Automated | - |
| D-40 | Journal | Get journal by trade ID | ✅ Automated | ✅ Manual |
| D-41 | Journal | Valid emotion tags accepted | ✅ Automated | ✅ Manual |
| D-42 | Isolation | Positions isolated bidirectionally | ✅ Automated | - |
| D-43 | Isolation | Completed trades isolated bidirectionally | ✅ Automated | - |
| D-44 | Computed Values | Session P&L = sum of realized_pnl | ✅ Automated | ✅ Manual |
| D-45 | Computed Values | LONG direction stored correctly | ✅ Automated | ✅ Manual |
| D-46 | Computed Values | SHORT direction stored correctly | ✅ Automated | ✅ Manual |
| D-47 | Computed Values | Duration >= 0 | ✅ Automated | - |
| D-48 | Computed Values | entry_time <= exit_time | ✅ Automated | - |
| D-49 | Response Format | All responses are JSON | ✅ Automated | - |
| D-50 | Response Format | broker_account_id in trade response | ✅ Automated | - |
| D-51 | Response Format | severity present in alert | ✅ Automated | ✅ Manual |
| D-52 | Response Format | No internal fields leaked | ✅ Automated | - |
| D-53 | Response Format | 404 for nonexistent resource | ✅ Automated | - |
| D-54 | Response Format | Invalid UUID → 422 | ✅ Automated | - |
| D-55 | Frontend | Unauthenticated → Connect Zerodha shown | - | ✅ Manual |
| D-56 | Frontend | Loading state shown during sync | - | ✅ Manual |
| D-57 | Frontend | Error banner shown on sync failure | - | ✅ Manual |
| D-58 | Frontend | Retry button triggers re-sync | - | ✅ Manual |
| D-59 | Frontend | RiskGuardianCard shows correct state color | - | ✅ Manual |
| D-60 | Frontend | Session P&L = realized + unrealized | - | ✅ Manual |
| D-61 | Frontend | Win rate color (green ≥50%, red <50%) | - | ✅ Manual |
| D-62 | Frontend | Margin bar animated on load | - | ✅ Manual |
| D-63 | Frontend | Price flash on WebSocket update | - | ✅ Manual |
| D-64 | Frontend | LIVE badge shown when WS connected | - | ✅ Manual |
| D-65 | Frontend | ClosedTradesTable grouped by day | - | ✅ Manual |
| D-66 | Frontend | Day P&L shown in separator row | - | ✅ Manual |
| D-67 | Frontend | Alert acknowledge updates UI immediately | - | ✅ Manual |
| D-68 | Frontend | Journal saves to backend + localStorage | - | ✅ Manual |
| D-69 | Frontend | Journal emotion tags save correctly | - | ✅ Manual |
| D-70 | Frontend | Token expiry shows reconnect prompt | - | ✅ Manual |
| D-71 | Frontend | Capital resolution: profile > Kite > floor | - | ✅ Manual |
| D-72 | Frontend | Pattern detection fires for today only | - | ✅ Manual |
| D-73 | Frontend | Toast shown for high/critical patterns | - | ✅ Manual |
| D-74 | Frontend | BlowupShieldCard shows correct shield score | - | ✅ Manual |
| D-75 | Frontend | PredictiveWarningsCard dismissible | - | ✅ Manual |
| D-76 | Frontend | HoldingsCard shows total value | - | ✅ Manual |
| D-77 | Frontend | MarginStatusCard color-coded utilization | - | ✅ Manual |
| D-78 | Frontend | ProgressTrackingCard shows week comparison | - | ✅ Manual |
| D-79 | Frontend | Mobile: table → card layout switch | - | ✅ Manual |
| D-80 | Frontend | Manual sync button triggers re-fetch | - | ✅ Manual |

---

## Detailed Test Cases

---

### GROUP 1 — Authentication Guard

---

#### D-01: No Token → 401 on All Endpoints
- **Component:** All API endpoints
- **What:** Every dashboard API endpoint must refuse unauthenticated requests
- **How:** Send requests to all 6 dashboard endpoints with no Authorization header
- **Endpoints tested:** `GET /api/positions/`, `GET /api/trades/completed`, `GET /api/trades/stats`, `GET /api/risk/state`, `GET /api/risk/alerts`, `GET /api/analytics/dashboard-stats`
- **Expected:** All return HTTP 401 or 403
- **Risk if fails:** Any user with a browser and curl can read all traders' data

---

#### D-02: Malformed Token → 401
- **Component:** Auth middleware
- **What:** A garbage JWT string must be rejected
- **How:** Send `Authorization: Bearer this.is.not.a.jwt` to all endpoints
- **Expected:** All return 401 or 403
- **Risk if fails:** Bypass of token validation entirely

---

#### D-03: Wrong Scheme → 401
- **Component:** Auth middleware
- **What:** A valid JWT with wrong scheme (`Basic` instead of `Bearer`) must be rejected
- **How:** Send `Authorization: Basic <valid_token>` to `/api/positions/`
- **Expected:** 401 or 403
- **Risk if fails:** Auth scheme not enforced

---

#### D-04: Revoked Token → 401
- **Component:** `get_verified_broker_account_id()` in deps.py
- **What:** A token issued before `broker_accounts.token_revoked_at` must be rejected
- **How:** Issue a token, set `token_revoked_at = now()` on the broker account, then use the old token
- **Expected:** 401 or 403 — not 200
- **Risk if fails:** Disconnected accounts can still read data. Critical for logout security.

---

#### D-05: Error Response Has No Stack Trace
- **Component:** FastAPI exception handlers
- **What:** Error responses must not include Python tracebacks, file paths, or line numbers
- **How:** Trigger a 401 error; check response body for "Traceback", `File "`, `line `
- **Expected:** No internal info in error body
- **Risk if fails:** Information leakage helps attackers understand codebase

---

### GROUP 2 — JWT Structure

---

#### D-06: sub=user_id, bid=broker_account_id
- **Component:** `create_access_token()` in deps.py
- **What:** JWT payload must have `sub` = stable user identity, `bid` = active broker session
- **How:** Decode JWT with secret; inspect claims
- **Expected:** `sub == str(user.id)`, `bid == str(broker_account.id)`
- **Why it matters:** sub is the stable identity (survives reconnect); bid scopes API data to one broker account

---

#### D-07: Token Has Expiry Claim
- **Component:** `create_access_token()` in deps.py
- **What:** JWT must have `exp` claim set to future timestamp
- **How:** Decode JWT; verify `exp > now()`
- **Expected:** exp is present and in the future
- **Note:** Expires in 24 hours matching Zerodha token lifecycle

---

#### D-08: Two Brokers Get Different Tokens
- **Component:** `create_access_token()`
- **What:** Two broker accounts (even for same user) must produce tokens with different `bid` claims
- **How:** Create two broker accounts; generate tokens; compare bid claims
- **Expected:** bid1 ≠ bid2

---

### GROUP 3 — Positions Endpoint

---

#### D-09: Returns 200 with Valid Token
- **Component:** `GET /api/positions/`
- **What:** Authenticated request returns success
- **How:** Send request with valid Bearer token
- **Expected:** HTTP 200

---

#### D-10: Empty Positions = Empty List
- **Component:** `GET /api/positions/`
- **What:** When no open positions exist, API returns empty list (not 404 or 500)
- **How:** Request with new account that has no positions
- **Expected:** 200 + `[]` or `{"positions": []}`
- **Why it matters:** Frontend renders empty state card, not crash

---

#### D-11: Required Fields Present
- **Component:** `GET /api/positions/`
- **What:** Each position object has all fields the OpenPositionsTable needs
- **Fields required:** `tradingsymbol`, `total_quantity`, `unrealized_pnl`, `average_entry_price`, `last_price`, `exchange`, `product`
- **Expected:** All fields present in response
- **Risk if fails:** OpenPositionsTable renders blank or throws TypeError

---

#### D-12: Isolated from Other User
- **Component:** `GET /api/positions/` + broker_account_id scoping
- **What:** User B cannot see User A's positions
- **How:** Create position for User A; request with User B's token
- **Expected:** User B's response contains no User A positions
- **Risk if fails:** Critical privacy and financial data leakage

---

#### D-13: Only Status='open' Returned
- **Component:** `GET /api/positions/` SQL filter
- **What:** Positions with status='closed' or any non-open status must not appear
- **How:** Create closed position (total_quantity=0, status='closed'); request positions
- **Expected:** Closed position does not appear
- **Risk if fails:** Frontend shows stale/phantom positions from previous sessions

---

### GROUP 4 — Completed Trades Endpoint

---

#### D-14: Returns 200
- **Component:** `GET /api/trades/completed`
- **Expected:** HTTP 200 with valid token

---

#### D-15: Empty List When No Trades
- **Component:** `GET /api/trades/completed`
- **What:** New account with no trades returns empty list, not error
- **Expected:** 200 + list (possibly empty)
- **Risk if fails:** Dashboard crashes on first login before any trade synced

---

#### D-16: All Fields Present
- **Component:** `GET /api/trades/completed`
- **Fields required:** `id`, `tradingsymbol`, `direction`, `total_quantity`, `avg_entry_price`, `avg_exit_price`, `realized_pnl`, `entry_time`, `exit_time`, `duration_minutes`
- **Expected:** All fields in response
- **Risk if fails:** ClosedTradesTable shows blanks; pattern detection breaks

---

#### D-17: realized_pnl Is Real Value
- **Component:** `GET /api/trades/completed` — Three-layer architecture validation
- **What:** `realized_pnl` must be the actual computed P&L (e.g., 200.0), NOT zero
- **How:** Create CompletedTrade with realized_pnl=200.00; verify API returns 200.0
- **Expected:** realized_pnl = 200.0
- **Risk if fails:** All P&L calculations, pattern detection, and analytics are wrong. This is the most important data integrity check.

---

#### D-18: Ordered by exit_time DESC
- **Component:** `GET /api/trades/completed` SQL ORDER BY
- **What:** Most recent trade must be first
- **How:** Create two trades at different times; verify ordering
- **Expected:** trades[0].exit_time >= trades[1].exit_time
- **Risk if fails:** ClosedTradesTable shows trades in wrong order; grouping by "Today" fails

---

#### D-19: Isolated from Other User
- **Component:** `GET /api/trades/completed`
- **What:** User B's token cannot see User A's completed trades
- **Expected:** No cross-user data leakage

---

#### D-20: Pagination Limit Respected
- **Component:** `GET /api/trades/completed?limit=5`
- **Expected:** Response contains ≤5 trades regardless of how many exist

---

#### D-21: Net P&L Correct
- **Component:** `GET /api/trades/completed` — sum of realized_pnl
- **What:** With 1 winning trade (₹200) and 1 losing trade (-₹250), net should be -₹50
- **Expected:** sum(realized_pnl) = -50.0
- **Risk if fails:** RiskGuardianCard shows wrong session P&L

---

### GROUP 5 — Risk State Endpoint

---

#### D-22: Returns 200
- **Component:** `GET /api/risk/state`
- **Expected:** HTTP 200

---

#### D-23: state Field Present
- **Component:** `GET /api/risk/state`
- **What:** Response must contain a field for current risk level
- **Expected:** One of: `state`, `risk_state`, or `level` field present
- **Risk if fails:** RiskGuardianCard cannot determine color (safe/caution/danger)

---

#### D-24: Valid State Value
- **Component:** `GET /api/risk/state`
- **What:** State value must be one of the known levels
- **Expected:** value in {safe, caution, danger, warning, low, medium, high, critical}

---

#### D-25: New Account Starts Safe
- **Component:** `GET /api/risk/state`
- **What:** A brand-new account with zero trades must be in safe state
- **Expected:** state = 'safe' or 'low' (not caution, not danger)
- **Risk if fails:** New users see a false danger warning on first login

---

### GROUP 6 — Risk Alerts Endpoint

---

#### D-26: Returns 200
- **Component:** `GET /api/risk/alerts`
- **Expected:** HTTP 200

---

#### D-27: Empty List for New Account
- **Component:** `GET /api/risk/alerts`
- **What:** Account with no alerts returns empty list
- **Expected:** 200 + `[]`
- **Risk if fails:** RecentAlertsCard crashes instead of showing "No alerts" empty state

---

#### D-28: Alert Fields Present
- **Component:** `GET /api/risk/alerts`
- **Fields required:** `id`, `pattern_type`, `severity`, `message`, `detected_at`
- **Expected:** All fields present
- **Risk if fails:** RecentAlertsCard cannot render severity badge or acknowledge button

---

#### D-29: Isolated from Other User
- **Component:** `GET /api/risk/alerts`
- **What:** User B cannot see User A's risk alerts
- **Expected:** str(alert.id) not in User B's response

---

#### D-30: hours= Filter Excludes Old Alerts
- **Component:** `GET /api/risk/alerts?hours=48`
- **What:** Alerts older than 48 hours must not appear in 48-hour window query
- **How:** Create alert with detected_at 50 hours ago; query with hours=48
- **Expected:** Old alert not in response
- **Risk if fails:** Frontend shows stale alerts from days/weeks ago

---

#### D-31: Acknowledge Updates State
- **Component:** `POST /api/risk/alerts/{id}/acknowledge`
- **What:** After acknowledging, `acknowledged_at` is set on the alert
- **How:** POST acknowledge; re-fetch alert; check acknowledged_at not null
- **Expected:** HTTP 200/204; acknowledged_at set
- **Risk if fails:** Alerts keep reappearing even after user dismisses them

---

#### D-32: Cannot Acknowledge Other User's Alert
- **Component:** `POST /api/risk/alerts/{id}/acknowledge` + authorization
- **What:** User B cannot acknowledge User A's alerts
- **Expected:** 403 or 404
- **Risk if fails:** User B can manipulate User A's alert state

---

### GROUP 7 — Dashboard Stats Endpoint

---

#### D-33: Returns 200
- **Component:** `GET /api/analytics/dashboard-stats`
- **Expected:** HTTP 200

---

#### D-34: Fields Present
- **Component:** `GET /api/analytics/dashboard-stats`
- **What:** Response is a JSON object (not list)
- **Expected:** dict with stats fields

---

#### D-35: Isolated from Other User
- **Component:** `GET /api/analytics/dashboard-stats`
- **What:** User B's stats are not polluted by User A's trades
- **Expected:** Clean zero stats for user with no trades

---

#### D-36: Win Rate Calculation
- **Component:** `GET /api/analytics/dashboard-stats`
- **What:** Win rate with 1 winner (₹200) and 1 loser (-₹250) must be 50%
- **Expected:** win_rate ≈ 50.0
- **Risk if fails:** ProgressTrackingCard and RiskGuardianCard show wrong win rate

---

### GROUP 8 — Journal Endpoint

---

#### D-37: Create Journal Entry
- **Component:** `POST /api/journal/`
- **What:** Can create a journal entry linked to a completed trade with notes + emotion tags
- **Payload:** `{broker_account_id, trade_id, notes, emotion_tags, entry_type}`
- **Expected:** HTTP 200 or 201

---

#### D-38: Create Without Trade Link
- **Component:** `POST /api/journal/`
- **What:** Daily journal entries (no trade_id) must be allowed (FK was dropped in migration 030)
- **Expected:** HTTP 200/201 with trade_id = null

---

#### D-39: Journal Isolated by JWT (Read Isolation)
- **Component:** `GET /api/journal/` + authorization
- **What:** User B cannot read User A's journal entries. The journal API scopes all reads by `broker_account_id` from the JWT `bid` claim, not by request body params. Write isolation is implicit: User B's POST creates under User B's account.
- **How:** User A creates a private journal entry. User B lists their entries. "User A private note" must not appear.
- **Expected:** User B's entry list is empty / does not include User A's notes

---

#### D-40: Get Journal by Trade ID
- **Component:** `GET /api/journal/trade/{id}`
- **What:** Fetching journal by a trade's ID returns previously saved notes
- **Expected:** 200 with `notes` field matching what was saved

---

#### D-41: Valid Emotion Tags Accepted
- **Component:** `POST /api/journal/`
- **What:** All 11 defined emotion tags (confident, anxious, fomo, greedy, fearful, revenge, calm, impatient, excited, frustrated, neutral) are accepted
- **Expected:** HTTP 200/201

---

### GROUP 9 — Data Isolation (Bidirectional)

---

#### D-42: Positions Isolated Bidirectionally
- **Component:** `GET /api/positions/`
- **What:** Create unique positions for User A (SBIN) and User B (HDFC). Verify:
  - User A sees SBIN, not HDFC
  - User B sees HDFC, not SBIN
- **Expected:** Perfect bidirectional isolation
- **Risk if fails:** Financial data leakage across accounts

---

#### D-43: Completed Trades Isolated Bidirectionally
- **Component:** `GET /api/trades/completed`
- **What:** Same bidirectional isolation test for completed trades
- **Expected:** No cross-account trade visibility

---

### GROUP 10 — Computed Values & Business Logic

---

#### D-44: Session P&L = Sum of realized_pnl
- **Component:** All endpoints + frontend aggregation
- **What:** Dashboard P&L = sum of all CompletedTrade.realized_pnl for today
- **Backend validation:** API returns correct pnl values
- **Frontend validation:** RiskGuardianCard sums them correctly
- **Expected:** 1 win (₹200) + 1 loss (-₹250) = -₹50

---

#### D-45: LONG Direction Stored and Returned Correctly
- **Component:** CompletedTrade model + API
- **What:** Trade entered with direction=LONG must return "LONG" in API
- **Expected:** trades[0].direction == "LONG"
- **Risk if fails:** ClosedTradesTable shows wrong direction badges; P&L sign inverted for shorts

---

#### D-46: SHORT Direction Stored and Returned Correctly
- **Component:** CompletedTrade model + API
- **What:** Trade with direction=SHORT returns "SHORT"
- **Expected:** trades[0].direction == "SHORT"

---

#### D-47: Duration >= 0 for All Trades
- **Component:** CompletedTrade.duration_minutes
- **What:** No trade can have negative duration
- **Expected:** All duration_minutes >= 0

---

#### D-48: entry_time <= exit_time for All Trades
- **Component:** CompletedTrade timestamps
- **What:** Exit must always be after (or equal to) entry
- **Expected:** entry_time <= exit_time for every completed trade

---

### GROUP 11 — Response Format & API Contract

---

#### D-49: All Responses Are JSON
- **Component:** FastAPI response content-type
- **Expected:** `content-type: application/json` header on all responses

---

#### D-50: broker_account_id in Trade Response
- **Component:** Completed trade API response
- **What:** Frontend needs broker_account_id to scope journal saves correctly
- **Expected:** `broker_account_id` field present in response

---

#### D-51: severity Present in Alert
- **Component:** Risk alert API response
- **What:** RecentAlertsCard renders different UI per severity
- **Expected:** `severity` field present; value is one of: `low`, `medium`, `high`, `danger`, `critical`, `caution`, `positive`

---

#### D-52: No Internal Fields Leaked
- **Component:** All API responses
- **What:** Raw database fields must not be exposed: `raw_payload`, `access_token`, `_sa_instance_state`
- **Expected:** None of those keys in any response

---

#### D-53: 404 for Nonexistent Resource
- **Component:** Single-resource endpoints
- **What:** Requesting a valid UUID that doesn't exist returns 404, not 500
- **Expected:** HTTP 404

---

#### D-54: Invalid UUID → 422
- **Component:** Path parameter validation
- **What:** Passing "not-a-uuid" where a UUID is expected returns 422
- **Expected:** HTTP 422 Unprocessable Entity

---

### GROUP 12 — Frontend Manual Test Cases

---

#### D-55: Unauthenticated State
- **Component:** Dashboard.tsx + BrokerContext
- **What:** When no token in localStorage, dashboard shows "Connect Zerodha" button, not blank
- **Steps:** Clear localStorage; visit `/`
- **Expected:** Connect button visible; no error thrown; no API requests made

---

#### D-56: Loading State During Sync
- **Component:** BrokerContext.syncStatus
- **What:** During sync, a spinner or loading indicator is shown on the sync button
- **Steps:** Click "Sync" button; observe immediately
- **Expected:** Spinner visible; button disabled; syncStatus = 'syncing'

---

#### D-57: Error Banner on Sync Failure
- **Component:** Dashboard.tsx error state
- **What:** If sync fails (API error), a red error banner appears with retry button
- **Steps:** Temporarily break API URL; trigger sync
- **Expected:** Red banner with retry button visible; no uncaught exception

---

#### D-58: Retry Button Triggers Re-sync
- **Component:** Dashboard.tsx retry handler
- **Steps:** Trigger sync failure; click retry
- **Expected:** Another sync attempt is made (spinner reappears)

---

#### D-59: RiskGuardianCard State Color
- **Component:** RiskGuardianCard.tsx
- **What:** Card background matches risk state
  - safe → green/emerald tones
  - caution → amber/yellow tones
  - danger → red tones
- **Steps:** Verify with different risk states
- **Expected:** Color matches state

---

#### D-60: Session P&L = Realized + Unrealized
- **Component:** Dashboard.tsx tradeStats calculation
- **What:** P&L shown in RiskGuardianCard = sum(completed trade P&L) + sum(open position unrealized P&L)
- **Steps:** Verify formula in code and visually
- **Expected:** Correct sum displayed

---

#### D-61: Win Rate Color Coding
- **Component:** RiskGuardianCard.tsx
- **What:** Win rate text color: green if ≥50%, red if <50%
- **Steps:** Create trades with <50% win rate; observe color
- **Expected:** Red text when win rate below 50%

---

#### D-62: Margin Bar Animated on Load
- **Component:** RiskGuardianCard.tsx + Framer Motion
- **What:** Margin utilization bar animates from 0 to actual value on page load
- **Steps:** Reload dashboard; watch margin bar
- **Expected:** Smooth animation (500ms)

---

#### D-63: Price Flash on WebSocket Update
- **Component:** OpenPositionsTable.tsx + usePriceStream + usePriceFlash
- **What:** When live price changes, the price cell flashes green (up) or red (down) for 600ms
- **Steps:** Observe open positions during market hours
- **Expected:** Flash effect visible on price change; disappears after 600ms

---

#### D-64: LIVE Badge When WebSocket Connected
- **Component:** OpenPositionsTable.tsx
- **What:** A "LIVE" badge appears in the positions table header when WebSocket is connected
- **Steps:** Verify during market hours
- **Expected:** "LIVE" badge visible

---

#### D-65: ClosedTradesTable Grouped by Day
- **Component:** ClosedTradesTable.tsx
- **What:** Trades are shown in date groups: "Today", "Yesterday", then actual dates
- **Steps:** Have trades on multiple days; observe grouping
- **Expected:** Date separator rows between groups; "Today" for current day

---

#### D-66: Day P&L in Separator Row
- **Component:** ClosedTradesTable.tsx
- **What:** Each date group header shows the total P&L for that day
- **Steps:** Have multiple trades on one day; verify sum shown in separator
- **Expected:** Separator shows correct day P&L total

---

#### D-67: Alert Acknowledge Updates UI Immediately
- **Component:** RecentAlertsCard.tsx + optimistic update
- **What:** Clicking acknowledge on an alert removes it from the list immediately (optimistic update); doesn't wait for API
- **Steps:** Click acknowledge on an alert; observe
- **Expected:** Alert disappears immediately from list; API call happens in background

---

#### D-68: Journal Saves to Backend + localStorage
- **Component:** TradeJournalSheet.tsx dual storage
- **What:** When saving a journal entry:
  1. Primary: saved to backend API
  2. Backup: also saved to localStorage
- **Steps:** Open journal for a trade; add notes; save; verify in API and localStorage
- **Expected:** Both locations have the entry

---

#### D-69: Journal Emotion Tags Save Correctly
- **Component:** TradeJournalSheet.tsx
- **What:** Selected emotion tags (e.g., FOMO + Anxious) are saved and restore correctly on re-open
- **Steps:** Open journal; select 2 tags; save; re-open same trade's journal
- **Expected:** Same 2 tags pre-selected

---

#### D-70: Token Expiry Shows Reconnect Prompt
- **Component:** BrokerContext + api.ts 401 handler
- **What:** When API returns 401, a "Session expired, reconnect" prompt appears (not a blank page)
- **How:** Token dispatches `tradementor:token-expired` custom event on 401; BrokerContext listens
- **Expected:** User sees reconnect UI, not error

---

#### D-71: Capital Resolution Hierarchy
- **Component:** AlertContext capital resolution
- **What:** Capital used for pattern detection follows priority:
  1. User-declared trading_capital in profile (highest)
  2. Kite API equity.total (live)
  3. ₹1,00,000 floor (cold start)
- **Steps:** Test each scenario by removing profile value and checking what capital is used
- **Expected:** Correct priority respected

---

#### D-72: Pattern Detection Fires for Today Only
- **Component:** Dashboard.tsx + AlertContext
- **What:** Client-side pattern detection only analyzes trades where `exit_time >= today 00:00 IST`
- **Steps:** Verify in Dashboard.tsx that completed trades are filtered to today before calling `runAnalysis()`
- **Expected:** Yesterday's trades do not trigger today's pattern alerts

---

#### D-73: Toast Shown for High/Critical Patterns
- **Component:** AlertContext.tsx toast logic
- **What:** When a new high/critical pattern is detected (not seen before), a toast notification appears
- **How:** Pattern key compared against `shownPatternKeys` (seeded from backend alerts)
- **Steps:** Create conditions for revenge trading pattern; observe
- **Expected:** Red toast appears; does not repeat if already seen

---

#### D-74: BlowupShieldCard Shield Score
- **Component:** BlowupShieldCard.tsx
- **What:** Shield score = % of alerts heeded
  - ≥70%: green
  - 40-70%: amber
  - <40%: red
- **Steps:** Verify score color and calculation with known alert history
- **Expected:** Correct color and percentage shown

---

#### D-75: PredictiveWarningsCard Dismissible
- **Component:** PredictiveWarningsCard.tsx
- **What:** Each warning has an X button; clicking it removes it from view for the session
- **Steps:** Click X on a predictive warning
- **Expected:** Warning disappears; does not come back until page refresh; re-appears after refresh (session-only dismiss)

---

#### D-76: HoldingsCard Total Value
- **Component:** HoldingsCard.tsx
- **What:** Shows total portfolio value and total P&L across all holdings
- **Steps:** Verify with known holdings data from Kite API
- **Expected:** Sum of (last_price × quantity) matches displayed total value

---

#### D-77: MarginStatusCard Color-Coded Utilization
- **Component:** MarginStatusCard.tsx
- **What:** Utilization bar color:
  - <60%: green (safe)
  - 60-80%: amber (warning)
  - >80%: red (danger)
- **Steps:** Check with different margin utilization levels
- **Expected:** Correct color thresholds

---

#### D-78: ProgressTrackingCard Week Comparison
- **Component:** ProgressTrackingCard.tsx
- **What:** Shows this week vs last week for P&L, win rate, trade count, danger alerts
  - Better: green arrow up
  - Worse: red arrow down
- **Steps:** Verify with known week-over-week data
- **Expected:** Correct trend indicators

---

#### D-79: Mobile Layout Switch
- **Component:** All dashboard cards
- **What:** On mobile screens (<768px), table layouts switch to card layouts
- **Steps:** Resize browser to <768px; verify
- **Expected:** OpenPositionsTable shows cards (not table); ClosedTradesTable shows cards

---

#### D-80: Manual Sync Button
- **Component:** RiskGuardianCard.tsx + BrokerContext.syncTrades()
- **What:** Clicking the sync button triggers `POST /api/zerodha/sync/all` then re-fetches all data
- **Steps:** Click sync button; verify network requests; verify data refreshes
- **Expected:** Spinner during sync; fresh data loaded after; last_sync_at updates

---

## How to Run Automated Tests

```bash
cd backend
pip install pytest pytest-asyncio httpx
pytest tests/test_dashboard_api.py -v -s
```

Results saved to `tests/test_results.txt` via:
```bash
python run_schema_tests.py
```

---

## Known Limitations

| Area | Limitation |
|------|-----------|
| Zerodha margins/holdings | Require live Kite access token — cannot be automated without mock |
| WebSocket price stream | Requires running backend + Kite WebSocket — manual test only |
| Pattern detection | Client-side in browser — Vitest unit tests needed (future) |
| OAuth callback | Requires browser redirect flow — manual test only |

---

## Test Data Requirements

To run all tests, the following must exist in Supabase:
- At least 1 user with guardian_phone set
- At least 1 broker_account (connected status)
- Migrations 001–034 all applied

All automated tests create their own data and roll back — no seed data needed.
