# TradeMentor AI — Working Notes
*Running log of decisions, state, and context. Updated every session.*
*If context is lost (restart/rate limit), read this + MEMORY.md + production_readiness_review.md*

---

## Current State (2026-03-10)

### Test Suite
- **296/296 tests passing** (6 files)
- test_db_schema (52), test_dashboard_api (55), test_behavioral_detection (56)
- test_notifications (30), test_trade_classifier (19), test_data_integrity (18)
- test_phase2_services (35), test_behavior_engine (32) — new this session

### Git
- Branch: main
- Last commit: Phase 3 BehaviorEngine + shadow mode (9fe7eae)
- All work committed cleanly, one commit per logical change

### Migrations Applied in Supabase
- 035: UNIQUE(broker_account_id, order_id) + processed_at on trades ✅
- 036: position_ledger table ✅
- 037: trading_sessions table ✅
- 038: alert state machine columns on risk_alerts ✅
- 039: behavioral event context on behavioral_events ✅
- **040: shadow_behavioral_events** — needs to be run ⚠️

---

## Phase Status

| Phase | Status | Key fact |
|-------|--------|----------|
| 0 | ✅ Done | Sentry, Redis, webhook 500 fix, reconnect fix |
| 1 | ✅ Done | idempotency, Redis locks, EOD reconciliation, /health |
| 2 | ✅ Done | position_ledger + trading_sessions + services + late fill |
| 3 | ⚠️ Shadow only | BehaviorEngine runs BUT old engines serve production. Items 6-7 pending validation. |
| 4 | 🔜 Deferred | Too complex for <5 users. Revisit at 50+ users. |
| 5 | 🔄 In progress | Started 2026-03-10 |
| 6 | ⬜ Not started | |

---

## Phase 5 — Adapted Implementation (Phase 4 deferred)

**Original Phase 5** is fully preserved in `docs/production_readiness_review.md` — do NOT modify it.
When Phase 4 is implemented later, re-read original Phase 5 to see what needs updating.

**Adapted Phase 5 execution order** (6 of 8 items, no Phase 4 needed):
1. ✅ celery-redbeat — Beat schedule survives restarts (5 min, zero risk)
2. ✅ Circuit breaker on Kite API — Redis key OPEN/CLOSED/HALF_OPEN per account
3. ✅ Kite Ticker Redis LTP cache — completes live price work (price_stream_service.py exists)
4. ✅ Position monitor — Celery Beat every 30s, checks open positions (adapted: no stream worker)
5. ✅ Alert consolidation — 5-min bucketing, hard cap at 8 alerts/session
6. ✅ BlowupShield empty state fix — P-05 product fix

**Skipped (need Phase 4):**
- Item 3: WebSocket event replay (XREAD from streams)
- Item 8: Prometheus/Grafana (operational setup, not code — do manually when needed)

---

## Critical "Don't Forget" Items

### Phase 3 is NOT in production
- `RiskDetector` + `BehavioralEvaluator` still serve all production alerts
- `BehaviorEngine` only writes to `shadow_behavioral_events`
- Cutover (Phase 3 items 6-7) happens AFTER script validation
- Script validation = user manually executes individual trade scripts, observes real-time alerts

### Phase 4 is deliberately skipped
- Redis Streams is overkill for <5 users
- Current Celery + Phase 1 locks are sufficient
- Phase 4 unblocks itself when user count reaches 50+
- The architecture is designed so Phase 4 can be added cleanly later

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

1. **Migration 040** needs to be run in Supabase (shadow_behavioral_events table)
2. **ZERODHA_API_KEY** not set in .env — KiteTicker won't connect without it
3. **Phase 3 cutover** (items 6-7) — after script validation
4. **Frontend sync button** — still shows, should be removed after KiteTicker is confirmed working
5. **margin_risk pattern** — intentionally skipped in BehaviorEngine (needs live Kite margin API)

---

## Hotfixes Applied (this session)

- `instrument_service.py`: missing `timezone` import → NameError on all 5 exchanges (NSE/NFO/BSE/MCX/BFO)
- `shield_service.py`: N+1 query storm (150+ queries per page) → batch-loaded (5 queries total)
- `BlowupShield.tsx`: continuous re-fetch → 5-min module-level cache + visibilitychange guard
- `main.py`: Sentry capturing normal Ctrl+C shutdown as errors → before_send filter added
- `position_ledger_service.py`: missing late-fill (out-of-order) handling → full replay on late arrival

---

## User Preferences / Non-Negotiables

- Never change a test to make it pass — fix the code
- No commented-out dead code — delete + use git
- Commit per logical change, descriptive messages
- QA-first: validate from user/QA/developer perspective before marking complete
- Script validation: user executes scripts manually one at a time (not automated)
- Phase 4 deferred until 50+ users — don't reopen unless asked
