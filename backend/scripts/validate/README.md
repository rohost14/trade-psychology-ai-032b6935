# Validation Scenario: "The Revenge Spiral"

Manual end-to-end test for behavioral detection patterns.
**You execute scripts one at a time. I don't run anything automatically.**

---

## Setup

```bash
cd backend
pip install -r requirements.txt   # if not already done
python scripts/validate/00_setup.py
```

Check that your profile has `daily_loss_limit` and `trading_capital` set in Settings.

---

## The Scenario

A typical bad trading day that progressively triggers behavioral patterns.

| Script | Trade | Expected Alert | Wait After |
|--------|-------|---------------|------------|
| 01 | NIFTY LONG → loss ₹2,500 | **None** — single loss | 2 min |
| 02 | BANKNIFTY LONG → loss ₹3,495 | **None** — 2 consecutive | 2 min |
| 03 | NIFTY LONG → loss ₹4,200 | **consecutive_loss CAUTION** | 3 min (within 10 min total for Script 04) |
| 04 | NIFTY LONG → loss ₹2,500 (4 min after Script 03) | **revenge_trade** | 1 min |
| 05 | 4 rapid trades → all losses | **overtrading_burst** | 2 min |
| 06 | NIFTY LONG 100-lot → loss ₹10,000 | **size_escalation + DANGER** | 2 min |
| 07 | BANKNIFTY → loss pushes past daily limit | **session_meltdown** | Observe, then cleanup |
| cleanup | Deletes all test data | — | — |

---

## What to Observe After Each Script

### Dashboard
- Closed Trades list (new trades appear)
- Alerts panel (new alerts with correct severity)
- Session P&L card (growing negative)

### Backend Logs
- `Risk detection: N new alerts` — production RiskDetector fired
- `[shadow] ... events | state=... | risk=X→Y` — BehaviorEngine shadow fired
- No error lines (no red in logs)

### Sentry
- No new error events after each script

### Supabase (optional — check tables directly)
```sql
-- See production alerts
SELECT pattern_type, severity, message, detected_at
FROM risk_alerts
ORDER BY detected_at DESC LIMIT 10;

-- See shadow events
SELECT event_type, severity, behavior_state, risk_score_before, risk_score_after, message
FROM shadow_behavioral_events
ORDER BY detected_at DESC LIMIT 20;
```

---

## Timing Notes

- **Script 04 must run within 10 minutes of Script 03** (revenge window = 10 min default)
- All other scripts can be run at any pace you prefer
- There's no harm in waiting longer — you're in control

---

## What validates what

| Pattern | Validated by | Notes |
|---------|-------------|-------|
| consecutive_loss_streak | Production (RiskDetector) + Shadow (BehaviorEngine) | Both should fire |
| revenge_trade | Shadow only | New pattern, not in RiskDetector |
| overtrading_burst | Production (RiskDetector) + Shadow | Compare counts |
| size_escalation | Shadow only | New pattern |
| session_meltdown | Shadow only | Requires daily_loss_limit set |

If shadow and production fire for the same patterns → high match rate → ready for Phase 3 cutover.

---

## Cleanup

```bash
python scripts/validate/cleanup.py
```

Deletes all test trades, completed_trades, shadow events, and test alerts from today.
Your real historical data is untouched.
