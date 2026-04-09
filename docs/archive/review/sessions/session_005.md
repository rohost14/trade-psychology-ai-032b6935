# Session 005 — BlowupShield Rebuild

**Date:** 2026-02-23
**Goal:** Replace all hardcoded money-saved values with data-driven calculations using real trade data.

## Problem

- `calculate_money_saved()`: Every DANGER alert = `3 trades x ₹1,000 = ₹3,000` — no actual trade data
- `get_intervention_history()`: Pattern losses from static map (`revenge=₹8,500`, `overtrading=₹4,200`)
- Two nearly identical pages (BlowupShield + MoneySaved) calling the same broken endpoint
- Dashboard card showed meaningless constants
- Claimed "High confidence: based on YOUR exact trading history" — but was just `severity=danger`

## What Was Done

### Backend

1. **NEW `backend/app/services/shield_service.py`** (~340 lines)
   - `get_shield_summary()` → hero metrics (capital_defended, shield_score, heeded_streak, etc.)
   - `get_intervention_timeline()` → per-alert detail with real trade data
   - `get_pattern_breakdown()` → grouped stats per pattern type
   - Alert outcome classification: heeded / partially_heeded / ignored
   - Post-alert trade detection (60-min window, same trading day)
   - Data-driven baselines from historically ignored alerts
   - Bootstrap from alert.details JSONB when < 3 data points

2. **NEW `backend/app/api/shield.py`** (3 endpoints)
   - `GET /api/shield/summary?days=30`
   - `GET /api/shield/timeline?limit=50`
   - `GET /api/shield/patterns`

3. **UPDATED `backend/app/main.py`** — registered shield router

4. **REMOVED from `analytics_service.py`**: `calculate_money_saved()`, `get_intervention_history()`

5. **REMOVED from `analytics.py`**: `/money-saved` and `/interventions` endpoints; simplified `/dashboard-stats`

### Frontend

6. **UPDATED `src/types/api.ts`** — Added `ShieldSummary`, `ShieldTimelineItem`, `PatternBreakdown` interfaces

7. **REWRITTEN `src/pages/BlowupShield.tsx`**
   - Hero cards: Capital Defended, Shield Score, Heeded Streak
   - Secondary metrics: this_week, this_month, blowups_prevented
   - Pattern Breakdown table
   - Intervention Timeline with outcome badges (heeded/partial/ignored), real trade data, confidence levels
   - Methodology disclaimer

8. **REWRITTEN `src/components/dashboard/BlowupShieldCard.tsx`**
   - Self-contained (fetches own data from `/api/shield/summary?days=7`)
   - No longer receives props from Dashboard
   - Shows weekly capital defended + shield score

9. **UPDATED `src/pages/Dashboard.tsx`**
   - Removed `MoneySaved` import, `moneySaved` state, `fetchMoneySaved()` callback
   - `BlowupShieldCard` now takes no props
   - Removed from `fetchAllData` Promise.all

10. **REPLACED `src/pages/MoneySaved.tsx`** with `Navigate` redirect to `/blowup-shield`

## Shield Algorithm Summary

- **Heeded** = acknowledged + no trades for 30 min → estimated savings from pattern baseline
- **Partially Heeded** = acknowledged but traded within 30-60 min → estimated - actual loss
- **Ignored** = not acknowledged + traded within 30 min → defended = 0 (actual cost tracked for baselines)
- **Baseline** = avg loss when user historically ignored the same pattern type
- **Bootstrap** = alert.details JSONB data (total_loss, size_increase_pct, consecutive_losses) or conservative defaults
- **Shield Score** = weighted_heeded / weighted_total × 100 (danger=2x, caution=1x)
- **Confidence** = high (10+ data points), medium (3-9), low (bootstrap)

## Verification

- [x] Python syntax passes (shield_service.py, shield.py, analytics_service.py, analytics.py, main.py)
- [x] Frontend builds (`npm run build` — 30s, no errors)
- [x] TRACKER.md updated
- [x] Session log created
