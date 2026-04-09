# Screen-by-Screen Review Tracker

**Purpose:** Master status file. Read this FIRST when resuming any session.

---

## How This Works

1. **TRACKER.md** (this file) — Overall status of every screen/feature
2. **screens/{name}.md** — Detailed findings, fixes, and decisions per screen
3. **sessions/session_{N}.md** — What was done in each session (append-only)

When resuming after context loss: Read TRACKER.md → find current task → read relevant screen file.

---

## Screens

| # | Screen | Status | File | Notes |
|---|--------|--------|------|-------|
| 1 | Dashboard | **19/19 FIXED** | `screens/dashboard.md` | D10 (journal AI pipeline + no localStorage), D11 (perf spinner removed) — complete session 21 |
| 2 | Analytics | **COMPLETE + AI** | `screens/analytics.md` | 6 endpoints, 4 tabs, 27 patterns, AI narratives, predictions |
| 3 | Goals | **2/2 FIXED → REARCHITECT** | `screens/goals.md` | G1/G2 fixed. Merging with DangerZone into AI-driven "My Patterns" — see `screens/goals-dangerzone-merge.md` |
| 4 | Chat (AI Coach) | **4/4 FIXED** | `screens/chat.md` | C1-C4: real patterns, profile context, enriched data, fallback logging |
| 5 | Settings | **6/6 FIXED** | `screens/settings.md` | S1-S6: 2-tab restructure, WhatsApp status, test button, error leakage |
| 6 | MoneySaved | **REDIRECTED** | `screens/money-saved.md` | Redirects to /blowup-shield |
| 7 | BlowupShield | **REDESIGNED** | `screens/blowup-shield.md` | Real counterfactual P&L (session 14). AlertCheckpoint system. No bootstrap numbers. |
| 8 | DangerZone | **MERGED** | `screens/danger-zone.md` | Merged into My Patterns (session 12). Routes /danger-zone + /goals removed. |
| 9 | My Patterns | **COMPLETE** | `screens/goals-dangerzone-merge.md` | New page combining Goals + DangerZone (session 12) |
| 10 | Personalization | **COMPLETE** | — | Settings page (session 13) |

## Cross-Cutting Features

| # | Feature | Status | File | Notes |
|---|---------|--------|------|-------|
| A | Zerodha OAuth Flow | **REVIEWED** | `screens/zerodha-oauth.md` | OA-01 fixed: OAuth error now shown via toast instead of silent console.log |
| B | Trade Sync Pipeline | **REVIEWED** | `screens/trade-sync.md` | 4 bugs fixed (TS-01..04): token logging, weekly crash, wrong P&L, dedup gap |
| C | Real-time Price Stream | **REVIEWED** | `screens/price-stream.md` | No bugs. 7 observations (reconnect backoff, heartbeat) deferred |
| D | Push Notifications | **REVIEWED** | `screens/push-notifications.md` | 3 bugs fixed (PN-01,05,06): type mismatch, never-deactivated subs, duplicate singleton |
| E | WhatsApp Alerts | **REVIEWED** | `screens/whatsapp.md` | Bugs fixed via TS-02/03 (weekly crash + wrong P&L). WA-02 fixed prior session. |
| F | Token Expiry Handling | PARTIAL | `screens/token-expiry.md` | D12 fixed (event listener wired) |
| G | Behavioral Detection | **ALL PATTERNS FIXED** | `screens/pattern-detection-audit.md` | Phases 1-4 (session 9) + adapter fix (session 10). All 27 BehavioralAnalysisService patterns + 5 BehavioralEvaluator patterns now use CompletedTrade.realized_pnl via adapter. |
| H | Onboarding | **REVIEWED** | `screens/onboarding.md` | No bugs. Intentional design choices noted. |
| I | Product North Star | **DOCUMENTED** | `screens/product-north-star.md` | Vision: real-time guardian + session memory + predictive intervention |

