# Session 9 — Pattern Detection Fix Implementation

**Date**: 2026-02-28
**Focus**: Implement Phases 1-4 of pattern detection fix plan

## Context

Real-world failure: Rs.11k -> Rs.3k across 5 consecutive losing trades. App only detected Position Size Warning (4x) and 1 Revenge Trading alert. Root cause: `Trade.pnl` always 0.0, real P&L in `CompletedTrade.realized_pnl` only.

## What Was Done

### Phase 1: Frontend — 4 New Pattern Detectors
- **`src/types/patterns.ts`**: Added 4 PatternType values: `consecutive_losses`, `capital_drawdown`, `same_instrument_chasing`, `all_loss_session`
- **`src/lib/patternDetector.ts`**: Added 4 detector functions + 4 PATTERN_NAMES + wired into `detectAllPatterns`:
  - `detectConsecutiveLosses()` — 3+ consecutive losing exits. Thresholds: 3=medium, 4=high, 5+=critical
  - `detectCapitalDrawdown()` — Session P&L as % of capital. Thresholds: 10%=medium, 25%=high, 40%+=critical
  - `detectSameInstrumentChasing()` — 2+ losses on same tradingsymbol. Thresholds: 2=medium, 3=high, 4+=critical
  - `detectAllLossSession()` — 3+ exits, 0 winners. Thresholds: 3=medium, 5=high, 7+=critical
- **`src/lib/emotionalTaxCalculator.ts`**: Added 4 PATTERN_NAMES + 4 `generateInsight` cases + 4 `getTopRecommendations` cases

**Key detail**: All 4 detectors filter to exit events only (`pnl !== 0`) since Dashboard maps CompletedTrades into entry (pnl=0) + exit (pnl=realized_pnl) events.

### Phase 2: Backend RiskDetector — CompletedTrade Query
- **`backend/app/services/risk_detector.py`**:
  - Added `CompletedTrade` import
  - Added CompletedTrade query (24h window, ordered by exit_time desc) in `detect_patterns()`
  - Rewrote `_detect_consecutive_losses()` — now uses `CompletedTrade.realized_pnl` (was checking `Trade.pnl` which is always 0)
  - Rewrote `_detect_revenge_sizing()` — finds most recent CompletedTrade loss, checks if trigger_trade came within 15min with >1.5x size
  - Rewrote `_detect_tilt_spiral()` — uses CompletedTrade P&L for loss tracking + position sizes
  - Kept overtrading + FOMO as-is (count/time based, no P&L needed)

### Phase 3: Backend DangerZone — Fix P&L Queries
- **`backend/app/services/danger_zone_service.py`**:
  - Added `CompletedTrade` import
  - Fixed `_get_today_pnl()`: `func.sum(Trade.pnl)` -> `func.sum(CompletedTrade.realized_pnl)` with `exit_time >= today_start`
  - Fixed `_count_consecutive_losses()`: Now queries `CompletedTrade` by `exit_time desc`, checks `realized_pnl < 0`

### Phase 4: Wire DangerZone into Sync Pipeline
- **`backend/app/api/zerodha.py`**:
  - Added step 3 after BehavioralEvaluator: `danger_zone_service.assess_danger_level()`
  - If danger/critical: calls `trigger_intervention()` (starts cooldown, sends WhatsApp if configured)
  - Danger zone level included in sync response (`results["danger_zone"]`)

## Build Verification
- `npm run build`: PASSES
- Python syntax: All 3 backend files compile cleanly

## Files Changed (6 total)

| File | Phase | Change |
|------|-------|--------|
| `src/types/patterns.ts` | 1 | +4 PatternType values |
| `src/lib/patternDetector.ts` | 1 | +4 detectors, +4 PATTERN_NAMES, wire detectAllPatterns |
| `src/lib/emotionalTaxCalculator.ts` | 1 | +4 PATTERN_NAMES, +4 insights, +4 recommendations |
| `backend/app/services/risk_detector.py` | 2 | CompletedTrade query, rewrite 3 methods |
| `backend/app/services/danger_zone_service.py` | 3 | Fix 2 P&L methods to use CompletedTrade |
| `backend/app/api/zerodha.py` | 4 | Add DangerZone step 3 in sync pipeline |

## What's Next
- Test with real data (5 consecutive losses scenario)
- Fix plan Phases 5-6: Wire notifications (push/WhatsApp) from sync pipeline
- Remaining broken patterns from audit (martingale, same-side-reentry, etc.)
