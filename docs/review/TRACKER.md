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
| 1 | Dashboard | **17/19 FIXED** | `screens/dashboard.md` | D10 (journal), D11 (perf) deferred |
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

- **Session**: 18 (2026-03-13)
- **Previous sessions summary (16-17):**
  - Session 16: Full architecture review. production_readiness_review.md. Phase 0–6 plan. Migrations 022-029 confirmed applied.
  - Session 17: Phases 0–3 complete. BehaviorEngine live. Hotfixes: instrument_service timezone, shield N+1, BlowupShield re-fetch, Sentry shutdown filter, position_ledger late-fill. 296/296 tests.
  - Session 18: Phase 4 Redis Streams implemented EARLY (not waiting for 50+ users). Full polling removal. WS replay. last_event_id localStorage. Zero polling intervals. DangerZone.tsx + MyPatterns.tsx still have 30s polling (pending conversion).
- **Build**: 296/296 tests pass (6 test files)

---

## Quick Reference

- All audit fixes verified (42/42 issues FIXED)
- Frontend builds: YES
- Backend: 296/296 tests passing
- All migrations applied: 035–041 (040 skipped)
- Trade Architecture Overhaul: COMPLETE
- AlertCheckpoint system: COMPLETE
- Redis Streams / zero-polling: COMPLETE (Phase 4 done)
- WebSocket replay on reconnect: COMPLETE
- Phases 0–6: ALL DONE (with minor deferred items per WORKING_NOTES)
- Architecture doc: `docs/SYSTEM_ARCHITECTURE.md`
