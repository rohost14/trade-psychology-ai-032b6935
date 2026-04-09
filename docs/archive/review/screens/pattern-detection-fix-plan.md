# Pattern Detection Fix — Implementation Plan

**Date:** 2026-02-24 (Session 8)
**Prerequisite:** Read `pattern-detection-audit.md` first for root cause analysis.

---

## Goal

Make ALL 31 behavioral patterns actually detect and alert the user in real-time. Fix the P&L pipeline, add missing frontend patterns, wire DangerZone auto-trigger, and connect notifications.

---

## Phase 1: Frontend — Add Missing Critical Patterns

**Impact:** HIGHEST. These show immediately on dashboard as toasts + sidebar alerts.
**Files:** 3 frontend files
**Effort:** ~160 lines added

### 1A. Add PatternType values

**File:** `src/types/patterns.ts` (line 10-18)

Add 4 new values to the union type:
```typescript
| 'consecutive_losses'
| 'capital_drawdown'
| 'same_instrument_chasing'
| 'all_loss_session'
```

### 1B. Add PATTERN_NAMES to both files

**File:** `src/lib/patternDetector.ts` (line 26-35)
**File:** `src/lib/emotionalTaxCalculator.ts` (line 16-25)

Add to both:
```
consecutive_losses: 'Consecutive Losses',
capital_drawdown: 'Capital Drawdown',
same_instrument_chasing: 'Same Instrument Chasing',
all_loss_session: 'All-Loss Session',
```

### 1C. Add 4 detector functions

**File:** `src/lib/patternDetector.ts` — add after `detectPositionSizing()` (line 282), before `detectAllPatterns()` (line 288)

**Important data note:** Dashboard.tsx maps each CompletedTrade into 2 Trade events:
- Entry event: `pnl: 0`, `traded_at: entry_time`
- Exit event: `pnl: ct.realized_pnl`, `traded_at: exit_time`

So all new detectors must filter to exit events only (`pnl !== 0`) to get real completed trade outcomes. Entry events always have `pnl: 0` and would pollute the analysis.

#### detectConsecutiveLosses(trades: Trade[]): BehaviorPattern[]

```
Logic:
1. Filter to exits only (pnl !== 0)
2. Sort by traded_at descending (newest first)
3. Walk from newest, count consecutive pnl < 0
4. If streak breaks (pnl > 0), stop counting
5. Thresholds: 3 = medium, 4 = high, 5+ = critical
6. Description includes streak count + total loss amount

Edge cases:
- Breakeven (pnl = 0) is filtered out as entry event — won't break streak
- Single losing trade: streak = 1, below threshold, no alert
```

#### detectCapitalDrawdown(trades: Trade[], capital: number): BehaviorPattern[]

```
Logic:
1. Filter to exits only (pnl !== 0)
2. Sum all exit P&L = session P&L
3. If positive, return [] (no drawdown)
4. drawdown% = abs(sessionPnl) / capital * 100
5. Thresholds: 10% = medium, 25% = high, 40%+ = critical
6. Insight: "At X% drawdown, you need Y% gain to break even" where Y = (X / (100-X)) * 100

Edge case:
- capital comes from goals.starting_capital (localStorage)
- Default is 100,000. User MUST set their real capital for this to work
- For our user: 6k loss / 11k capital = 55% → critical
- For default 100k: 6k / 100k = 6% → below 10% threshold, NO alert
- This means capital_drawdown effectiveness depends on user setting starting_capital
```

#### detectSameInstrumentChasing(trades: Trade[]): BehaviorPattern[]

```
Logic:
1. Filter to exits with pnl < 0 (losing exits only)
2. Group by tradingsymbol
3. For each symbol with 2+ losing exits → create alert
4. Thresholds: 2 losses = medium, 3 = high, 4+ = critical
5. Description: "Lost on {SYMBOL} {N} times today. Total: Rs.{X}"

Edge case:
- Uses tradingsymbol from Trade event (set in Dashboard mapping from CompletedTrade)
- Multiple patterns possible (one per symbol with 2+ losses)
```

