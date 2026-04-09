# Goals + DangerZone Rearchitecture Plan

**Status:** DOCUMENTED — not yet implementing
**Date:** 2026-02-23
**Session:** 6

---

## Problem

Three places store the same risk limits, completely disconnected:

| Rule | Goals page | Settings > Risk Limits | DangerZone service |
|------|-----------|----------------------|-------------------|
| Daily loss limit | `max_daily_loss` | `daily_loss_limit` | reads from UserProfile |
| Max trades/day | `max_trades_per_day` | `daily_trade_limit` | hardcoded defaults |
| Position size | `max_position_size_percent` | `max_position_size` | not tracked |
| Trading hours | `allowed_trading_start/end` | `trading_hours_start/end` | `avoid_first/last_minutes` |

Most traders will never set goals manually. Without goals set, adherence scoring and DangerZone thresholds are meaningless (scoring against defaults nobody chose).

## Decision

Merge Goals + DangerZone into a single AI-driven system.

### Core Concept: AI-Derived Baselines

Instead of manual rule-setting, the system watches 2-3 weeks of trading and learns:
- Typical daily loss range
- Normal trade count per day
- Usual position sizes
- Session timing patterns
- Loss pattern behaviors (e.g., "after 2 consecutive losses, next trade is 40% larger")

Alerts flag **deviations from the trader's own normal**, not from arbitrary rules.

### Screen Restructure

| Screen | Purpose |
|--------|---------|
| Dashboard | Live state — stays as-is |
| My Patterns (was Goals+DangerZone) | AI-derived baselines + live deviation meter + "your norms" cards. Calm state shows patterns/stats, active state shows real-time escalation |
| Settings | Profile, broker, guardian, AI persona, notifications. No risk limit sliders — those are learned |
| Optional manual overrides | Small section in Settings or My Patterns: override AI baselines if trader wants |

### Key Decisions

1. **Manual goals:** Keep as option, but AI takes priority. Manual overrides only when trader explicitly sets them.
2. **Guardian/WhatsApp:** Stays in Settings. That's where user configures guardian phone number, alert triggers, and notification preferences.
3. **24hr cooldown on goal edits:** Remove. Contradicts "mirror, not blocker" philosophy.

### What to Keep from Each Screen

**From Goals:**
- Emotional tax calculator (great concept — keep)
- Streak tracking
- Adherence scoring concept (but score against AI baselines, not manual rules)
- Commitment log (repurpose as "baseline changes" log)

**From DangerZone:**
- The escalation engine (safe → caution → warning → danger → critical)
- Cooldown system
- WhatsApp/guardian alert triggers
- Real-time monitoring loop (30-second refresh)

**Kill:**
- Manual rule-setting as a required step
- Triple-duplicated risk limit sliders (Goals, Settings, DangerZone)
- 24hr edit cooldown

### What to Build (Backend)

- New `baseline_service.py`: Calculates trader norms from historical data
- Update `danger_zone_service.py`: Read from AI baselines instead of UserProfile
- New migration: `baselines` table (trader_id, metric, value, confidence, updated_at)
- Update `analytics_service.py`: Feed baseline data into deviation calculations

### What to Build (Frontend)

- New "My Patterns" page replacing Goals + DangerZone
- Remove risk limit sliders from Settings
- Add optional "Manual Override" section (collapsed by default)
- Update nav: remove Goals and DangerZone links, add My Patterns

---

## OPEN: Cold Start Problem

**Brainstorm later:** During the first 2-3 weeks while AI builds baselines, what keeps traders engaged? Analytics also needs a few days of data. Need hook features for day-1 value.

Ideas to explore:
- Instant pattern detection from first few trades (even without baselines)
- "Getting to know you" progress indicator
- Quick wins from Analytics (even with limited data)
- AI coach conversations don't need trading data
- Onboarding that sets initial expectations

---

## Files Affected (When Implementing)

### Backend
- `backend/app/services/danger_zone_service.py` — rework to use baselines
- `backend/app/services/baseline_service.py` — NEW
- `backend/app/api/danger_zone.py` — merge/rework endpoints
- `backend/app/api/goals.py` — deprecate or merge
- `backend/app/models/` — new baseline model
- `backend/migrations/` — new migration

### Frontend
- `src/pages/Goals.tsx` — replace with MyPatterns
- `src/pages/DangerZone.tsx` — merge into MyPatterns
- `src/pages/Settings.tsx` — remove Risk Limits tab
- `src/hooks/useGoals.ts` — rework
- `src/lib/emotionalTaxCalculator.ts` — update to use baselines
- `src/components/goals/` — rework components
- `src/App.tsx` — update routes
- `src/components/Layout.tsx` — update nav
