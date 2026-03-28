# Known Gaps & Roadmap
*All identified gaps, their priority, and planned resolution*

---

## Priority Classification

- **P0** — Blocks production at current scale. Fix before first user.
- **P1** — Will cause production incidents within first month.
- **P2** — Quality/polish. Fix before public launch.
- **P3** — Nice-to-have. Phase C or later.

---

## P0: Critical (Fix Before First User)

| # | Gap | Impact | Fix | Effort |
|---|-----|--------|-----|--------|
| P0-1 | Rotate Supabase DB password | Credentials were in test_pooler.py (on disk, never committed) | Supabase → Settings → Database → Reset | 5 min |
| P0-2 | Add `VITE_SENTRY_DSN` + `SENTRY_DSN` to production `.env` | No error visibility in production | Create Sentry project, add DSN to env | 15 min |
| P0-3 | Set `BACKEND_CORS_ORIGINS` to your actual domain | Would block the app entirely in prod | Add domain to env var | 5 min |

---

## P1: Operational (Fix Before Scale)

| # | Gap | Impact | Fix | Effort |
|---|-----|--------|-----|--------|
| P1-1 | VAPID keys not generated | Push notifications silently fail | `npx web-push generate-vapid-keys`, add to `.env` | 15 min |
| ~~P1-2~~ | ~~No circuit breaker open alerting~~ | — | **✅ DONE (S22)** — `sentry_sdk.capture_message` on CLOSED→OPEN in `circuit_breaker_service.py` | — |
| ~~P1-3~~ | ~~No dead letter queue~~ | — | **✅ DONE (S22)** — `MaxRetriesExceededError` captured to Sentry in `alert_tasks.py::send_whatsapp_alert` | — |
| ~~P1-4~~ | ~~Integration test suite missing~~ | — | **✅ DONE (S22)** — 26 integration tests across 5 classes in `tests/test_integration.py` | — |
| P1-5 | `test_pooler.py` + `test_import.py` in gitignore but still exist on disk | Risk if deployed to server | Delete them after credentials rotated | 5 min |

---

## P2: Quality (Fix Before Public Launch)

| # | Gap | Impact | Fix | Effort |
|---|-----|--------|-----|--------|
| P2-1 | No skeleton/shimmer loading states | Cards flash empty on load (bad first impression) | Add shadcn `<Skeleton>` to all cards | 4 hours |
| P2-2 | No empty state illustrations | New users see blank tables with no guidance | Design + add illustrated empty states | 4 hours |
| P2-3 | No formal a11y audit | Screen reader users blocked | Screen reader + keyboard navigation test | 1 day |
| P2-4 | `.env.example` outdated | Developers/deployers miss required vars | Add `VITE_SENTRY_DSN`, `VAPID_*`, document all vars | 30 min |
| P2-5 | No Dockerfile | Manual deploy steps, no containerization | Write Dockerfile + docker-compose | 2 hours |
| P2-6 | No maintenance mode | Can't take backend offline for migrations without user-facing errors | Add `MAINTENANCE_MODE` env flag → 503 with message | 1 hour |
| P2-7 | WebSocket reconnect: no user-visible indicator | User doesn't know they're offline/reconnecting | Add connection dot animation in Layout header | 30 min |

---

## P3: Scaling (Phase C — Before 500 Users)

| # | Gap | Impact at Scale | Fix | Effort |
|---|-----|----------------|-----|--------|
| P3-1 | Per-user KiteTicker | Zerodha throttles at ~10 simultaneous | Shared KiteTicker + instrument subscription dedup | 2 days |
| P3-2 | WebSocket single process | Breaks at 500+ concurrent users | Redis pub/sub + horizontal uvicorn scaling | 1 week |
| P3-3 | No read replica | Analytics queries compete with write path | Enable Supabase read replica | 1 day (config) |
| P3-4 | CSP `unsafe-inline` | Low security, CSP bypass possible | Nonce-based CSP (requires Vite plugin) | 4 hours |
| P3-5 | FIFO lock no checkpoint/resume | Fails for accounts with 1000+ ledger entries | Add checkpointing to position_ledger_service | 1 day |
| ~~P3-6~~ | ~~Options expiry handling~~ | — | **✅ DONE (S22)** — `_expire_stale_positions()` in `reconciliation_tasks.py`; weekly exact-date + monthly proxy logic | — |
| P3-7 | Per-account feature flags | Can't A/B test or disable features per user | Add feature flag system (simple Redis-based) | 1 day |

---

## Known Deferred Features (Not Bugs)

| Feature | Status | Notes |
|---------|--------|-------|
| Dhan broker integration | Stub only (`dhan_service.py`) | Architecture is broker-agnostic (broker_interface.py). Dhan SDK integration needed. |
| MoneySaved page | Route exists, deferred | Was deferred in session 16. BlowupShield covers the core value. |
| Personalization page | Route exists, deferred | `ai_personalization_service.py` exists. UI not built. |
| Push notifications | Backend wired, VAPID not configured | Needs VAPID keys + browser notification permission flow |
| Commodity EOD (MCX) | Beat task exists | `send_commodity_eod` task — MCX positions only. Low priority for equity traders. |
| PositionLedger cutover | Service built, not fully used | `position_ledger_service.py` exists. Full cutover deferred (was Phase 6 item 4). |
| AI split (fast/deep) | Service has logic, not exposed | `ai_service.py` has fast (Haiku) and deep (Sonnet) modes. Not yet wired to separate endpoints. |

