# TradeMentor AI — Working Notes
*Running log of decisions, state, and context. Updated every session.*
*If context is lost (restart/rate limit), read this + MEMORY.md + production_readiness_review.md*

---

## Current State (2026-03-13)

### Test Suite
- **296/296 tests passing** (6 files)
- test_db_schema (52), test_dashboard_api (55), test_behavioral_detection (56)
- test_notifications (30), test_trade_classifier (19), test_data_integrity (18)
- test_phase2_services (35), test_behavior_engine (32)

### Git
- Branch: main
- Last commits: Redis Streams event-driven updates, remove all polling
- All work committed cleanly, one commit per logical change

### Migrations Applied in Supabase
- 035: UNIQUE(broker_account_id, order_id) + processed_at on trades ✅
- 036: position_ledger table ✅
- 037: trading_sessions table ✅
- 038: alert state machine columns on risk_alerts ✅
- 039: behavioral event context on behavioral_events ✅
- **040: shadow_behavioral_events** — SKIP (shadow mode removed)
- **041: coach_sessions** ✅ Applied

---

## Phase Status (as of 2026-03-13)

| Phase | Status | Key fact |
|-------|--------|----------|
| 0 | ✅ Done | Sentry, Redis, webhook 500 fix, reconnect fix |
| 1 | ✅ Done | idempotency, Redis locks, EOD reconciliation, /health |
| 2 | ✅ Done | position_ledger + trading_sessions + services + late fill |
| 3 | ✅ Done | BehaviorEngine in production. danger/caution severity. RiskDetector deprecated. |
| 4 | ✅ DONE EARLY | Redis Streams fully implemented. publish_event() dual-write. WS replay. Zero polling. |
| 5 | ✅ Done (6/8) | Items 8 (Prometheus) deferred. Item 3 (WS replay) NOW COMPLETE via Phase 4. |
| 6 | ✅ Done (5/7) | Items 4 (PositionLedger cutover) + 6 (AI split) deferred |

---

## Phase 4 — Redis Streams (COMPLETE as of 2026-03-13)

Implemented ahead of schedule (originally planned for 50+ users).

### What was built:
- `event_bus.py`: dual-write to `stream:events` (global) + `stream:{account_id}` (per-account)
- `publish_event()`: sync, never-raises, called from Celery after each pipeline step
- `start_event_subscriber()`: async loop on server boot, XREAD BLOCK 100ms, dispatches to WebSocket
- `replay_events_for_account()`: XREAD from per-account stream, used on reconnect
- WebSocket endpoint: `?since=last_event_id` triggers replay of all missed events
- `WebSocketContext.tsx`: persists `last_event_id` per account in localStorage
- `useMargins.ts`: one fetch on mount (Redis cache) + WebSocket updates. Zero polling.

### Polling removed:
| Data | Before | After |
|------|--------|-------|
| Trades | 60s interval | WebSocket trade_update event |
| Alerts | 60s interval | WebSocket alert_update event |
| Margins | 30s interval | WebSocket margin_update event |
| Prices | KiteTicker (unchanged) | KiteTicker (unchanged) |
| **Total** | **3 intervals** | **0 intervals** |