## Current Session

- **Session**: 29 (2026-03-22) — LATEST
- **Session 29 work**:
  - **Admin rate limiting**: `/api/admin/auth/login` — IP sliding-window 5/15min via `admin_login_limiter`. Per-email Redis lockout after 5 consecutive failures (15-min TTL, cleared on success). `/api/admin/auth/verify` — IP rate-limited 5/5min via `admin_otp_limiter`.
  - **BTST analytics**: Backend endpoint `/api/analytics/btst` already existed — added missing `hold_type` (weekend_hold vs overnight) and `instrument_type` fields to trade list. Frontend: `BTSTCard` component in `BehaviorTab.tsx` — 4 summary metrics + context blurb + collapsible trade table with reversal highlighting.
  - **Onboarding flow**: `GettingStartedCard` (`src/components/dashboard/GettingStartedCard.tsx`) — 4-step checklist (Connect ✅, Profile, Sync, Analytics). Auto-hides when 3+ trades + onboarding completed. Per-account dismiss in localStorage. Inline sync button. Wired into Dashboard.tsx using existing `reopenOnboarding` from `useOnboarding` hook.
  - **QA audit fixes** (4 real bugs fixed from 26 reported, 22 were false positives):
    1. `/api/analytics/recalculate-pnl` — added `analytics_limiter` Depends + clamped `days_back` to 1–90 (prevents DoS via unlimited FIFO computation)
    2. OAuth fallback JWT-in-URL removed — `_store_auth_code` now raises on Redis failure instead of embedding raw JWT in redirect URL (was exposing JWT in browser history + server logs)
    3. Admin OTP no longer logged in plaintext — log now says to use `redis-cli GET admin_otp:{email}` in dev
    4. Admin system health `whatsapp.provider` was hardcoded `"gupshup"` — now uses `whatsapp_service.provider` property (returns actual provider). Also fixed `asyncio.get_event_loop()` → `get_running_loop()` deprecation in `whatsapp_service.py`.
  - **QA resolution (29-issue pass)**:
    - **S1 ✅**: WebSocket token revocation — `websocket.py` now checks `BrokerAccount.token_revoked_at` after JWT validation at connect time. Revoked tokens get `close(4001)`. One DB query per WS connect (not per message).
    - **B1 ✅**: `insolvent` risk level — added to TypeScript `MarginStatus`/`MarginSnapshot` types; `MarginStatusCard` now shows `AlertTriangle` + destructive border for insolvent state; `get_margin_history()` now counts `insolvent_occurrences` in statistics.
    - **M1 ✅**: WhatsApp provider confusion — startup warning added in `whatsapp_service.py` when Gupshup vars are set but Twilio is not (prevents silent message drop). Added Gupshup vars to `.env.example` with migration-pending comment.
    - **M4 ✅**: Webhook DLQ — `process_webhook_trade` now captures `MaxRetriesExceededError` → Sentry `capture_message` + error log before re-raising. Pattern matches WhatsApp DLQ (session 22).
    - **S4 ✅**: Encryption key validation — `main.py` lifespan now calls `Fernet(settings.ENCRYPTION_KEY.encode())` at startup and raises `RuntimeError` if invalid. Fails fast at deploy time instead of per-user at runtime. `.env.example` warns against key rotation.
    - **S3 ✅**: Admin JWT secret startup warning — `main.py` lifespan logs WARNING when `ADMIN_JWT_SECRET` is unset (admin panel will 404 silently). Also added to `.env.example`.
    - **D1 ✅**: Webhook P&L partial commit — added `await db.rollback()` in `apply_fill` exception handler so flushed-but-uncommitted ledger data doesn't get accidentally committed by behavior detection.
    - **D3 ✅**: Stale position cleanup — added 60-day max-age fallback for positions with unparseable expiry (non-NSE/MCX symbols). These get `status="stale"` with a warning log instead of accumulating indefinitely.
    - **B2 ✅**: Threshold floor validation — added `@field_validator` for `daily_trade_limit` (1–500) and `trading_since` (1990–2100) to `ProfileUpdate`.
    - **B3 ✅**: Blowup Shield underestimate — `get_shield_summary()` now returns `is_partial: bool` when `cp_calculating > 0`. `ShieldSummary` TypeScript type updated. `BlowupShield.tsx` shows `₹X+` and "X still calculating" when partial.
