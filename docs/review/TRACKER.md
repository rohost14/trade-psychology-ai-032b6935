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

- **Session**: 15
- **Started**: 2026-03-07
- **Working on**: Screen-by-screen review of cross-cutting features
- **Previous sessions summary (11-14):**
  - Session 11: Pattern detection production-grade rebuild (3-tier thresholds, IST timezone fix, BehavioralEvaluator + RiskDetector profile params, Settings "Trading Limits" card, migration 028)
  - Session 12: Goals + DangerZone → "My Patterns" merge (DangerLevel bug fixed, _LEVEL_ORDER + _upgrade_level, new My Patterns page, 24hr cooldown removed)
  - Session 13: Production Audit (32/38 addressable issues fixed, 6 deferred)
  - Session 14: BlowupShield redesign — AlertCheckpoint counterfactual P&L system (checkpoint_tasks.py, alert_checkpoint.py model, alert_checkpoint_service.py, migration 029, ShieldService fully rewritten, frontend BlowupShield.tsx rewritten)
  - Session 15: 212/212 tests passing; cross-cutting A–H reviewed (8 bugs fixed); SYSTEM_ARCHITECTURE.md updated (2200 lines, 18 sections, accurate)
- **Build**: ALL 212 tests pass (5 test files)
- **Session 16 (current)**: Full architecture review complete. Master doc: `docs/production_readiness_review.md`. All architecture docs merged. Migrations 022-029 confirmed applied. Phased execution plan (Phase 0–6) added with dependency map. Next: START Phase 0 — Sentry + AOF + C-00 (webhook 500) + H-00 (broker_email reconnect).

---

## Quick Reference

- All audit fixes verified (42/42 issues FIXED)
- Frontend builds: YES
- Backend: 212/212 tests passing
- Migrations pending in Supabase: 022, 023, 024, 025, 028, 029
- Trade Architecture Overhaul: COMPLETE (all 12 steps)
- AlertCheckpoint system: COMPLETE (sessions 14-15)
- Uncommitted changes: ~150+ files (single "Initial commit" so far)
- Architecture doc: `docs/SYSTEM_ARCHITECTURE.md`