### Dual-write design:
- Celery pipeline = primary (processes trades, saves to DB, runs BehaviorEngine)
- Redis Streams = notifications + replay only (never used for processing)
- Celery fails → stream not written (correct — don't record failed events)
- Redis fails → Celery still processes (publish_event is fail-silent)

### At 50+ users (next step for Phase 4):
- Replace per-call Redis connection in publish_event() with connection pool
- Add XREADGROUP consumer groups for reliable delivery (XACK, PEL management)
- See WORKING_NOTES for full explanation

### Remaining polling (intentional/acceptable):
- `PredictiveWarningsCard.tsx` — 5-min interval (AI predictions, not event-driven)
- `DangerZone.tsx` — 30s interval (⚠️ should be converted to event-driven)
- `MyPatterns.tsx` — 30s interval (⚠️ should be converted to event-driven)

---

## Critical "Don't Forget" Items

### Phase 3 cutover still pending
- `BehaviorEngine` is in production (shadow mode removed per git log)
- Script validation (10 test trade scripts) still needs to be run manually
- After validation: confirm RiskDetector fully deprecated

### Phase 4 connection pool (for 50+ users)
- publish_event() opens new TCP connection per call — fine now, breaks at 50+ users
- Fix: shared ConnectionPool in publish_event() + XREADGROUP consumer groups
- Trigger: first time Sentry shows "max clients reached" from Upstash

### Script Validation Plan (post Phase 5-6)
- User executes individual scripts manually, one at a time with delays
- Each script inserts ONE trade with specific characteristics
- User observes dashboard/logs/Sentry after each execution
- Scripts to prepare (NOT execute automatically):
  - Script 1: Single loss trade
  - Script 2: Second loss (approaches consecutive threshold)
  - Script 3: Third loss quickly (triggers consecutive_loss_streak)
  - Script 4: New trade 3min after loss (triggers revenge_trade)
  - Script 5-8: Rapid trades in succession (triggers overtrading_burst)
  - Script 9: Large position after losses (triggers size_escalation/excess_exposure)
  - Script 10: Session P&L tanks (triggers session_meltdown)
- Tag all test trades with `tag = 'TEST_SCENARIO'` for easy cleanup
- Cleanup script: `DELETE FROM trades WHERE tag = 'TEST_SCENARIO'` (cascades)

---

## Architecture Notes

### Live Price Streaming
- `PriceStreamProvider` interface (easy swap to SharedPriceStream post-partnership)
- `PerUserPriceStream`: one KiteTicker per active account
- KiteTicker MODE_LTP (lightest mode)
- `price_stream.start_account()` called from WebSocket `subscribe_positions`
- `price_stream.refresh_subscriptions()` called after every trade fill
- `price_stream.restart_all()` called on server startup

### BehaviorEngine (Shadow Mode)
- 11 patterns implemented (margin_risk intentionally skipped — needs live API)
- Writes to `shadow_behavioral_events` table only
- Never raises (bulletproof try/except)
- Uses `TradingSession.risk_score` for cumulative state
- Behavior states: Stable → Pressure → Tilt Risk → Tilt → Breakdown → Recovery

### EOD Reconciliation
- Runs at 4:00 AM IST daily (not 3-min polling)
- Staggered: 10 accounts/sec (scales to 1000+ users)
- Looks at yesterday's Kite orders vs our DB

### Coach Insight
- Non-blocking: returns fallback immediately, queues LLM generation to Celery
- 15-minute cache in `UserProfile.ai_cache["coach_insight"]`
- Frontend polls once after 5s if `status: "generating"`

### Sentry Config
- `before_send` filter drops: KeyboardInterrupt, SystemExit, CancelledError
- These are normal shutdown events, not bugs
- Traces sample rate: 10%

---

## Known Pending Items

1. **ZERODHA_API_KEY** not set in .env — KiteTicker won't connect without it
2. **Script validation** — 10 test trade scripts, run manually, observe BehaviorEngine alerts
3. **Frontend sync button** — still shows, remove after KiteTicker confirmed working
4. **margin_risk pattern** — intentionally skipped in BehaviorEngine (needs live Kite margin API)
5. **UserProfile.user_id FK** — missing FK from user_profiles to users. Needed for multi-account features. Deferred to multi-broker work.
6. **G6: Some routes use get_current_broker_account_id (not verified)** — needs full route audit. Deferred.
7. **Phase 4 XREADGROUP** — for guaranteed delivery at 50+ users. ConnectionPool already added.

---

## Hotfixes Applied (session 17)

- `instrument_service.py`: missing `timezone` import → NameError on all 5 exchanges (NSE/NFO/BSE/MCX/BFO)
- `shield_service.py`: N+1 query storm (150+ queries per page) → batch-loaded (5 queries total)
- `BlowupShield.tsx`: continuous re-fetch → 5-min module-level cache + visibilitychange guard
- `main.py`: Sentry capturing normal Ctrl+C shutdown as errors → before_send filter added
- `position_ledger_service.py`: missing late-fill (out-of-order) handling → full replay on late arrival

## Multi-broker Architecture (session 18)

- `broker_interface.py`: `BrokerInterface` ABC + `BrokerFactory` + `get_broker_service()` already existed but were dead code
- `ZerodhaClient` now inherits `BrokerInterface` — interface contract enforced at class level
- Added `validate_token()` to `ZerodhaClient` (was missing from interface impl)
- Added `get_ltp()` as optional method on interface (raises NotImplementedError by default)
- `get_instruments()` signature updated: `access_token` now optional param (Kite doesn't need auth for instruments)
- `BrokerFactory.register(BrokerType.ZERODHA, ZerodhaClient)` — factory now live
- `get_broker_service("zerodha")` works and returns `ZerodhaClient` instance
- `dhan_service.py` created — full stub with all abstract methods and key Dhan differences documented
- **To add Dhan**: implement all methods in `dhan_service.py`, uncomment `BrokerFactory.register`, add config keys
- Existing routes unchanged — they still use `zerodha_client` singleton directly (backward-compatible)
- New code should use: `get_broker_service(account.broker_name)` instead of importing `zerodha_client`

## Fixes Applied (session 18) — see docs/FIXES_SESSION_18.md

- `event_bus.py`: per-call Redis TCP connection → shared ConnectionPool (max 10). Zero connections wasted.
- `event_bus.py`: stale docstring ("5 trading days validation" → updated to reflect Phase 4 complete)
- `DangerZone.tsx`: 30s setInterval removed → refetch on lastTradeEvent/lastAlertEvent from WebSocket
- `MyPatterns.tsx`: 30s setInterval removed → refetch on lastTradeEvent/lastAlertEvent from WebSocket
- `zerodha.py`: new broker_account now auto-creates UserProfile immediately (not lazy on first profile access)
- `zerodha.py`: POST /metrics/reset was unprotected → added get_verified_broker_account_id dependency

---

## User Preferences / Non-Negotiables

- Never change a test to make it pass — fix the code
- No commented-out dead code — delete + use git
- Commit per logical change, descriptive messages
- QA-first: validate from user/QA/developer perspective before marking complete
- Script validation: user executes scripts manually one at a time (not automated)
- Phase 4 deferred until 50+ users — don't reopen unless asked
