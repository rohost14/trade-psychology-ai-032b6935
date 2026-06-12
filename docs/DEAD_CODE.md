# Dead Code Register

Code that has been commented out or disabled. Kept for reference. Do not delete the underlying files.

---

## BehavioralEvaluator (signal pipeline v1)

**File**: `backend/app/services/behavioral_evaluator.py`  
**Disabled in**: `backend/app/api/zerodha.py` — `sync_all_data()` (around line 906)  
**Status**: Call-site removed. Service file intact.

**What it did**: Confidence-scored behavioral signal detector. Evaluated fills and emitted `BehavioralEvent` records (separate table from `RiskAlert`). Used dedup window of 60 min.

**Why disabled**: Superseded by `BehaviorEngine` (22 patterns → `RiskAlert`). `BehavioralEvent` table unused by frontend since Phase 3 cutover (Session 21). Running both caused redundant DB writes with no user-facing value.

**When to delete**: After confirming `BehavioralEvent` table has no downstream queries in analytics or reports (safe to drop migration + model + service).

---

## RiskDetector (legacy P&L-based detector)

**File**: `backend/app/services/risk_detector.py`  
**Status**: File still present. `calculate_risk_state()` was last called from `api/risk.py` — removed in Feature 2 review (MED-3 fix). No remaining callers.

**What it did**: Earlier pattern detector using P&L thresholds. Wrote to `RiskAlert` table. `calculate_risk_state()` read RiskAlerts and returned risk_state/active_patterns.

**Why disabled**: Replaced by `BehaviorEngine` + direct RiskAlert query in `/risk/state`. RiskDetector used a different risk vocabulary and didn't match BehaviorEngine's behavior_state.

**When to delete**: After BehaviorEngine has run stably for 30+ days in production with no rollback requests.