#### detectAllLossSession(trades: Trade[]): BehaviorPattern[]

```
Logic:
1. Filter to exits only (pnl !== 0)
2. Count winners (pnl > 0) and total exits
3. If exits >= 3 AND winners === 0 → all-loss session
4. Thresholds: 3-4 trades = medium, 5-6 = high, 7+ = critical
5. Description: "0% win rate today: all {N} trades were losses. Total: Rs.{X}"

Edge case:
- Will not fire if even 1 trade is a winner
- Intentionally strict — this is a "stop everything" signal
```

### 1D. Wire into detectAllPatterns()

**File:** `src/lib/patternDetector.ts` (line 296-299)

Add 4 new calls:
```typescript
allPatterns.push(...detectConsecutiveLosses(trades));
allPatterns.push(...detectCapitalDrawdown(trades, capital));
allPatterns.push(...detectSameInstrumentChasing(trades));
allPatterns.push(...detectAllLossSession(trades));
```

### 1E. No other frontend changes needed

- `AlertContext.tsx`: Already calls `detectAllPatterns()` generically. New patterns flow through.
- `Dashboard.tsx`: Merges patterns generically by severity. New patterns appear in sidebar.
- `RecentAlertsCard.tsx`: Renders by severity field, not pattern type. Works as-is.
- Toast notifications: AlertContext shows toasts for critical/high severity. New critical patterns will toast.

---

## Phase 2: Backend RiskDetector — Fix P&L Source

**Impact:** HIGH. Backend alerts persist in DB, survive page refreshes, feed the shield/analytics.
**Files:** 1 backend file
**Effort:** ~60 lines modified

### 2A. Add CompletedTrade import

**File:** `backend/app/services/risk_detector.py`

Add: `from app.models.completed_trade import CompletedTrade`

### 2B. Add CompletedTrade query to detect_patterns()

In `detect_patterns()` (line 24-95), after the existing Trade query (line 47-58), add a CompletedTrade query:

```python
# Get recent completed trades (with real P&L) for loss-dependent patterns
ct_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
ct_result = await db.execute(
    select(CompletedTrade)
    .where(
        and_(
            CompletedTrade.broker_account_id == broker_account_id,
            CompletedTrade.exit_time >= ct_cutoff,
        )
    )
    .order_by(desc(CompletedTrade.exit_time))
)
recent_completed = list(ct_result.scalars().all())
```

### 2C. Rewrite _detect_consecutive_losses()

Change signature to accept `completed_trades: List[CompletedTrade]` instead of `trades: List[Trade]`.

```python
async def _detect_consecutive_losses(self, completed_trades, trigger_trade):
    sorted_ct = sorted(completed_trades, key=lambda ct: ct.exit_time, reverse=True)

    consecutive = 0
    losing_ids = []
    total_loss = 0

    for ct in sorted_ct:
        pnl = float(ct.realized_pnl or 0)
        if pnl < 0:
            consecutive += 1
            losing_ids.append(ct.id)
            total_loss += abs(pnl)
        else:
            break

    if consecutive >= 5:
        return RiskAlert(severity="danger", pattern_type="consecutive_loss",
            message=f"DANGER: {consecutive} consecutive losing trades. Total loss: Rs.{total_loss:,.0f}",
            ...)
    elif consecutive >= 3:
        return RiskAlert(severity="caution", pattern_type="consecutive_loss",
            message=f"CAUTION: {consecutive} consecutive losses. Total: Rs.{total_loss:,.0f}",
            ...)
    return None
```

### 2D. Rewrite _detect_revenge_sizing()

Use CompletedTrade for loss detection + Trade for size comparison:

```python
# Check if most recent completed trade was a loss
if recent_completed and float(recent_completed[0].realized_pnl or 0) < 0:
    last_loss = recent_completed[0]
    # Check if trigger_trade entered within 15min of loss exit
    # Check if trigger_trade size > 1.5x last_loss size
```

### 2E. Rewrite _detect_tilt_spiral()

Use CompletedTrade P&L instead of Trade.pnl for loss tracking.

