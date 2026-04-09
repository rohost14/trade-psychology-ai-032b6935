# Session 8 — Pattern Detection Pipeline Audit & Fix Plan

**Date:** 2026-02-24
**Focus:** Deep audit of entire behavioral detection pipeline after real-world failure

---

## Trigger

User traded 5 consecutive losing trades, lost ~50% of capital (Rs.11k → ~Rs.5k), traded NIFTY25400CE twice after losing on it. System only flagged Position Size Warning (4x) and Revenge Trading (1x). Missed everything critical.

## What We Did

### 1. Chat AI Prompt Fix (completed before audit)
- Rewrote system prompt in `ai_service.py` to enforce conversational tone
- Added 7 absolute rules: use real data, talk like a person, never apologize, never suggest manual tracking
- Fixed fallback responses to extract data from trading context
- Build passes, syntax valid

### 2. Full Pipeline Audit
Launched 3 parallel exploration agents to trace:
- All pattern definitions across 5 detection systems
- Complete data flow from trade sync to alert display
- Notification pipeline (push, WhatsApp, WebSocket)

### 3. Root Cause Identified
**Trade.pnl = 0.0 for all synced trades.** Real P&L only in CompletedTrade.realized_pnl (FIFO matching). Every detector checking `Trade.pnl < 0` is dead code.

### 4. Documentation Created
- `docs/review/screens/pattern-detection-audit.md` — Complete catalog of all 31 patterns, which work, which don't, and why
- `docs/review/screens/pattern-detection-fix-plan.md` — 6-phase implementation plan with exact file/line references

## Key Findings

- **31 total patterns** across 5 detection systems
- **22 patterns BROKEN** (all P&L-dependent ones)
- **9 patterns working** (count/time/size-based only)
- **DangerZoneService NEVER auto-triggered** — only manual API call
- **Notification pipeline completely dead** — push/WhatsApp code exists but never called
- **Frontend has only 4 of 31 patterns** — the main gap

## Fix Plan Summary (6 Phases)

| Phase | What | Files | Impact |
|-------|------|-------|--------|
| 1 | Add 4 frontend patterns (consecutive_losses, capital_drawdown, same_instrument_chasing, all_loss_session) | 3 frontend | HIGHEST — immediate user-visible |
| 2 | Fix RiskDetector to use CompletedTrade | 1 backend | HIGH — backend alerts work |
| 3 | Fix DangerZone P&L queries | 1 backend | HIGH — interventions work |
| 4 | Wire DangerZone into sync pipeline | 1 backend | HIGH — auto-triggers |
| 5 | Fix BehavioralAnalysisService (27 patterns) | 1 backend | MEDIUM — deferred |
| 6 | Wire notification pipeline | Multiple | MEDIUM — deferred |

## Status

- Audit: COMPLETE
- Documentation: COMPLETE
- Implementation: NOT STARTED (pending user approval)

## Documents

- `docs/review/screens/pattern-detection-audit.md` — Full audit (all 31 patterns)
- `docs/review/screens/pattern-detection-fix-plan.md` — Implementation plan (6 phases)
