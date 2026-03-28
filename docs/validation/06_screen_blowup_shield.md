# Screen 06: Blowup Shield
*Route: `/blowup-shield` | File: `src/pages/BlowupShield.tsx`*

---

## Purpose
Shows the trader real, verifiable evidence that listening to behavioral alerts saved them money. Uses counterfactual P&L: "If you had stayed in this position instead of exiting when alerted, here's what would have happened." No estimated or hardcoded values — all real market prices.

---

## Layout

```
┌────────────────────────────────────────────────────────┐
│  Hero Stats Row                                        │
│  [Capital Defended: ₹28,400]  [Shield Score: 73%]     │
│  [Heeded Streak: 4]           [Coverage: 12/18 alerts] │
├────────────────────────────────────────────────────────┤
│  Data Coverage Bar                                     │
│  "12 complete | 3 calculating | 3 unavailable"         │
├────────────────────────────────────────────────────────┤
│  Pattern Breakdown Table                               │
│  [Pattern | Occurrences | Total Saved | Avg per alert] │
├────────────────────────────────────────────────────────┤
│  Intervention Timeline (chronological)                 │
│  Each card shows:                                      │
│  - Pattern type + severity                             │
│  - Alert time                                          │
│  - Your actual P&L after exit                          │
│  - Counterfactual P&L (what would have happened)       │
│  - Saved: ₹X   [green] / Cost: ₹X [red]              │
│  - Status: ✅ Verified | ⏳ Calculating | ⚪ No data   │
└────────────────────────────────────────────────────────┘
```

---

## Key Design Principle: Zero Estimated Values

**Before Session 14**: Shield used hardcoded per-pattern estimates (e.g., "revenge trade costs ₹800"). Completely fake.

**After Session 14**: Full counterfactual system using real market prices.

```
Alert fires (danger/critical severity)
  → create_alert_checkpoint: snapshot position + get_ltp() at T+0
  → fetch_t5_pnl (T+5 min): what is the position P&L now?
  → fetch_t30_pnl (T+30 min): what would it have been if held?
  → complete_checkpoint (T+60 min):
      money_saved = user_actual_pnl_after_exit - counterfactual_pnl_t30
      (can be negative — user did worse than if they'd held)
```

`money_saved` is stored on `AlertCheckpoint` model. It's the real number.

---

## Components

### Hero Stats
- **API**: `GET /api/shield/summary`
- **Service**: `shield_service.py`
- **Data sources**:
  - `capital_defended` = sum of `max(0, checkpoint.money_saved)` for complete checkpoints only
  - `shield_score` = heeded_count / total_alerts_with_checkpoints (%)
  - `heeded_streak` = consecutive interventions where money_saved > 0

### Data Coverage Bar
- Shows checkpoint_coverage: `{complete: N, calculating: N, unavailable: N}`
- `calculating` = checkpoint task chain in progress (T+30 not yet reached)
- `unavailable` = alert was low/medium severity (no checkpoint created) OR predates the system
- **Validation**: ✅ No fake numbers shown when status is "calculating"

### Pattern Breakdown Table
- **API**: `GET /api/shield/patterns`
- Groups checkpoints by pattern_type, aggregates total saved
- Only includes complete checkpoints in ₹ sums
- **Validation**: ✅ Calculating rows show "—" not ₹0

### Intervention Timeline
- **API**: `GET /api/shield/timeline`
- Per-checkpoint card showing:
  - `calculation_status`: `complete` / `calculating` / `unavailable`
  - `user_actual_pnl` (what the user's position actually did after alert)
  - `counterfactual_pnl_t30` (what it would have done if held to T+30)
  - `money_saved` (difference)
- Colour coding: green if money_saved > 0, red if negative
- **Validation**: ✅ Negative money_saved shown honestly (not hidden)

---

## Backend: Checkpoint Task Chain

`backend/app/tasks/checkpoint_tasks.py`:

```python
create_alert_checkpoint (T+0)
  → AlertCheckpoint row created, status = "calculating"
  → self-chains: fetch_t5_pnl.apply_async(countdown=300)

fetch_t5_pnl (T+5)
  → stores user_actual_pnl_t5
  → self-chains: fetch_t30_pnl.apply_async(countdown=1500)

fetch_t30_pnl (T+30)
  → stores counterfactual_pnl_t30
  → computes money_saved = user_actual_pnl_t5 - counterfactual_pnl_t30
  → status = "complete"
  → self-chains: complete_checkpoint.apply_async(countdown=1800)

complete_checkpoint (T+60)
  → final cleanup, publishes shield_update event
```

Each task uses exponential backoff (min(2^n × 10, 300)s) on failure.

---

## APIs Called

| Endpoint | When | Purpose |
|----------|------|---------|
| `GET /api/shield/summary` | Mount | Hero stats |
| `GET /api/shield/patterns` | Mount | Pattern breakdown |
| `GET /api/shield/timeline` | Mount | Intervention timeline |

All three called on mount. No polling — Shield data is append-only (old checkpoints don't change).

---

## Validation Checklist

- [x] Capital defended = sum of POSITIVE money_saved only (not total gross)
- [x] Negative results shown honestly in timeline (not hidden or clipped to 0)
- [x] "Calculating" state shown while T+30 checkpoint is pending
- [x] "No position data" shown for alerts predating the system
- [x] Pattern breakdown only counts complete checkpoints in ₹ totals
- [x] Checkpoint chain self-schedules correctly (T+5 → T+30 → T+60)
- [x] Only danger/critical alerts create checkpoints (not low/medium)
- [x] Shield score formula: heeded / total_with_checkpoints (not heeded / all_alerts)
