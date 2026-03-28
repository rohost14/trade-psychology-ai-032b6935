# Screen 03: My Patterns
*Route: `/my-patterns` | File: `src/pages/MyPatterns.tsx`*

---

## Purpose
Merged replacement for the old "Goals" and "Danger Zone" screens. Shows the trader's current behavioral state (danger level), active commitments/goals, emotional cost of bad patterns, streak progress, and full alert history. "Mirror, not blocker" philosophy — shows facts, no restrictions.

---

## Layout

```
┌────────────────────────────────────────────────────────┐
│  DANGER BANNER (full width, colour-coded)              │
│  "You are in CAUTION zone — 2 consecutive losses"     │
│  [Trigger Intervention] button (if warning+)           │
├────────────────────────────────────────────────────────┤
│  Row: EmotionalTaxCard  |  StreakTrackerCard           │
├────────────────────────────────────────────────────────┤
│  GoalCommitmentsCard (active commitments + log)        │
├────────────────────────────────────────────────────────┤
│  AlertHistory (last 30 alerts, expandable)             │
└────────────────────────────────────────────────────────┘
```

---

## Components

### Danger Status Banner
- **API**: `GET /api/danger-zone/status`
- **Polling**: Was 30s. Now re-fetches on `lastAlertEvent` from WebSocketContext
- **Levels**: `safe` (green) | `caution` (amber) | `warning` (orange) | `danger` (red) | `critical` (dark red)
- **Content**: Level badge, message, trigger count, cooldown remaining if active
- **Action**: "Trigger Intervention" → `POST /api/danger-zone/trigger-intervention`
  - Rate limited: 4 calls / 15 minutes per account (prevents guardian phone spam)
  - Creates cooldown, sends WhatsApp to user + guardian if configured

**Danger level thresholds** (from UserProfile, fallback to defaults):
```
consecutive_losses >= 3     → caution
consecutive_losses >= 5     → warning
daily_loss >= 50% of limit  → warning
daily_loss >= 80% of limit  → danger
active patterns >= 3        → caution
pattern severity = critical → danger
```

### EmotionalTaxCard (`src/components/goals/EmotionalTaxCard.tsx`)
- **API**: `GET /api/analytics/behavior?period=30` (reuses behavior tab data)
- **Content**: Top 3 costly patterns with ₹ cost, total emotional tax this month
- Example: "Revenge trading: ₹4,200 this month"
- **Validation**: ✅ Uses realized_pnl from CompletedTrade, not estimated values

### StreakTrackerCard (`src/components/goals/StreakTrackerCard.tsx`)
- **API**: `GET /api/goals/` → goal commitments + achievement dates
- **Content**: 30-day calendar heatmap, current streak, milestone badges (3d/7d/14d/21d/30d)
- **Validation**: ✅ Milestones are cosmetic motivators, not access gates

### GoalCommitmentsCard (`src/components/goals/GoalCommitmentsCard.tsx`)
- **API**: `GET /api/goals/` + `POST /api/goals/` + `PUT /api/goals/{id}` + `DELETE /api/goals/{id}`
- **Content**: Active commitments list, add/edit/delete commitment
- Example commitments: "I will set SL before entering", "No trading after 3 consecutive losses"
- **Validation**: ✅ Free-form text, no enforcement logic
- Note: 24-hour cooldown antipattern was REMOVED — users can edit freely

### AlertHistory (inline in `MyPatterns.tsx`)
- **API**: `GET /api/risk/alerts?limit=30`
- **Content**: Expandable list of last 30 behavioral alerts with severity, pattern type, time, acknowledged status
- **Acknowledge**: `POST /api/risk/alerts/{id}/acknowledge`
- **Validation**: ✅ Acknowledge removes from unread count in header

---

## APIs Called

| Endpoint | When | Purpose |
|----------|------|---------|
| `GET /api/danger-zone/status` | Mount + alert events | Danger level banner |
| `GET /api/danger-zone/summary` | Optional, on expand | Full summary with cooldown history |
| `POST /api/danger-zone/trigger-intervention` | Button click | Start cooldown + notify |
| `GET /api/analytics/behavior` | Mount | Emotional tax data |
| `GET /api/goals/` | Mount | Commitments + streaks |
| `POST /api/goals/` | New commitment | Create |
| `PUT /api/goals/{id}` | Edit | Update commitment |
| `DELETE /api/goals/{id}` | Delete | Remove commitment |
| `GET /api/risk/alerts` | Mount | Alert history |
| `POST /api/risk/alerts/{id}/acknowledge` | Acknowledge button | Mark as read |

---

## DangerLevel Ordering (Important Bug Fix)

The old code compared danger levels as strings (`'danger' < 'warning'` was `True` alphabetically — WRONG).
Fixed with numeric ordering in `danger_zone_service.py`:

```python
_LEVEL_ORDER = {"safe": 0, "caution": 1, "warning": 2, "danger": 3, "critical": 4}

def _upgrade_level(current: str, candidate: str) -> str:
    if _LEVEL_ORDER.get(candidate, 0) > _LEVEL_ORDER.get(current, 0):
        return candidate
    return current
```

**Validation**: ✅ Level comparison is numeric, never alphabetical

---

## Validation Checklist

- [x] Danger level colours match: safe=green, caution=amber, warning=orange, danger=red, critical=dark red
- [x] Trigger Intervention rate-limited (4/15min) — no infinite WhatsApp spam
- [x] Emotional tax shows ₹ values from real CompletedTrade P&L
- [x] Streak calendar resets if day missed (no artificial maintenance)
- [x] Goals editable immediately — no 24hr lock
- [x] Alert history shows acknowledged vs unacknowledged differently
- [x] "Polling was 30s" — now event-driven via lastAlertEvent WebSocket trigger
- [x] Cooldown remaining shows countdown (minutes, not timestamps)