- **Previous session**: 28 (2026-03-21)
- **Previous sessions summary (18–27):**
  - Session 18: Phase 4 Redis Streams early. Full polling removal. WS replay.
  - Session 19: Portfolio Radar. AI Chat SSE streaming. Production readiness audit (8.2→8.5/10).
  - Session 20: 4 new behavioral patterns. Strategy detection (15 types). Journal redesign. Migrations 045+046.
  - Session 21: Dual engine eliminated. BehaviorEngine rewritten (15 patterns). New /alerts page.
  - Session 22: Celery 100 workers, Procfile, Docker, maintenance mode, WS reconnect indicator, skeleton states. Score 8.7/10.
  - Session 23: framer-motion removed (CSS animations), bundle split, guest mode + demo data, mobile nav redesign.
  - Session 24: Email reports built (SMTP), email wired into report_tasks, Settings UI email card.
  - Session 25: SEBI compliance — Terms/Privacy pages, ComplianceDisclaimer component, consent gate.
  - Session 26: Landing page (full marketing). Admin panel complete (9 routers, full frontend). Gupshup plan. Stitch prompts.
  - Session 27: Behavioral engine gap analysis. Full spec for 8 new patterns. No code.
- **Build**: 296/296 unit tests + 26 integration tests

---

## Quick Reference

- Overall score: **8.7/10** — GO for production (up to ~1,000–1,200 users)
- Frontend builds: YES (0 TypeScript errors, all routes lazy-loaded)
- Backend: 296/296 unit tests + 26 integration tests passing
- Migrations applied in Supabase: 035–046 (040 skipped). **047, 048, 049 written but NOT YET applied.**
- 9 live screens: Dashboard, Analytics, My Patterns, Chat, Portfolio Radar, Blowup Shield, Settings, Alerts, Reports
- Admin panel: `/admin/*` — Login, Overview, Users, System, Insights, Broadcast, Audit Log, Config
- Single detection engine: BehaviorEngine (backend only) — patternDetector.ts deleted
- Trade Architecture Overhaul: COMPLETE
- AlertCheckpoint system: COMPLETE
- Redis Streams / zero-polling: COMPLETE
- WebSocket replay on reconnect: COMPLETE
- Phases 0–6: ALL DONE
- Architecture doc: `docs/SYSTEM_ARCHITECTURE.md`

## Behavioral Engine — Pattern Status (after Session 28)

BehaviorEngine now has **22 patterns** (up from 18). All thresholds in `trading_defaults.py`.

| ID | Pattern | Status | Notes |
|----|---------|--------|-------|
| G3 | Expiry day detection bug fix | ✅ Done S28 | `is_expiry_day()` in instrument_parser.py replaces `weekday()==3` everywhere |
| G2 | Expiry day overtrading alert (pattern 19) | ✅ Done S28 | Fires after 13:00 IST. 5+ trades or 8+ = caution/danger. Baseline comparison future work. |
| G4 | Opening 5-min trap (pattern 20) | ✅ Done S28 | Entry 09:15–09:20 IST on derivatives. 1 = caution, 2+ = danger. |
| G5 | End-of-session MIS panic (pattern 21) | ✅ Done S28 | MIS entry after 15:10 IST. 2 = caution, 3+ = danger. |
| G6 | Post-loss recovery bet (pattern 22) | ✅ Done S28 | After 2 consecutive losses, 2×+ avg size = caution, 3×+ = danger. |
| G9 | Monthly vs weekly expiry thresholds | ✅ Done S28 | no_stoploss: monthly=10min/20%, weekly=15min/30%, normal=30min/25%. |
| G1 | BTST analytics | ⚠️ Not started | Entry >15:00 IST + NRML + exit <09:45 next day. Analytics page + reports. Needs MTM snapshot decision. |
| G7 | Deep OTM lottery buying | Blocked | Needs spot price at trade time — not stored. Revisit after price feed. |
| G8 | Strategy pivot confusion | P3 | Low priority. Analytics only. |

