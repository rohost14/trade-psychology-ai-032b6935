> **ARCHIVED 21 Aug 2026 — do not use as a current reference.**
>
> Predates the August cleanup (14 Jul 2026). Six dead constants and the whole of
> L3 have been removed since; this list was never updated.

---

# Dead Code Register

Code that has been disabled and archived. Kept for reference under `_archive/` folders. Never deleted.

---

## ARCHIVED (Engine v2 Phase 0 — 2026-07-14)

### BehavioralEvaluator (signal pipeline v1)

**File**: `backend/app/services/_archive/behavioral_evaluator.py` (archived from `services/`)
**Tests**: `backend/tests/_archive/test_behavioral_detection.py` (archived with it)

**What it did**: Confidence-scored behavioral signal detector. Evaluated fills and emitted `BehavioralEvent` records (separate table from `RiskAlert`). Used dedup window of 60 min.

**Why archived**: Superseded by `BehaviorEngine` (24 patterns → `RiskAlert`). Call-site in `zerodha.py sync_all_data()` was removed at Session 21 cutover; BehaviorEngine has run stably for 3+ months since. Zero live imports remained (verified 2026-07-14 — comment references only).

**BehavioralEvent table**: model (`models/behavioral_event.py`) and DB table retained — table is FROZEN (no writes since Session 21). The one live reader (`/api/analytics/critical-trades`) was silently matching zero rows for all post-cutover trades; fixed in Phase 0 to read `RiskAlert` instead. Table/model/migration can be dropped in Engine v2 Phase 1 when the new BehaviorEvent record is designed (may reuse or replace this table).

### RiskDetector (legacy P&L-based detector)

**File**: `backend/app/services/_archive/risk_detector.py` (archived from `services/`)

**What it did**: Earlier pattern detector using P&L thresholds. Wrote to `RiskAlert` table. `calculate_risk_state()` read RiskAlerts and returned risk_state/active_patterns.

**Why archived**: Replaced by `BehaviorEngine` + direct RiskAlert query in `/risk/state` (MED-3 fix). Zero live imports remained (verified 2026-07-14). Delete-condition ("30+ days stable production") long met.

**Note**: pattern-name references in `cooldown_service.py` / `danger_zone_service.py` comments ("revenge_sizing", "tilt_loss_spiral", "fomo" — risk_detector vocabulary) remain because historical RiskAlert rows with those pattern_types exist in the DB.

### push_behavioral_event (websocket)

**Was**: `backend/app/api/websocket.py` ConnectionManager method. Removed outright (19 lines, no callers, tied to BehavioralEvaluator flow). Recoverable from git history if ever needed.

---

## STILL LIVE — scheduled for retirement in Engine v2 Phase 4

### BehavioralAnalysisService (legacy batch layer)

**File**: `backend/app/services/behavioral_analysis_service.py`
**Live callers**:
- `api/behavioral.py` — `/api/behavioral/analysis` used by `ExportReportButton.tsx` (Analytics export)
- `api/analytics.py` `elif tab == "behavior"` — AI narrative behavior tab

**Retirement plan**: Engine v2 Phase 4 step 8 — analytics endpoints switch to reading BehaviorEvents, then archive this service. Do NOT archive before rerouting both callers.