### 2F. Update detect_patterns() calls

Pass `recent_completed` to the rewritten methods instead of `recent_trades`.

---

## Phase 3: Backend DangerZone — Fix P&L Source

**Impact:** HIGH. Enables cooldowns, interventions, WhatsApp alerts.
**Files:** 1 backend file
**Effort:** ~30 lines modified

### 3A. Add CompletedTrade import

**File:** `backend/app/services/danger_zone_service.py`

Add: `from app.models.completed_trade import CompletedTrade`

### 3B. Fix _get_today_pnl() (line 477-497)

Replace:
```python
select(func.sum(Trade.pnl)).where(
    Trade.broker_account_id == broker_account_id,
    Trade.status == "COMPLETE",
    Trade.order_timestamp >= today_start
)
```

With:
```python
select(func.sum(CompletedTrade.realized_pnl)).where(
    CompletedTrade.broker_account_id == broker_account_id,
    CompletedTrade.exit_time >= today_start
)
```

### 3C. Fix _count_consecutive_losses() (line 526-550)

Replace Trade query with:
```python
select(CompletedTrade).where(
    CompletedTrade.broker_account_id == broker_account_id,
).order_by(CompletedTrade.exit_time.desc()).limit(10)
```

And change `trade.pnl < 0` to `float(ct.realized_pnl or 0) < 0`.

---

## Phase 4: Wire DangerZone into Sync Pipeline

**Impact:** HIGH. Without this, DangerZone never auto-triggers.
**Files:** 1 backend file
**Effort:** ~20 lines added

### 4A. Add DangerZone step to sync_all_data()

**File:** `backend/app/api/zerodha.py` — in `sync_all_data()`, after BehavioralEvaluator block (line 660), before `account.sync_status = "complete"` (line 662)

```python
# 3. DangerZone auto-assessment (runs AFTER all data + signals ready)
try:
    from app.services.danger_zone_service import danger_zone_service

    dz_status = await danger_zone_service.assess_danger_level(db, broker_account_id)
    results["danger_zone"] = {
        "level": dz_status.level.value,
        "triggers": dz_status.triggers,
        "consecutive_losses": dz_status.consecutive_losses,
    }

    # Auto-trigger intervention for danger/critical
    if dz_status.level.value in ("danger", "critical"):
        try:
            intervention = await danger_zone_service.trigger_intervention(
                db, broker_account_id, dz_status
            )
            results["intervention"] = intervention
        except Exception as int_err:
            logger.error(f"Intervention failed (non-fatal): {int_err}")

except Exception as e:
    logger.error(f"Danger zone assessment failed (non-fatal): {e}")
    results["danger_zone_error"] = str(e)
```

This enables:
- Automatic cooldown activation on danger/critical
- WhatsApp alert to guardian (if configured + Twilio active)
- Danger level included in sync response (frontend can use this)

---

## Phase 5 (Future): Fix BehavioralAnalysisService P&L

**Impact:** MEDIUM. These 27 patterns run on-demand from Analytics page.
**Files:** 1 backend file (behavioral_analysis_service.py, 1813 lines)
**Effort:** LARGE — every pattern's `_calculate_pnl()` needs to use CompletedTrade
**Recommendation:** Defer to next session. The 27 patterns work correctly when called from `/api/behavioral/analysis` IF Trade.pnl is populated. Since PnLCalculator does update Trade.pnl for SELL fills, some patterns may partially work for the SELL-side analysis. Full fix requires refactoring `_get_recent_trades()` to join with CompletedTrade.

---

## Phase 6 (Future): Wire Notification Pipeline

**Impact:** MEDIUM-HIGH. Enables push + WhatsApp for detected patterns.
**Files:** Multiple (trade_tasks.py, danger_zone_service.py, push_notification_service.py)
**Effort:** MEDIUM
**Prerequisite:** Phase 4 (DangerZone wiring)

Currently dead code paths:
- `push_notification_service.send_risk_alert_notification()` — never called
- `send_danger_alert.delay()` — Celery task exists, never queued from sync
- `websocket.notify_risk_alert()` — defined but never invoked