---

## Known Pending Items (not blocking production)

| Item | Priority | Status | Notes |
|------|----------|--------|-------|
| Shared KiteTicker (multi-account) | **P2 — pending Zerodha partnership** | Pending | Per-user ticker fine until partnership. Do not re-raise until partnership confirmed. |
| WebSocket horizontal sharding | P2 at ~1,000+ users | Pending | Redis pub/sub per instrument |
| Options expiry position close | ~~P2~~ | **✅ DONE (S22)** | `_expire_stale_positions` in reconciliation_tasks.py — weekly + monthly proxy logic |
| Integration test suite (full pipeline) | ~~P1~~ | **✅ DONE (S22)** | 26 tests: WebSocket JWT auth, event replay, position monitor, circuit breaker, options expiry |
| Circuit breaker open alerting | ~~P2~~ | **✅ DONE (S22)** | Sentry `capture_message` on CLOSED→OPEN transition |
| WhatsApp DLQ (dead letter) | ~~P1~~ | **✅ DONE (S22)** | Sentry error on MaxRetriesExceededError in send_whatsapp_alert |
| Prometheus → Grafana wiring | P2 | Pending | Endpoint exists, not wired externally |
| **Apply migrations 047+048+049** | **P0** | **Pending** | Run in Supabase SQL editor before admin panel works |
| **Admin JWT secret env var** | **P0** | **Pending** | Add `ADMIN_JWT_SECRET` to .env + Supabase/Railway env |
| **Create first admin user** | **P0** | **Pending** | INSERT into admin_users with bcrypt hash |
| **WhatsApp Gupshup migration** | P1 | Blocked | Waiting on Meta template approval. Code ready to write (Day 2 tasks). |
| **Guardian phone verification** | P1 | Blocked | Depends on WhatsApp working |
| **Payment / Razorpay integration** | P1 | Not started | Subscriptions table + Razorpay SDK + webhook handler + plan gating |
| **Zerodha Publisher Program** | P2 | Not started | Business track — apply at developers.zerodha.com |
| **Rate limit admin login** | ~~P1~~ | **✅ DONE (S29)** | IP sliding-window (5/15min) + per-email lockout after 5 failures (Redis). OTP endpoint also rate-limited. |
| **SMTP configured for admin OTP** | P1 | Not started | Falls back to log in dev — needs real SMTP/SES for prod |
| **Onboarding flow** | ~~P2~~ | **✅ DONE (S29)** | `GettingStartedCard` on Dashboard: 4-step checklist, auto-hides at 3+ trades, dismiss button, reopens wizard |
| `.env.example` + Dockerfile | ~~P2~~ | **✅ DONE (S22)** | backend/.env.example, .env.example (FE), Dockerfile, docker-compose.yml |
| Maintenance mode | ~~P2~~ | **✅ DONE (S22)** | `MAINTENANCE_MODE` env flag → 503 middleware + FE /maintenance page |
| WS reconnect indicator | ~~P2~~ | **✅ DONE (S22)** | Amber dot in Layout header, `isReconnecting` state in WebSocketContext |
| Skeleton loading states | ~~P2~~ | **✅ DONE (S22)** | All 6 data-heavy components use shadcn Skeleton |
| Empty state illustrations | ~~P2~~ | **✅ DONE (S22)** | Icon + heading + SEBI stat cards pattern across all blank tables |
