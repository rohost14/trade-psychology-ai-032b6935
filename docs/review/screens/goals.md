# Goals Screen Review

**Status:** 2/2 FIXED (G3 no-op, G4 deferred)
**Session:** 6
**Date:** 2026-02-23

---

## Issues Found

### G1: `log_type` vs `type` field mismatch — CRITICAL — FIXED
- **Backend** model/schema uses `log_type`
- **Frontend** type and CommitmentLogCard use `type`
- When commitment log entries come from backend API, `entry.type` is `undefined` → wrong icons/colors
- **Fix:** Map `log_type` → `type` in `useGoals.ts` when receiving backend data (line 102)

### G2: Risk calculation uses `starting_capital` instead of `current_capital` — HIGH — FIXED
- `emotionalTaxCalculator.ts:168` used `goals.starting_capital`
- Risk limits should track real account balance, not starting capital
- **Fix:** Changed to `goals.current_capital`

### G3: CommitmentLog entries from backend missing frontend-only fields — MEDIUM — NO-OP
- Frontend type has `previous_value`, `new_value`, `pattern_type` fields
- Backend never sends these (not in schema)
- Components use optional chaining — no crash
- `description` field from backend already contains the change details
- **Decision:** No code change needed. Fields are optional.

### G4: GoalEditModal doesn't expose all goal fields — LOW — DEFERRED
- Missing from modal: `min_time_between_trades_minutes`, `max_position_size_percent`, trading hours
- Feature gap, not a bug
- **Decision:** Defer unless user requests

---

## Files Changed

| File | Change |
|------|--------|
| `src/hooks/useGoals.ts` | Map `log_type` → `type`, stringify `id` for backend entries |
| `src/lib/emotionalTaxCalculator.ts` | `starting_capital` → `current_capital` in risk calc |

## Verification

- [x] `npm run build` passes (37s, no errors)
- [x] CommitmentLog field mapping handles both backend (`log_type`) and localStorage (`type`) entries
- [x] Risk calculation uses current capital for accurate risk limits