Fix: After DangerZone assessment (Phase 4), add:
```python
# Queue danger alert notification
if dz_status.level.value == "critical":
    try:
        from app.tasks.alert_tasks import send_danger_alert
        send_danger_alert.delay(str(broker_account_id), "critical", dz_status.triggers)
    except Exception:
        pass
```

**Note:** Requires Celery running + Twilio configured for WhatsApp, VAPID keys for push.

---

## Verification Checklist

### After Phase 1 (Frontend):
- [ ] `npm run build` passes
- [ ] PatternType in patterns.ts has 12 values (8 old + 4 new)
- [ ] patternDetector.ts PATTERN_NAMES has 12 entries
- [ ] emotionalTaxCalculator.ts PATTERN_NAMES has 12 entries
- [ ] detectAllPatterns() calls 8 detectors (4 old + 4 new)
- [ ] With 5 consecutive losses: consecutive_losses alert appears (critical)
- [ ] With 50% drawdown: capital_drawdown alert appears (critical)
- [ ] With 2 losses on same symbol: same_instrument_chasing alert appears (medium)
- [ ] With 0% win rate (3+ trades): all_loss_session alert appears

### After Phase 2 (RiskDetector):
- [ ] Python syntax valid
- [ ] RiskDetector imports CompletedTrade
- [ ] detect_patterns() queries both Trade and CompletedTrade
- [ ] _detect_consecutive_losses uses CompletedTrade.realized_pnl
- [ ] /api/risk/alerts returns consecutive_loss alerts for 3+ losses

### After Phase 3 (DangerZone):
- [ ] Python syntax valid
- [ ] _get_today_pnl() queries CompletedTrade.realized_pnl
- [ ] _count_consecutive_losses() queries CompletedTrade

### After Phase 4 (Wiring):
- [ ] Python syntax valid
- [ ] sync_all_data() response includes danger_zone section
- [ ] With 5 consecutive losses: danger_zone.level = "critical"
- [ ] With daily_loss_limit set and 100% used: intervention triggers

---

## File Change Summary

| Phase | File | Changes | Lines |
|-------|------|---------|-------|
| 1 | `src/types/patterns.ts` | +4 PatternType values | +4 |
| 1 | `src/lib/patternDetector.ts` | +4 detectors, +4 PATTERN_NAMES, update detectAllPatterns | +160 |
| 1 | `src/lib/emotionalTaxCalculator.ts` | +4 PATTERN_NAMES | +4 |
| 2 | `backend/app/services/risk_detector.py` | Import + CompletedTrade query + rewrite 3 methods | +40, -30 |
| 3 | `backend/app/services/danger_zone_service.py` | Import + fix 2 methods | +15, -10 |
| 4 | `backend/app/api/zerodha.py` | Add DangerZone step to sync pipeline | +20 |
| **Total** | **6 files** | | **~240 lines** |

---

## What This Fixes (User's Scenario Replay)

**Scenario:** 5 consecutive losing trades, 50% capital lost, NIFTY25400CE traded twice after losing.

**Before (broken):**
- Position Size Warning x4 (medium) ← only working alert
- Revenge Trading x1 (medium)
- NOTHING ELSE

**After (fixed):**
- Consecutive Losses (CRITICAL) — "5 consecutive losing trades. Total loss: Rs.7,230"
- Capital Drawdown (CRITICAL) — "Session drawdown: 55% of capital (Rs.6,000 lost)"
- Same Instrument Chasing (MEDIUM) — "Lost on NIFTY25400CE 2 times today. Total: Rs.3,098"
- All-Loss Session (HIGH) — "0% win rate today: all 5 trades were losses"
- Position Size Warning x4 (MEDIUM) — unchanged
- Revenge Trading x1 (MEDIUM) — unchanged
- Backend: consecutive_loss (DANGER) in RiskAlert table
- DangerZone: level=CRITICAL, triggers=[consecutive_loss_critical]
- Intervention: cooldown activated automatically
- WhatsApp: sent to guardian (if configured)
