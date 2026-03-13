# Session 18 Fixes — Architecture Gaps & Polling Removal

*Documented before implementation. Each fix has problem, root cause, solution, and files affected.*

---

## FIX-01: publish_event() opens a new Redis TCP connection per call

**Problem**
`event_bus.py:74` calls `redis_lib.from_url(settings.REDIS_URL)` inside `publish_event()`.
Every trade webhook creates 3 calls → 3 new TCP connections to Upstash.
At 50+ simultaneous users this hits Upstash's connection limit and adds 20–50ms RTT per call.

**Root cause**
No shared connection pool. Each call creates a fresh connection, uses it, closes it.

**Solution**
Module-level `ConnectionPool` initialized lazily on first call. All subsequent calls borrow
from the pool (max 10 connections). The pool is shared across all Celery workers in the same process.

**Files**
- `backend/app/core/event_bus.py` — add `_sync_pool` + `_get_sync_redis()`, replace `from_url` call

**Risk**: Zero. Pool is backward-compatible; connection semantics identical.

---

## FIX-02: DangerZone.tsx polls every 30 seconds

**Problem**
`src/pages/DangerZone.tsx:98` runs `setInterval(fetchData, 30000)`.
The data on this page (danger level, consecutive losses, daily loss %) only changes when
a trade fills or a risk alert fires — both of which already deliver a WebSocket event.
The 30s poll fires regardless of whether anything changed.

**Root cause**
This page predates the WebSocket event bus. Was written before `lastTradeEvent`/`lastAlertEvent`
were available from `useWebSocket()`.

**Solution**
Remove the `setInterval`. Watch `lastTradeEvent` and `lastAlertEvent` from `useWebSocket()`.
Refetch when either changes. Keep the initial fetch on mount. Keep the manual Refresh button.

**Files**
- `src/pages/DangerZone.tsx`

**Risk**: Zero. Refetch logic is identical; only the trigger changes (event vs timer).

---

## FIX-03: MyPatterns.tsx polls every 30 seconds

**Problem**
Same as FIX-02. `src/pages/MyPatterns.tsx:284` runs `setInterval(fetchStatus, 30000)`.
Page shows danger status + streak + alert history — all of which change only on trade fill or alert.

**Root cause**
Same as FIX-02.

**Solution**
Same pattern: remove setInterval, watch `lastTradeEvent` + `lastAlertEvent`.

**Files**
- `src/pages/MyPatterns.tsx`

**Risk**: Zero.

---

## FIX-04: New broker_account created without a UserProfile

**Problem**
When a user connects Zerodha for the first time, `zerodha.py` creates a `BrokerAccount` and commits.
No `UserProfile` is created at that point. The profile is auto-created lazily when the user first
hits `GET /api/profile/` — which means:
- Risk thresholds (daily_loss_limit, max_position_size) are NULL until onboarding completes
- BehaviorEngine uses Tier 3 universal defaults for the first session instead of user settings
- If the user trades before visiting the profile page, all pattern detection runs blind

**Root cause**
UserProfile was designed to be auto-created on demand (graceful degradation), but the right
place to create it is at account creation time, not on first profile access.

**Solution**
After `broker_account` is created and committed in the OAuth callback, immediately create a
`UserProfile` with defaults and commit. Idempotent: use `ON CONFLICT DO NOTHING` logic (check
if exists before creating, since reconnects hit the `existing_account` branch).

**Files**
- `backend/app/api/zerodha.py` — callback handler, new broker_account branch

**Risk**: Low. Only affects new account creation path. Existing accounts unchanged.

---

## FIX-05: /api/zerodha/metrics/reset is unprotected

**Problem**
`zerodha.py:304-308` — `POST /metrics/reset` has no auth dependency. Any unauthenticated
request resets global API metrics (used for monitoring). With Sentry and Railway deployed,
this is a publicly accessible endpoint that wipes observability data.

**Root cause**
Oversight — other metrics endpoints also have no auth, but reset is destructive.

**Solution**
Add `broker_account_id: UUID = Depends(get_verified_broker_account_id)` to the reset endpoint.
The GET `/metrics` can stay public (read-only). Only reset needs protection.

**Files**
- `backend/app/api/zerodha.py`

**Risk**: Zero (additive auth check only).

---

## FIX-06: event_bus.py docstring has stale Phase 4 language

**Problem**
The module docstring says "After 5 trading days of validated dual-write → Phase 4 cutover
replaces Celery." Phase 4 is done. This is confusing and wrong.

**Solution**
Update the docstring to reflect current state: Streams are permanent infrastructure,
not a validation phase. Note what changes at 50+ users (connection pool → XREADGROUP).

**Files**
- `backend/app/core/event_bus.py`

**Risk**: Zero (documentation only).

---

## NOT FIXING NOW (deferred with reasons)

| Gap | Why deferred |
|-----|-------------|
| G1: UserProfile lacks user_id FK | Requires migration + backfill. No current feature needs cross-account queries. Deferred to multi-broker work. |
| G2: Service-layer ownership checks | JWT validation at HTTP layer is sufficient. Service trust model is acceptable for single-team codebase. |
| G5: Guardian split between User + UserProfile | API response works correctly (merges them). Clean separation is a refactor, not a bug. |
| G6: Some endpoints use unverified broker dep | Needs full route audit. Lower priority than active polling issues. Do separately. |
| Multi-instance Redis Streams | Each instance independently reads global stream and dispatches to its local WebSocket connections. With sticky sessions this works correctly — no pub/sub needed. Revisit at actual multi-instance deployment. |

---

## IMPLEMENTATION ORDER

1. FIX-06 (docstring — zero risk, do first for clarity)
2. FIX-01 (connection pool — backend, no tests affected)
3. FIX-05 (metrics/reset auth — backend, additive)
4. FIX-04 (UserProfile auto-create — backend, new account path)
5. FIX-02 (DangerZone polling — frontend)
6. FIX-03 (MyPatterns polling — frontend)