---

## Already Fixed in Session 22 (2026-03-17)

| Fix | File |
|-----|------|
| **Circuit breaker Sentry alerting** — `sentry_sdk.capture_message` on CLOSED→OPEN | `backend/app/services/circuit_breaker_service.py` |
| **WhatsApp dead letter queue** — Sentry capture on `MaxRetriesExceededError` | `backend/app/tasks/alert_tasks.py` |
| **26 integration tests** — WebSocket JWT auth (4), event replay (3), position monitor (3), circuit breaker Sentry (1), options expiry (7) + existing 9 | `backend/tests/test_integration.py` |
| **Options expiry cleanup** — `_expire_stale_positions()` zeroes OTM worthless positions at 4 AM IST | `backend/app/tasks/reconciliation_tasks.py` |
| **Celery concurrency** — bumped from 50 → 100 workers | `backend/app/core/celery_app.py` |
| **report_tasks parallelisation** — sequential per-account loops → `asyncio.gather` batches of 20 | `backend/app/tasks/report_tasks.py` |
| **Procfile** — web / worker / beat process definitions | `backend/Procfile` |
| **`.env.example` files** — backend + frontend with all required vars documented | `backend/.env.example`, `.env.example` |
| **Dockerfile + docker-compose** — multi-stage python:3.11-slim, non-root user, web/worker/beat/redis/db services | `backend/Dockerfile`, `docker-compose.yml` |
| **Maintenance mode** — `MAINTENANCE_MODE` env flag → 503 middleware + FE `/maintenance` page | `backend/app/main.py`, `src/App.tsx`, `src/lib/api.ts` |
| **WS reconnect indicator** — amber pulsing dot in Layout header | `src/contexts/WebSocketContext.tsx`, `src/components/Layout.tsx` |
| **Skeleton loading states** — shadcn `<Skeleton>` in 6 data-heavy components | Dashboard, Analytics tabs |
| **Empty state illustrations** — icon + heading + SEBI stat cards pattern | All blank table components |

---

## Already Fixed in Session 21 (2026-03-16)

| Fix | File |
|-----|------|
| **Dual engine eliminated** — `patternDetector.ts` + `patternConfig.ts` deleted | Removed from src/lib/ |
| `AlertContext.tsx` rewritten — backend-only, WebSocket toast on new alerts | `src/contexts/AlertContext.tsx` |
| `Dashboard.tsx` — removed `runAnalysis()` call and Trade-mapping useEffect | `src/pages/Dashboard.tsx` |
| `MyPatterns.tsx` — emotionalTax now derived from backend alerts (not detectAllPatterns) | `src/pages/MyPatterns.tsx` |
| **New `/alerts` page** — Live / History / Patterns tabs, full-featured alert center | `src/pages/Alerts.tsx` |
| Alerts nav item added to Layout (desktop + mobile) with unread count badge | `src/components/Layout.tsx` |
| 15 backend pattern_type → frontend PatternType mappings added to AlertContext | `src/contexts/AlertContext.tsx` |
| `trading_defaults.py` — 35+ research-backed COLD_START_DEFAULTS (Session 21) | `backend/app/core/trading_defaults.py` |
| `behavior_engine.py` — all 15 detectors rewritten, zero hardcoded constants | `backend/app/services/behavior_engine.py` |

---

## Already Fixed in This Session (Session 20)

| Fix | File |
|-----|------|
| Hardcoded Supabase credentials redacted | `backend/test_pooler.py` |
| `test_pooler.py` + `test_import.py` gitignored | `.gitignore` |
| Rate limit on `trigger-intervention` (4/15min) | `backend/app/api/danger_zone.py` |
| ErrorBoundary around `<Outlet />` in Layout | `src/components/Layout.tsx` |

---

## Already Fixed in Session 19

| Fix | File |
|-----|------|
| Polling eradicated (position monitor, portfolio radar, PredictiveWarnings) | Multiple |
| Alert firing gap (`_fire_position_alert` creates real RiskAlert) | `position_monitor_tasks.py` |
| 23x asyncio.run() migration | All 7 task files |
| CSP header | `backend/app/main.py` |
| Frontend Sentry (`@sentry/react`) | `src/main.tsx`, `ErrorBoundary.tsx` |
| Bundle code splitting (1.41MB → 739KB) | `src/App.tsx` |
| Rate limiting (Redis sliding window) | `backend/app/core/rate_limit.py` |
| DB indexes migration 044 | `backend/migrations/044_missing_indexes.sql` |
| Zod validation on Settings | `src/pages/Settings.tsx` |
| localStorage clear on disconnect | `src/contexts/BrokerContext.tsx` |
| FIFO lock TTL 30s → 60s | `backend/app/tasks/trade_tasks.py` |
| broadcast_price sequential → gather | `backend/app/api/websocket.py` |
