# Session 006 — Goals Screen Review

**Date:** 2026-02-23
**Goal:** Fix data contract mismatch and risk calculation bug in Goals screen.

## Problem

1. Backend sends `log_type` for commitment log entries, frontend reads `type` → all entries render with wrong styling/icons when data comes from API
2. Risk-per-trade calculation uses `starting_capital` instead of `current_capital` → risk limits don't track actual account balance

## What Was Done

### G1: Field mapping fix (CRITICAL)

**File:** `src/hooks/useGoals.ts` (line 102)

Changed:
```typescript
setCommitmentLog(data.commitment_log || []);
```
To:
```typescript
setCommitmentLog(
  (data.commitment_log || []).map((entry: any) => ({
    ...entry,
    type: entry.log_type || entry.type,
    id: String(entry.id),
  }))
);
```

This maps `log_type` → `type` for backend entries while keeping localStorage entries unchanged (they already have `type`). Also stringifies `id` since backend returns numeric IDs.

### G2: Risk calculation fix (HIGH)

**File:** `src/lib/emotionalTaxCalculator.ts` (line 168)

Changed `goals.starting_capital` → `goals.current_capital`

### G3: Optional fields (MEDIUM) — No code change

Frontend-only fields (`previous_value`, `new_value`, `pattern_type`) are already optional. The `description` field from backend contains the change details. No crash risk.

### G4: GoalEditModal missing fields (LOW) — Deferred

Feature gap (missing UI for `min_time_between_trades_minutes`, `max_position_size_percent`, trading hours). Not a bug.

## Verification

- [x] `npm run build` passes (37s, no errors)
- [x] No regressions

## Goals + DangerZone Rearchitecture Decision

After reviewing Goals, DangerZone, and Settings > Risk Limits, identified a **triple duplication problem**: three places store the same risk limits, completely disconnected from each other. Most traders will never set goals manually.

**Decision:** Merge Goals + DangerZone into a single AI-driven "My Patterns" screen.
- AI learns trader baselines from 2-3 weeks of actual trading data
- Alerts flag deviations from trader's OWN normal, not from manual rules
- Manual overrides available but not required (AI-first, manual-override)
- Guardian/WhatsApp config stays in Settings
- Kill: triple-duplicated risk sliders, 24hr edit cooldown

**Full plan:** `docs/review/screens/goals-dangerzone-merge.md`

**OPEN — Cold Start Problem:** What keeps traders engaged during the first 2-3 weeks while AI builds baselines and analytics are sparse? Brainstorm this later after finishing screen reviews.

## Next

Continue reviewing remaining screens: Chat (AI Coach), Settings
